"""Pure Funding/OI crowding classification and evidence qualification.

The classifier is the first proposal-layer consumer of the normalized
derivatives ``MarketContext``.  It is deliberately I/O-free and shadow-first:
runtime callers may observe ``would_block`` but this module owns no proposal
mutation or enforcement path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.exchange.derivatives import MarketContext, SeriesStatus

CrowdingState = Literal[
    "crowded_long",
    "crowded_short",
    "neutral",
    "unavailable",
]
EvidenceStatus = Literal["qualified", "insufficient_evidence", "failed"]
RegimeBucket = Literal["bull", "bear", "sideways", "unknown"]


class FundingOiCrowdingClassification(BaseModel):
    """Immutable, serialization-safe decision-time crowding result."""

    state: CrowdingState
    as_of: datetime
    funding_rate: Decimal | None = None
    funding_low_threshold: Decimal | None = None
    funding_high_threshold: Decimal | None = None
    funding_point_count: int = Field(default=0, ge=0)
    oi_latest: Decimal | None = None
    oi_reference: Decimal | None = None
    oi_delta: Decimal | None = None
    reason: str

    model_config = ConfigDict(frozen=True)

    @field_validator("as_of")
    @classmethod
    def _utc_as_of(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(timezone.utc)


class FundingOiEvidenceInput(BaseModel):
    """Normalized dual-lane evidence summary for future veto eligibility."""

    proposal_expectancy_delta: Decimal | None = Field(default=None, allow_inf_nan=False)
    proposal_with_crowd_count: int = Field(default=0, ge=0)
    snapshot_expectancy_delta: Decimal | None = Field(default=None, allow_inf_nan=False)
    snapshot_with_crowd_count: int = Field(default=0, ge=0)
    regime_buckets: tuple[RegimeBucket, ...] = ()
    snapshot_generation_id: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    configuration_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    seed: int | None = None

    model_config = ConfigDict(frozen=True)


class FundingOiEvidenceResult(BaseModel):
    """Qualification verdict that never silently treats missing evidence as pass."""

    status: EvidenceStatus
    reasons: tuple[str, ...] = ()

    model_config = ConfigDict(frozen=True)

    @property
    def qualified(self) -> bool:
        return self.status == "qualified"


def classify_funding_oi_crowding(
    context: MarketContext | None,
    *,
    as_of: datetime | None = None,
    funding_window_days: int = 30,
    funding_low_percentile: Decimal = Decimal("0.05"),
    funding_high_percentile: Decimal = Decimal("0.95"),
    oi_lookback_hours: int = 24,
) -> FundingOiCrowdingClassification:
    """Classify the Funding-paying side when OI confirms rising crowding."""
    _validate_parameters(
        funding_window_days,
        funding_low_percentile,
        funding_high_percentile,
        oi_lookback_hours,
    )
    if context is None:
        if as_of is None:
            raise ValueError("as_of is required when market context is missing")
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return _unavailable(
            as_of.astimezone(timezone.utc),
            "missing_market_context",
        )

    as_of = context.as_of
    if context.funding_availability.status not in {
        SeriesStatus.FRESH,
        SeriesStatus.CACHED,
    }:
        return _unavailable(as_of, "funding_unavailable")
    if context.open_interest_availability.status not in {
        SeriesStatus.FRESH,
        SeriesStatus.CACHED,
    }:
        return _unavailable(as_of, "open_interest_unavailable")

    window_start = as_of - timedelta(days=funding_window_days)
    funding = tuple(
        point for point in context.funding if window_start <= point.timestamp <= as_of
    )
    expected_points = funding_window_days * 3
    if len(funding) < expected_points:
        return _unavailable(as_of, "funding_window_too_short", len(funding))

    rates = sorted(point.rate for point in funding)
    low = _nearest_rank(rates, funding_low_percentile)
    high = _nearest_rank(rates, funding_high_percentile)
    current_rate = funding[-1].rate

    oi = tuple(point for point in context.open_interest if point.timestamp <= as_of)
    if not oi:
        return _unavailable(as_of, "open_interest_missing", len(funding))
    target = as_of - timedelta(hours=oi_lookback_hours)
    references = tuple(point for point in oi if point.timestamp <= target)
    if not references:
        return _unavailable(as_of, "open_interest_reference_missing", len(funding))
    reference_point = references[-1]
    if target - reference_point.timestamp > timedelta(hours=1):
        return _unavailable(as_of, "open_interest_reference_too_old", len(funding))

    latest_oi = oi[-1].open_interest
    reference_oi = reference_point.open_interest
    delta = latest_oi - reference_oi
    oi_rising = delta > 0
    if current_rate > 0 and current_rate >= high and oi_rising:
        state: CrowdingState = "crowded_long"
        reason = "positive_funding_high_extreme_with_rising_oi"
    elif current_rate < 0 and current_rate <= low and oi_rising:
        state = "crowded_short"
        reason = "negative_funding_low_extreme_with_rising_oi"
    else:
        state = "neutral"
        reason = "crowding_conjunction_not_met"

    return FundingOiCrowdingClassification(
        state=state,
        as_of=as_of,
        funding_rate=current_rate,
        funding_low_threshold=low,
        funding_high_threshold=high,
        funding_point_count=len(funding),
        oi_latest=latest_oi,
        oi_reference=reference_oi,
        oi_delta=delta,
        reason=reason,
    )


def crowding_would_block(state: CrowdingState, signal: str) -> bool:
    """Return the side-aware shadow decision without mutating a proposal."""
    return (state == "crowded_long" and signal == "long") or (
        state == "crowded_short" and signal == "short"
    )


def qualify_funding_oi_evidence(
    evidence: FundingOiEvidenceInput,
) -> FundingOiEvidenceResult:
    """Fail closed when future veto evidence is absent, weak, or negative."""
    missing: list[str] = []
    if evidence.proposal_expectancy_delta is None:
        missing.append("proposal_expectancy_missing")
    if evidence.snapshot_expectancy_delta is None:
        missing.append("snapshot_expectancy_missing")
    if evidence.proposal_with_crowd_count == 0:
        missing.append("proposal_crowding_sample_empty")
    if evidence.snapshot_with_crowd_count == 0:
        missing.append("snapshot_crowding_sample_empty")
    if not evidence.snapshot_generation_id:
        missing.append("snapshot_generation_missing")
    if not evidence.configuration_digest:
        missing.append("configuration_digest_missing")
    if evidence.seed is None:
        missing.append("seed_missing")
    buckets = {item for item in evidence.regime_buckets if item != "unknown"}
    if len(buckets) < 2:
        missing.append("regime_diversity_insufficient")
    if missing:
        return FundingOiEvidenceResult(
            status="insufficient_evidence",
            reasons=tuple(missing),
        )

    assert evidence.proposal_expectancy_delta is not None
    assert evidence.snapshot_expectancy_delta is not None
    failed: list[str] = []
    if evidence.proposal_expectancy_delta < 0:
        failed.append("proposal_expectancy_delta_negative")
    if evidence.snapshot_expectancy_delta < 0:
        failed.append("snapshot_expectancy_delta_negative")
    if failed:
        return FundingOiEvidenceResult(status="failed", reasons=tuple(failed))
    return FundingOiEvidenceResult(status="qualified")


def _nearest_rank(values: list[Decimal], percentile: Decimal) -> Decimal:
    rank = max(
        1,
        int(
            (percentile * Decimal(len(values))).to_integral_value(
                rounding=ROUND_CEILING
            )
        ),
    )
    return values[rank - 1]


def _validate_parameters(
    window_days: int,
    low: Decimal,
    high: Decimal,
    oi_hours: int,
) -> None:
    if window_days < 1:
        raise ValueError("funding_window_days must be positive")
    if not Decimal("0") < low < Decimal("0.5"):
        raise ValueError("funding_low_percentile must be between 0 and 0.5")
    if not Decimal("0.5") < high < Decimal("1"):
        raise ValueError("funding_high_percentile must be between 0.5 and 1")
    if low >= high:
        raise ValueError("funding percentiles must be ordered")
    if oi_hours < 1:
        raise ValueError("oi_lookback_hours must be positive")


def _unavailable(
    as_of: datetime,
    reason: str,
    funding_point_count: int = 0,
) -> FundingOiCrowdingClassification:
    return FundingOiCrowdingClassification(
        state="unavailable",
        as_of=as_of,
        funding_point_count=funding_point_count,
        reason=reason,
    )


__all__ = [
    "CrowdingState",
    "FundingOiCrowdingClassification",
    "FundingOiEvidenceInput",
    "FundingOiEvidenceResult",
    "RegimeBucket",
    "classify_funding_oi_crowding",
    "crowding_would_block",
    "qualify_funding_oi_evidence",
]
