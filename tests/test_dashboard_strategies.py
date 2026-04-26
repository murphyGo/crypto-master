"""Tests for the Analysis Technique Status page (Phase 7.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

from src.dashboard.pages.strategies import (
    build_summary_dataframe,
    build_trend_dataframe,
)
from src.strategy.base import BaseStrategy, TechniqueInfo
from src.strategy.performance import (
    PerformanceRecord,
    PerformanceTracker,
    TechniquePerformance,
    TradeOutcome,
)

# =============================================================================
# Helpers
# =============================================================================


def make_info(
    name: str = "tech_a",
    version: str = "1.0.0",
    technique_type: str = "prompt",
    symbols: list[str] | None = None,
) -> TechniqueInfo:
    return TechniqueInfo(
        name=name,
        version=version,
        description=f"{name} description",
        technique_type=technique_type,
        symbols=symbols if symbols is not None else ["BTC/USDT"],
    )


def make_strategy(info: TechniqueInfo | None = None) -> BaseStrategy:
    info = info or make_info()
    strategy = MagicMock(spec=BaseStrategy)
    strategy.name = info.name
    strategy.version = info.version
    strategy.info = info
    return strategy


def make_perf(
    name: str,
    version: str = "1.0.0",
    *,
    total_trades: int = 0,
    wins: int = 0,
    losses: int = 0,
    win_rate: float = 0.0,
    avg_pnl_percent: float = 0.0,
    total_pnl_percent: float = 0.0,
    best_trade_pnl: float = 0.0,
    worst_trade_pnl: float = 0.0,
) -> TechniquePerformance:
    return TechniquePerformance(
        technique_name=name,
        technique_version=version,
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        avg_pnl_percent=avg_pnl_percent,
        total_pnl_percent=total_pnl_percent,
        best_trade_pnl=best_trade_pnl,
        worst_trade_pnl=worst_trade_pnl,
    )


def make_record(
    *,
    technique_name: str = "tech_a",
    version: str = "1.0.0",
    signal: str = "long",
    entry: str = "100",
    exit_price: str | None = "110",
    outcome: TradeOutcome = TradeOutcome.WIN,
    analysis_at: datetime | None = None,
    exit_at: datetime | None = None,
    pnl_percent: float | None = None,
) -> PerformanceRecord:
    return PerformanceRecord(
        technique_name=technique_name,
        technique_version=version,
        symbol="BTC/USDT",
        timeframe="1h",
        signal=signal,  # type: ignore[arg-type]
        entry_price=Decimal(entry),
        stop_loss=Decimal("95"),
        take_profit=Decimal("115"),
        confidence=0.8,
        analysis_timestamp=analysis_at or datetime(2026, 1, 1, 0, 0, 0),
        outcome=outcome,
        exit_price=Decimal(exit_price) if exit_price is not None else None,
        exit_timestamp=exit_at,
        pnl_percent=pnl_percent,
    )


# =============================================================================
# build_summary_dataframe
# =============================================================================


def test_summary_one_row_per_strategy() -> None:
    tracker = MagicMock(spec=PerformanceTracker)
    tracker.get_performance.side_effect = lambda name, version: make_perf(
        name, version, total_trades=10, win_rate=0.6, avg_pnl_percent=1.5
    )
    strategies = {
        "tech_a": make_strategy(make_info("tech_a", symbols=["BTC/USDT"])),
        "tech_b": make_strategy(make_info("tech_b", symbols=["ETH/USDT"])),
    }

    df = build_summary_dataframe(strategies, tracker)

    assert len(df) == 2
    assert set(df["Technique"]) == {"tech_a", "tech_b"}
    assert all(df["Total Trades"] == 10)
    assert all(df["Win Rate %"] == 60.0)


def test_summary_sorts_by_technique_name() -> None:
    tracker = MagicMock(spec=PerformanceTracker)
    tracker.get_performance.side_effect = lambda name, version: make_perf(name)
    strategies = {
        "zeta": make_strategy(make_info("zeta")),
        "alpha": make_strategy(make_info("alpha")),
    }

    df = build_summary_dataframe(strategies, tracker)

    assert list(df["Technique"]) == ["alpha", "zeta"]


def test_summary_handles_no_history() -> None:
    """A technique with zero trades must still appear in the table."""
    tracker = MagicMock(spec=PerformanceTracker)
    tracker.get_performance.side_effect = lambda name, version: make_perf(name)
    strategies = {"new_strat": make_strategy(make_info("new_strat"))}

    df = build_summary_dataframe(strategies, tracker)

    row = df.iloc[0]
    assert row["Total Trades"] == 0
    assert row["Win Rate %"] == 0.0


def test_summary_renders_dash_for_no_symbols() -> None:
    tracker = MagicMock(spec=PerformanceTracker)
    tracker.get_performance.side_effect = lambda name, version: make_perf(name)
    strategies = {
        "any": make_strategy(make_info("any", symbols=[])),
    }

    df = build_summary_dataframe(strategies, tracker)

    assert df.iloc[0]["Symbols"] == "—"


def test_summary_empty_strategies_gives_empty_frame() -> None:
    tracker = MagicMock(spec=PerformanceTracker)

    df = build_summary_dataframe({}, tracker)

    assert df.empty


# =============================================================================
# build_trend_dataframe
# =============================================================================


def test_trend_empty_records_returns_empty_frame() -> None:
    df = build_trend_dataframe([])

    assert df.empty
    assert list(df.columns) == ["timestamp", "pnl_percent", "cumulative_pnl"]


def test_trend_skips_pending_records() -> None:
    """Pending records have no exit and no P&L; they must not appear."""
    pending = make_record(outcome=TradeOutcome.PENDING, exit_price=None)

    df = build_trend_dataframe([pending])

    assert df.empty


def test_trend_uses_stored_pnl_when_set() -> None:
    """Records with explicit pnl_percent take precedence over recalculation."""
    rec = make_record(
        outcome=TradeOutcome.WIN,
        exit_price="200",  # would compute 100% if we used calculate_pnl
        pnl_percent=12.5,  # but the stored value should win
    )

    df = build_trend_dataframe([rec])

    assert df.iloc[0]["pnl_percent"] == 12.5


def test_trend_falls_back_to_calculate_when_pnl_missing() -> None:
    rec = make_record(
        signal="long",
        entry="100",
        exit_price="110",  # +10%
        outcome=TradeOutcome.WIN,
        pnl_percent=None,
    )

    df = build_trend_dataframe([rec])

    assert df.iloc[0]["pnl_percent"] == 10.0


def test_trend_orders_by_timestamp_and_cumsums() -> None:
    t0 = datetime(2026, 1, 1)
    r_old = make_record(
        analysis_at=t0,
        exit_at=t0 + timedelta(hours=1),
        pnl_percent=5.0,
    )
    r_new = make_record(
        analysis_at=t0 + timedelta(days=1),
        exit_at=t0 + timedelta(days=1, hours=1),
        pnl_percent=-2.0,
    )
    # Pass in reverse order to prove sorting is by timestamp, not insertion.
    df = build_trend_dataframe([r_new, r_old])

    assert list(df["pnl_percent"]) == [5.0, -2.0]
    assert list(df["cumulative_pnl"]) == [5.0, 3.0]


def test_trend_uses_exit_timestamp_when_available() -> None:
    """The trend axis should reflect when the trade closed, not when it was analyzed."""
    analysis = datetime(2026, 1, 1)
    exit_at = datetime(2026, 1, 5)
    rec = make_record(
        analysis_at=analysis,
        exit_at=exit_at,
        pnl_percent=3.0,
    )

    df = build_trend_dataframe([rec])

    assert df.iloc[0]["timestamp"] == exit_at


def test_trend_falls_back_to_analysis_timestamp_when_no_exit() -> None:
    """Backstop: a closed-but-no-exit-time record (test fixture) still plots."""
    analysis = datetime(2026, 1, 1)
    rec = make_record(
        analysis_at=analysis,
        exit_at=None,
        pnl_percent=3.0,
    )

    df = build_trend_dataframe([rec])

    assert df.iloc[0]["timestamp"] == analysis


# =============================================================================
# AppTest smoke: the page renders in a real Streamlit script
# =============================================================================


def test_strategies_page_renders_warning_when_no_strategies(
    tmp_path: Path,
) -> None:
    """Page must not crash when the strategies dir is empty."""
    from streamlit.testing.v1 import AppTest

    # Build a minimal one-page Streamlit script that calls render()
    # against an empty tmp directory — no real strategies, no real data.
    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from pathlib import Path
from src.dashboard.pages.strategies import render
from src.strategy.performance import PerformanceTracker

render(
    strategies_dir=Path({str(tmp_path)!r}),
    tracker=PerformanceTracker(data_dir=Path({str(tmp_path / "perf")!r})),
)
"""
    at = AppTest.from_string(script).run(timeout=10)

    assert not at.exception, [str(e) for e in at.exception]
    warnings = [w.value for w in at.warning]
    assert any("No analysis techniques found" in w for w in warnings), warnings


def test_strategies_page_smoke_with_real_directory() -> None:
    """End-to-end: full app with strategies/ on disk renders without exception."""
    from streamlit.testing.v1 import AppTest

    script = f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})
from src.dashboard.pages.strategies import render

render()
"""
    at = AppTest.from_string(script).run(timeout=15)

    assert not at.exception, [str(e) for e in at.exception]
    titles = [t.value for t in at.title]
    assert any("Analysis Techniques" in t for t in titles), titles
