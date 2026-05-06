"""Tests for runtime safety score models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.runtime.safety_score import (
    RuntimeSafetyBand,
    RuntimeSafetyInputs,
    RuntimeSafetyPolicy,
    RuntimeSafetyScore,
)


def test_runtime_safety_inputs_defaults_are_zero() -> None:
    inputs = RuntimeSafetyInputs()

    assert inputs.recent_cycle_errors == 0
    assert inputs.recent_notification_failures == 0
    assert inputs.recent_llm_timeouts == 0
    assert inputs.stale_quote_warnings == 0
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
