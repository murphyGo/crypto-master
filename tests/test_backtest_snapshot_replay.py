"""Tests for deterministic Snapshot v1/v2 market-context replay."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.backtest.reproducibility import canonical_configuration_digest
from src.backtest.snapshot import Snapshot, SnapshotMetadata, SnapshotValidationError
from src.backtest.snapshot_replay import SnapshotReplaySource
from src.backtest.snapshot_v2 import (
    SnapshotSeriesMetadata,
    SnapshotV2,
    SnapshotV2Metadata,
    VersionedSnapshot,
    save_snapshot_v2,
)
from src.exchange.derivatives import (
    FundingRate,
    MarketContextRequirements,
    OpenInterestHistory,
    OpenInterestPoint,
    SeriesKind,
    SeriesSnapshot,
    SeriesStatus,
)
from src.models import OHLCV
from src.strategy.market_context import MarketContextBuilder

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _ohlcv(
    count: int = 25, *, close_offset: Decimal = Decimal("0")
) -> tuple[OHLCV, ...]:
    return tuple(
        OHLCV(
            timestamp=START + timedelta(hours=index),
            open=Decimal("100") + close_offset,
            high=Decimal("101") + close_offset,
            low=Decimal("99") + close_offset,
            close=Decimal("100") + close_offset,
            volume=Decimal("10"),
        )
        for index in range(count)
    )


def _series_metadata(
    points: tuple[object, ...],
    *,
    requested_since: datetime,
    requested_until: datetime,
    granularity: str,
    truncated: bool = False,
) -> SnapshotSeriesMetadata:
    timestamps = tuple(point.timestamp for point in points)
    return SnapshotSeriesMetadata(
        fetched_at=START + timedelta(days=3),
        requested_since=requested_since,
        requested_until=requested_until,
        actual_since=timestamps[0] if timestamps else None,
        actual_until=timestamps[-1] if timestamps else None,
        granularity=granularity,
        point_count=len(points),
        truncated_at_venue_retention=truncated,
    )


def _bundle(
    *,
    close_offset: Decimal = Decimal("0"),
    oi_count: int = 25,
) -> SnapshotV2:
    candles = _ohlcv(close_offset=close_offset)
    funding = tuple(
        FundingRate(
            symbol="BTC/USDT",
            timestamp=START + timedelta(hours=8 * index),
            rate=Decimal("0.0001") + Decimal(index) / Decimal("1000000"),
        )
        for index in range(4)
    )
    oi_points = tuple(
        OpenInterestPoint(
            symbol="BTC/USDT",
            timestamp=START + timedelta(hours=index),
            open_interest=Decimal("1000") + index,
            open_interest_value=Decimal("100000") + index,
        )
        for index in range(oi_count)
    )
    end = candles[-1].timestamp
    metadata = SnapshotV2Metadata(
        source="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        created_at=START + timedelta(days=4),
        ohlcv=_series_metadata(
            candles,
            requested_since=START,
            requested_until=end,
            granularity="1h",
        ),
        funding=_series_metadata(
            funding,
            requested_since=START,
            requested_until=end,
            granularity="8h",
        ),
        open_interest=_series_metadata(
            oi_points,
            requested_since=START,
            requested_until=end,
            granularity="1h",
        ),
    )
    return SnapshotV2(
        metadata=metadata,
        ohlcv=candles,
        funding=funding,
        open_interest=OpenInterestHistory(
            symbol="BTC/USDT",
            requested_since=START,
            requested_until=end,
            actual_since=oi_points[0].timestamp,
            actual_until=oi_points[-1].timestamp,
            points=oi_points,
        ),
    )


def _source(tmp_path: Path) -> SnapshotReplaySource:
    save_snapshot_v2(_bundle(), tmp_path)
    return SnapshotReplaySource.from_directory(tmp_path)


def test_v2_source_pins_identity_and_serves_same_bundle(tmp_path: Path) -> None:
    source = _source(tmp_path)

    assert source.schema_version == 2
    assert source.generation_id is not None
    assert source.identity.symbol == "BTC/USDT"
    assert source.identity.timeframe == "1h"
    assert source.ohlcv == _ohlcv()


def test_context_excludes_future_records_and_predicted_funding(tmp_path: Path) -> None:
    source = _source(tmp_path)
    as_of = START + timedelta(hours=9)

    evaluation = source.context_for("BTC/USDT", as_of=as_of)

    assert evaluation.requirements_satisfied
    assert evaluation.context is not None
    assert [point.timestamp for point in evaluation.context.funding] == [
        START,
        START + timedelta(hours=8),
    ]
    assert evaluation.context.open_interest[-1].timestamp == as_of
    assert all(point.timestamp <= as_of for point in evaluation.context.open_interest)
    assert evaluation.context.predicted_funding_rate is None
    assert evaluation.context.predicted_funding_observed_at is None


def test_v1_source_is_explicitly_unavailable_for_required_context() -> None:
    candles = list(_ohlcv())
    legacy = Snapshot(
        metadata=SnapshotMetadata(
            symbol="BTC/USDT",
            timeframe="1h",
            source="binance",
            fetched_at=START + timedelta(days=1),
            candle_count=len(candles),
            first_timestamp=candles[0].timestamp,
            last_timestamp=candles[-1].timestamp,
            fetcher_version="test",
        ),
        ohlcv=candles,
    )
    source = SnapshotReplaySource(
        VersionedSnapshot(schema_version=1, legacy_snapshot=legacy)
    )

    evaluation = source.context_for(
        "BTC/USDT",
        as_of=candles[-1].timestamp,
        requirements=MarketContextRequirements(funding_required=True),
    )

    assert evaluation.context is None
    assert not evaluation.requirements_satisfied
    assert evaluation.unmet_reasons == ("funding_required",)


def test_coverage_reports_prefix_then_contiguous_eligible_suffix(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)

    coverage = source.assess_coverage(
        MarketContextRequirements(
            funding_required=True,
            funding_min_points=2,
            open_interest_required=True,
            open_interest_min_points=3,
        ),
        warmup_candles=2,
    )

    assert coverage.first_eligible_index == 8
    assert coverage.ignored_prefix_bars == 7
    assert coverage.eligible_bars == 17
    assert coverage.post_eligibility_unmet_bars == 0


def test_loaded_source_is_unchanged_after_current_moves(tmp_path: Path) -> None:
    first_generation = save_snapshot_v2(_bundle(), tmp_path)
    pinned = SnapshotReplaySource.from_directory(tmp_path)
    second_generation = save_snapshot_v2(_bundle(close_offset=Decimal("5")), tmp_path)

    assert first_generation != second_generation
    assert pinned.generation_id == first_generation
    assert pinned.ohlcv[-1].close == Decimal("100")
    assert (
        SnapshotReplaySource.from_directory(tmp_path).generation_id == second_generation
    )


def test_snapshot_and_live_series_use_identical_builder_output(tmp_path: Path) -> None:
    source = _source(tmp_path)
    bundle = _bundle()
    as_of = START + timedelta(hours=16)
    funding = SeriesSnapshot(
        venue="binance",
        symbol="BTC/USDT",
        series=SeriesKind.FUNDING,
        records=bundle.funding,
        fetched_at=bundle.metadata.funding.fetched_at,
        status=SeriesStatus.FRESH,
    )
    oi = SeriesSnapshot(
        venue="binance",
        symbol="BTC/USDT",
        series=SeriesKind.OPEN_INTEREST,
        records=bundle.open_interest.points,
        fetched_at=bundle.metadata.open_interest.fetched_at,
        status=SeriesStatus.FRESH,
    )

    live = MarketContextBuilder().build(
        "BTC/USDT", as_of=as_of, funding=funding, open_interest=oi
    )
    replay = source.context_for("BTC/USDT", as_of=as_of)

    assert replay.model_dump(mode="json") == live.model_dump(mode="json")


def test_source_rejects_uncovered_derivatives_suffix() -> None:
    with pytest.raises(SnapshotValidationError, match="uncovered suffix"):
        SnapshotReplaySource(
            VersionedSnapshot(
                schema_version=2,
                generation_id="a" * 64,
                snapshot_v2=_bundle(oi_count=22),
            )
        )


def test_source_rejects_unexplained_funding_prefix_gap() -> None:
    bundle = _bundle()
    funding = bundle.funding[2:]
    metadata = bundle.metadata.model_copy(
        update={
            "funding": _series_metadata(
                funding,
                requested_since=START,
                requested_until=bundle.ohlcv[-1].timestamp,
                granularity="8h",
            )
        }
    )
    shortened = SnapshotV2(
        metadata=metadata,
        ohlcv=bundle.ohlcv,
        funding=funding,
        open_interest=bundle.open_interest,
    )

    with pytest.raises(SnapshotValidationError, match="unexplained prefix gap"):
        SnapshotReplaySource(
            VersionedSnapshot(
                schema_version=2,
                generation_id="a" * 64,
                snapshot_v2=shortened,
            )
        )


def test_source_rejects_symbol_mismatch(tmp_path: Path) -> None:
    source = _source(tmp_path)

    with pytest.raises(ValueError, match="does not match request"):
        source.context_for("ETH/USDT", as_of=START)


def test_configuration_digest_is_order_independent_and_identity_sensitive() -> None:
    left = canonical_configuration_digest(
        {"seed": 7, "strategy": {"name": "test", "version": "1.0.0"}}
    )
    reordered = canonical_configuration_digest(
        {"strategy": {"version": "1.0.0", "name": "test"}, "seed": 7}
    )
    changed = canonical_configuration_digest(
        {"seed": 8, "strategy": {"name": "test", "version": "1.0.0"}}
    )

    assert left == reordered
    assert left != changed
