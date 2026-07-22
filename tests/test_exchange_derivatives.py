"""Tests for normalized derivatives market-data contracts."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.exchange.derivatives import (
    ContextEvaluation,
    CurrentFundingRate,
    DerivativesDataContiguityError,
    DerivativesDataError,
    DerivativesDataNotSupportedError,
    DerivativesDataValidationError,
    FundingRate,
    MarketContextRequirements,
    OpenInterestHistory,
    OpenInterestPoint,
    SeriesAvailability,
    SeriesKind,
    SeriesSnapshot,
    UnsupportedFundingIntervalError,
)

UTC = timezone.utc
START = datetime(2026, 7, 1, tzinfo=UTC)


def _oi_point(
    hours: int,
    *,
    symbol: str = "BTC/USDT",
    amount: str = "100",
) -> OpenInterestPoint:
    return OpenInterestPoint(
        symbol=symbol,
        timestamp=START + timedelta(hours=hours),
        open_interest=Decimal(amount),
        open_interest_value=Decimal("10000000"),
    )


def test_funding_rate_is_frozen_and_allows_signed_decimal() -> None:
    point = FundingRate(
        symbol="BTC/USDT",
        timestamp=START,
        rate=Decimal("-0.0001"),
    )

    assert point.rate == Decimal("-0.0001")
    with pytest.raises(ValidationError):
        point.rate = Decimal("0")  # type: ignore[misc]


def test_derivatives_timestamp_is_normalized_to_utc() -> None:
    point = FundingRate(
        symbol="BTC/USDT",
        timestamp=datetime(2026, 7, 1, 9, tzinfo=timezone(timedelta(hours=9))),
        rate=Decimal("0.0001"),
    )

    assert point.timestamp == START
    assert point.timestamp.tzinfo is UTC


@pytest.mark.parametrize(
    "model_factory",
    [
        lambda: FundingRate(
            symbol="BTC/USDT", timestamp=datetime(2026, 7, 1), rate=Decimal("0")
        ),
        lambda: OpenInterestPoint(
            symbol="BTC/USDT",
            timestamp=datetime(2026, 7, 1),
            open_interest=Decimal("1"),
        ),
    ],
)
def test_naive_derivatives_timestamps_are_rejected(
    model_factory: Callable[[], object],
) -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        model_factory()


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_funding_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError, match="finite"):
        FundingRate(symbol="BTC/USDT", timestamp=START, rate=Decimal(value))


def test_open_interest_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        _oi_point(0, amount="-1")


def test_symbol_cannot_be_empty_or_padded() -> None:
    with pytest.raises(ValidationError):
        FundingRate(symbol="", timestamp=START, rate=Decimal("0"))
    with pytest.raises(ValidationError, match="surrounding whitespace"):
        FundingRate(symbol=" BTC/USDT", timestamp=START, rate=Decimal("0"))


def test_current_funding_validates_optional_fields() -> None:
    current = CurrentFundingRate(
        symbol="BTC/USDT",
        observed_at=START,
        rate=Decimal("0.0001"),
        predicted_rate=Decimal("-0.0002"),
        next_funding_at=START + timedelta(hours=8),
        interval_hours=8,
    )

    assert current.interval_hours == 8
    assert current.predicted_rate == Decimal("-0.0002")


def test_open_interest_history_rejects_duplicate_or_out_of_order_points() -> None:
    first = _oi_point(0)
    with pytest.raises(ValidationError, match="strictly chronological"):
        OpenInterestHistory(
            symbol="BTC/USDT",
            actual_since=first.timestamp,
            actual_until=first.timestamp,
            points=(first, first),
        )


def test_open_interest_history_rejects_mixed_symbols() -> None:
    first = _oi_point(0)
    second = _oi_point(1, symbol="ETH/USDT")
    with pytest.raises(ValidationError, match="history symbol"):
        OpenInterestHistory(
            symbol="BTC/USDT",
            actual_since=first.timestamp,
            actual_until=second.timestamp,
            points=(first, second),
        )


def test_open_interest_history_requires_exact_actual_bounds() -> None:
    first = _oi_point(0)
    second = _oi_point(1)
    with pytest.raises(ValidationError, match="actual_since"):
        OpenInterestHistory(
            symbol="BTC/USDT",
            actual_since=second.timestamp,
            actual_until=second.timestamp,
            points=(first, second),
        )


def test_open_interest_history_exposes_retention_truncation() -> None:
    first = _oi_point(24)
    second = _oi_point(25)
    history = OpenInterestHistory(
        symbol="BTC/USDT",
        requested_since=START,
        requested_until=START + timedelta(hours=48),
        actual_since=first.timestamp,
        actual_until=second.timestamp,
        truncated_at_venue_retention=True,
        points=(first, second),
    )

    assert history.truncated_at_venue_retention is True
    assert history.actual_since == first.timestamp


def test_open_interest_history_rejects_false_retention_truncation() -> None:
    first = _oi_point(0)
    with pytest.raises(ValidationError, match="shortened prefix"):
        OpenInterestHistory(
            symbol="BTC/USDT",
            requested_since=START,
            actual_since=first.timestamp,
            actual_until=first.timestamp,
            truncated_at_venue_retention=True,
            points=(first,),
        )


def test_empty_open_interest_history_has_no_actual_bounds() -> None:
    history = OpenInterestHistory(
        symbol="BTC/USDT",
        requested_since=START,
        requested_until=START + timedelta(hours=1),
    )

    assert history.points == ()
    assert history.actual_since is None
    assert history.actual_until is None


@pytest.mark.parametrize(
    ("error_type", "expected_code"),
    [
        (DerivativesDataError, "derivatives_data_error"),
        (DerivativesDataNotSupportedError, "unsupported_venue"),
        (DerivativesDataValidationError, "invalid_payload"),
        (DerivativesDataContiguityError, "timestamp_gap"),
        (UnsupportedFundingIntervalError, "unsupported_interval"),
    ],
)
def test_derivatives_errors_expose_stable_codes(
    error_type: type[DerivativesDataError], expected_code: str
) -> None:
    assert error_type("failure").code == expected_code


def test_series_snapshot_rejects_mixed_future_or_duplicate_records() -> None:
    funding = FundingRate(symbol="BTC/USDT", timestamp=START, rate=Decimal("0"))
    with pytest.raises(ValidationError, match="funding records only"):
        SeriesSnapshot(
            venue="binance",
            symbol="BTC/USDT",
            series=SeriesKind.FUNDING,
            records=(_oi_point(0),),
            fetched_at=START,
        )
    with pytest.raises(ValidationError, match="strictly chronological"):
        SeriesSnapshot(
            venue="binance",
            symbol="BTC/USDT",
            series=SeriesKind.FUNDING,
            records=(funding, funding),
            fetched_at=START,
        )


def test_series_availability_enforces_status_point_coherence() -> None:
    with pytest.raises(ValidationError, match="requires normalized points"):
        SeriesAvailability(series="funding", status="fresh")
    with pytest.raises(ValidationError, match="cannot expose points"):
        SeriesAvailability(
            series="funding",
            status="unavailable",
            point_count=1,
            data_timestamp=START,
        )


def test_requirements_enforce_global_freshness_ceilings() -> None:
    with pytest.raises(ValidationError):
        MarketContextRequirements(funding_max_age_seconds=32401)
    with pytest.raises(ValidationError):
        MarketContextRequirements(open_interest_max_age_seconds=7201)


def test_context_evaluation_requires_stable_reason_coherence() -> None:
    evaluation = ContextEvaluation(
        context=None,
        requirements_satisfied=False,
        unmet_reasons=("funding_required", "open_interest_required"),
    )
    assert evaluation.unmet_reasons == (
        "funding_required",
        "open_interest_required",
    )
    with pytest.raises(ValidationError, match="inverse"):
        ContextEvaluation(
            context=None,
            requirements_satisfied=True,
            unmet_reasons=("funding_required",),
        )


def test_refresh_contract_serialization_has_no_raw_or_credential_fields() -> None:
    snapshot = SeriesSnapshot(
        venue="binance",
        symbol="BTC/USDT",
        series="open_interest",
        records=(_oi_point(0),),
        fetched_at=START,
    )
    serialized = snapshot.model_dump_json()
    assert "api_key" not in serialized
    assert "secret" not in serialized
    assert "raw" not in serialized
