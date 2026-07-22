"""Normalized derivatives market-data contracts.

The models in this module form the trust boundary between exchange adapters
and later runtime/snapshot consumers.  Raw ccxt dictionaries must be mapped
into these immutable values before leaving an adapter.

Related Requirements:
- FR-016: Binance Integration
- FR-019: Exchange Abstraction
- FR-046: Funding and Open-Interest Context
- NFR-011: Credential and Data Boundary Safety
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self


class DerivativesDataError(Exception):
    """Base error for normalized derivatives-data failures."""

    code = "derivatives_data_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or type(self).code


class DerivativesDataNotSupportedError(DerivativesDataError):
    """Raised when an exchange does not implement derivatives context data."""

    code = "unsupported_venue"


class DerivativesDataValidationError(DerivativesDataError):
    """Raised when an exchange payload cannot satisfy the normalized contract."""

    code = "invalid_payload"


class DerivativesDataContiguityError(DerivativesDataValidationError):
    """Raised when a history contains a missing or irregular expected point."""

    code = "timestamp_gap"


class UnsupportedFundingIntervalError(DerivativesDataValidationError):
    """Raised when funding observations are not on the supported 8h grid."""

    code = "unsupported_interval"


class SeriesKind(str, Enum):
    """Normalized derivatives series identifiers."""

    FUNDING = "funding"
    OPEN_INTEREST = "open_interest"


class SeriesStatus(str, Enum):
    """Stable availability states exposed to consumers and telemetry."""

    FRESH = "fresh"
    CACHED = "cached"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    UNSUPPORTED_INTERVAL = "unsupported_interval"


DerivativesErrorCode = Literal[
    "authentication_unexpected",
    "circuit_open",
    "deadline_exceeded",
    "derivatives_data_error",
    "internal_error",
    "invalid_payload",
    "network_transient",
    "rate_limited",
    "request_budget_exhausted",
    "remote_5xx",
    "timestamp_gap",
    "unsupported_interval",
    "unsupported_venue",
    "venue_unavailable",
]

UnmetReason = Literal[
    "funding_required",
    "funding_min_points",
    "funding_max_age",
    "open_interest_required",
    "open_interest_min_points",
    "open_interest_max_age",
]


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _finite_decimal(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("numeric value must be finite")
    return value


class _FrozenDerivativesModel(BaseModel):
    """Shared immutability configuration for derivatives domain values."""

    model_config = ConfigDict(frozen=True)


class FundingRate(_FrozenDerivativesModel):
    """One settled funding-rate observation."""

    symbol: str = Field(min_length=1)
    timestamp: datetime
    rate: Decimal

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("symbol must not contain surrounding whitespace")
        return value

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: datetime) -> datetime:
        normalized = _as_utc(value)
        assert normalized is not None
        return normalized

    @field_validator("rate")
    @classmethod
    def _validate_rate(cls, value: Decimal) -> Decimal:
        return _finite_decimal(value)


class CurrentFundingRate(_FrozenDerivativesModel):
    """Current and, when available, predicted funding-rate view."""

    symbol: str = Field(min_length=1)
    observed_at: datetime
    rate: Decimal
    predicted_rate: Decimal | None = None
    next_funding_at: datetime | None = None
    interval_hours: int | None = Field(default=None, gt=0)

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("symbol must not contain surrounding whitespace")
        return value

    @field_validator("observed_at", "next_funding_at")
    @classmethod
    def _validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)

    @field_validator("rate", "predicted_rate")
    @classmethod
    def _validate_rates(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return _finite_decimal(value)


class OpenInterestPoint(_FrozenDerivativesModel):
    """One normalized open-interest observation."""

    symbol: str = Field(min_length=1)
    timestamp: datetime
    open_interest: Decimal = Field(ge=0)
    open_interest_value: Decimal | None = Field(default=None, ge=0)

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("symbol must not contain surrounding whitespace")
        return value

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: datetime) -> datetime:
        normalized = _as_utc(value)
        assert normalized is not None
        return normalized

    @field_validator("open_interest", "open_interest_value")
    @classmethod
    def _validate_values(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return _finite_decimal(value)


class OpenInterestHistory(_FrozenDerivativesModel):
    """OI history plus explicit request and venue-retention coverage metadata."""

    symbol: str = Field(min_length=1)
    timeframe: Literal["1h"] = "1h"
    requested_since: datetime | None = None
    requested_until: datetime | None = None
    actual_since: datetime | None = None
    actual_until: datetime | None = None
    truncated_at_venue_retention: bool = False
    points: tuple[OpenInterestPoint, ...] = ()

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("symbol must not contain surrounding whitespace")
        return value

    @field_validator(
        "requested_since",
        "requested_until",
        "actual_since",
        "actual_until",
    )
    @classmethod
    def _validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)

    @model_validator(mode="after")
    def _validate_history(self) -> Self:
        if (
            self.requested_since is not None
            and self.requested_until is not None
            and self.requested_until < self.requested_since
        ):
            raise ValueError("requested_until must be on or after requested_since")

        timestamps = [point.timestamp for point in self.points]
        if any(point.symbol != self.symbol for point in self.points):
            raise ValueError("all points must use the history symbol")
        if any(
            current <= previous
            for previous, current in zip(timestamps, timestamps[1:], strict=False)
        ):
            raise ValueError("points must be strictly chronological and unique")

        if self.points:
            if self.actual_since != self.points[0].timestamp:
                raise ValueError("actual_since must equal the first point timestamp")
            if self.actual_until != self.points[-1].timestamp:
                raise ValueError("actual_until must equal the last point timestamp")
        elif self.actual_since is not None or self.actual_until is not None:
            raise ValueError("empty histories cannot declare actual bounds")

        if self.truncated_at_venue_retention and (
            self.requested_since is None or self.actual_since is None
        ):
            raise ValueError(
                "retention truncation requires requested and actual starts"
            )
        if (
            self.truncated_at_venue_retention
            and self.actual_since is not None
            and self.requested_since is not None
            and self.actual_since <= self.requested_since
        ):
            raise ValueError("retention truncation requires a shortened prefix")
        if (
            self.actual_since is not None
            and self.requested_since is not None
            and self.actual_since < self.requested_since
        ):
            raise ValueError("actual history cannot begin before requested_since")
        if (
            self.actual_until is not None
            and self.requested_until is not None
            and self.actual_until > self.requested_until
        ):
            raise ValueError("actual history cannot end after requested_until")
        return self


class SeriesAvailability(_FrozenDerivativesModel):
    """Consumer-safe availability metadata for one normalized series."""

    series: SeriesKind
    status: SeriesStatus
    data_timestamp: datetime | None = None
    fetched_at: datetime | None = None
    age_seconds: float | None = Field(default=None, ge=0)
    from_cache: bool = False
    point_count: int = Field(default=0, ge=0)
    truncated_at_venue_retention: bool = False
    error_code: DerivativesErrorCode | None = None

    @field_validator("data_timestamp", "fetched_at")
    @classmethod
    def _normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)

    @model_validator(mode="after")
    def _validate_coherence(self) -> Self:
        if self.status in {SeriesStatus.FRESH, SeriesStatus.CACHED}:
            if self.point_count < 1 or self.data_timestamp is None:
                raise ValueError("available status requires normalized points")
            if self.age_seconds is None:
                raise ValueError("available status requires age_seconds")
        elif self.status is SeriesStatus.STALE:
            if self.data_timestamp is None or self.age_seconds is None:
                raise ValueError("stale status requires last-known age metadata")
        elif self.point_count or self.data_timestamp is not None:
            raise ValueError("unavailable status cannot expose points")
        if self.series is SeriesKind.FUNDING and self.truncated_at_venue_retention:
            raise ValueError("retention truncation applies only to open interest")
        return self


class MarketContextRequirements(_FrozenDerivativesModel):
    """Typed, globally bounded strategy requirements for derivatives context."""

    funding_required: bool = False
    funding_min_points: int = Field(default=1, ge=1)
    funding_max_age_seconds: int = Field(default=32400, gt=0, le=32400)
    open_interest_required: bool = False
    open_interest_min_points: int = Field(default=1, ge=1)
    open_interest_max_age_seconds: int = Field(default=7200, gt=0, le=7200)

    @property
    def requires_any(self) -> bool:
        return self.funding_required or self.open_interest_required


class MarketContext(_FrozenDerivativesModel):
    """No-look-ahead Funding/OI view at one OHLCV decision boundary."""

    symbol: str = Field(min_length=1)
    as_of: datetime
    funding: tuple[FundingRate, ...] = ()
    open_interest: tuple[OpenInterestPoint, ...] = ()
    funding_availability: SeriesAvailability
    open_interest_availability: SeriesAvailability
    predicted_funding_rate: Decimal | None = None
    predicted_funding_observed_at: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def _context_symbol(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("symbol must not contain surrounding whitespace")
        return value

    @field_validator("as_of", "predicted_funding_observed_at")
    @classmethod
    def _context_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)

    @field_validator("predicted_funding_rate")
    @classmethod
    def _context_predicted_rate(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else _finite_decimal(value)

    @model_validator(mode="after")
    def _validate_context(self) -> Self:
        if self.funding_availability.series is not SeriesKind.FUNDING:
            raise ValueError("funding availability must describe funding")
        if self.open_interest_availability.series is not SeriesKind.OPEN_INTEREST:
            raise ValueError("open-interest availability must describe open interest")
        for funding_record in self.funding:
            if funding_record.symbol != self.symbol:
                raise ValueError("all context records must use the context symbol")
            if funding_record.timestamp > self.as_of:
                raise ValueError("context records cannot be later than as_of")
        for oi_record in self.open_interest:
            if oi_record.symbol != self.symbol:
                raise ValueError("all context records must use the context symbol")
            if oi_record.timestamp > self.as_of:
                raise ValueError("context records cannot be later than as_of")
        _validate_records(self.funding)
        _validate_records(self.open_interest)
        if (self.predicted_funding_rate is None) != (
            self.predicted_funding_observed_at is None
        ):
            raise ValueError("predicted funding value and timestamp must be paired")
        return self


class SeriesSnapshot(_FrozenDerivativesModel):
    """Immutable last-known series state owned by the runtime service."""

    venue: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    series: SeriesKind
    records: tuple[FundingRate | OpenInterestPoint, ...] = ()
    fetched_at: datetime
    status: SeriesStatus = SeriesStatus.FRESH
    from_cache: bool = False
    error_code: DerivativesErrorCode | None = None
    truncated_at_venue_retention: bool = False
    predicted_funding_rate: Decimal | None = None
    predicted_funding_observed_at: datetime | None = None

    @field_validator("symbol", "venue")
    @classmethod
    def _snapshot_names(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("names must not contain surrounding whitespace")
        return value

    @field_validator("fetched_at", "predicted_funding_observed_at")
    @classmethod
    def _snapshot_timestamps(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)

    @field_validator("predicted_funding_rate")
    @classmethod
    def _snapshot_predicted_rate(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else _finite_decimal(value)

    @model_validator(mode="after")
    def _validate_snapshot(self) -> Self:
        _validate_records(self.records)
        for record in self.records:
            if record.symbol != self.symbol:
                raise ValueError("all snapshot records must use the snapshot symbol")
            if self.series is SeriesKind.FUNDING and not isinstance(
                record, FundingRate
            ):
                raise ValueError("funding snapshots accept funding records only")
            if self.series is SeriesKind.OPEN_INTEREST and not isinstance(
                record, OpenInterestPoint
            ):
                raise ValueError("open-interest snapshots accept OI records only")
        if (
            self.status
            in {
                SeriesStatus.FRESH,
                SeriesStatus.CACHED,
                SeriesStatus.STALE,
            }
            and not self.records
        ):
            raise ValueError("available snapshot status requires records")
        if (
            self.status
            in {
                SeriesStatus.UNAVAILABLE,
                SeriesStatus.UNSUPPORTED,
                SeriesStatus.UNSUPPORTED_INTERVAL,
            }
            and self.records
        ):
            raise ValueError("unavailable snapshot status cannot contain records")
        if self.series is SeriesKind.FUNDING and self.truncated_at_venue_retention:
            raise ValueError("retention truncation applies only to open interest")
        if (self.predicted_funding_rate is None) != (
            self.predicted_funding_observed_at is None
        ):
            raise ValueError("predicted funding value and timestamp must be paired")
        if self.series is SeriesKind.OPEN_INTEREST and (
            self.predicted_funding_rate is not None
            or self.predicted_funding_observed_at is not None
        ):
            raise ValueError("predicted funding applies only to funding snapshots")
        return self


class ContextEvaluation(_FrozenDerivativesModel):
    """Context plus deterministic requirement decision."""

    context: MarketContext | None = None
    requirements_satisfied: bool
    unmet_reasons: tuple[UnmetReason, ...] = ()

    @model_validator(mode="after")
    def _evaluation_coherence(self) -> Self:
        if self.requirements_satisfied == bool(self.unmet_reasons):
            raise ValueError("satisfaction must be the inverse of unmet reasons")
        return self


class SeriesRefreshOutcome(_FrozenDerivativesModel):
    """Safe per-series result used by refresh summaries and tests."""

    symbol: str
    series: SeriesKind
    status: SeriesStatus
    error_code: DerivativesErrorCode | None = None
    attempt_count: int = Field(default=0, ge=0)
    circuit_state: Literal["closed", "open", "half_open"] = "closed"
    from_cache: bool = False


class RefreshSummary(_FrozenDerivativesModel):
    """Bounded, serialization-safe cycle refresh summary."""

    cycle_id: str
    requested_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    cached_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    cancelled_count: int = Field(ge=0)
    outcomes: tuple[SeriesRefreshOutcome, ...] = ()


@runtime_checkable
class DerivativesDataSource(Protocol):
    """Narrow public-data port accepted by the runtime context service."""

    @property
    def name(self) -> str: ...

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def get_funding_rate(self, symbol: str) -> CurrentFundingRate: ...

    async def get_funding_rate_history(
        self,
        symbol: str,
        since: int,
        limit: int = 1000,
        *,
        until: int | None = None,
    ) -> list[FundingRate]: ...

    async def get_open_interest(self, symbol: str) -> OpenInterestPoint: ...

    async def get_open_interest_history(
        self,
        symbol: str,
        timeframe: Literal["1h"] = "1h",
        since: int | None = None,
        limit: int = 500,
        *,
        until: int | None = None,
    ) -> OpenInterestHistory: ...


def _validate_records(
    records: tuple[FundingRate | OpenInterestPoint, ...],
) -> None:
    timestamps = [record.timestamp for record in records]
    if any(
        current <= previous
        for previous, current in zip(timestamps, timestamps[1:], strict=False)
    ):
        raise ValueError("records must be strictly chronological and unique")


__all__ = [
    "CurrentFundingRate",
    "DerivativesDataContiguityError",
    "DerivativesDataError",
    "DerivativesDataNotSupportedError",
    "DerivativesDataValidationError",
    "DerivativesDataSource",
    "DerivativesErrorCode",
    "ContextEvaluation",
    "FundingRate",
    "MarketContext",
    "MarketContextRequirements",
    "OpenInterestHistory",
    "OpenInterestPoint",
    "RefreshSummary",
    "SeriesAvailability",
    "SeriesKind",
    "SeriesRefreshOutcome",
    "SeriesSnapshot",
    "SeriesStatus",
    "UnmetReason",
    "UnsupportedFundingIntervalError",
]
