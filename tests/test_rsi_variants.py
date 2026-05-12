"""Tests for the RSI baseline variants (Phase 9.4).

The Phase 9.2 baseline ``strategies/rsi.py`` was deliberately
universal-timeframe so it could run on whichever single TF the
engine passed. Phase 9.4 added two cadence-locked siblings:

* ``rsi_4h.py``  — declares ``timeframes: ["4h"]`` (swing)
* ``rsi_15m.py`` — declares ``timeframes: ["15m"]`` (scalp)

Both reuse :class:`strategies.rsi.RSIMeanReversionStrategy` directly,
so signal logic equivalence is automatic by construction. These
tests verify:

1. Each variant loads cleanly through the production
   ``load_all_strategies`` path with the expected metadata.
2. Each variant produces an identical signal to the universal
   reference on the same OHLCV input — no logic drift.
3. The three TECHNIQUE_INFO names are unique so the loader's
   duplicate-name guard does not silently drop one.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.models import OHLCV
from src.strategy.base import BaseStrategy
from src.strategy.loader import load_all_strategies, load_strategy

REPO_ROOT = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = REPO_ROOT / "strategies"


def _oversold_candles() -> list[OHLCV]:
    """Build a candle stream that drives RSI below 30.

    A monotonic decline of ~1% per bar gives Wilder's RSI plenty of
    negative deltas to drive the indicator into the oversold zone
    well before the strategy's ``period * 3`` minimum is reached.
    """
    start = datetime(2026, 1, 1)
    price = 50_000.0
    candles: list[OHLCV] = []
    for i in range(60):
        price *= 0.99  # 1% drop per candle
        c = Decimal(str(round(price, 2)))
        candles.append(
            OHLCV(
                timestamp=start + timedelta(hours=i),
                open=c,
                high=c + Decimal("10"),
                low=c - Decimal("10"),
                close=c,
                volume=Decimal("100"),
            )
        )
    return candles


def test_all_three_variants_load_via_loader() -> None:
    """The production loader picks up universal + 4h + 15m as
    three distinct techniques (no duplicate-name collisions)."""
    strategies = load_all_strategies(STRATEGIES_DIR)
    for name in ("rsi_universal", "rsi_4h", "rsi_15m"):
        assert name in strategies, f"loader missed {name}"
        assert isinstance(strategies[name], BaseStrategy)


def test_rsi_4h_metadata() -> None:
    s = load_strategy(STRATEGIES_DIR / "rsi_4h.py")
    assert s.name == "rsi_4h"
    assert s.info.timeframes == ["4h"]
    assert s.info.symbols == []  # universal symbol
    assert s.info.status == "experimental"


def test_rsi_15m_metadata() -> None:
    s = load_strategy(STRATEGIES_DIR / "rsi_15m.py")
    assert s.name == "rsi_15m"
    assert s.info.timeframes == ["15m"]
    assert s.info.symbols == []
    assert s.info.status == "experimental"


def test_rsi_universal_renamed() -> None:
    """The Phase 9.2 ``rsi_mean_reversion`` was renamed to
    ``rsi_universal`` for symmetry with the cadence-locked siblings."""
    s = load_strategy(STRATEGIES_DIR / "rsi.py")
    assert s.name == "rsi_universal"


def test_rsi_declares_dynamic_minimum_candles() -> None:
    """RSI warmup tracks the configured period instead of engine defaults."""

    s = load_strategy(STRATEGIES_DIR / "rsi.py")
    assert s.minimum_candles == 42


@pytest.mark.asyncio
async def test_variants_match_universal_on_same_input() -> None:
    """All three variants share one strategy class, so they must
    produce byte-identical signals on identical OHLCV input. This
    guards against accidental divergence if someone later changes
    one variant's wrapper."""
    universal = load_strategy(STRATEGIES_DIR / "rsi.py")
    rsi_4h = load_strategy(STRATEGIES_DIR / "rsi_4h.py")
    rsi_15m = load_strategy(STRATEGIES_DIR / "rsi_15m.py")

    candles = _oversold_candles()
    a = await universal.analyze(candles, "BTC/USDT", "4h")
    b = await rsi_4h.analyze(candles, "BTC/USDT", "4h")
    c = await rsi_15m.analyze(candles, "BTC/USDT", "15m")

    # Same signal direction (the candles drive RSI below 30 → long).
    assert a.signal == b.signal == c.signal == "long"
    # Same numeric outputs (entry / SL / TP are deterministic from
    # the close price and fixed percentages).
    assert a.entry_price == b.entry_price == c.entry_price
    assert a.stop_loss == b.stop_loss == c.stop_loss
    assert a.take_profit == b.take_profit == c.take_profit
    assert a.confidence == pytest.approx(b.confidence)
    assert a.confidence == pytest.approx(c.confidence)


def test_variants_do_not_share_technique_info_dict() -> None:
    """If someone copy-pastes ``TECHNIQUE_INFO`` they could end up
    sharing a mutable dict reference. Verify the three are distinct
    objects so a future mutation of one's fields can't bleed into
    another."""
    import strategies.rsi as universal_mod
    import strategies.rsi_4h as rsi_4h_mod
    import strategies.rsi_15m as rsi_15m_mod

    assert universal_mod.TECHNIQUE_INFO is not rsi_4h_mod.TECHNIQUE_INFO
    assert universal_mod.TECHNIQUE_INFO is not rsi_15m_mod.TECHNIQUE_INFO
    assert rsi_4h_mod.TECHNIQUE_INFO is not rsi_15m_mod.TECHNIQUE_INFO


def test_all_rsi_variants_pin_take_profit_pct_at_0_05() -> None:
    """DEBT-060 regression pin: all RSI variants ship TP = 5%.

    The 5% TP gives the family a nominal R/R of 2.5:1 against the
    fixed 2% SL, which carries enough margin above the proposal-
    layer 2.0 R/R floor to survive worst-case ATR-driven SL
    widening (~2.25% on 4h alts per ``src/utils/trading_math.py``).
    A future "tighten TP" change without re-running the widening
    math would silently fail-closed; this pin keeps the value
    explicit so any regression must update the test in lockstep.
    """
    import strategies.rsi as universal_mod
    import strategies.rsi_4h as rsi_4h_mod
    import strategies.rsi_15m as rsi_15m_mod

    # rsi_4h and rsi_15m delegate to the universal class but re-
    # declare their own ``TAKE_PROFIT_PCT`` for documentation /
    # debuggability. Assert the value on whichever module owns it
    # (universal is the canonical source; the two siblings inherit
    # behaviorally via direct class reuse — see test_variants_match_
    # universal_on_same_input).
    assert universal_mod.TAKE_PROFIT_PCT == 0.05
    # Siblings import the class, so they see the same constant
    # through ``strategies.rsi`` at runtime. Pin the module-level
    # constant on the siblings too if they redeclare it (they
    # currently do not — they inherit via class reuse, so the
    # universal pin above is sufficient). Belt-and-suspenders:
    # confirm neither sibling has shadowed the constant locally
    # with a different value.
    for mod in (rsi_4h_mod, rsi_15m_mod):
        local_tp = getattr(mod, "TAKE_PROFIT_PCT", None)
        if local_tp is not None:
            assert local_tp == 0.05, (
                f"{mod.__name__} shadows TAKE_PROFIT_PCT with "
                f"{local_tp!r}; must stay 0.05 to preserve R/R margin "
                f"above the 2.0 proposal-engine floor."
            )
