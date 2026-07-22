"""Pure no-look-ahead construction and evaluation of derivatives context."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Protocol

from src.exchange.derivatives import (
    ContextEvaluation,
    MarketContext,
    MarketContextRequirements,
    SeriesAvailability,
    SeriesKind,
    SeriesSnapshot,
    SeriesStatus,
    UnmetReason,
)

FUNDING_HARD_MAX_AGE_SECONDS = 9 * 60 * 60
OPEN_INTEREST_HARD_MAX_AGE_SECONDS = 2 * 60 * 60


class MarketContextProvider(Protocol):
    """Read-only context seam consumed by the proposal engine."""

    def context_for(
        self,
        symbol: str,
        *,
        as_of: datetime,
        requirements: MarketContextRequirements | None = None,
    ) -> ContextEvaluation: ...


class MarketContextBuilder:
    """Build bounded context from immutable cache or snapshot inputs."""

    def build(
        self,
        symbol: str,
        *,
        as_of: datetime,
        funding: SeriesSnapshot | None,
        open_interest: SeriesSnapshot | None,
        requirements: MarketContextRequirements | None = None,
    ) -> ContextEvaluation:
        normalized_as_of = _as_utc(as_of)
        funding_records, funding_availability = self._project(
            symbol,
            as_of=normalized_as_of,
            snapshot=funding,
            series=SeriesKind.FUNDING,
            hard_max_age_seconds=FUNDING_HARD_MAX_AGE_SECONDS,
        )
        oi_records, oi_availability = self._project(
            symbol,
            as_of=normalized_as_of,
            snapshot=open_interest,
            series=SeriesKind.OPEN_INTEREST,
            hard_max_age_seconds=OPEN_INTEREST_HARD_MAX_AGE_SECONDS,
        )

        predicted_rate = None
        predicted_at = None
        if funding is not None and funding.status is SeriesStatus.FRESH:
            predicted_rate = funding.predicted_funding_rate
            predicted_at = funding.predicted_funding_observed_at

        context = MarketContext(
            symbol=symbol,
            as_of=normalized_as_of,
            funding=funding_records,
            open_interest=oi_records,
            funding_availability=funding_availability,
            open_interest_availability=oi_availability,
            predicted_funding_rate=predicted_rate,
            predicted_funding_observed_at=predicted_at,
        )
        return self.evaluate(context, requirements)

    def evaluate(
        self,
        context: MarketContext | None,
        requirements: MarketContextRequirements | None,
    ) -> ContextEvaluation:
        """Apply requirements in one stable, testable reason order."""
        if requirements is None:
            return ContextEvaluation(
                context=context,
                requirements_satisfied=True,
            )

        reasons: list[UnmetReason] = []
        if requirements.funding_required:
            availability = None if context is None else context.funding_availability
            points = 0 if context is None else len(context.funding)
            if availability is None or availability.status not in {
                SeriesStatus.FRESH,
                SeriesStatus.CACHED,
            }:
                reasons.append("funding_required")
            elif points < requirements.funding_min_points:
                reasons.append("funding_min_points")
            elif (
                availability.age_seconds is None
                or availability.age_seconds > requirements.funding_max_age_seconds
            ):
                reasons.append("funding_max_age")

        if requirements.open_interest_required:
            availability = (
                None if context is None else context.open_interest_availability
            )
            points = 0 if context is None else len(context.open_interest)
            if availability is None or availability.status not in {
                SeriesStatus.FRESH,
                SeriesStatus.CACHED,
            }:
                reasons.append("open_interest_required")
            elif points < requirements.open_interest_min_points:
                reasons.append("open_interest_min_points")
            elif (
                availability.age_seconds is None
                or availability.age_seconds > requirements.open_interest_max_age_seconds
            ):
                reasons.append("open_interest_max_age")

        return ContextEvaluation(
            context=context,
            requirements_satisfied=not reasons,
            unmet_reasons=tuple(reasons),
        )

    def _project(
        self,
        symbol: str,
        *,
        as_of: datetime,
        snapshot: SeriesSnapshot | None,
        series: SeriesKind,
        hard_max_age_seconds: int,
    ) -> tuple[tuple, SeriesAvailability]:
        if snapshot is None or snapshot.status in {
            SeriesStatus.UNAVAILABLE,
            SeriesStatus.UNSUPPORTED,
            SeriesStatus.UNSUPPORTED_INTERVAL,
        }:
            status = SeriesStatus.UNAVAILABLE if snapshot is None else snapshot.status
            return (), SeriesAvailability(
                series=series,
                status=status,
                fetched_at=None if snapshot is None else snapshot.fetched_at,
                from_cache=False if snapshot is None else snapshot.from_cache,
                error_code=None if snapshot is None else snapshot.error_code,
                truncated_at_venue_retention=(
                    False if snapshot is None else snapshot.truncated_at_venue_retention
                ),
            )
        if snapshot.symbol != symbol or snapshot.series is not series:
            raise ValueError("snapshot symbol and series must match the request")

        records = tuple(
            record for record in snapshot.records if record.timestamp <= as_of
        )
        _validate_records(records)
        if not records:
            return (), SeriesAvailability(
                series=series,
                status=SeriesStatus.UNAVAILABLE,
                fetched_at=snapshot.fetched_at,
                from_cache=snapshot.from_cache,
                error_code=snapshot.error_code,
                truncated_at_venue_retention=snapshot.truncated_at_venue_retention,
            )

        tail = records[-1].timestamp
        age_seconds = max(0.0, (as_of - tail).total_seconds())
        if age_seconds > hard_max_age_seconds:
            return (), SeriesAvailability(
                series=series,
                status=SeriesStatus.STALE,
                data_timestamp=tail,
                fetched_at=snapshot.fetched_at,
                age_seconds=age_seconds,
                from_cache=True,
                point_count=0,
                truncated_at_venue_retention=snapshot.truncated_at_venue_retention,
                error_code=snapshot.error_code,
            )

        status = snapshot.status
        if status is SeriesStatus.FRESH and snapshot.from_cache:
            status = SeriesStatus.CACHED
        return records, SeriesAvailability(
            series=series,
            status=status,
            data_timestamp=tail,
            fetched_at=snapshot.fetched_at,
            age_seconds=age_seconds,
            from_cache=snapshot.from_cache,
            point_count=len(records),
            truncated_at_venue_retention=snapshot.truncated_at_venue_retention,
            error_code=snapshot.error_code,
        )


def market_context_prompt_json(context: MarketContext | None) -> str:
    """Render only normalized allowlisted fields for prompt placeholders."""
    if context is None:
        return "null"
    payload = context.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validate_records(records: tuple) -> None:
    timestamps = [record.timestamp for record in records]
    if any(
        current <= previous
        for previous, current in zip(timestamps, timestamps[1:], strict=False)
    ):
        raise ValueError("records must be strictly chronological and unique")


__all__ = [
    "FUNDING_HARD_MAX_AGE_SECONDS",
    "MarketContextBuilder",
    "MarketContextProvider",
    "OPEN_INTEREST_HARD_MAX_AGE_SECONDS",
    "market_context_prompt_json",
]
