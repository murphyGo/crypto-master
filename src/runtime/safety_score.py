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

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.runtime.activity_events import ActivityEvent, ActivityEventType
from src.utils.time import ensure_utc, now_utc

DEFAULT_RECENT_LOOKBACK_HOURS = 24

# Default for an absent ``sub_account_id`` — a portfolio-level gate that drops
# the proposer account collapses to one shared bucket. Centralized here so the
# kill-switch dedup tuple and any future consumer agree on the sentinel.
GLOBAL_SUB_ACCOUNT_SENTINEL = "__global__"


# =============================================================================
# Bounded typed accessors over ``ActivityEvent.details`` (CAH-13, Part 2)
# =============================================================================
#
# ``ActivityEvent.details`` is intentionally a free-form ``dict[str, Any]`` (the
# polymorphism is load-bearing — see the per-event-type payload contracts in
# ``activity_events``). We deliberately do NOT type the whole dict. But the
# RUNTIME-PAUSING safety-score path reads a *bounded* set of keys with silent
# ``.get(default)`` fallbacks, where producer/consumer drift would fail silently
# and skew the operator's safety band. These accessors centralize exactly those
# key strings + defaults in one place so a drift is a single-site, test-catchable
# change. Each accessor preserves the historical ``.get(...)`` semantics exactly.


def event_advisory(event: ActivityEvent) -> bool:
    """Truthiness of ``details["advisory"]`` (default falsy).

    Paper-mode kill switches / cap breaches set this; the safety score
    excludes advisory-only conditions from the LIVE money-safety rollup.
    Mirrors the historical ``bool(event.details.get("advisory"))``.
    """
    return bool(event.details.get("advisory"))


def event_cycle_id(event: ActivityEvent) -> str | None:
    """Cycle id for the event, preferring the top-level field.

    The engine reliably sets the top-level ``cycle_id`` on both the
    paper-advisory and live hard-block branches; we fall back to
    ``details["cycle_id"]`` for robustness, matching the historical
    ``event.cycle_id`` ``or`` ``details.get("cycle_id")`` order (default
    ``None``).
    """
    cycle_id = event.cycle_id
    if cycle_id is None:
        cycle_id = event.details.get("cycle_id")
    return cycle_id


def event_gate_reason(event: ActivityEvent) -> str | None:
    """``details["gate_reason"]`` discriminator (default ``None``).

    Returns the raw string as persisted (a
    ``src.runtime.gate_reason.GateReason`` ``.value``); compare against
    ``GateReason`` members at consumer sites. Mirrors the historical
    ``event.details.get("gate_reason")``.
    """
    return event.details.get("gate_reason")


def event_sub_account_id(event: ActivityEvent) -> str:
    """``details["sub_account_id"]`` normalized to a non-empty string.

    A missing / falsy account id normalizes to
    :data:`GLOBAL_SUB_ACCOUNT_SENTINEL` so a portfolio-level gate counts
    once per cycle. Mirrors the historical
    ``event.details.get("sub_account_id") or "__global__"``.
    """
    return event.details.get("sub_account_id") or GLOBAL_SUB_ACCOUNT_SENTINEL


def event_reason(event: ActivityEvent) -> str:
    """``details["reason"]`` coerced to ``str`` (default ``""``).

    Mirrors the historical ``str(event.details.get("reason", ""))``.
    """
    return str(event.details.get("reason", ""))


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
    correlation_warnings: int = Field(default=0, ge=0)
    liquidation_events: int = Field(default=0, ge=0)
    cold_start_blocks: int = Field(default=0, ge=0)
    kill_switch_conditions: int = Field(default=0, ge=0)
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
        correlation_warnings=_count(events, ActivityEventType.CORRELATION_WARNING),
        liquidation_events=_count(events, ActivityEventType.LIQUIDATED),
        cold_start_blocks=_count(events, ActivityEventType.COLD_START_BLOCKED),
        kill_switch_conditions=_count_kill_switch_conditions(events),
        open_drawdown_percent=open_drawdown_percent,
    )


def recent_activity_events(
    events: list[ActivityEvent],
    *,
    lookback_hours: int = DEFAULT_RECENT_LOOKBACK_HOURS,
    now: datetime | None = None,
) -> list[ActivityEvent]:
    """Return events inside the runtime safety recency window."""
    if lookback_hours <= 0:
        return list(events)
    cutoff = ensure_utc(now or now_utc()) - timedelta(hours=lookback_hours)
    return [event for event in events if ensure_utc(event.timestamp) >= cutoff]


def inputs_from_recent_activity_events(
    events: list[ActivityEvent],
    *,
    lookback_hours: int = DEFAULT_RECENT_LOOKBACK_HOURS,
    now: datetime | None = None,
    open_drawdown_percent: float = 0.0,
) -> RuntimeSafetyInputs:
    """Aggregate safety inputs from only recent runtime activity events."""
    return inputs_from_activity_events(
        recent_activity_events(events, lookback_hours=lookback_hours, now=now),
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
        min(inputs.correlation_warnings * 10, 30),
        f"correlation warnings={inputs.correlation_warnings}",
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
        min(inputs.kill_switch_conditions * 25, 60),
        f"kill-switch conditions={inputs.kill_switch_conditions}",
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


def _count_kill_switch_conditions(events: list[ActivityEvent]) -> int:
    """Count distinct LIVE kill-switch conditions in ``events``.

    DEBT-068(h): kill-switch trips are persistent portfolio-condition
    gates that should pull the runtime safety score toward DEGRADED. A
    single tripped condition can fire on every proposal in a cycle, so
    raw event counts overstate severity. We instead count DISTINCT
    ``(cycle_id, gate_reason, sub_account_id)`` tuples — one trip of a
    given gate, in a given cycle, on a given account, counts once.

    Paper advisories (``details.advisory`` truthy) are EXCLUDED: the
    score measures live money-safety health, and paper-mode kill
    switches are advisory-only (the proposal still proceeds). The
    ``cycle_id`` is read from the event's top-level field (where the
    engine reliably sets it on both the paper-advisory and live
    hard-block branches), falling back to ``details`` for robustness.
    Missing/None ``sub_account_id`` normalizes to ``"__global__"`` so a
    portfolio-level gate counts once per cycle. The portfolio/global
    gates (``portfolio_kill_switch`` / ``portfolio_daily_loss_kill_switch``)
    drop the proposer ``sub_account_id`` at emit time (DEBT-068(h)), so a
    single global trip that fires across N proposers in one cycle collapses
    to ONE condition here instead of N. Account-level gates carry a stable
    real account id and so still count per-account.
    """
    conditions: set[tuple[str | None, Any, str]] = set()
    for event in events:
        if event.event_type != ActivityEventType.RISK_KILL_SWITCH_TRIPPED.value:
            continue
        if event_advisory(event):
            continue
        conditions.add(
            (
                event_cycle_id(event),
                event_gate_reason(event),
                event_sub_account_id(event),
            )
        )
    return len(conditions)


def _is_stale_quote(event: ActivityEvent) -> bool:
    reason = event_reason(event)
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
    "GLOBAL_SUB_ACCOUNT_SENTINEL",
    "RuntimeSafetyBand",
    "RuntimeSafetyInputs",
    "RuntimeSafetyPolicy",
    "RuntimeSafetyScore",
    "compute_runtime_safety_score",
    "event_advisory",
    "event_cycle_id",
    "event_gate_reason",
    "event_reason",
    "event_sub_account_id",
    "format_runtime_safety_summary",
    "inputs_from_activity_events",
    "inputs_from_recent_activity_events",
    "recent_activity_events",
]
