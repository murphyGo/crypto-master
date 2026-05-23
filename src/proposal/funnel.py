"""Proposal funnel aggregator (proposal-funnel-audit unit).

Pure / derived-on-read aggregation over :class:`ProposalRecord`
instances. The funnel taxonomy is owned by
``aidlc-docs/construction/proposal-funnel-audit/functional-design/spec.md``;
this module is the read-side projection that turns a list of records
into per-state counts the dashboard can render.

Per the resolved open decisions (2026-05-13):

* **Derived-on-read** — counters are not persisted. The proposal
  record store is small enough (thousands of files, not millions) that
  scanning is cheap, and a derived view avoids a second persistence
  contract that can drift from the records.
* **Forward-only with ``gate_rejected_unknown`` fallback** for legacy
  rows. Records whose ``final_state`` still equals the model default
  (``generated``) *and* whose ``decision`` is non-PENDING (i.e. the
  record has been through the score gate but pre-dates this field) get
  bucketed into ``gate_rejected_unknown``. We do *not* infer the
  original terminal gate by walking ``decision`` / ``trade_id``.

Related Requirements:
- FR-011 / FR-012 / FR-013 / FR-014 / FR-015 / FR-029 / FR-043:
  proposal lifecycle visibility.
- NFR-007 / NFR-012: persistence + live trading observability.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from src.proposal.interaction import (
    ProposalDecision,
    ProposalFinalState,
    ProposalRecord,
)
from src.utils.time import ensure_utc


@dataclass(frozen=True)
class FunnelWindow:
    """Optional time window for :func:`compute_funnel_counts`.

    Inclusive on both ends. ``start`` / ``end`` may each be ``None`` to
    leave that side unbounded. Comparison is against the record's
    ``decision_at`` when set, falling back to ``proposal.created_at``
    so records that never reached a terminal state still participate
    in the window.
    """

    start: datetime | None = None
    end: datetime | None = None


class FunnelCounts(BaseModel):
    """Per-state count snapshot.

    One field per :class:`ProposalFinalState` value; all counts are
    non-negative integers. ``total`` is the sum across every state so
    callers can render conversion ratios without re-walking the input.

    The shape matches the dashboard's funnel-conversion table (spec
    §4 "Funnel-conversion table") — operators read the columns in the
    canonical funnel order.
    """

    generated: int = 0
    scored: int = 0
    score_accepted: int = 0
    score_rejected: int = 0
    gate_rejected_market_regime: int = 0
    gate_rejected_correlation: int = 0
    gate_rejected_trend_filter: int = 0
    gate_rejected_sibling_family: int = 0
    gate_rejected_runtime_safety_pause: int = 0
    gate_rejected_total_cap: int = 0
    gate_rejected_symbol_cap: int = 0
    gate_rejected_stale_quote: int = 0
    # cross-account-risk-policy (2026-05-13): new buckets for the
    # per-account aggregate cap, stale-position block, and risk-sizing
    # rejections. ``gate_rejected_unknown`` remains the legacy
    # fallback for pre-cutover rows.
    gate_rejected_account_aggregate_cap: int = 0
    gate_rejected_stale_position_block: int = 0
    gate_rejected_risk_sizing: int = 0
    # cross-account-risk-policy DEBT-068(b): opt-in global symbol/side
    # cap bucket. Only live-mode hard-blocks land here; paper mode is
    # advisory-only and leaves the record in ``proposal_opened``.
    gate_rejected_global_cap: int = 0
    # cross-account-risk-policy DEBT-068(c-1): stateless kill-switch
    # buckets. Per-account open-drawdown / open-stop-risk and the
    # cross-account portfolio drawdown. Only live-mode hard-blocks land
    # here; paper mode is advisory-only.
    gate_rejected_open_drawdown_kill_switch: int = 0
    gate_rejected_open_stop_risk_kill_switch: int = 0
    gate_rejected_portfolio_kill_switch: int = 0
    # strategy-tuning (2026-05-13): action-driven terminals. Pause
    # rides on a dedicated ``gate_rejected_*`` bucket; shadow is a
    # *non-rejection* terminal that records the proposal without
    # opening, so the dashboard separates "blocked" from "measured-
    # only".
    gate_rejected_strategy_action_pause: int = 0
    shadow_recorded: int = 0
    gate_rejected_unknown: int = 0
    proposal_opened: int = 0
    trade_opened: int = 0
    outcome_linked: int = 0
    open_errored: int = 0
    total: int = 0

    @property
    def gate_rejected_total(self) -> int:
        """Sum of every ``gate_rejected_*`` bucket (post-acceptance rejections)."""
        return (
            self.gate_rejected_market_regime
            + self.gate_rejected_correlation
            + self.gate_rejected_trend_filter
            + self.gate_rejected_sibling_family
            + self.gate_rejected_runtime_safety_pause
            + self.gate_rejected_total_cap
            + self.gate_rejected_symbol_cap
            + self.gate_rejected_stale_quote
            + self.gate_rejected_account_aggregate_cap
            + self.gate_rejected_stale_position_block
            + self.gate_rejected_risk_sizing
            + self.gate_rejected_global_cap
            + self.gate_rejected_open_drawdown_kill_switch
            + self.gate_rejected_open_stop_risk_kill_switch
            + self.gate_rejected_portfolio_kill_switch
            + self.gate_rejected_strategy_action_pause
            + self.gate_rejected_unknown
        )

    @property
    def score_accepted_total(self) -> int:
        """Total proposals that cleared the score gate.

        Operators routinely ask "how many proposals passed the score
        gate?" — that's every record currently sitting in
        ``score_accepted`` plus every record that moved downstream of
        it (every ``gate_rejected_*`` bucket, ``proposal_opened``,
        ``trade_opened``, ``outcome_linked``, ``open_errored``). The
        derived sum saves callers from re-deriving it from the funnel
        order each time.
        """
        return (
            self.score_accepted
            + self.gate_rejected_total
            + self.shadow_recorded
            + self.proposal_opened
            + self.trade_opened
            + self.outcome_linked
            + self.open_errored
        )


# Mapping from ``ProposalFinalState`` to the ``FunnelCounts`` field
# name. Defined at module level so the aggregator does not re-derive it
# per call.
_STATE_TO_FIELD: dict[ProposalFinalState, str] = {
    ProposalFinalState.GENERATED: "generated",
    ProposalFinalState.SCORED: "scored",
    ProposalFinalState.SCORE_ACCEPTED: "score_accepted",
    ProposalFinalState.SCORE_REJECTED: "score_rejected",
    ProposalFinalState.GATE_REJECTED_MARKET_REGIME: "gate_rejected_market_regime",
    ProposalFinalState.GATE_REJECTED_CORRELATION: "gate_rejected_correlation",
    ProposalFinalState.GATE_REJECTED_TREND_FILTER: "gate_rejected_trend_filter",
    ProposalFinalState.GATE_REJECTED_SIBLING_FAMILY: "gate_rejected_sibling_family",
    ProposalFinalState.GATE_REJECTED_RUNTIME_SAFETY_PAUSE: (
        "gate_rejected_runtime_safety_pause"
    ),
    ProposalFinalState.GATE_REJECTED_TOTAL_CAP: "gate_rejected_total_cap",
    ProposalFinalState.GATE_REJECTED_SYMBOL_CAP: "gate_rejected_symbol_cap",
    ProposalFinalState.GATE_REJECTED_STALE_QUOTE: "gate_rejected_stale_quote",
    ProposalFinalState.GATE_REJECTED_ACCOUNT_AGGREGATE_CAP: (
        "gate_rejected_account_aggregate_cap"
    ),
    ProposalFinalState.GATE_REJECTED_STALE_POSITION_BLOCK: (
        "gate_rejected_stale_position_block"
    ),
    ProposalFinalState.GATE_REJECTED_RISK_SIZING: "gate_rejected_risk_sizing",
    ProposalFinalState.GATE_REJECTED_GLOBAL_CAP: "gate_rejected_global_cap",
    ProposalFinalState.GATE_REJECTED_OPEN_DRAWDOWN_KILL_SWITCH: (
        "gate_rejected_open_drawdown_kill_switch"
    ),
    ProposalFinalState.GATE_REJECTED_OPEN_STOP_RISK_KILL_SWITCH: (
        "gate_rejected_open_stop_risk_kill_switch"
    ),
    ProposalFinalState.GATE_REJECTED_PORTFOLIO_KILL_SWITCH: (
        "gate_rejected_portfolio_kill_switch"
    ),
    ProposalFinalState.GATE_REJECTED_STRATEGY_ACTION_PAUSE: (
        "gate_rejected_strategy_action_pause"
    ),
    ProposalFinalState.SHADOW_RECORDED: "shadow_recorded",
    ProposalFinalState.GATE_REJECTED_UNKNOWN: "gate_rejected_unknown",
    ProposalFinalState.PROPOSAL_OPENED: "proposal_opened",
    ProposalFinalState.TRADE_OPENED: "trade_opened",
    ProposalFinalState.OUTCOME_LINKED: "outcome_linked",
    ProposalFinalState.OPEN_ERRORED: "open_errored",
}


def _classify(record: ProposalRecord) -> ProposalFinalState:
    """Return the effective funnel state for one record.

    Legacy rows (``final_state`` is the default ``generated`` but the
    proposal has clearly progressed) get bucketed into
    ``GATE_REJECTED_UNKNOWN`` per the resolved backfill policy. We
    intentionally do *not* infer the original terminal gate — the
    fallback bucket is the operator-visible "legacy" signal and rolls
    over naturally as new proposals come through.
    """
    state_raw = record.final_state
    state = (
        ProposalFinalState(state_raw)
        if not isinstance(state_raw, ProposalFinalState)
        else state_raw
    )
    if state is not ProposalFinalState.GENERATED:
        return state

    # Forward-only fallback: a record that has a non-PENDING decision
    # but still carries the default ``generated`` final-state pre-dates
    # the funnel field. The dashboard shows these in their own bucket.
    decision_raw = record.decision
    decision = (
        ProposalDecision(decision_raw)
        if not isinstance(decision_raw, ProposalDecision)
        else decision_raw
    )
    if decision is ProposalDecision.PENDING:
        return ProposalFinalState.GENERATED
    return ProposalFinalState.GATE_REJECTED_UNKNOWN


def _record_timestamp(record: ProposalRecord) -> datetime:
    """Pick the timestamp the window filter compares against."""
    if record.decision_at is not None:
        return ensure_utc(record.decision_at)
    return ensure_utc(record.proposal.created_at)


def compute_funnel_counts(
    records: Iterable[ProposalRecord],
    window: FunnelWindow | None = None,
) -> FunnelCounts:
    """Count proposal records by terminal funnel state.

    Pure function — no IO, no global state. The caller is responsible
    for fetching the records (typically via ``ProposalHistory.list_all``)
    and for picking the window. Returns a :class:`FunnelCounts` whose
    fields sum to ``len(filtered_records)``.

    Args:
        records: Iterable of :class:`ProposalRecord`. The aggregator
            walks the input once.
        window: Optional :class:`FunnelWindow` to filter records by
            ``decision_at`` (falling back to ``proposal.created_at``).
            Either bound may be ``None`` to leave that side unbounded.

    Returns:
        Populated :class:`FunnelCounts`.
    """
    counts: dict[str, int] = dict.fromkeys(_STATE_TO_FIELD.values(), 0)
    total = 0

    start = ensure_utc(window.start) if window and window.start is not None else None
    end = ensure_utc(window.end) if window and window.end is not None else None

    for record in records:
        ts = _record_timestamp(record)
        if start is not None and ts < start:
            continue
        if end is not None and ts > end:
            continue
        state = _classify(record)
        field = _STATE_TO_FIELD[state]
        counts[field] += 1
        total += 1

    return FunnelCounts(total=total, **counts)


def compute_funnel_counts_by_strategy(
    records: Iterable[ProposalRecord],
    window: FunnelWindow | None = None,
) -> dict[str, FunnelCounts]:
    """Group :func:`compute_funnel_counts` by ``technique_name``.

    Drives the per-strategy emitted-to-opened heatmap (spec §4). The
    return value is a mapping keyed by ``proposal.technique_name`` so
    operators can immediately see "RSI emitted 400 proposals but
    opened 4" — and which gate consumed the other 396.
    """
    grouped: dict[str, list[ProposalRecord]] = {}
    for record in records:
        grouped.setdefault(record.proposal.technique_name, []).append(record)

    return {
        technique: compute_funnel_counts(bucket, window=window)
        for technique, bucket in grouped.items()
    }


def compute_funnel_counts_by_sub_account(
    records: Iterable[ProposalRecord],
    window: FunnelWindow | None = None,
) -> dict[str, FunnelCounts]:
    """Group :func:`compute_funnel_counts` by ``sub_account_id``.

    Drives the per-account funnel summary (spec §4 "Per-account funnel
    summary"). One row per sub-account.
    """
    grouped: dict[str, list[ProposalRecord]] = {}
    for record in records:
        sub_id = record.sub_account_id or record.proposal.sub_account_id
        grouped.setdefault(sub_id, []).append(record)

    return {
        sub_id: compute_funnel_counts(bucket, window=window)
        for sub_id, bucket in grouped.items()
    }


__all__ = [
    "FunnelCounts",
    "FunnelWindow",
    "compute_funnel_counts",
    "compute_funnel_counts_by_strategy",
    "compute_funnel_counts_by_sub_account",
]
