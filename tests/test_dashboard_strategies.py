"""Tests for the Analysis Technique Status page (Phase 7.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

from src.backtest.analyzer import PerformanceMetrics
from src.backtest.multi_account_report import MultiAccountReport
from src.dashboard.pages.strategies import (
    build_combinations_equity_dataframe,
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
from src.strategy.tuning import (
    StrategyAction,
    StrategyOverride,
    StrategyTuningPolicy,
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
# build_combinations_equity_dataframe
# =============================================================================


def test_combinations_equity_dataframe_pivots_sub_accounts() -> None:
    report = MultiAccountReport(
        run_id="combo-test",
        symbol="BTC/USDT",
        timeframe="1h",
        per_sub_account={
            "suba": PerformanceMetrics(final_balance=Decimal("10100")),
            "subb": PerformanceMetrics(final_balance=Decimal("9900")),
        },
        equity_curves={
            "suba": [
                (datetime(2026, 1, 1, 0, 0, 0), Decimal("10000")),
                (datetime(2026, 1, 1, 1, 0, 0), Decimal("10100")),
            ],
            "subb": [
                (datetime(2026, 1, 1, 0, 0, 0), Decimal("10000")),
                (datetime(2026, 1, 1, 1, 0, 0), Decimal("9900")),
            ],
        },
    )

    frame = build_combinations_equity_dataframe(report)

    assert list(frame.columns) == ["suba", "subb"]
    assert frame.iloc[-1]["suba"] == 10100.0
    assert frame.iloc[-1]["subb"] == 9900.0


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
# DEBT-061: fail-closed columns
# =============================================================================


def test_summary_emits_zero_fail_closed_columns_when_tracker_omitted() -> None:
    """Legacy callers (no fail-closed tracker) still get the columns at zero."""
    tracker = MagicMock(spec=PerformanceTracker)
    tracker.get_performance.side_effect = lambda name, version: make_perf(name)
    strategies = {"tech_a": make_strategy(make_info("tech_a"))}

    df = build_summary_dataframe(strategies, tracker)

    assert "Emitted" in df.columns
    assert "Fail-Closed" in df.columns
    assert "Fail-Closed %" in df.columns
    assert df.iloc[0]["Emitted"] == 0
    assert df.iloc[0]["Fail-Closed"] == 0
    assert df.iloc[0]["Fail-Closed %"] == 0.0


def test_summary_surfaces_fail_closed_rate_per_strategy(tmp_path: Path) -> None:
    """End-to-end: a strategy that fail-closed 3/10 emissions shows 30%."""
    from src.proposal.fail_closed_metrics import FailClosedMetricsTracker

    fc_tracker = FailClosedMetricsTracker(data_dir=tmp_path)
    for _ in range(10):
        fc_tracker.record_emitted("tech_a", "1.0.0")
    for _ in range(3):
        fc_tracker.record_fail_closed("tech_a", "1.0.0")

    perf_tracker = MagicMock(spec=PerformanceTracker)
    # The fail-closed tracker is queried with the perf tracker's
    # ``sub_account_id`` (canonical pattern in
    # ``build_summary_dataframe``), so the MagicMock must expose the
    # "default" namespace that ``record_emitted`` wrote under.
    perf_tracker.sub_account_id = "default"
    perf_tracker.get_performance.side_effect = lambda name, version: make_perf(name)
    strategies = {"tech_a": make_strategy(make_info("tech_a"))}

    df = build_summary_dataframe(strategies, perf_tracker, fc_tracker)

    row = df.iloc[0]
    assert row["Emitted"] == 10
    assert row["Fail-Closed"] == 3
    assert row["Fail-Closed %"] == 30.0


def test_summary_renders_per_sub_account_fail_closed_counts(tmp_path: Path) -> None:
    """Two sub-accounts running the same strategy show their own counts.

    Pin for the post-quant-fix per-call sub-account API: when the same
    ``FailClosedMetricsTracker`` instance carries counters for multiple
    sub-accounts, the dashboard summary for sub-account ``paper`` must
    surface ``paper``'s counts, not aggregate over every sub-account.
    """
    from src.proposal.fail_closed_metrics import FailClosedMetricsTracker

    fc_tracker = FailClosedMetricsTracker(data_dir=tmp_path)
    # Heavily-fail-closed under "paper", clean under "paper_alt".
    for _ in range(8):
        fc_tracker.record_emitted("tech_a", "1.0.0", sub_account_id="paper")
    for _ in range(2):
        fc_tracker.record_fail_closed("tech_a", "1.0.0", sub_account_id="paper")
    for _ in range(4):
        fc_tracker.record_emitted("tech_a", "1.0.0", sub_account_id="paper_alt")

    perf_tracker = MagicMock(spec=PerformanceTracker)
    perf_tracker.get_performance.side_effect = lambda name, version: make_perf(name)
    strategies = {"tech_a": make_strategy(make_info("tech_a"))}

    paper_df = build_summary_dataframe(
        strategies, perf_tracker, fc_tracker, sub_account_id="paper"
    )
    paper_alt_df = build_summary_dataframe(
        strategies, perf_tracker, fc_tracker, sub_account_id="paper_alt"
    )

    paper_row = paper_df.iloc[0]
    paper_alt_row = paper_alt_df.iloc[0]
    assert paper_row["Emitted"] == 8
    assert paper_row["Fail-Closed"] == 2
    assert paper_row["Fail-Closed %"] == 25.0
    assert paper_alt_row["Emitted"] == 4
    assert paper_alt_row["Fail-Closed"] == 0
    assert paper_alt_row["Fail-Closed %"] == 0.0


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
    # Phase 21.2: PerformanceRecord timestamps are UTC-aware via the
    # field validator. Pass aware fixtures so the dataframe equality
    # holds against the validator's coerced output.
    analysis = datetime(2026, 1, 1, tzinfo=timezone.utc)
    exit_at = datetime(2026, 1, 5, tzinfo=timezone.utc)
    rec = make_record(
        analysis_at=analysis,
        exit_at=exit_at,
        pnl_percent=3.0,
    )

    df = build_trend_dataframe([rec])

    assert df.iloc[0]["timestamp"] == exit_at


def test_trend_falls_back_to_analysis_timestamp_when_no_exit() -> None:
    """Backstop: a closed-but-no-exit-time record (test fixture) still plots."""
    analysis = datetime(2026, 1, 1, tzinfo=timezone.utc)
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


# =============================================================================
# strategy-tuning DEBT-069(a): Applied / Recommended view + YAML clipboard diff
# =============================================================================


def _make_tracker_returning(
    perf_by_name: dict[str, TechniquePerformance],
    sub_account_id: str = "lab",
) -> MagicMock:
    tracker = MagicMock(spec=PerformanceTracker)
    tracker.sub_account_id = sub_account_id
    tracker.get_performance.side_effect = lambda name, version: perf_by_name[name]
    return tracker


def _keep_band_perf(name: str) -> TechniquePerformance:
    """Healthy band: PF 1.5, win 50%, 30 closed ⇒ recommends keep."""
    return TechniquePerformance(
        technique_name=name,
        technique_version="1.0.0",
        wins=15,
        losses=15,
        breakevens=0,
        win_rate=0.5,
        total_pnl_percent=10.0,
        gross_win_pct=30.0,
        gross_loss_pct=20.0,
        max_drawdown_pct=3.0,
    )


def _thin_evidence_perf(name: str) -> TechniquePerformance:
    """Zero closed trades ⇒ recommender returns None (insufficient)."""
    return TechniquePerformance(
        technique_name=name,
        technique_version="1.0.0",
    )


def test_tuning_rows_applied_and_recommended_keep_match() -> None:
    from src.dashboard.pages.strategies import build_strategy_tuning_rows

    strategies = {"rsi": make_strategy(make_info(name="rsi"))}
    tracker = _make_tracker_returning({"rsi": _keep_band_perf("rsi")})
    policy = StrategyTuningPolicy(enabled=True)  # default applied = keep

    rows = build_strategy_tuning_rows(strategies, policy, tracker)

    assert len(rows) == 1
    row = rows[0]
    assert row.sub_account_id == "lab"
    assert row.applied == "keep"
    assert row.recommended == "keep"
    assert row.differs is False
    assert row.yaml_diff == ""
    assert "closed=30" in row.evidence_summary
    assert "PF=1.50" in row.evidence_summary


def test_tuning_rows_recommendation_differs_produces_yaml_diff() -> None:
    from src.dashboard.pages.strategies import build_strategy_tuning_rows

    strategies = {"rsi": make_strategy(make_info(name="rsi"))}
    tracker = _make_tracker_returning({"rsi": _keep_band_perf("rsi")})
    # Applied = pause, but evidence recommends keep ⇒ differs + diff.
    policy = StrategyTuningPolicy(
        enabled=True,
        strategy_overrides={"rsi": StrategyOverride(applied=StrategyAction.PAUSE)},
    )

    rows = build_strategy_tuning_rows(strategies, policy, tracker)

    row = rows[0]
    assert row.applied == "pause"
    assert row.recommended == "keep"
    assert row.differs is True
    assert "strategy_tuning:" in row.yaml_diff
    assert "rsi:" in row.yaml_diff
    assert "applied: keep" in row.yaml_diff
    assert "was: pause" in row.yaml_diff


def test_tuning_rows_thin_evidence_falls_back_to_seed() -> None:
    # DEBT-069(b): thin evidence (recommender returns None) now falls back
    # to the per-strategy seed instead of rendering a dash. An *unnamed*
    # strategy hits the catch-all seed (retune); applied defaults to keep,
    # so the seed differs and a YAML diff is offered.
    from src.dashboard.pages.strategies import build_strategy_tuning_rows

    strategies = {"cold": make_strategy(make_info(name="cold"))}
    tracker = _make_tracker_returning({"cold": _thin_evidence_perf("cold")})
    policy = StrategyTuningPolicy(enabled=True)

    rows = build_strategy_tuning_rows(strategies, policy, tracker)

    row = rows[0]
    assert row.applied == "keep"
    assert row.recommended == "retune"  # catch-all seed
    assert row.differs is True
    assert "applied: retune" in row.yaml_diff


def test_tuning_rows_thin_evidence_seeded_pause_produces_yaml_diff() -> None:
    # DEBT-069(b): a named family seeded to PAUSE under thin evidence shows
    # a diff vs the applied KEEP and a valid YAML snippet.
    from src.dashboard.pages.strategies import build_strategy_tuning_rows

    strategies = {
        "momentum_pinball_orb": make_strategy(make_info(name="momentum_pinball_orb"))
    }
    tracker = _make_tracker_returning(
        {"momentum_pinball_orb": _thin_evidence_perf("momentum_pinball_orb")}
    )
    policy = StrategyTuningPolicy(enabled=True)  # applied defaults to keep

    rows = build_strategy_tuning_rows(strategies, policy, tracker)

    row = rows[0]
    assert row.applied == "keep"
    assert row.recommended == "pause"  # seeded
    assert row.differs is True
    assert "strategy_tuning:" in row.yaml_diff
    assert "    momentum_pinball_orb:" in row.yaml_diff
    assert "      applied: pause" in row.yaml_diff


def test_tuning_rows_live_recommendation_supersedes_seed() -> None:
    # DEBT-069(b): when live evidence is sufficient, the recommender output
    # wins — the seed must NOT override a real recommendation. rsi_universal
    # seeds to SCOUT, but keep-band evidence recommends KEEP.
    from src.dashboard.pages.strategies import build_strategy_tuning_rows

    strategies = {
        "rsi_universal": make_strategy(make_info(name="rsi_universal"))
    }
    tracker = _make_tracker_returning(
        {"rsi_universal": _keep_band_perf("rsi_universal")}
    )
    policy = StrategyTuningPolicy(enabled=True)

    rows = build_strategy_tuning_rows(strategies, policy, tracker)

    row = rows[0]
    assert row.recommended == "keep"  # live recommendation, not the scout seed


def test_tuning_rows_sub_account_id_override_wins() -> None:
    from src.dashboard.pages.strategies import build_strategy_tuning_rows

    strategies = {"rsi": make_strategy(make_info(name="rsi"))}
    tracker = _make_tracker_returning(
        {"rsi": _keep_band_perf("rsi")}, sub_account_id="tracker-default"
    )
    policy = StrategyTuningPolicy(enabled=True)

    rows = build_strategy_tuning_rows(
        strategies, policy, tracker, sub_account_id="explicit"
    )

    assert rows[0].sub_account_id == "explicit"


def test_tuning_yaml_diff_empty_when_recommended_equals_applied() -> None:
    from src.dashboard.pages.strategies import build_strategy_tuning_yaml_diff

    assert (
        build_strategy_tuning_yaml_diff(
            "lab", "rsi", StrategyAction.KEEP, StrategyAction.KEEP
        )
        == ""
    )


def test_tuning_yaml_diff_content() -> None:
    from src.dashboard.pages.strategies import build_strategy_tuning_yaml_diff

    diff = build_strategy_tuning_yaml_diff(
        "lab", "momentum_pinball_orb", StrategyAction.KEEP, StrategyAction.PAUSE
    )
    assert "lab: apply recommended action for 'momentum_pinball_orb'" in diff
    assert "(was: keep)" in diff
    assert "    momentum_pinball_orb:" in diff
    assert "      applied: pause" in diff


def test_tuning_dataframe_columns_and_empty() -> None:
    from src.dashboard.pages.strategies import (
        build_strategy_tuning_dataframe,
        build_strategy_tuning_rows,
    )

    empty = build_strategy_tuning_dataframe([])
    assert list(empty.columns) == [
        "Sub-account",
        "Strategy",
        "Applied",
        "Recommended",
        "Evidence",
    ]
    assert empty.empty

    strategies = {"rsi": make_strategy(make_info(name="rsi"))}
    tracker = _make_tracker_returning({"rsi": _keep_band_perf("rsi")})
    rows = build_strategy_tuning_rows(
        strategies, StrategyTuningPolicy(enabled=True), tracker
    )
    df = build_strategy_tuning_dataframe(rows)
    assert df.iloc[0]["Applied"] == "keep"
    assert df.iloc[0]["Recommended"] == "keep"
