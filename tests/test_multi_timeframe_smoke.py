"""End-to-end smoke for Phase 9.1 multi-timeframe support.

Loads ``strategies/chasulang_ict_smc.md`` (the dormant template that
motivated 9.1) through the production loader path and exercises
``PromptStrategy.format_prompt`` with the exact data shape
``ProposalEngine`` now passes. Catches drift between the template and
the framework — if someone adds a ``{ohlcv_30m}`` placeholder to
chasulang without updating the engine's TF list, this test fails.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from src.models import OHLCV
from src.strategy.loader import PromptStrategy, load_strategy

CHASULANG_PATH = Path(__file__).resolve().parent.parent / "strategies" / "chasulang_ict_smc.md"


def _make_candles(n: int, base: int) -> list[OHLCV]:
    out: list[OHLCV] = []
    start = datetime(2026, 1, 1)
    for i in range(n):
        price = Decimal(base + i)
        out.append(
            OHLCV(
                timestamp=start + timedelta(hours=i),
                open=price,
                high=price + Decimal("10"),
                low=price - Decimal("10"),
                close=price + Decimal("5"),
                volume=Decimal("100"),
            )
        )
    return out


def test_chasulang_template_loads_and_declares_multi_tf() -> None:
    strategy = load_strategy(CHASULANG_PATH)
    assert isinstance(strategy, PromptStrategy)
    assert strategy.info.requires_multi_timeframe is True
    # Macro→micro ordering: the engine derives the primary TF from the
    # last entry, so this matters.
    assert strategy.info.timeframes == ["4h", "1h", "15m", "5m"]


def test_chasulang_format_prompt_fills_every_placeholder() -> None:
    """All five non-trivial placeholders are filled, no fail-fast.

    This is the smoke that proves the dormant template is now alive:
    feed it the dict + current_price the engine produces and confirm
    no ``StrategyValidationError`` is raised.
    """
    strategy = load_strategy(CHASULANG_PATH)
    assert isinstance(strategy, PromptStrategy)

    ohlcv_by_tf = {
        "4h": _make_candles(30, 50_000),
        "1h": _make_candles(30, 50_500),
        "15m": _make_candles(30, 50_700),
        "5m": _make_candles(30, 50_800),
    }
    primary = ohlcv_by_tf["5m"]
    rendered = strategy.format_prompt(
        primary,
        "BTC/USDT",
        "5m",
        ohlcv_by_timeframe=ohlcv_by_tf,
        current_price=Decimal("50855.50"),
    )

    # Every per-TF placeholder consumed.
    for placeholder in ("{ohlcv_4h}", "{ohlcv_1h}", "{ohlcv_15m}", "{ohlcv_5m}"):
        assert placeholder not in rendered
    assert "{current_price}" not in rendered
    assert "{symbol}" not in rendered
    # Real values landed.
    assert "BTC/USDT" in rendered
    assert "50855.50" in rendered
