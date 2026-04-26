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

from src.logger import get_logger
from src.strategy.base import BaseStrategy
from src.strategy.loader import DEFAULT_STRATEGIES_DIR, load_all_strategies
from src.strategy.performance import PerformanceRecord, PerformanceTracker

logger = get_logger("crypto_master.dashboard.strategies")


# =============================================================================
# Pure helpers (importable + testable without Streamlit runtime)
# =============================================================================


def build_summary_dataframe(
    strategies: dict[str, BaseStrategy],
    tracker: PerformanceTracker,
) -> pd.DataFrame:
    """One row per technique with aggregate performance.

    Args:
        strategies: ``{name: BaseStrategy}``, typically from
            ``load_all_strategies``.
        tracker: ``PerformanceTracker`` to query for each technique.

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


# =============================================================================
# Streamlit render
# =============================================================================


def render(
    strategies_dir: Path | None = None,
    tracker: PerformanceTracker | None = None,
) -> None:
    """Render the Analysis Techniques page.

    Args:
        strategies_dir: Override the strategies directory. Defaults to
            ``strategies/`` (loader's default).
        tracker: Override the performance source. Defaults to
            ``PerformanceTracker()`` (reads from ``data/performance/``).
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

    # ---- Summary table ----
    st.subheader("Summary")
    summary = build_summary_dataframe(strategies, perf_tracker)
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
    "build_summary_dataframe",
    "build_trend_dataframe",
    "render",
]
