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


__all__ = [
    "RuntimeSafetyBand",
    "RuntimeSafetyInputs",
    "RuntimeSafetyPolicy",
    "RuntimeSafetyScore",
]
