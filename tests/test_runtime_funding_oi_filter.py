from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import perf_counter

import pytest

from src.exchange.derivatives import (
    FundingRate,
    MarketContext,
    OpenInterestPoint,
    SeriesAvailability,
    SeriesKind,
    SeriesStatus,
)
from src.runtime.funding_oi_filter import (
    FundingOiEvidenceInput,
    classify_funding_oi_crowding,
    crowding_would_block,
    qualify_funding_oi_evidence,
)

AS_OF = datetime(2026, 7, 22, 16, tzinfo=timezone.utc)


def _context(
    *,
    current_rate: str,
    oi_latest: str = "125",
    oi_reference: str = "100",
    funding_points: int = 90,
    oi_points: int = 2,
) -> MarketContext:
    funding = []
    for index in range(funding_points):
        rate = Decimal("0")
        if index == funding_points - 1:
            rate = Decimal(current_rate)
        funding.append(
            FundingRate(
                symbol="BTC/USDT",
                timestamp=AS_OF - timedelta(hours=8 * (funding_points - 1 - index)),
                rate=rate,
            )
        )
    if oi_points == 2:
        oi = [
            OpenInterestPoint(
                symbol="BTC/USDT",
                timestamp=AS_OF - timedelta(hours=24),
                open_interest=Decimal(oi_reference),
            ),
            OpenInterestPoint(
                symbol="BTC/USDT",
                timestamp=AS_OF,
                open_interest=Decimal(oi_latest),
            ),
        ]
    else:
        oi = [
            OpenInterestPoint(
                symbol="BTC/USDT",
                timestamp=AS_OF - timedelta(hours=oi_points - 1 - index),
                open_interest=(
                    Decimal(oi_latest)
                    if index == oi_points - 1
                    else Decimal(oi_reference)
                ),
            )
            for index in range(oi_points)
        ]
    return MarketContext(
        symbol="BTC/USDT",
        as_of=AS_OF,
        funding=tuple(funding),
        open_interest=tuple(oi),
        funding_availability=SeriesAvailability(
            series=SeriesKind.FUNDING,
            status=SeriesStatus.FRESH,
            data_timestamp=funding[-1].timestamp,
            fetched_at=AS_OF,
            age_seconds=0,
            point_count=len(funding),
        ),
        open_interest_availability=SeriesAvailability(
            series=SeriesKind.OPEN_INTEREST,
            status=SeriesStatus.FRESH,
            data_timestamp=oi[-1].timestamp,
            fetched_at=AS_OF,
            age_seconds=0,
            point_count=len(oi),
        ),
    )


def test_classifies_crowded_long_and_side_match() -> None:
    result = classify_funding_oi_crowding(_context(current_rate="0.01"))
    assert result.state == "crowded_long"
    assert result.funding_point_count == 90
    assert result.oi_delta == Decimal("25")
    assert crowding_would_block(result.state, "long") is True
    assert crowding_would_block(result.state, "short") is False


def test_classifies_crowded_short() -> None:
    result = classify_funding_oi_crowding(_context(current_rate="-0.01"))
    assert result.state == "crowded_short"
    assert crowding_would_block(result.state, "short") is True


def test_funding_extreme_without_rising_oi_is_neutral() -> None:
    result = classify_funding_oi_crowding(
        _context(current_rate="0.01", oi_latest="100", oi_reference="100")
    )
    assert result.state == "neutral"


def test_short_funding_window_is_explicitly_unavailable() -> None:
    result = classify_funding_oi_crowding(
        _context(current_rate="0.01", funding_points=89)
    )
    assert result.state == "unavailable"
    assert result.reason == "funding_window_too_short"


def test_missing_context_requires_and_preserves_explicit_as_of() -> None:
    result = classify_funding_oi_crowding(None, as_of=AS_OF)
    assert result.state == "unavailable"
    assert result.as_of == AS_OF
    with pytest.raises(ValueError, match="as_of is required"):
        classify_funding_oi_crowding(None)


def test_invalid_threshold_envelope_fails_loudly() -> None:
    with pytest.raises(ValueError, match="low_percentile"):
        classify_funding_oi_crowding(
            _context(current_rate="0.01"),
            funding_low_percentile=Decimal("0.75"),
        )


def test_classification_is_deterministic_and_ignores_predicted_funding() -> None:
    context = _context(current_rate="0.01")
    with_prediction = context.model_copy(
        update={
            "predicted_funding_rate": Decimal("-0.25"),
            "predicted_funding_observed_at": AS_OF,
        }
    )

    first = classify_funding_oi_crowding(context)
    second = classify_funding_oi_crowding(with_prediction)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_evidence_requires_both_lanes_identity_samples_and_diversity() -> None:
    result = qualify_funding_oi_evidence(FundingOiEvidenceInput())
    assert result.status == "insufficient_evidence"
    assert "snapshot_generation_missing" in result.reasons
    assert "regime_diversity_insufficient" in result.reasons


def test_evidence_rejects_unpinned_identity_and_unknown_regime_label() -> None:
    with pytest.raises(ValueError):
        FundingOiEvidenceInput(snapshot_generation_id="abc123")
    with pytest.raises(ValueError):
        FundingOiEvidenceInput(regime_buckets=("bull", "invented"))  # type: ignore[arg-type]


def test_negative_delta_fails_and_non_negative_dual_lane_qualifies() -> None:
    base = {
        "proposal_expectancy_delta": Decimal("0.1"),
        "proposal_with_crowd_count": 12,
        "snapshot_expectancy_delta": Decimal("0"),
        "snapshot_with_crowd_count": 20,
        "regime_buckets": ("bull", "bear", "unknown"),
        "snapshot_generation_id": "a" * 64,
        "configuration_digest": "f" * 64,
        "seed": 7,
    }
    qualified = qualify_funding_oi_evidence(FundingOiEvidenceInput(**base))
    assert qualified.qualified is True

    failed = qualify_funding_oi_evidence(
        FundingOiEvidenceInput(**{**base, "snapshot_expectancy_delta": Decimal("-0.1")})
    )
    assert failed.status == "failed"
    assert failed.reasons == ("snapshot_expectancy_delta_negative",)


def test_classifier_p95_is_within_five_milliseconds_at_design_envelope() -> None:
    context = _context(current_rate="0.01", funding_points=90, oi_points=500)
    samples = []
    for _ in range(100):
        started = perf_counter()
        result = classify_funding_oi_crowding(context)
        samples.append(perf_counter() - started)

    assert result.state == "crowded_long"
    p95 = sorted(samples)[94]
    print(f"funding_oi_classifier samples=100 p95={p95:.6f}s")
    assert p95 <= 0.005, f"classifier p95={p95:.6f}s exceeds 0.005s"
