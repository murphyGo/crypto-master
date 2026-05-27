"""Tests for the ``GateReason`` closed vocabulary (CAH-13, Part 1).

The enum's ``.value`` for every member is an on-disk contract — the
activity-log JSONL persists these strings and dashboards / the safety
score read them back by equality. These tests PIN the historical literal
for each member so an accidental rename of a value (which would silently
break back-compat with already-written logs) fails loudly.
"""

from __future__ import annotations

from src.runtime.gate_reason import GateReason

# The exact strings historically written to ``details["gate_reason"]`` by
# ``src.runtime.engine`` (and the ``operator_freeze`` value consumed by the
# cross-account-risk panel's risk-gate set). Hand-pinned, NOT derived from the
# enum, so a value rename is caught.
HISTORICAL_GATE_REASON_VALUES: dict[GateReason, str] = {
    GateReason.RISK_SIZING: "risk_sizing",
    GateReason.DAILY_LOSS_KILL_SWITCH: "daily_loss_kill_switch",
    GateReason.OPEN_DRAWDOWN_KILL_SWITCH: "open_drawdown_kill_switch",
    GateReason.OPEN_STOP_RISK_KILL_SWITCH: "open_stop_risk_kill_switch",
    GateReason.PORTFOLIO_KILL_SWITCH: "portfolio_kill_switch",
    GateReason.PORTFOLIO_DAILY_LOSS_KILL_SWITCH: "portfolio_daily_loss_kill_switch",
    GateReason.TOTAL_CAP: "total_cap",
    GateReason.SYMBOL_CAP: "symbol_cap",
    GateReason.ACCOUNT_AGGREGATE_CAP: "account_aggregate_cap",
    GateReason.GLOBAL_CAP: "global_cap",
    GateReason.STALE_POSITION_BLOCK: "stale_position_block",
    GateReason.SIBLING_FAMILY_DEDUP: "sibling_family_dedup",
    GateReason.RUNTIME_SAFETY_PAUSED: "runtime_safety_paused",
    GateReason.TREND_FILTER_BLOCKED: "trend_filter_blocked",
    GateReason.MARKET_REGIME_BLOCKED: "market_regime_blocked",
    GateReason.STRATEGY_ACTION_SHADOW: "strategy_action_shadow",
    GateReason.STRATEGY_ACTION_PAUSE: "strategy_action_pause",
    GateReason.CORRELATION_BLOCKED: "correlation_blocked",
    GateReason.STALE_QUOTE_NO_LIVE_DATA: "stale_quote_no_live_data",
    GateReason.OPERATOR_FREEZE: "operator_freeze",
}


def test_each_member_value_matches_historical_literal() -> None:
    for member, literal in HISTORICAL_GATE_REASON_VALUES.items():
        assert member.value == literal


def test_no_member_is_missing_from_the_pin() -> None:
    # If a new member is added without pinning its historical literal, this
    # fails — forcing a deliberate decision about the on-disk contract.
    assert set(GateReason) == set(HISTORICAL_GATE_REASON_VALUES)


def test_str_backed_member_equals_its_raw_string() -> None:
    # str-backed so equality against the raw persisted string holds — this is
    # what the consumer comparison sites rely on.
    assert GateReason.TOTAL_CAP == "total_cap"
    assert GateReason.GLOBAL_CAP.value == "global_cap"


def test_member_serializes_to_value_inside_activity_event_details() -> None:
    # A GateReason placed in the free-form details dict serializes to its
    # .value via model_dump(mode="json"), keeping on-disk JSONL byte-identical.
    from src.runtime.activity_events import ActivityEvent, ActivityEventType

    event = ActivityEvent(
        event_type=ActivityEventType.PROPOSAL_REJECTED,
        details={"gate_reason": GateReason.TOTAL_CAP},
    )
    dumped = event.model_dump(mode="json")
    assert dumped["details"]["gate_reason"] == "total_cap"
