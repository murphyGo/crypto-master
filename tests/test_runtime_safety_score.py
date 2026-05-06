"""Tests for runtime safety score models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.runtime.activity_log import ActivityEvent, ActivityEventType
from src.runtime.safety_score import (
    RuntimeSafetyBand,
    RuntimeSafetyInputs,
    RuntimeSafetyPolicy,
    RuntimeSafetyScore,
    compute_runtime_safety_score,
    format_runtime_safety_summary,
    inputs_from_activity_events,
)


def test_runtime_safety_inputs_defaults_are_zero() -> None:
    inputs = RuntimeSafetyInputs()

    assert inputs.recent_cycle_errors == 0
    assert inputs.recent_notification_failures == 0
    assert inputs.recent_llm_timeouts == 0
    assert inputs.stale_quote_warnings == 0
    assert inputs.correlation_warnings == 0
    assert inputs.liquidation_events == 0
    assert inputs.cold_start_blocks == 0
    assert inputs.open_drawdown_percent == 0.0


def test_runtime_safety_inputs_reject_negative_counts() -> None:
    with pytest.raises(ValidationError, match="recent_cycle_errors"):
        RuntimeSafetyInputs(recent_cycle_errors=-1)


def test_runtime_safety_policy_maps_score_bands() -> None:
    policy = RuntimeSafetyPolicy()

    assert policy.band_for_score(100) == RuntimeSafetyBand.SAFE
    assert policy.band_for_score(85) == RuntimeSafetyBand.SAFE
    assert policy.band_for_score(70) == RuntimeSafetyBand.DEGRADED
    assert policy.band_for_score(45) == RuntimeSafetyBand.RISKY
    assert policy.band_for_score(10) == RuntimeSafetyBand.PAUSE_RECOMMENDED


def test_runtime_safety_policy_rejects_non_descending_thresholds() -> None:
    with pytest.raises(ValidationError, match="safe > degraded > risky"):
        RuntimeSafetyPolicy(safe_score=70, degraded_score=80, risky_score=40)


def test_runtime_safety_score_requires_bounded_score() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        RuntimeSafetyScore(
            score=101,
            band=RuntimeSafetyBand.SAFE,
            inputs=RuntimeSafetyInputs(),
        )


def test_inputs_from_activity_events_counts_safety_signals() -> None:
    events = [
        ActivityEvent(event_type=ActivityEventType.CYCLE_ERRORED),
        ActivityEvent(event_type=ActivityEventType.NOTIFICATION_FAILED),
        ActivityEvent(event_type=ActivityEventType.LLM_TIMEOUT),
        ActivityEvent(event_type=ActivityEventType.LIQUIDATED),
        ActivityEvent(event_type=ActivityEventType.COLD_START_BLOCKED),
        ActivityEvent(event_type=ActivityEventType.CORRELATION_WARNING),
        ActivityEvent(
            event_type=ActivityEventType.PROPOSAL_REJECTED,
            message="Stale-quote rejected BTC/USDT long",
            details={"reason": "stale_quote_past_sl"},
        ),
    ]

    inputs = inputs_from_activity_events(events, open_drawdown_percent=12.5)

    assert inputs.recent_cycle_errors == 1
    assert inputs.recent_notification_failures == 1
    assert inputs.recent_llm_timeouts == 1
    assert inputs.liquidation_events == 1
    assert inputs.cold_start_blocks == 1
    assert inputs.stale_quote_warnings == 1
    assert inputs.correlation_warnings == 1
    assert inputs.open_drawdown_percent == 12.5


def test_compute_runtime_safety_score_safe_when_no_penalties() -> None:
    safety = compute_runtime_safety_score(RuntimeSafetyInputs())

    assert safety.score == 100
    assert safety.band == RuntimeSafetyBand.SAFE
    assert safety.factors == ["no recent safety penalties"]


def test_compute_runtime_safety_score_applies_penalties() -> None:
    safety = compute_runtime_safety_score(
        RuntimeSafetyInputs(
            recent_cycle_errors=1,
            recent_notification_failures=1,
            recent_llm_timeouts=2,
            stale_quote_warnings=1,
            correlation_warnings=1,
            open_drawdown_percent=5.5,
        )
    )

    assert safety.score == 40
    assert safety.band == RuntimeSafetyBand.RISKY
    assert any("cycle errors=1" in factor for factor in safety.factors)


def test_compute_runtime_safety_score_recommends_pause_on_liquidation() -> None:
    safety = compute_runtime_safety_score(
        RuntimeSafetyInputs(liquidation_events=2),
    )

    assert safety.score == 20
    assert safety.band == RuntimeSafetyBand.PAUSE_RECOMMENDED


def test_format_runtime_safety_summary_is_compact() -> None:
    safety = compute_runtime_safety_score(
        RuntimeSafetyInputs(recent_cycle_errors=1),
    )

    assert format_runtime_safety_summary(safety) == "runtime_safety: 85/100 safe"
