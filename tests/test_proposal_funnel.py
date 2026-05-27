"""Tests for the proposal funnel aggregator (proposal-funnel-audit).

Pins the funnel taxonomy spec §1 (final-state classification), the
schema round-trip for the new ``ProposalRecord.final_state`` field,
and the ``gate_rejected_unknown`` fallback for legacy rows missing
the field.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.proposal.funnel import (
    FunnelCounts,
    FunnelWindow,
    compute_funnel_counts,
    compute_funnel_counts_by_strategy,
    compute_funnel_counts_by_sub_account,
)
from src.proposal.interaction import (
    ProposalDecision,
    ProposalFinalState,
    ProposalHistory,
    ProposalRecord,
)
from tests.test_proposal_interaction import make_proposal

# =============================================================================
# Helpers
# =============================================================================


def _record(
    *,
    proposal_id: str,
    technique_name: str = "rsi_v1",
    sub_account_id: str = "default",
    final_state: ProposalFinalState | None = None,
    decision: ProposalDecision = ProposalDecision.PENDING,
    decision_at: datetime | None = None,
    created_at: datetime | None = None,
) -> ProposalRecord:
    proposal = make_proposal(
        proposal_id=proposal_id,
        technique_name=technique_name,
        created_at=created_at,
    )
    update: dict[str, object] = {"sub_account_id": sub_account_id}
    if final_state is not None:
        update["final_state"] = final_state.value
    record = ProposalRecord(
        proposal=proposal.model_copy(update={"sub_account_id": sub_account_id}),
        decision=decision,
        decision_at=decision_at,
    )
    return record.model_copy(update=update)


# =============================================================================
# Schema round-trip + legacy default
# =============================================================================


def test_proposal_record_defaults_final_state_to_generated() -> None:
    record = ProposalRecord(proposal=make_proposal(proposal_id="p1"))
    # ``use_enum_values=True`` on the model — the persisted value is
    # the enum's underlying string.
    assert record.final_state == ProposalFinalState.GENERATED.value


def test_proposal_record_round_trip_preserves_final_state(tmp_path: Path) -> None:
    history = ProposalHistory(data_dir=tmp_path)
    record = ProposalRecord(
        proposal=make_proposal(proposal_id="p_round_trip"),
        final_state=ProposalFinalState.GATE_REJECTED_TOTAL_CAP,
    )
    history.save(record)
    loaded = history.load("p_round_trip")
    assert loaded.final_state == ProposalFinalState.GATE_REJECTED_TOTAL_CAP.value


def test_legacy_record_without_final_state_loads_with_default(
    tmp_path: Path,
) -> None:
    """A pre-cutover on-disk row that has no ``final_state`` key must
    still load — the model default backstops it. The aggregator buckets
    such rows into ``gate_rejected_unknown`` when they have a decided
    ``decision`` field (resolved 2026-05-13).
    """
    history = ProposalHistory(data_dir=tmp_path)
    # Write a record then strip the ``final_state`` key from JSON so we
    # mimic a pre-cutover file on disk.
    record = ProposalRecord(
        proposal=make_proposal(proposal_id="legacy_1"),
        decision=ProposalDecision.REJECTED,
        decision_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        rejection_reason="counter_trend_short_in_uptrend",
    )
    history.save(record)
    path = tmp_path / "default" / "legacy_1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("final_state", None)
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = history.load("legacy_1")
    # Default still applies — file loads.
    assert loaded.final_state == ProposalFinalState.GENERATED.value


def test_aggregator_buckets_decided_legacy_row_into_unknown() -> None:
    """A record with a non-PENDING decision but ``final_state=generated``
    is a legacy row — bucket into ``gate_rejected_unknown``."""
    legacy = _record(
        proposal_id="legacy_a",
        decision=ProposalDecision.REJECTED,
    )
    fresh = _record(
        proposal_id="fresh_a",
        decision=ProposalDecision.PENDING,
    )
    counts = compute_funnel_counts([legacy, fresh])
    assert counts.gate_rejected_unknown == 1
    assert counts.generated == 1
    assert counts.total == 2


# =============================================================================
# Per-state counting
# =============================================================================


def test_each_final_state_lands_in_its_own_bucket() -> None:
    # For ``GENERATED`` we need a PENDING decision so the aggregator
    # doesn't fall through to the legacy ``gate_rejected_unknown``
    # backfill bucket. Every other state survives any decision.
    records = [
        _record(
            proposal_id=f"p_{state.value}",
            final_state=state,
            decision=(
                ProposalDecision.PENDING
                if state is ProposalFinalState.GENERATED
                else ProposalDecision.ACCEPTED
            ),
        )
        for state in ProposalFinalState
    ]
    counts = compute_funnel_counts(records)
    # Every state contributes exactly one to its own bucket.
    for state in ProposalFinalState:
        attr = state.value
        assert getattr(counts, attr) == 1, f"state {attr} should count 1"
    assert counts.total == len(list(ProposalFinalState))


def test_funnel_field_coverage_for_every_final_state() -> None:
    """PROP-F1 (CAH-12): every ``ProposalFinalState`` has a backing field.

    This is the regression guard that makes "add a new terminal" safe.
    The ``_STATE_TO_FIELD`` mapping and ``gate_rejected_total`` are now
    derived from the enum via ``getattr(self, member.value)``; if a future
    enum member lacks a matching ``FunnelCounts`` field this assertion
    fails loudly instead of the aggregator KeyError-ing at runtime.
    """
    field_names = set(FunnelCounts.model_fields)
    state_values = {state.value for state in ProposalFinalState}
    assert state_values <= field_names, (
        "every ProposalFinalState.value must back a FunnelCounts field; "
        f"missing: {sorted(state_values - field_names)}"
    )


def test_state_to_field_derivation_reproduces_identity() -> None:
    """The derived ``_STATE_TO_FIELD`` maps each state to its own ``.value``."""
    from src.proposal.funnel import _STATE_TO_FIELD

    assert _STATE_TO_FIELD == {state: state.value for state in ProposalFinalState}


def test_gate_rejected_total_derivation_sums_exactly_the_gate_members() -> None:
    """PROP-F1: ``gate_rejected_total`` sums precisely the GATE_REJECTED_* fields.

    Builds a ``FunnelCounts`` with a distinct value in every
    ``GATE_REJECTED_*`` bucket (and noise in non-gate buckets) and asserts
    the derived total equals the hand-summed gate buckets only — no
    double-count, no missed bucket, no leakage from non-gate fields.
    """
    gate_members = [
        s for s in ProposalFinalState if s.name.startswith("GATE_REJECTED_")
    ]
    # Distinct values so a missed/duplicated term changes the total.
    gate_values = {member.value: i + 1 for i, member in enumerate(gate_members)}
    counts = FunnelCounts(
        # Non-gate buckets carry noise that must NOT count toward the total.
        generated=100,
        scored=200,
        score_accepted=300,
        proposal_opened=400,
        trade_opened=500,
        shadow_recorded=600,
        **gate_values,
    )
    expected = sum(gate_values.values())
    assert counts.gate_rejected_total == expected
    # Sanity: 20 gate buckets summing 1..20 => 210.
    assert len(gate_members) == 20
    assert expected == 210


def test_gate_rejected_total_sums_every_gate_bucket() -> None:
    records = [
        _record(
            proposal_id="m",
            final_state=ProposalFinalState.GATE_REJECTED_MARKET_REGIME,
            decision=ProposalDecision.ACCEPTED,
        ),
        _record(
            proposal_id="c",
            final_state=ProposalFinalState.GATE_REJECTED_CORRELATION,
            decision=ProposalDecision.ACCEPTED,
        ),
        _record(
            proposal_id="cap",
            final_state=ProposalFinalState.GATE_REJECTED_TOTAL_CAP,
            decision=ProposalDecision.ACCEPTED,
        ),
        _record(
            proposal_id="unk",
            final_state=ProposalFinalState.GATE_REJECTED_UNKNOWN,
            decision=ProposalDecision.ACCEPTED,
        ),
    ]
    counts = compute_funnel_counts(records)
    assert counts.gate_rejected_total == 4


def test_score_accepted_total_sums_every_post_score_state() -> None:
    """One record per state downstream of (and including) ``score_accepted``.

    The derived property must equal the count of every proposal that
    cleared the score gate — that is, the sum across ``score_accepted``
    plus every ``gate_rejected_*`` bucket plus the four terminal
    downstream states (``proposal_opened``, ``trade_opened``,
    ``outcome_linked``, ``open_errored``).
    """
    post_score_states = [
        ProposalFinalState.SCORE_ACCEPTED,
        ProposalFinalState.GATE_REJECTED_MARKET_REGIME,
        ProposalFinalState.GATE_REJECTED_CORRELATION,
        ProposalFinalState.GATE_REJECTED_TREND_FILTER,
        ProposalFinalState.GATE_REJECTED_SIBLING_FAMILY,
        ProposalFinalState.GATE_REJECTED_RUNTIME_SAFETY_PAUSE,
        ProposalFinalState.GATE_REJECTED_TOTAL_CAP,
        ProposalFinalState.GATE_REJECTED_SYMBOL_CAP,
        ProposalFinalState.GATE_REJECTED_STALE_QUOTE,
        ProposalFinalState.GATE_REJECTED_UNKNOWN,
        ProposalFinalState.PROPOSAL_OPENED,
        ProposalFinalState.TRADE_OPENED,
        ProposalFinalState.OUTCOME_LINKED,
        ProposalFinalState.OPEN_ERRORED,
    ]
    records = [
        _record(
            proposal_id=f"sa_{state.value}",
            final_state=state,
            decision=ProposalDecision.ACCEPTED,
        )
        for state in post_score_states
    ]
    # Also seed records that should NOT count toward score_accepted_total.
    records.extend(
        [
            _record(
                proposal_id="gen",
                final_state=ProposalFinalState.GENERATED,
                decision=ProposalDecision.PENDING,
            ),
            _record(
                proposal_id="scored",
                final_state=ProposalFinalState.SCORED,
                decision=ProposalDecision.PENDING,
            ),
            _record(
                proposal_id="rej",
                final_state=ProposalFinalState.SCORE_REJECTED,
                decision=ProposalDecision.REJECTED,
            ),
        ]
    )
    counts = compute_funnel_counts(records)
    assert counts.score_accepted_total == len(post_score_states)


# =============================================================================
# Window filter
# =============================================================================


def test_window_filter_excludes_records_outside_range() -> None:
    base = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    inside = _record(
        proposal_id="inside",
        final_state=ProposalFinalState.TRADE_OPENED,
        decision=ProposalDecision.ACCEPTED,
        decision_at=base,
    )
    too_old = _record(
        proposal_id="too_old",
        final_state=ProposalFinalState.TRADE_OPENED,
        decision=ProposalDecision.ACCEPTED,
        decision_at=base - timedelta(days=30),
    )
    counts = compute_funnel_counts(
        [inside, too_old],
        window=FunnelWindow(
            start=base - timedelta(days=1), end=base + timedelta(days=1)
        ),
    )
    assert counts.trade_opened == 1
    assert counts.total == 1


def test_window_falls_back_to_created_at_when_decision_at_missing() -> None:
    base = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    # PENDING record has no decision_at — window should use created_at.
    pending = _record(
        proposal_id="pending_inside",
        decision=ProposalDecision.PENDING,
        created_at=base,
    )
    pending_old = _record(
        proposal_id="pending_old",
        decision=ProposalDecision.PENDING,
        created_at=base - timedelta(days=10),
    )
    counts = compute_funnel_counts(
        [pending, pending_old],
        window=FunnelWindow(start=base - timedelta(days=1), end=base + timedelta(days=1)),
    )
    assert counts.generated == 1
    assert counts.total == 1


# =============================================================================
# Group-by
# =============================================================================


def test_compute_funnel_counts_by_strategy_isolates_per_technique() -> None:
    records = [
        _record(
            proposal_id="rsi_1",
            technique_name="rsi_v1",
            final_state=ProposalFinalState.TRADE_OPENED,
            decision=ProposalDecision.ACCEPTED,
        ),
        _record(
            proposal_id="rsi_2",
            technique_name="rsi_v1",
            final_state=ProposalFinalState.SCORE_REJECTED,
            decision=ProposalDecision.REJECTED,
        ),
        _record(
            proposal_id="orb_1",
            technique_name="orb_v1",
            final_state=ProposalFinalState.GATE_REJECTED_TOTAL_CAP,
            decision=ProposalDecision.ACCEPTED,
        ),
    ]
    grouped = compute_funnel_counts_by_strategy(records)
    assert grouped["rsi_v1"].trade_opened == 1
    assert grouped["rsi_v1"].score_rejected == 1
    assert grouped["orb_v1"].gate_rejected_total_cap == 1


def test_compute_funnel_counts_by_sub_account_isolates_per_account() -> None:
    records = [
        _record(
            proposal_id="a1",
            sub_account_id="alpha",
            final_state=ProposalFinalState.TRADE_OPENED,
            decision=ProposalDecision.ACCEPTED,
        ),
        _record(
            proposal_id="b1",
            sub_account_id="beta",
            final_state=ProposalFinalState.SCORE_REJECTED,
            decision=ProposalDecision.REJECTED,
        ),
    ]
    grouped = compute_funnel_counts_by_sub_account(records)
    assert grouped["alpha"].trade_opened == 1
    assert grouped["beta"].score_rejected == 1


# =============================================================================
# FunnelCounts model surface
# =============================================================================


def test_funnel_counts_defaults_to_zero() -> None:
    counts = FunnelCounts()
    for attr in (
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
        "total",
    ):
        assert getattr(counts, attr) == 0


def test_funnel_counts_total_matches_sum_of_buckets() -> None:
    records = [
        _record(
            proposal_id=f"p_{i}",
            final_state=ProposalFinalState.TRADE_OPENED,
            decision=ProposalDecision.ACCEPTED,
        )
        for i in range(3)
    ]
    counts = compute_funnel_counts(records)
    assert counts.total == 3
    assert counts.trade_opened == 3
