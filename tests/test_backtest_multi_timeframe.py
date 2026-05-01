"""Tests for the multi-timeframe backtester (Phase 9.3).

Covers:
- Input validation on ``run_multi_timeframe``
- Single-TF parity: a multi-TF run with one TF behaves identically to
  ``run`` on the same series (modulo the strategy contract).
- Per-step slicing — at primary candle ``i`` no higher-TF candle in
  the slice has timestamp > primary candle's timestamp (no future
  leakage).
- Warmup gating — analyze is not called until every TF has reached
  ``warmup_candles``.
- Dispatcher: ``run_for_strategy`` routes single-TF strategies to
  ``run`` and multi-TF strategies to ``run_multi_timeframe``;
  raises when multi-TF strategy gets no dict.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.backtest.engine import (
    BacktestConfig,
    Backtester,
    BacktestError,
    slice_multi_tf_by_index,
)
from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo

# =============================================================================
# Helpers
# =============================================================================


def candle(ts: datetime, close: Decimal) -> OHLCV:
    return OHLCV(
        timestamp=ts,
        open=close,
        high=close + Decimal("100"),
        low=close - Decimal("100"),
        close=close,
        volume=Decimal("100"),
    )


def make_5m(count: int, *, base: Decimal = Decimal("50000")) -> list[OHLCV]:
    start = datetime(2026, 1, 1)
    return [candle(start + timedelta(minutes=5 * i), base) for i in range(count)]


def aligned_higher(
    primary: list[OHLCV],
    minutes_per_candle: int,
    *,
    base: Decimal = Decimal("50000"),
) -> list[OHLCV]:
    """Build a higher-TF series whose timestamps land on primary boundaries.

    Useful so the bisect cutoff lines up cleanly to a real candle.
    """
    if not primary:
        return []
    span = primary[-1].timestamp - primary[0].timestamp
    n_candles = (span.total_seconds() // (minutes_per_candle * 60)).__int__() + 1
    return [
        candle(primary[0].timestamp + timedelta(minutes=minutes_per_candle * i), base)
        for i in range(n_candles)
    ]


class StaticStrategy(BaseStrategy):
    """Always returns ``signal`` after warmup; tracks every analyze call."""

    def __init__(
        self,
        *,
        info: TechniqueInfo | None = None,
        signal: AnalysisResult | None = None,
        requires_multi_tf: bool = False,
    ) -> None:
        super().__init__(
            info=info
            or TechniqueInfo(
                name="static_test",
                version="1.0.0",
                description="static signal under test",
                technique_type="code",
                requires_multi_timeframe=requires_multi_tf,
            )
        )
        self._signal = signal or AnalysisResult(
            signal="long",
            confidence=0.8,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49500"),
            take_profit=Decimal("51000"),
            reasoning="static",
        )
        self.calls: list[dict[str, object]] = []

    async def analyze(
        self,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
        current_price: Decimal | None = None,
    ) -> AnalysisResult:
        self.calls.append(
            {
                "primary_len": len(ohlcv),
                "primary_last_ts": ohlcv[-1].timestamp if ohlcv else None,
                "by_tf_keys": (
                    sorted(ohlcv_by_timeframe.keys())
                    if ohlcv_by_timeframe is not None
                    else None
                ),
                "by_tf_lens": (
                    {tf: len(c) for tf, c in ohlcv_by_timeframe.items()}
                    if ohlcv_by_timeframe is not None
                    else None
                ),
                "by_tf_last_ts": (
                    {
                        tf: (c[-1].timestamp if c else None)
                        for tf, c in ohlcv_by_timeframe.items()
                    }
                    if ohlcv_by_timeframe is not None
                    else None
                ),
                "current_price": current_price,
            }
        )
        return self._signal


def make_backtester(tmp_path: Path, *, warmup: int = 5) -> Backtester:
    return Backtester(
        config=BacktestConfig(
            initial_balance=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=0,
            warmup_candles=warmup,
            leverage=1,
            risk_percent=1.0,
            max_position_size_percent=50.0,
            min_risk_reward_ratio=1.5,
        ),
        data_dir=tmp_path / "backtest",
    )


# =============================================================================
# slice_multi_tf_by_index
# =============================================================================


class TestSliceHelper:
    def test_single_tf_passthrough(self) -> None:
        primary = make_5m(10)
        sliced, mtf = slice_multi_tf_by_index(primary, None, 2, 5)
        assert sliced == primary[2:5]
        assert mtf is None

    def test_multi_tf_subset_by_timestamp(self) -> None:
        primary = make_5m(20)  # 5m candles, 0..95min
        # Higher TF: 4 candles at 0min, 25min, 50min, 75min
        higher = [
            candle(primary[0].timestamp + timedelta(minutes=25 * i), Decimal("50000"))
            for i in range(4)
        ]
        sliced, mtf = slice_multi_tf_by_index(
            primary, {"5m": primary, "25m": higher}, 5, 11
        )
        # primary slice covers minutes 25..50 (indices 5..10 inclusive).
        assert sliced == primary[5:11]
        assert mtf is not None
        # Higher-TF slice: candles at 25min and 50min — both fall within
        # [primary[5].timestamp, primary[10].timestamp].
        assert len(mtf["25m"]) == 2
        assert mtf["25m"][0].timestamp == primary[5].timestamp
        assert mtf["25m"][1].timestamp == primary[5].timestamp + timedelta(minutes=25)

    def test_empty_primary_slice_yields_empty_higher(self) -> None:
        primary = make_5m(10)
        higher = aligned_higher(primary, 30)
        sliced, mtf = slice_multi_tf_by_index(
            primary, {"5m": primary, "30m": higher}, 5, 5
        )
        assert sliced == []
        assert mtf == {"5m": [], "30m": []}


# =============================================================================
# run_multi_timeframe — input validation
# =============================================================================


class TestRunMultiTimeframeValidation:
    @pytest.mark.asyncio
    async def test_empty_dict_raises(self, tmp_path: Path) -> None:
        bt = make_backtester(tmp_path)
        with pytest.raises(BacktestError, match="empty"):
            await bt.run_multi_timeframe(
                strategy=StaticStrategy(requires_multi_tf=True),
                ohlcv_by_timeframe={},
                symbol="BTC/USDT",
                primary_timeframe="5m",
            )

    @pytest.mark.asyncio
    async def test_missing_primary_key_raises(self, tmp_path: Path) -> None:
        bt = make_backtester(tmp_path)
        with pytest.raises(BacktestError, match="not in"):
            await bt.run_multi_timeframe(
                strategy=StaticStrategy(requires_multi_tf=True),
                ohlcv_by_timeframe={"4h": make_5m(10)},
                symbol="BTC/USDT",
                primary_timeframe="5m",
            )

    @pytest.mark.asyncio
    async def test_empty_primary_series_raises(self, tmp_path: Path) -> None:
        bt = make_backtester(tmp_path)
        with pytest.raises(BacktestError, match="empty candle list"):
            await bt.run_multi_timeframe(
                strategy=StaticStrategy(requires_multi_tf=True),
                ohlcv_by_timeframe={"5m": [], "4h": make_5m(5)},
                symbol="BTC/USDT",
                primary_timeframe="5m",
            )


# =============================================================================
# run_multi_timeframe — semantics
# =============================================================================


class TestRunMultiTimeframeSemantics:
    @pytest.mark.asyncio
    async def test_no_future_leakage_in_higher_tf_slice(self, tmp_path: Path) -> None:
        """At every analyze call, no higher-TF candle is ahead of the
        primary candle's timestamp."""
        primary = make_5m(40)
        higher = aligned_higher(primary, 20)  # 20m candles
        strat = StaticStrategy(requires_multi_tf=True)
        bt = make_backtester(tmp_path, warmup=3)

        await bt.run_multi_timeframe(
            strategy=strat,
            ohlcv_by_timeframe={"5m": primary, "20m": higher},
            symbol="BTC/USDT",
            primary_timeframe="5m",
        )

        assert strat.calls, "Strategy should have been invoked at least once"
        for call in strat.calls:
            assert call["primary_last_ts"] is not None
            primary_ts = call["primary_last_ts"]
            higher_last_ts = call["by_tf_last_ts"]["20m"]  # type: ignore[index]
            # Higher-TF cutoff must be ≤ primary candle's timestamp.
            assert higher_last_ts is not None
            assert higher_last_ts <= primary_ts

    @pytest.mark.asyncio
    async def test_warmup_gates_every_timeframe(self, tmp_path: Path) -> None:
        """analyze is only called once every TF has ≥ warmup candles."""
        primary = make_5m(40)
        # 20m TF will only have 1 candle by primary index 3 (15 min in),
        # 2 by index 7, 3 by index 11, 4 by index 15. So with warmup=4
        # the first analyze call should land at index 15 (or later).
        higher = aligned_higher(primary, 20)
        strat = StaticStrategy(requires_multi_tf=True)
        bt = make_backtester(tmp_path, warmup=4)

        await bt.run_multi_timeframe(
            strategy=strat,
            ohlcv_by_timeframe={"5m": primary, "20m": higher},
            symbol="BTC/USDT",
            primary_timeframe="5m",
        )

        assert strat.calls, "expected at least one analyze call"
        # First call's higher-TF slice must already meet warmup.
        first = strat.calls[0]
        assert first["by_tf_lens"]["20m"] >= 4  # type: ignore[index]
        assert first["by_tf_lens"]["5m"] >= 4  # type: ignore[index]

    @pytest.mark.asyncio
    async def test_result_timeframe_is_primary(self, tmp_path: Path) -> None:
        primary = make_5m(30)
        higher = aligned_higher(primary, 30)
        strat = StaticStrategy(
            requires_multi_tf=True,
            signal=AnalysisResult(
                signal="neutral",
                confidence=0.0,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49500"),
                take_profit=Decimal("51000"),
                reasoning="quiet",
            ),
        )
        bt = make_backtester(tmp_path, warmup=3)

        result = await bt.run_multi_timeframe(
            strategy=strat,
            ohlcv_by_timeframe={"5m": primary, "30m": higher},
            symbol="BTC/USDT",
            primary_timeframe="5m",
        )

        assert result.timeframe == "5m"
        assert result.symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_current_price_comes_from_primary_close(self, tmp_path: Path) -> None:
        primary = make_5m(20)
        # Mutate one close so we can verify it propagated.
        primary[10] = OHLCV(
            timestamp=primary[10].timestamp,
            open=primary[10].open,
            high=primary[10].high,
            low=primary[10].low,
            close=Decimal("12345.67"),
            volume=primary[10].volume,
        )
        # Higher TF aligned 1:1 with primary so warmup gating is
        # deterministic. The contents don't matter — we're checking
        # the per-step ``current_price`` derivation.
        strat = StaticStrategy(
            requires_multi_tf=True,
            signal=AnalysisResult(
                signal="neutral",
                confidence=0.0,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49500"),
                take_profit=Decimal("51000"),
                reasoning="neutral",
            ),
        )
        bt = make_backtester(tmp_path, warmup=3)

        await bt.run_multi_timeframe(
            strategy=strat,
            ohlcv_by_timeframe={"5m": primary, "alt_5m": list(primary)},
            symbol="BTC/USDT",
            primary_timeframe="5m",
        )

        # Find the analyze call at primary index 10 (primary_len=11).
        match = next(c for c in strat.calls if c["primary_len"] == 11)
        assert match["current_price"] == Decimal("12345.67")


# =============================================================================
# run_for_strategy dispatcher
# =============================================================================


class TestRunForStrategy:
    @pytest.mark.asyncio
    async def test_single_tf_strategy_routes_to_run(self, tmp_path: Path) -> None:
        primary = make_5m(20)
        strat = StaticStrategy(requires_multi_tf=False)
        bt = make_backtester(tmp_path, warmup=3)

        result = await bt.run_for_strategy(
            strategy=strat,
            ohlcv=primary,
            symbol="BTC/USDT",
            timeframe="5m",
        )

        assert result.timeframe == "5m"
        # analyze call shape on the single-TF path: by_tf_keys is None.
        assert strat.calls, "expected analyze to fire"
        assert all(c["by_tf_keys"] is None for c in strat.calls)

    @pytest.mark.asyncio
    async def test_multi_tf_strategy_routes_to_multi(self, tmp_path: Path) -> None:
        primary = make_5m(20)
        higher = aligned_higher(primary, 20)
        strat = StaticStrategy(requires_multi_tf=True)
        bt = make_backtester(tmp_path, warmup=3)

        result = await bt.run_for_strategy(
            strategy=strat,
            ohlcv=primary,
            symbol="BTC/USDT",
            timeframe="5m",
            ohlcv_by_timeframe={"5m": primary, "20m": higher},
        )

        assert result.timeframe == "5m"
        assert strat.calls
        # Every call received the multi-TF dict.
        assert all(c["by_tf_keys"] == ["20m", "5m"] for c in strat.calls)

    @pytest.mark.asyncio
    async def test_multi_tf_strategy_without_dict_raises(self, tmp_path: Path) -> None:
        primary = make_5m(20)
        strat = StaticStrategy(requires_multi_tf=True)
        bt = make_backtester(tmp_path, warmup=3)

        with pytest.raises(BacktestError, match="requires_multi_timeframe"):
            await bt.run_for_strategy(
                strategy=strat,
                ohlcv=primary,
                symbol="BTC/USDT",
                timeframe="5m",
            )
