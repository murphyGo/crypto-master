"""Runtime safety score models and status bands.

This module defines the stable input and output contract for operator-facing
runtime safety rollups. Event extraction and dashboard rendering are later
construction steps.

Related Requirements:
- FR-014: Proposal Auto-Accept/Reject
- FR-015: Trading History / Runtime Visibility
- FR-042: Operator-facing runtime safety score
- NFR-007: Trading History Storage
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from src.runtime.activity_log import ActivityEvent, ActivityEventType


class RuntimeSafetyBand(str, Enum):
    """Operator-facing safety status band."""

    SAFE = "safe"
    DEGRADED = "degraded"
    RISKY = "risky"
    PAUSE_RECOMMENDED = "pause_recommended"


class RuntimeSafetyInputs(BaseModel):
    """Aggregated runtime signals used to compute a safety score."""

    recent_cycle_errors: int = Field(default=0, ge=0)
    recent_notification_failures: int = Field(default=0, ge=0)
    recent_llm_timeouts: int = Field(default=0, ge=0)
    stale_quote_warnings: int = Field(default=0, ge=0)
    liquidation_events: int = Field(default=0, ge=0)
    cold_start_blocks: int = Field(default=0, ge=0)
    open_drawdown_percent: float = Field(default=0.0, ge=0.0)


class RuntimeSafetyPolicy(BaseModel):
    """Thresholds for mapping a numeric score to a status band."""

    safe_score: int = Field(default=85, ge=0, le=100)
    degraded_score: int = Field(default=65, ge=0, le=100)
    risky_score: int = Field(default=40, ge=0, le=100)

    @model_validator(mode="after")
    def _validate_descending_thresholds(self) -> RuntimeSafetyPolicy:
        if not (self.safe_score > self.degraded_score > self.risky_score):
            raise ValueError("safety thresholds must satisfy safe > degraded > risky")
        return self

    def band_for_score(self, score: int) -> RuntimeSafetyBand:
        """Map a score in ``0..100`` to a safety band."""
        score = max(0, min(100, score))
        if score >= self.safe_score:
            return RuntimeSafetyBand.SAFE
        if score >= self.degraded_score:
            return RuntimeSafetyBand.DEGRADED
        if score >= self.risky_score:
            return RuntimeSafetyBand.RISKY
        return RuntimeSafetyBand.PAUSE_RECOMMENDED


class RuntimeSafetyScore(BaseModel):
    """Computed operator-facing runtime safety result."""

    score: int = Field(ge=0, le=100)
    band: RuntimeSafetyBand
    inputs: RuntimeSafetyInputs
    factors: list[str] = Field(default_factory=list)


def format_runtime_safety_summary(score: RuntimeSafetyScore) -> str:
    """Render a compact safety summary for operator notification surfaces."""
    return f"runtime_safety: {score.score}/100 {score.band.value}"


def inputs_from_activity_events(
    events: list[ActivityEvent],
    *,
    open_drawdown_percent: float = 0.0,
) -> RuntimeSafetyInputs:
    """Aggregate safety inputs from runtime activity events."""
    return RuntimeSafetyInputs(
        recent_cycle_errors=_count(events, ActivityEventType.CYCLE_ERRORED),
        recent_notification_failures=_count(
            events,
            ActivityEventType.NOTIFICATION_FAILED,
        ),
        recent_llm_timeouts=_count(events, ActivityEventType.LLM_TIMEOUT),
        stale_quote_warnings=sum(1 for event in events if _is_stale_quote(event)),
        liquidation_events=_count(events, ActivityEventType.LIQUIDATED),
        cold_start_blocks=_count(events, ActivityEventType.COLD_START_BLOCKED),
        open_drawdown_percent=open_drawdown_percent,
    )


def compute_runtime_safety_score(
    inputs: RuntimeSafetyInputs,
    *,
    policy: RuntimeSafetyPolicy | None = None,
) -> RuntimeSafetyScore:
    """Compute an operator-facing safety score from aggregated inputs."""
    policy = policy or RuntimeSafetyPolicy()
    score = 100
    factors: list[str] = []

    score = _apply_penalty(
        score,
        min(inputs.recent_cycle_errors * 15, 45),
        f"cycle errors={inputs.recent_cycle_errors}",
        factors,
    )
    score = _apply_penalty(
        score,
        min(inputs.recent_notification_failures * 10, 30),
        f"notification failures={inputs.recent_notification_failures}",
        factors,
    )
    score = _apply_penalty(
        score,
        min(inputs.recent_llm_timeouts * 5, 20),
        f"llm timeouts={inputs.recent_llm_timeouts}",
        factors,
    )
    score = _apply_penalty(
        score,
        min(inputs.stale_quote_warnings * 10, 30),
        f"stale quote warnings={inputs.stale_quote_warnings}",
        factors,
    )
    score = _apply_penalty(
        score,
        min(inputs.liquidation_events * 40, 80),
        f"liquidations={inputs.liquidation_events}",
        factors,
    )
    score = _apply_penalty(
        score,
        min(inputs.cold_start_blocks * 5, 15),
        f"cold-start blocks={inputs.cold_start_blocks}",
        factors,
    )
    score = _apply_penalty(
        score,
        min(int(inputs.open_drawdown_percent), 30),
        f"open drawdown={inputs.open_drawdown_percent:.2f}%",
        factors,
    )

    score = max(0, min(100, score))
    if not factors:
        factors.append("no recent safety penalties")
    return RuntimeSafetyScore(
        score=score,
        band=policy.band_for_score(score),
        inputs=inputs,
        factors=factors,
    )


def _count(events: list[ActivityEvent], event_type: ActivityEventType) -> int:
    return sum(1 for event in events if event.event_type == event_type.value)


def _is_stale_quote(event: ActivityEvent) -> bool:
    reason = str(event.details.get("reason", ""))
    return "stale_quote" in reason or "stale-quote" in event.message


def _apply_penalty(
    score: int,
    penalty: int,
    factor: str,
    factors: list[str],
) -> int:
    if penalty <= 0:
        return score
    factors.append(f"{factor} (-{penalty})")
    return score - penalty


__all__ = [
    "RuntimeSafetyBand",
    "RuntimeSafetyInputs",
    "RuntimeSafetyPolicy",
    "RuntimeSafetyScore",
    "compute_runtime_safety_score",
    "format_runtime_safety_summary",
    "inputs_from_activity_events",
]
