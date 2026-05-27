"""Proposal funnel dashboard page (proposal-funnel-audit unit).

Reads :class:`ProposalRecord` files via
:class:`src.proposal.interaction.ProposalHistory` and the activity log
via :class:`src.runtime.activity_log.ActivityLog`, projects them into
the funnel-conversion taxonomy from
``aidlc-docs/construction/proposal-funnel-audit/functional-design/spec.md``
§1, and renders the four operator views from spec §4:

1. **Funnel-conversion table** — count at each terminal state plus
   adjacent-state conversion ratios.
2. **Per-gate rejection volume** — bar chart + a clickable sample
   diagnostic for the most-recent rejection in each gate.
3. **Per-strategy heatmap** — strategies × funnel states; colour
   scales by ratio against the strategy's ``generated`` count.
4. **Per-strategy drill-through** — rejection-cause breakdown for the
   selected strategy.

The command-center single-line summary is consumed by
``src/dashboard/app.py``'s ``render_home`` via
:func:`build_command_center_summary`.

Pure helpers live above the Streamlit ``render`` so tests can import
them without spinning the Streamlit runtime.

Related Requirements:
- FR-013 / FR-014 / FR-029 / FR-043: proposal lifecycle visibility.
- NFR-007 / NFR-012: persistence + live trading observability.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.logger import get_logger
from src.proposal.funnel import (
    FunnelCounts,
    FunnelWindow,
    compute_funnel_counts,
    compute_funnel_counts_by_strategy,
    compute_funnel_counts_by_sub_account,
)
from src.proposal.interaction import ProposalHistory
from src.runtime.activity_log import (
    ActivityEvent,
    ActivityEventType,
    ActivityLog,
)
from src.runtime.gate_reason import GateReason
from src.utils.time import now_utc

logger = get_logger("crypto_master.dashboard.proposals")


# Canonical funnel-state ordering for table columns. The order matches
# the spec §4 "Funnel-conversion table" column list so the dashboard
# reads top-to-bottom like the funnel itself.
FUNNEL_COLUMN_ORDER: tuple[str, ...] = (
    "generated",
    "score_accepted",
    "score_rejected",
    "gate_rejected_market_regime",
    "gate_rejected_correlation",
    "gate_rejected_trend_filter",
    "gate_rejected_sibling_family",
    "gate_rejected_runtime_safety_pause",
    "gate_rejected_total_cap",
    "gate_rejected_symbol_cap",
    "gate_rejected_stale_quote",
    "gate_rejected_unknown",
    "proposal_opened",
    "trade_opened",
    "outcome_linked",
    "open_errored",
)

# The post-acceptance gate states the bar chart + heatmap surface as a
# group. Score-rejection is shown separately (it's the dominant
# single failure mode but happens *before* the gate chain).
GATE_REJECTION_COLUMNS: tuple[str, ...] = (
    "gate_rejected_market_regime",
    "gate_rejected_correlation",
    "gate_rejected_trend_filter",
    "gate_rejected_sibling_family",
    "gate_rejected_runtime_safety_pause",
    "gate_rejected_total_cap",
    "gate_rejected_symbol_cap",
    "gate_rejected_stale_quote",
    "gate_rejected_unknown",
)

# ``gate_reason`` discriminator values matched against the activity
# event ``details.gate_reason`` field (or legacy ``details.reason``)
# when bucketing per-gate sample events. Order matches
# ``GATE_REJECTION_COLUMNS`` so the bar chart and sample lookup agree.
GATE_REASON_BY_STATE: dict[str, tuple[str, ...]] = {
    "gate_rejected_market_regime": (GateReason.MARKET_REGIME_BLOCKED.value,),
    "gate_rejected_correlation": (GateReason.CORRELATION_BLOCKED.value,),
    "gate_rejected_trend_filter": (GateReason.TREND_FILTER_BLOCKED.value,),
    "gate_rejected_sibling_family": (GateReason.SIBLING_FAMILY_DEDUP.value,),
    "gate_rejected_runtime_safety_pause": (GateReason.RUNTIME_SAFETY_PAUSED.value,),
    "gate_rejected_total_cap": (GateReason.TOTAL_CAP.value,),
    "gate_rejected_symbol_cap": (GateReason.SYMBOL_CAP.value,),
    "gate_rejected_stale_quote": (GateReason.STALE_QUOTE_NO_LIVE_DATA.value,),
}


# =============================================================================
# Pure helpers (importable + testable without Streamlit runtime)
# =============================================================================


def window_for_label(
    label: str,
    *,
    now: datetime | None = None,
) -> FunnelWindow:
    """Translate the dashboard's window selector into a :class:`FunnelWindow`.

    ``label`` is one of ``"24h"``, ``"7d"``, ``"30d"``, ``"lifetime"``.
    ``lifetime`` returns an unbounded window.
    """
    if label == "lifetime":
        return FunnelWindow()
    if now is None:
        now = now_utc()
    if label == "24h":
        return FunnelWindow(start=now - timedelta(hours=24), end=now)
    if label == "7d":
        return FunnelWindow(start=now - timedelta(days=7), end=now)
    if label == "30d":
        return FunnelWindow(start=now - timedelta(days=30), end=now)
    return FunnelWindow()


def build_funnel_table(counts: FunnelCounts) -> pd.DataFrame:
    """Render :class:`FunnelCounts` as a single-row DataFrame.

    Columns are in :data:`FUNNEL_COLUMN_ORDER` so the operator reads
    the table top-to-bottom matching the funnel flow.
    """
    row = {col: getattr(counts, col, 0) for col in FUNNEL_COLUMN_ORDER}
    return pd.DataFrame([row])


def build_conversion_summary(counts: FunnelCounts) -> dict[str, float]:
    """Compute adjacent-state conversion ratios.

    Returns a flat ``{"label": ratio}`` mapping; ratios are in [0, 1]
    or ``0.0`` when the denominator is zero. The four ratios mirror
    the 2026-05-13 snapshot's 2,624 -> 773 -> 118 -> 100 funnel:

    * ``generated_to_score_accepted`` — how many proposals cleared
      the score gate.
    * ``score_accepted_to_proposal_opened`` — how many score-accepted
      proposals survived the post-acceptance gate chain.
    * ``proposal_opened_to_trade_opened`` — how many opens reached a
      confirmed fill (the ``POSITION_OPEN_ERRORED`` denominator).
    * ``generated_to_trade_opened`` — end-to-end conversion.
    """

    def safe(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return float(numerator) / float(denominator)

    generated_total = counts.generated + counts.score_accepted + counts.score_rejected
    # Every gate rejection is by definition score-accepted-then-blocked,
    # so the score-accepted denominator includes them.
    score_accepted_total = (
        counts.score_accepted
        + counts.gate_rejected_total
        + counts.proposal_opened
        + counts.trade_opened
        + counts.outcome_linked
        + counts.open_errored
    )
    proposal_opened_total = (
        counts.proposal_opened
        + counts.trade_opened
        + counts.outcome_linked
        + counts.open_errored
    )
    trade_opened_total = (
        counts.trade_opened + counts.outcome_linked + counts.open_errored
    )

    return {
        "generated_to_score_accepted": safe(
            score_accepted_total, generated_total + score_accepted_total
        ),
        "score_accepted_to_proposal_opened": safe(
            proposal_opened_total, score_accepted_total
        ),
        "proposal_opened_to_trade_opened": safe(
            trade_opened_total, proposal_opened_total
        ),
        "generated_to_trade_opened": safe(
            trade_opened_total, generated_total + score_accepted_total
        ),
    }


def build_per_strategy_heatmap(
    by_strategy: dict[str, FunnelCounts],
) -> pd.DataFrame:
    """Rows = strategies; columns = funnel states.

    Empty input returns an empty DataFrame with the canonical column
    order so the dashboard can render a "no data" message without
    branching on shape.
    """
    if not by_strategy:
        return pd.DataFrame(columns=list(FUNNEL_COLUMN_ORDER))
    rows = []
    for technique, counts in sorted(by_strategy.items()):
        row: dict[str, object] = {"Technique": technique}
        for col in FUNNEL_COLUMN_ORDER:
            row[col] = getattr(counts, col, 0)
        rows.append(row)
    return pd.DataFrame(rows)


def build_per_gate_volume(counts: FunnelCounts) -> pd.DataFrame:
    """One row per gate-rejection bucket with the bar-chart count.

    The dashboard renders this as a horizontal bar chart so the
    operator immediately sees which gate is consuming the most volume.
    """
    rows = [
        {"gate": col, "count": getattr(counts, col, 0)}
        for col in GATE_REJECTION_COLUMNS
    ]
    return pd.DataFrame(rows)


def latest_sample_event_for_gate(
    events: Iterable[ActivityEvent],
    state: str,
) -> ActivityEvent | None:
    """Return the most-recent activity event that drove ``state``.

    Matches on the spec's canonical ``gate_reason`` discriminator
    first, falling back to ``details.reason`` for legacy events that
    pre-date the gate_reason field. Returns ``None`` when no event
    matches — the dashboard renders "no recent sample" in that case.
    """
    reasons = GATE_REASON_BY_STATE.get(state, ())
    if not reasons:
        return None

    matches = []
    for event in events:
        details = event.details
        gate_reason = details.get("gate_reason")
        reason = details.get("reason")
        if gate_reason is not None and gate_reason in reasons:
            matches.append(event)
            continue
        # Legacy fallback — match prefix on the reason string. The
        # market-regime gate emits ``market_regime_blocked_<regime>``
        # so a prefix match keeps the bucket populated for events
        # written before the gate_reason field landed.
        if isinstance(reason, str):
            if any(reason == r or reason.startswith(f"{r}_") for r in reasons):
                matches.append(event)
    if not matches:
        return None
    return max(matches, key=lambda event: event.timestamp)


def build_command_center_summary(counts: FunnelCounts) -> str:
    """Single-line funnel summary for the dashboard home view.

    Format: ``"X generated -> Y accepted -> Z opened (W% conversion)"``
    where the percent is ``trade_opened / (generated + score_*)`` —
    the end-to-end conversion the 2026-05-13 review wants on the home
    page.
    """
    generated_total = counts.generated + counts.score_accepted + counts.score_rejected
    score_accepted_total = (
        counts.score_accepted
        + counts.gate_rejected_total
        + counts.proposal_opened
        + counts.trade_opened
        + counts.outcome_linked
        + counts.open_errored
    )
    opened_total = (
        counts.trade_opened + counts.outcome_linked + counts.open_errored
    )
    grand_total = generated_total + score_accepted_total
    if grand_total <= 0:
        ratio = 0.0
    else:
        ratio = float(opened_total) / float(grand_total) * 100.0
    return (
        f"{grand_total} generated -> {score_accepted_total} accepted -> "
        f"{opened_total} opened ({ratio:.1f}% conversion)"
    )


# =============================================================================
# Streamlit render
# =============================================================================


def render(
    history: ProposalHistory | None = None,
    activity_log: ActivityLog | None = None,
) -> None:
    """Render the Proposal Funnel page.

    Args:
        history: Override the proposal history source. Defaults to a
            fresh :class:`ProposalHistory` that reads from the
            configured data dir.
        activity_log: Override the activity-event source. Defaults to
            :class:`ActivityLog`. Used to surface the per-gate sample
            event diagnostic.
    """
    st.title("Proposal Funnel")
    st.caption(
        "End-to-end proposal lifecycle: generated -> scored -> "
        "(gates) -> opened -> outcome."
    )

    history = history or ProposalHistory()
    activity_log = activity_log or ActivityLog()

    records = history.list_all()
    events = activity_log.read_all()

    if not records:
        st.info(
            "No proposal records on disk yet. The funnel will populate "
            "once the engine emits proposals."
        )
        return

    # ---- Time-window selector ----
    window_label = st.radio(
        "Window",
        options=("24h", "7d", "30d", "lifetime"),
        index=3,
        horizontal=True,
    )
    window = window_for_label(str(window_label))

    counts = compute_funnel_counts(records, window=window)

    # ---- Funnel-conversion table ----
    st.subheader("Funnel conversion")
    table = build_funnel_table(counts)
    st.dataframe(table, hide_index=True, use_container_width=True)

    conv = build_conversion_summary(counts)
    cols = st.columns(4)
    cols[0].metric(
        "Generated -> score-accepted",
        f"{conv['generated_to_score_accepted'] * 100:.1f}%",
    )
    cols[1].metric(
        "Score-accepted -> opened",
        f"{conv['score_accepted_to_proposal_opened'] * 100:.1f}%",
    )
    cols[2].metric(
        "Opened -> filled",
        f"{conv['proposal_opened_to_trade_opened'] * 100:.1f}%",
    )
    cols[3].metric(
        "End-to-end",
        f"{conv['generated_to_trade_opened'] * 100:.1f}%",
    )

    # ---- Per-gate volume + sample ----
    st.subheader("Per-gate rejection volume")
    volume = build_per_gate_volume(counts)
    if volume["count"].sum() == 0:
        st.info("No post-acceptance gate rejections in this window.")
    else:
        st.bar_chart(
            volume.set_index("gate")["count"],
            use_container_width=True,
        )
        sample_gate = st.selectbox(
            "Sample rejection (most recent)",
            options=GATE_REJECTION_COLUMNS,
        )
        sample = latest_sample_event_for_gate(events, str(sample_gate))
        if sample is None:
            st.caption("No recent sample event for this gate.")
        else:
            st.json(sample.details)

    # ---- Per-strategy heatmap ----
    st.subheader("Per-strategy funnel")
    by_strategy = compute_funnel_counts_by_strategy(records, window=window)
    heatmap = build_per_strategy_heatmap(by_strategy)
    if heatmap.empty:
        st.info("No per-strategy data in this window.")
    else:
        st.dataframe(heatmap, hide_index=True, use_container_width=True)

    # ---- Drill-through ----
    st.subheader("Drill-through")
    techniques = sorted(by_strategy.keys())
    if techniques:
        selected = st.selectbox("Strategy", options=techniques)
        selected_counts = by_strategy[str(selected)]
        breakdown_rows = [
            {"state": col, "count": getattr(selected_counts, col, 0)}
            for col in FUNNEL_COLUMN_ORDER
            if getattr(selected_counts, col, 0) > 0
        ]
        if not breakdown_rows:
            st.caption("No proposals matched this strategy in the window.")
        else:
            st.dataframe(
                pd.DataFrame(breakdown_rows),
                hide_index=True,
                use_container_width=True,
            )

    # ---- Per-account summary ----
    st.subheader("Per-sub-account summary")
    by_sub = compute_funnel_counts_by_sub_account(records, window=window)
    for sub_id, sub_counts in sorted(by_sub.items()):
        st.caption(f"{sub_id}: {build_command_center_summary(sub_counts)}")


def load_funnel_summary(
    history: ProposalHistory | None = None,
    *,
    window_label: str = "24h",
    now: datetime | None = None,
) -> FunnelCounts:
    """Convenience used by the home command-center single-line summary.

    The home view doesn't need the full funnel page render; it only
    wants a :class:`FunnelCounts` snapshot it can pass to
    :func:`build_command_center_summary`.
    """
    history = history or ProposalHistory()
    records = history.list_all()
    window = window_for_label(window_label, now=now)
    return compute_funnel_counts(records, window=window)


__all__ = [
    "FUNNEL_COLUMN_ORDER",
    "GATE_REJECTION_COLUMNS",
    "build_command_center_summary",
    "build_conversion_summary",
    "build_funnel_table",
    "build_per_gate_volume",
    "build_per_strategy_heatmap",
    "latest_sample_event_for_gate",
    "load_funnel_summary",
    "render",
    "window_for_label",
]


# Re-export so type-checkers + IDE see the public surface; ``ActivityEventType``
# is imported above for future filtering hooks.
_ = ActivityEventType
