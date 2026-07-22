"""Tests for pure derivatives MarketContext construction."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.exchange.derivatives import (
    FundingRate,
    MarketContextRequirements,
    OpenInterestPoint,
    SeriesKind,
    SeriesSnapshot,
    SeriesStatus,
)
from src.strategy.market_context import MarketContextBuilder

UTC = timezone.utc
AS_OF = datetime(2026, 7, 19, 0, tzinfo=UTC)


def _funding(*ages: float, cached: bool = False) -> SeriesSnapshot:
    records = tuple(
        FundingRate(
            symbol="BTC/USDT",
            timestamp=AS_OF - timedelta(hours=age),
            rate=Decimal("0.0001"),
        )
        for age in sorted(ages, reverse=True)
    )
    return SeriesSnapshot(
        venue="binance",
        symbol="BTC/USDT",
        series=SeriesKind.FUNDING,
        records=records,
        fetched_at=AS_OF,
        from_cache=cached,
    )


def _oi(*ages: float, truncated: bool = False) -> SeriesSnapshot:
    records = tuple(
        OpenInterestPoint(
            symbol="BTC/USDT",
            timestamp=AS_OF - timedelta(hours=age),
            open_interest=Decimal("100"),
        )
        for age in sorted(ages, reverse=True)
    )
    return SeriesSnapshot(
        venue="binance",
        symbol="BTC/USDT",
        series=SeriesKind.OPEN_INTEREST,
        records=records,
        fetched_at=AS_OF,
        truncated_at_venue_retention=truncated,
    )


def test_builder_accepts_exact_hard_age_and_removes_just_expired_data() -> None:
    builder = MarketContextBuilder()
    exact = builder.build(
        "BTC/USDT",
        as_of=AS_OF,
        funding=_funding(9),
        open_interest=_oi(2),
    ).context
    assert exact is not None
    assert len(exact.funding) == 1
    assert len(exact.open_interest) == 1

    expired = builder.build(
        "BTC/USDT",
        as_of=AS_OF,
        funding=_funding(9 + 1 / 3600),
        open_interest=_oi(2 + 1 / 3600),
    ).context
    assert expired is not None
    assert expired.funding == ()
    assert expired.open_interest == ()
    assert expired.funding_availability.status is SeriesStatus.STALE
    assert expired.open_interest_availability.status is SeriesStatus.STALE


def test_builder_excludes_future_records_and_preserves_partial_context() -> None:
    future = SeriesSnapshot(
        venue="binance",
        symbol="BTC/USDT",
        series="funding",
        records=(
            FundingRate(
                symbol="BTC/USDT",
                timestamp=AS_OF + timedelta(seconds=1),
                rate=Decimal("0.1"),
            ),
        ),
        fetched_at=AS_OF,
    )
    context = (
        MarketContextBuilder()
        .build(
            "BTC/USDT",
            as_of=AS_OF,
            funding=future,
            open_interest=_oi(1),
        )
        .context
    )
    assert context is not None
    assert context.funding == ()
    assert len(context.open_interest) == 1


def test_builder_projects_cached_provenance_and_retention() -> None:
    context = (
        MarketContextBuilder()
        .build(
            "BTC/USDT",
            as_of=AS_OF,
            funding=_funding(8, cached=True),
            open_interest=_oi(1, truncated=True),
        )
        .context
    )
    assert context is not None
    assert context.funding_availability.status is SeriesStatus.CACHED
    assert context.funding_availability.from_cache is True
    assert context.open_interest_availability.truncated_at_venue_retention is True


def test_requirements_use_stable_funding_then_oi_reason_order() -> None:
    evaluation = MarketContextBuilder().build(
        "BTC/USDT",
        as_of=AS_OF,
        funding=None,
        open_interest=None,
        requirements=MarketContextRequirements(
            funding_required=True,
            open_interest_required=True,
        ),
    )
    assert evaluation.requirements_satisfied is False
    assert evaluation.unmet_reasons == (
        "funding_required",
        "open_interest_required",
    )


def test_equal_normalized_inputs_produce_byte_equivalent_context() -> None:
    builder = MarketContextBuilder()
    first = builder.build(
        "BTC/USDT", as_of=AS_OF, funding=_funding(8), open_interest=_oi(1)
    )
    second = builder.build(
        "BTC/USDT", as_of=AS_OF, funding=_funding(8), open_interest=_oi(1)
    )
    assert first.model_dump_json() == second.model_dump_json()
