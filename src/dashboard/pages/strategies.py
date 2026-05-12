"""Analysis technique status page (Phase 7.2).

Lists every registered analysis technique alongside its aggregate
performance, and lets the user pick one technique to see its
cumulative-P&L trend over time.

Data sources are kept thin and pluggable (constructor args take a
``PerformanceTracker`` and a strategies directory) so unit tests can
swap them in without touching disk paths the production app uses.

Related Requirements:
- FR-028: Chart Analysis Technique Status
- FR-005: Analysis Technique Performance Tracking (consumed)
- NFR-005: Analysis Technique Storage (consumed)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.backtest.multi_account_report import MultiAccountReport
from src.logger import get_logger
from src.proposal.fail_closed_metrics import FailClosedMetricsTracker
from src.strategy.base import BaseStrategy
from src.strategy.loader import DEFAULT_STRATEGIES_DIR, load_all_strategies
from src.strategy.performance import PerformanceRecord, PerformanceTracker

logger = get_logger("crypto_master.dashboard.strategies")
DEFAULT_COMBINATIONS_DIR = Path("data/backtest/combinations")


# =============================================================================
# Pure helpers (importable + testable without Streamlit runtime)
# =============================================================================


def build_summary_dataframe(
    strategies: dict[str, BaseStrategy],
    tracker: PerformanceTracker,
    fail_closed_tracker: FailClosedMetricsTracker | None = None,
    sub_account_id: str | None = None,
) -> pd.DataFrame:
    """One row per technique with aggregate performance.

    Args:
        strategies: ``{name: BaseStrategy}``, typically from
            ``load_all_strategies``.
        tracker: ``PerformanceTracker`` to query for each technique.
        fail_closed_tracker: Optional DEBT-061 emission / fail-closed
            tracker. When supplied, three additional columns are
            populated per row: ``Emitted``, ``Fail-Closed``, and
            ``Fail-Closed %``. Operators read the percentage to
            detect silent throughput collapse (a strategy that
            consistently emits then fail-closes at the R/R gate
            shows up as high % with non-zero Emitted). When omitted
            (e.g. legacy callers, fresh test fixtures), the columns
            still render with zeros so the column shape is stable
            across pages.
        sub_account_id: Which sub-account's fail-closed counters to
            query. Defaults to the ``PerformanceTracker``'s
            ``sub_account_id`` (canonical pattern — the perf tracker
            is the source of truth for "which sub-account is this
            page rendering"). Passing this explicitly is the way to
            render a per-sub-account view from a single shared
            ``FailClosedMetricsTracker`` instance (post-quant-fix
            shape: per-call sub-account, not constructor-bound).

    Returns:
        A DataFrame ordered by technique name. Numeric performance
        columns are returned as native floats / ints so the caller can
        format them however it likes (``st.dataframe`` formats by
        default; tests assert on raw values).
    """
    rows: list[dict[str, object]] = []
    for name in sorted(strategies):
        strategy = strategies[name]
        info = strategy.info
        perf = tracker.get_performance(strategy.name, strategy.version)
        # DEBT-061: fetch zero-snapshot when no tracker is wired in or
        # when the strategy has no recorded emissions, so the column
        # shape is stable whether the runtime persisted anything yet.
        if fail_closed_tracker is None:
            emitted = 0
            fail_closed = 0
            fail_closed_rate = 0.0
        else:
            # Canonical pattern: the performance tracker is
            # sub-account-scoped at construction, so its
            # ``sub_account_id`` is the source of truth for which
            # sub-account this page is rendering. The fail-closed
            # tracker is *not* sub-account-scoped at construction
            # (post-quant fix) so we pass the sub-account through per
            # call. Only resolved when the fail-closed tracker is
            # wired in — legacy callers that pass a MagicMock perf
            # tracker (which doesn't surface ``sub_account_id``)
            # never reach this branch.
            effective_sub_account = (
                sub_account_id
                if sub_account_id is not None
                else tracker.sub_account_id
            )
            counts = fail_closed_tracker.get(
                strategy.name,
                sub_account_id=effective_sub_account,
            )
            emitted = counts.proposals_emitted
            fail_closed = counts.proposals_fail_closed
            fail_closed_rate = counts.fail_closed_rate
        rows.append(
            {
                "Technique": info.name,
                "Version": info.version,
                "Type": info.technique_type,
                "Symbols": ", ".join(info.symbols) if info.symbols else "—",
                "Total Trades": perf.total_trades,
                "Wins": perf.wins,
                "Losses": perf.losses,
                "Win Rate %": round(perf.win_rate * 100, 2),
                "Avg P&L %": round(perf.avg_pnl_percent, 2),
                "Total P&L %": round(perf.total_pnl_percent, 2),
                "Best Trade %": round(perf.best_trade_pnl, 2),
                "Worst Trade %": round(perf.worst_trade_pnl, 2),
                "Emitted": emitted,
                "Fail-Closed": fail_closed,
                "Fail-Closed %": round(fail_closed_rate * 100, 2),
            }
        )
    return pd.DataFrame(rows)


def build_trend_dataframe(
    records: list[PerformanceRecord],
) -> pd.DataFrame:
    """Time-ordered cumulative-P&L series for a single technique.

    Pending records (no exit yet) and records missing a P&L are
    skipped — they would either show as 0 (misleading) or break the
    cumsum. Returns an empty DataFrame if nothing qualifies; the
    caller is expected to render a "no data" message in that case.

    Args:
        records: Raw ``PerformanceRecord`` list, typically from
            ``PerformanceTracker.load_records``.

    Returns:
        DataFrame with columns ``timestamp``, ``pnl_percent``,
        ``cumulative_pnl``, sorted ascending by timestamp.
    """
    rows: list[dict[str, object]] = []
    for r in records:
        pnl = r.pnl_percent if r.pnl_percent is not None else r.calculate_pnl()
        if pnl is None:
            continue
        timestamp = r.exit_timestamp or r.analysis_timestamp
        rows.append({"timestamp": timestamp, "pnl_percent": pnl})

    if not rows:
        return pd.DataFrame(columns=["timestamp", "pnl_percent", "cumulative_pnl"])

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df["cumulative_pnl"] = df["pnl_percent"].cumsum()
    return df


def latest_combinations_run(
    combinations_dir: Path = DEFAULT_COMBINATIONS_DIR,
) -> Path | None:
    """Return the newest combination report directory, if any."""
    if not combinations_dir.exists():
        return None
    candidates = [p for p in combinations_dir.iterdir() if (p / "report.json").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_combinations_report(run_dir: Path) -> MultiAccountReport:
    """Load a saved Phase 19.5 combination report."""
    return MultiAccountReport.model_validate_json(
        (run_dir / "report.json").read_text(encoding="utf-8")
    )


def build_combinations_equity_dataframe(report: MultiAccountReport) -> pd.DataFrame:
    """Build a side-by-side equity curve table from a combination report."""
    rows: list[dict[str, object]] = []
    for sub_account_id, points in report.equity_curves.items():
        for timestamp, equity in points:
            rows.append(
                {
                    "timestamp": timestamp,
                    "sub_account_id": sub_account_id,
                    "equity": float(equity),
                }
            )
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    return frame.pivot(
        index="timestamp",
        columns="sub_account_id",
        values="equity",
    ).sort_index()


# =============================================================================
# Streamlit render
# =============================================================================


def render(
    strategies_dir: Path | None = None,
    tracker: PerformanceTracker | None = None,
    fail_closed_tracker: FailClosedMetricsTracker | None = None,
) -> None:
    """Render the Analysis Techniques page.

    Args:
        strategies_dir: Override the strategies directory. Defaults to
            ``strategies/`` (loader's default).
        tracker: Override the performance source. Defaults to
            ``PerformanceTracker()`` (reads from ``data/performance/``).
        fail_closed_tracker: Override the DEBT-061 emission /
            fail-closed source. Defaults to
            ``FailClosedMetricsTracker()`` so the dashboard shows the
            same cumulative counts the runtime engine writes.
    """
    st.title("📊 Analysis Techniques")
    st.caption("Registered techniques and their performance over time.")

    directory = strategies_dir or DEFAULT_STRATEGIES_DIR
    strategies = load_all_strategies(directory)

    if not strategies:
        st.warning(
            f"No analysis techniques found in `{directory}`. "
            "Add a `.md` or `.py` file to that directory to register a technique."
        )
        return

    perf_tracker = tracker or PerformanceTracker()
    fc_tracker = fail_closed_tracker or FailClosedMetricsTracker()

    latest_combo = latest_combinations_run()
    if latest_combo is not None:
        st.info(f"Latest combination backtest: `{latest_combo / 'report.json'}`")
        combo_report = load_combinations_report(latest_combo)
        combo_equity = build_combinations_equity_dataframe(combo_report)
        if not combo_equity.empty:
            st.line_chart(combo_equity, use_container_width=True)

    # ---- Summary table ----
    st.subheader("Summary")
    summary = build_summary_dataframe(strategies, perf_tracker, fc_tracker)
    st.dataframe(summary, hide_index=True, use_container_width=True)

    # ---- Per-technique trend ----
    st.subheader("Performance Trend")
    options = sorted(strategies.keys())
    selected = st.selectbox(
        "Technique",
        options=options,
        format_func=lambda key: (
            f"{strategies[key].info.name} v{strategies[key].info.version}"
        ),
    )

    if not selected:
        return

    strategy = strategies[selected]
    records = perf_tracker.load_records(strategy.name, strategy.version)
    trend = build_trend_dataframe(records)

    if trend.empty:
        st.info(
            "No completed trades yet. The trend chart will populate "
            "once this technique accumulates closed records."
        )
        return

    st.line_chart(
        trend.set_index("timestamp")[["cumulative_pnl"]],
        use_container_width=True,
    )
    latest = trend["cumulative_pnl"].iloc[-1]
    st.caption(f"{len(trend)} closed records | latest cumulative P&L: {latest:.2f}%")


__all__ = [
    "build_combinations_equity_dataframe",
    "build_summary_dataframe",
    "build_trend_dataframe",
    "latest_combinations_run",
    "load_combinations_report",
    "render",
]
