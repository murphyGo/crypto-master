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
from pydantic import BaseModel

from src.backtest.multi_account_report import MultiAccountReport
from src.logger import get_logger
from src.proposal.fail_closed_metrics import FailClosedMetricsTracker
from src.strategy.base import BaseStrategy
from src.strategy.loader import DEFAULT_STRATEGIES_DIR, load_all_strategies
from src.strategy.performance import PerformanceRecord, PerformanceTracker
from src.strategy.tuning import StrategyAction, StrategyTuningPolicy
from src.strategy.tuning_recommender import (
    RecommenderEvidence,
    evidence_from_performance,
    recommend_action,
    seed_action_for,
)

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
        # Q2 follow-up: synthetic / reconciliation-close records carry a
        # 0% P&L by construction and would flatten the cumulative trend
        # without representing a real trade outcome — skip them.
        if r.synthetic:
            continue
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
# strategy-tuning Slice 2 (a): Applied / Recommended view + YAML clipboard diff
# (DEBT-069(a)). Render-only — the write path is explicitly out of scope per the
# resolved Open Decision. The operator copies the YAML diff and applies it by
# hand + restart. Pure builders below stay Streamlit-free so they are unit-
# testable; the thin ``render_strategy_tuning`` wraps them with ``st.*`` calls.
# =============================================================================


class StrategyTuningRow(BaseModel):
    """One per-``(sub-account, strategy)`` row for the tuning view.

    Attributes:
        sub_account_id: Which sub-account this row belongs to.
        strategy: Technique name (the key into
            ``StrategyTuningPolicy.applied_action_for`` / overrides).
        applied: The currently-applied action (config state), e.g.
            ``"keep"`` / ``"scout"`` / ``"pause"``.
        recommended: The recommendation rendered as a string. This is the
            live ``recommend_action`` output, or — when the recommender
            returns ``None`` (evidence too thin) — the per-strategy seed
            (``seed_action_for``) so the operator always sees a starting
            recommendation (DEBT-069(b)).
        evidence_summary: Human-readable one-line evidence digest
            (closed trades, profit factor, win rate, closed PnL,
            fail-closed rate) so the operator can sanity-check the
            recommendation without re-running anything.
        differs: ``True`` when the recommendation is present AND differs
            from the applied action — the only rows for which a YAML
            diff is worth copying.
        yaml_diff: The clipboard-ready YAML override snippet the operator
            pastes into the sub-account config to apply the
            recommendation. Empty string when there is nothing to apply
            (no recommendation, or recommendation already applied).
    """

    sub_account_id: str
    strategy: str
    applied: str
    recommended: str
    evidence_summary: str
    differs: bool
    yaml_diff: str


def _format_evidence_summary(evidence: RecommenderEvidence) -> str:
    """One-line digest of the evidence the recommender consumed."""
    pf = (
        f"{evidence.profit_factor:.2f}"
        if evidence.profit_factor is not None
        else "n/a"
    )
    return (
        f"closed={evidence.closed_trades}, "
        f"PF={pf}, "
        f"win={evidence.win_rate * 100:.0f}%, "
        f"closed_pnl={evidence.closed_pnl_pct:.1f}%, "
        f"fail_closed={evidence.fail_closed_rate * 100:.0f}%"
    )


def build_strategy_tuning_yaml_diff(
    sub_account_id: str,
    strategy: str,
    applied: StrategyAction,
    recommended: StrategyAction,
) -> str:
    """Clipboard-ready YAML override snippet for one recommendation.

    Render-only operator-apply helper (DEBT-069(a)): the operator copies
    this snippet into the sub-account's ``strategy_tuning`` block (the
    ``strategy_overrides[<strategy>].applied`` key) and restarts. No
    write-back widget exists by design.

    Returns an empty string when ``recommended == applied`` (nothing to
    apply).
    """
    if recommended == applied:
        return ""
    return (
        f"# {sub_account_id}: apply recommended action for {strategy!r}\n"
        f"# (was: {applied.value})\n"
        "strategy_tuning:\n"
        "  strategy_overrides:\n"
        f"    {strategy}:\n"
        f"      applied: {recommended.value}\n"
    )


def build_strategy_tuning_rows(
    strategies: dict[str, BaseStrategy],
    policy: StrategyTuningPolicy,
    tracker: PerformanceTracker,
    fail_closed_tracker: FailClosedMetricsTracker | None = None,
    sub_account_id: str | None = None,
) -> list[StrategyTuningRow]:
    """Build the Applied / Recommended rows for one sub-account.

    Pure (no Streamlit, no new disk writes). For each strategy:

    * ``Applied`` is ``policy.applied_action_for(name)`` (config state).
    * ``Recommended`` is ``recommend_action(evidence, thresholds)`` where
      ``thresholds`` are the per-strategy thresholds
      (``policy.thresholds_for(name)``). When the recommender returns
      ``None`` (evidence too thin), the row falls back to the per-strategy
      seed via ``seed_action_for(name)`` (DEBT-069(b)) so every strategy
      gets a starting recommendation on day one. The seed is treated as a
      real recommendation — it can ``differ`` from the applied state and
      produce a YAML diff — but it never changes Applied and never gates
      trades.

    Args:
        strategies: ``{name: BaseStrategy}``, typically from
            ``load_all_strategies``.
        policy: The sub-account's :class:`StrategyTuningPolicy`.
        tracker: Performance source queried per strategy.
        fail_closed_tracker: Optional DEBT-061 fail-closed source. When
            omitted the fail-closed rate is ``0.0`` (the recommender's
            documented "never emitted" value).
        sub_account_id: Sub-account label for the rows + YAML diff.
            Defaults to the tracker's ``sub_account_id``.
    """
    effective_sub_account = (
        sub_account_id if sub_account_id is not None else tracker.sub_account_id
    )
    rows: list[StrategyTuningRow] = []
    for name in sorted(strategies):
        strategy = strategies[name]
        perf = tracker.get_performance(strategy.name, strategy.version)
        if fail_closed_tracker is None:
            fail_closed_rate = 0.0
        else:
            counts = fail_closed_tracker.get(
                strategy.name,
                sub_account_id=effective_sub_account,
            )
            fail_closed_rate = counts.fail_closed_rate

        evidence = evidence_from_performance(
            perf, fail_closed_rate=fail_closed_rate
        )
        applied = policy.applied_action_for(strategy.name)
        # DEBT-069(b): the live recommender is authoritative; the per-strategy
        # seed is only a fallback when evidence is too thin to recommend
        # (``recommend_action`` returns ``None``). The seed CAN differ from
        # the applied state (e.g. a seeded ``pause`` vs an applied ``keep``),
        # in which case the diff + YAML snippet are surfaced exactly as for a
        # live recommendation. With the catch-all seed, every strategy now
        # gets a non-``None`` recommendation, so there is no insufficient-
        # evidence path left for this builder.
        recommended = recommend_action(
            evidence, policy.thresholds_for(strategy.name)
        ) or seed_action_for(strategy.name)
        differs = recommended != applied
        yaml_diff = build_strategy_tuning_yaml_diff(
            effective_sub_account, strategy.name, applied, recommended
        )

        rows.append(
            StrategyTuningRow(
                sub_account_id=effective_sub_account,
                strategy=strategy.name,
                applied=applied.value,
                recommended=recommended.value,
                evidence_summary=_format_evidence_summary(evidence),
                differs=differs,
                yaml_diff=yaml_diff,
            )
        )
    return rows


def build_strategy_tuning_dataframe(rows: list[StrategyTuningRow]) -> pd.DataFrame:
    """Tabular view of the tuning rows (Applied / Recommended / Evidence)."""
    columns = [
        "Sub-account",
        "Strategy",
        "Applied",
        "Recommended",
        "Evidence",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Sub-account": r.sub_account_id,
                "Strategy": r.strategy,
                "Applied": r.applied,
                "Recommended": r.recommended,
                "Evidence": r.evidence_summary,
            }
            for r in rows
        ],
        columns=columns,
    )


def render_strategy_tuning(
    strategies: dict[str, BaseStrategy],
    policy: StrategyTuningPolicy,
    tracker: PerformanceTracker,
    fail_closed_tracker: FailClosedMetricsTracker | None = None,
    sub_account_id: str | None = None,
) -> None:
    """Render the strategy-tuning Applied / Recommended section (thin).

    Render-only (DEBT-069(a)): shows the per-strategy applied vs
    recommended actions, the evidence digest, and — for the strategies
    whose recommendation differs from what's applied — a copyable YAML
    override the operator pastes into the sub-account config and applies
    by hand + restart. There is no write-back widget by design.
    """
    st.subheader("Strategy Tuning")
    if not policy.enabled:
        st.info(
            "Strategy-tuning is disabled for this sub-account "
            "(`strategy_tuning.enabled: false`). The Recommended column "
            "still computes from evidence, but nothing is enforced."
        )

    rows = build_strategy_tuning_rows(
        strategies,
        policy,
        tracker,
        fail_closed_tracker=fail_closed_tracker,
        sub_account_id=sub_account_id,
    )
    table = build_strategy_tuning_dataframe(rows)
    if table.empty:
        st.info("No strategies to evaluate.")
        return

    st.dataframe(table, hide_index=True, use_container_width=True)

    diffs = [r for r in rows if r.differs and r.yaml_diff]
    if not diffs:
        st.caption(
            "No pending changes — every applied action matches the "
            "recommendation."
        )
        return

    st.caption(
        "Recommended changes (render-only). Copy a YAML diff into the "
        "sub-account config and restart to apply — there is no write-back "
        "from this page."
    )
    for row in diffs:
        with st.expander(
            f"{row.strategy}: {row.applied} → {row.recommended}", expanded=False
        ):
            st.code(row.yaml_diff, language="yaml")


# =============================================================================
# Streamlit render
# =============================================================================


def render(
    strategies_dir: Path | None = None,
    tracker: PerformanceTracker | None = None,
    fail_closed_tracker: FailClosedMetricsTracker | None = None,
    tuning_policy: StrategyTuningPolicy | None = None,
    tuning_sub_account_id: str | None = None,
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
        tuning_policy: Optional :class:`StrategyTuningPolicy` to render
            the DEBT-069(a) Applied / Recommended section against. When
            ``None`` a default (``enabled=False``) policy is used so the
            Recommended column still computes from evidence without
            requiring a registry to be wired into the page.
        tuning_sub_account_id: Sub-account label for the tuning section.
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

    # ---- Strategy tuning Applied / Recommended (DEBT-069(a)) ----
    render_strategy_tuning(
        strategies,
        tuning_policy or StrategyTuningPolicy(),
        perf_tracker,
        fail_closed_tracker=fc_tracker,
        sub_account_id=tuning_sub_account_id,
    )

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
    "StrategyTuningRow",
    "build_combinations_equity_dataframe",
    "build_strategy_tuning_dataframe",
    "build_strategy_tuning_rows",
    "build_strategy_tuning_yaml_diff",
    "build_summary_dataframe",
    "build_trend_dataframe",
    "latest_combinations_run",
    "load_combinations_report",
    "render",
    "render_strategy_tuning",
]
