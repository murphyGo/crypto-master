"""Unit tests for :mod:`src.utils.trading_math`.

Pins the per-trade PnL convention so that backtester, portfolio, and
paper-trader can all route through a single helper (DEBT-024 / Phase
20.1). Both sign branches are exercised plus the zero-quantity edge
case so that an accidental sign flip is caught at the helper level
before it propagates to the ledger sites.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.models import OHLCV
from src.utils.trading_math import (
    ATR_FLOOR_MULTIPLIER,
    DEFAULT_TF_MIN_SL_PCT,
    TF_MIN_SL_PCT,
    compute_atr,
    enforce_sl_floor,
    pnl_for_trade,
)
from src.utils.trading_types import PositionSide, TradeSide


def test_shared_side_aliases_are_importable() -> None:
    long_side: TradeSide = "long"
    short_side: PositionSide = "short"
    assert (long_side, short_side) == ("long", "short")


class TestPnlForTradeLong:
    """Long-side sign and magnitude pinning."""

    def test_long_profit(self) -> None:
        # Entry 100, exit 110, qty 2 -> +20
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=Decimal("2"),
            side="long",
        )
        assert pnl == Decimal("20")

    def test_long_loss(self) -> None:
        # Entry 100, exit 90, qty 2 -> -20
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("90"),
            qty=Decimal("2"),
            side="long",
        )
        assert pnl == Decimal("-20")

    def test_long_no_move(self) -> None:
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("100"),
            qty=Decimal("2"),
            side="long",
        )
        assert pnl == Decimal("0")


class TestPnlForTradeShort:
    """Short-side sign and magnitude pinning."""

    def test_short_profit(self) -> None:
        # Short from 100 to 90, qty 2 -> +20
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("90"),
            qty=Decimal("2"),
            side="short",
        )
        assert pnl == Decimal("20")

    def test_short_loss(self) -> None:
        # Short from 100 to 110, qty 2 -> -20
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=Decimal("2"),
            side="short",
        )
        assert pnl == Decimal("-20")

    def test_short_no_move(self) -> None:
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("100"),
            qty=Decimal("2"),
            side="short",
        )
        assert pnl == Decimal("0")


class TestPnlForTradeEdgeCases:
    """Boundary conditions that must not regress."""

    def test_zero_quantity_long(self) -> None:
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=Decimal("0"),
            side="long",
        )
        assert pnl == Decimal("0")

    def test_zero_quantity_short(self) -> None:
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("90"),
            qty=Decimal("0"),
            side="short",
        )
        assert pnl == Decimal("0")

    def test_fractional_decimal_precision(self) -> None:
        # Use values that would lose precision in float math; the
        # Decimal contract is the whole point of the helper.
        pnl = pnl_for_trade(
            entry=Decimal("0.1"),
            exit=Decimal("0.3"),
            qty=Decimal("0.2"),
            side="long",
        )
        assert pnl == Decimal("0.04")

    def test_leverage_is_not_a_parameter(self) -> None:
        # Two callers with different "leverage" assumptions but the
        # same already-levered qty MUST get the same number out.
        # This is the whole point of DEBT-024 / Phase 20.1.
        levered_qty = Decimal("5")  # already includes leverage
        pnl_a = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=levered_qty,
            side="long",
        )
        pnl_b = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=levered_qty,
            side="long",
        )
        assert pnl_a == pnl_b == Decimal("50")

    def test_invalid_side_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown trade side"):
            pnl_for_trade(
                entry=Decimal("100"),
                exit=Decimal("110"),
                qty=Decimal("1"),
                side="flat",  # type: ignore[arg-type]
            )


# =============================================================================
# Wilder ATR + SL floor enforcement (P1 items F + G)
# =============================================================================


def _make_candle(
    *,
    high: str,
    low: str,
    close: str,
    timestamp: datetime,
    open_: str | None = None,
) -> OHLCV:
    return OHLCV(
        timestamp=timestamp,
        open=Decimal(open_ if open_ is not None else close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("1"),
    )


def _build_ohlcv(rows: list[tuple[str, str, str]]) -> list[OHLCV]:
    """Build OHLCV from ``[(high, low, close), ...]`` rows."""
    start = datetime(2026, 1, 1)
    return [
        _make_candle(
            high=high,
            low=low,
            close=close,
            timestamp=start + timedelta(hours=i),
        )
        for i, (high, low, close) in enumerate(rows)
    ]


class TestComputeAtr:
    """Wilder's ATR(14) on Decimal OHLCV."""

    def test_compute_atr_known_values(self) -> None:
        # 6 candles → use period=2 so we can hand-compute easily.
        # Candle 0 has no prev close, so TRs are computed from i=1..5.
        # Choose values so TR = high - low for every bar (no gap):
        #   bar 1: TR = 102 - 100 = 2
        #   bar 2: TR = 104 - 101 = 3
        #   bar 3: TR = 105 - 101 = 4
        #   bar 4: TR = 107 - 102 = 5
        #   bar 5: TR = 109 - 103 = 6
        # First ATR (period=2) = mean(TR1, TR2) = (2 + 3) / 2 = 2.5
        # Then Wilder smoothing (period=2 → (prev*1 + tr)/2):
        #   ATR after TR3 = (2.5 + 4) / 2 = 3.25
        #   ATR after TR4 = (3.25 + 5) / 2 = 4.125
        #   ATR after TR5 = (4.125 + 6) / 2 = 5.0625
        rows = [
            ("100", "99", "100"),  # bar 0 (no TR)
            ("102", "100", "101"),  # TR=2
            ("104", "101", "103"),  # TR=3
            ("105", "101", "104"),  # TR=4
            ("107", "102", "106"),  # TR=5
            ("109", "103", "108"),  # TR=6
        ]
        candles = _build_ohlcv(rows)
        result = compute_atr(candles, period=2)
        assert result == Decimal("5.0625")

    def test_compute_atr_uses_gaps_via_prev_close(self) -> None:
        # Force at least one TR to be driven by abs(low - prev_close)
        # so the gap-aware branch is exercised. Bar 1 closes at 100;
        # bar 2 has high=98, low=90 → high-low=8 but
        # abs(low - prev_close) = abs(90 - 100) = 10 wins.
        rows = [
            ("100", "99", "100"),
            ("100", "98", "100"),  # TR = max(2, 0, 2) = 2
            ("98", "90", "92"),  # TR = max(8, 2, 10) = 10
        ]
        candles = _build_ohlcv(rows)
        result = compute_atr(candles, period=2)
        # First-and-only ATR window is the mean of the two TRs.
        assert result == Decimal("6")

    def test_compute_atr_insufficient_data_returns_none(self) -> None:
        # period=14 needs 15 candles; 14 must return None.
        rows = [("100", "99", "100")] * 14
        candles = _build_ohlcv(rows)
        assert compute_atr(candles, period=14) is None

    def test_compute_atr_exact_minimum_data_works(self) -> None:
        # period+1 candles = exactly enough for one ATR.
        rows = [("100", "99", "100")] * 15
        candles = _build_ohlcv(rows)
        result = compute_atr(candles, period=14)
        assert result is not None
        assert result == Decimal("1")  # every TR is 100 - 99 = 1

    def test_compute_atr_negative_period_raises(self) -> None:
        rows = [("100", "99", "100")] * 5
        with pytest.raises(ValueError, match="period must be positive"):
            compute_atr(_build_ohlcv(rows), period=0)


class TestEnforceSlFloorLong:
    """Long SL widens DOWN."""

    def test_long_atr_widens_below_existing(self) -> None:
        # Entry 100, ATR=2 → ATR floor = 1.5 * 2 = 3.
        # TF floor (1h) = 100 * 0.008 = 0.8.
        # Existing SL distance = 100 - 99 = 1, below max(3, 0.8)=3.
        # Floored SL distance = 3 → SL = 100 - 3 = 97.
        result = enforce_sl_floor(
            side="long",
            entry_price=Decimal("100"),
            stop_loss=Decimal("99"),
            timeframe="1h",
            atr=Decimal("2"),
        )
        assert result == Decimal("97")

    def test_long_tf_widens_when_no_atr(self) -> None:
        # Entry 1000, TF 4h → floor pct = 0.015 → distance = 15.
        # Existing SL 995 → distance 5 → widen to 1000 - 15 = 985.
        result = enforce_sl_floor(
            side="long",
            entry_price=Decimal("1000"),
            stop_loss=Decimal("995"),
            timeframe="4h",
            atr=None,
        )
        assert result == Decimal("985")

    def test_long_already_wide_returned_unchanged(self) -> None:
        # SL 90 → distance 10. ATR floor = 1.5 * 2 = 3,
        # TF (1h) = 100 * 0.008 = 0.8 → max = 3 < 10. Unchanged.
        result = enforce_sl_floor(
            side="long",
            entry_price=Decimal("100"),
            stop_loss=Decimal("90"),
            timeframe="1h",
            atr=Decimal("2"),
        )
        assert result == Decimal("90")

    def test_long_wider_floor_wins(self) -> None:
        # Entry 100, ATR=10 → ATR floor = 15. TF (1h) = 0.8.
        # ATR floor wins. SL=99 → widened to 100 - 15 = 85.
        result = enforce_sl_floor(
            side="long",
            entry_price=Decimal("100"),
            stop_loss=Decimal("99"),
            timeframe="1h",
            atr=Decimal("10"),
        )
        assert result == Decimal("85")


class TestEnforceSlFloorShort:
    """Short SL widens UP."""

    def test_short_atr_widens_above_existing(self) -> None:
        # Entry 100, ATR=2 → ATR floor = 3. SL 101 → distance 1.
        # Widen to 100 + 3 = 103.
        result = enforce_sl_floor(
            side="short",
            entry_price=Decimal("100"),
            stop_loss=Decimal("101"),
            timeframe="1h",
            atr=Decimal("2"),
        )
        assert result == Decimal("103")

    def test_short_tf_widens_when_no_atr(self) -> None:
        # Entry 1000, TF 4h → distance 15. SL 1005 → widen to 1015.
        result = enforce_sl_floor(
            side="short",
            entry_price=Decimal("1000"),
            stop_loss=Decimal("1005"),
            timeframe="4h",
            atr=None,
        )
        assert result == Decimal("1015")

    def test_short_already_wide_returned_unchanged(self) -> None:
        result = enforce_sl_floor(
            side="short",
            entry_price=Decimal("100"),
            stop_loss=Decimal("110"),
            timeframe="1h",
            atr=Decimal("2"),
        )
        assert result == Decimal("110")


class TestEnforceSlFloorEdgeCases:
    def test_unknown_tf_uses_default_pct(self) -> None:
        # Unknown TF "3h" → DEFAULT_TF_MIN_SL_PCT = 0.008.
        # Entry 1000 → distance 8. SL 999 → widen to 992.
        assert "3h" not in TF_MIN_SL_PCT
        result = enforce_sl_floor(
            side="long",
            entry_price=Decimal("1000"),
            stop_loss=Decimal("999"),
            timeframe="3h",
            atr=None,
        )
        # 1000 * DEFAULT_TF_MIN_SL_PCT
        expected = Decimal("1000") - (Decimal("1000") * DEFAULT_TF_MIN_SL_PCT)
        assert result == expected

    def test_no_atr_uses_tf_only(self) -> None:
        # When atr is None, ATR floor contributes 0 → TF floor wins.
        result = enforce_sl_floor(
            side="long",
            entry_price=Decimal("100"),
            stop_loss=Decimal("99.9"),
            timeframe="15m",  # 0.004
            atr=None,
        )
        # 100 * 0.004 = 0.4 → SL = 100 - 0.4 = 99.6
        assert result == Decimal("99.6")

    def test_invalid_side_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown trade side"):
            enforce_sl_floor(
                side="flat",  # type: ignore[arg-type]
                entry_price=Decimal("100"),
                stop_loss=Decimal("99"),
                timeframe="1h",
                atr=None,
            )

    def test_atr_floor_multiplier_constant(self) -> None:
        # Sanity-pin the public multiplier so an accidental tweak shows
        # up here rather than in a downstream regression.
        assert ATR_FLOOR_MULTIPLIER == Decimal("1.5")
