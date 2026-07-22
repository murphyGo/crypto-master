"""Pinned Snapshot v1/v2 source for deterministic market-context replay."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.backtest.reproducibility import ReplayIdentity
from src.backtest.snapshot import SnapshotValidationError
from src.backtest.snapshot_v2 import VersionedSnapshot, load_snapshot_versioned
from src.exchange.derivatives import (
    ContextEvaluation,
    FundingRate,
    MarketContextRequirements,
    OpenInterestPoint,
    SeriesKind,
    SeriesSnapshot,
    SeriesStatus,
    UnmetReason,
)
from src.models import OHLCV
from src.strategy.market_context import MarketContextBuilder


class ReplayCoverage(BaseModel):
    """Requirement coverage measured over potential decision bars."""

    first_eligible_index: int | None = Field(default=None, ge=0)
    ignored_prefix_bars: int = Field(default=0, ge=0)
    eligible_bars: int = Field(default=0, ge=0)
    unmet_bars: int = Field(default=0, ge=0)
    post_eligibility_unmet_bars: int = Field(default=0, ge=0)
    unmet_reasons: tuple[UnmetReason, ...] = ()

    model_config = ConfigDict(frozen=True)


class SnapshotReplaySource:
    """Read one selected snapshot once and serve its immutable replay view."""

    def __init__(
        self,
        snapshot: VersionedSnapshot,
        *,
        builder: MarketContextBuilder | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._builder = builder or MarketContextBuilder()
        self._ohlcv = snapshot.ohlcv
        if not self._ohlcv:
            raise SnapshotValidationError("replay snapshot requires OHLCV rows")

        if snapshot.schema_version == 2:
            bundle = snapshot.snapshot_v2
            assert bundle is not None
            v2_metadata = bundle.metadata
            self._identity = ReplayIdentity(
                schema_version=2,
                generation_id=snapshot.generation_id,
                source=v2_metadata.source,
                symbol=v2_metadata.symbol,
                timeframe=v2_metadata.timeframe,
            )
            self._validate_v2_coverage()
            self._funding = self._series_snapshot(SeriesKind.FUNDING)
            self._open_interest = self._series_snapshot(SeriesKind.OPEN_INTEREST)
        else:
            legacy = snapshot.legacy_snapshot
            assert legacy is not None
            legacy_metadata = legacy.metadata
            self._identity = ReplayIdentity(
                schema_version=1,
                source=legacy_metadata.source,
                symbol=legacy_metadata.symbol,
                timeframe=legacy_metadata.timeframe,
            )
            self._funding = None
            self._open_interest = None

    @classmethod
    def from_directory(
        cls,
        directory: Path,
        *,
        generation_id: str | None = None,
        builder: MarketContextBuilder | None = None,
    ) -> SnapshotReplaySource:
        """Load and pin `CURRENT` once, or select an exact generation id."""

        return cls(
            load_snapshot_versioned(directory, generation_id=generation_id),
            builder=builder,
        )

    @property
    def identity(self) -> ReplayIdentity:
        return self._identity

    @property
    def schema_version(self) -> int:
        return self._identity.schema_version

    @property
    def generation_id(self) -> str | None:
        return self._identity.generation_id

    @property
    def symbol(self) -> str:
        return self._identity.symbol

    @property
    def timeframe(self) -> str:
        return self._identity.timeframe

    @property
    def ohlcv(self) -> tuple[OHLCV, ...]:
        return self._ohlcv

    def context_for(
        self,
        symbol: str,
        *,
        as_of: datetime,
        requirements: MarketContextRequirements | None = None,
    ) -> ContextEvaluation:
        """Build one no-look-ahead context at the requested candle close."""

        if symbol != self.symbol:
            raise ValueError(
                f"replay symbol {self.symbol!r} does not match request {symbol!r}"
            )
        if self.schema_version == 1:
            return self._builder.evaluate(None, requirements)
        return self._builder.build(
            symbol,
            as_of=as_of,
            funding=self._funding,
            open_interest=self._open_interest,
            requirements=requirements,
        )

    def assess_coverage(
        self,
        requirements: MarketContextRequirements,
        *,
        warmup_candles: int,
    ) -> ReplayCoverage:
        """Measure a contiguous requirements-satisfied replay suffix."""

        start_index = max(0, warmup_candles - 1)
        first_eligible: int | None = None
        eligible = 0
        unmet = 0
        post_eligible_unmet = 0
        reasons: list[UnmetReason] = []
        for index, candle in enumerate(self._ohlcv):
            if index < start_index:
                continue
            evaluation = self.context_for(
                self.symbol,
                as_of=candle.timestamp,
                requirements=requirements,
            )
            if evaluation.requirements_satisfied:
                if first_eligible is None:
                    first_eligible = index
                eligible += 1
                continue
            unmet += 1
            for reason in evaluation.unmet_reasons:
                if reason not in reasons:
                    reasons.append(reason)
            if first_eligible is not None:
                post_eligible_unmet += 1

        ignored_prefix = (
            max(0, len(self._ohlcv) - start_index)
            if first_eligible is None
            else max(0, first_eligible - start_index)
        )
        return ReplayCoverage(
            first_eligible_index=first_eligible,
            ignored_prefix_bars=ignored_prefix,
            eligible_bars=eligible,
            unmet_bars=unmet,
            post_eligibility_unmet_bars=post_eligible_unmet,
            unmet_reasons=tuple(reasons),
        )

    def _series_snapshot(self, series: SeriesKind) -> SeriesSnapshot | None:
        bundle = self._snapshot.snapshot_v2
        assert bundle is not None
        metadata = bundle.metadata
        if series is SeriesKind.FUNDING:
            records: tuple[FundingRate | OpenInterestPoint, ...] = bundle.funding
            series_metadata = metadata.funding
            truncated = False
        else:
            records = bundle.open_interest.points
            series_metadata = metadata.open_interest
            truncated = bundle.open_interest.truncated_at_venue_retention
        if not records:
            return None
        return SeriesSnapshot(
            venue=metadata.source,
            symbol=metadata.symbol,
            series=series,
            records=records,
            fetched_at=series_metadata.fetched_at,
            status=SeriesStatus.FRESH,
            from_cache=False,
            truncated_at_venue_retention=truncated,
        )

    def _validate_v2_coverage(self) -> None:
        bundle = self._snapshot.snapshot_v2
        assert bundle is not None
        first = self._ohlcv[0].timestamp
        last = self._ohlcv[-1].timestamp
        metadata = bundle.metadata
        self._validate_series_coverage(
            label="funding",
            requested_since=metadata.funding.requested_since,
            requested_until=metadata.funding.requested_until,
            actual_since=metadata.funding.actual_since,
            actual_until=metadata.funding.actual_until,
            first=first,
            last=last,
            interval=timedelta(hours=8),
            retention_truncated=False,
        )
        self._validate_series_coverage(
            label="open interest",
            requested_since=metadata.open_interest.requested_since,
            requested_until=metadata.open_interest.requested_until,
            actual_since=metadata.open_interest.actual_since,
            actual_until=metadata.open_interest.actual_until,
            first=first,
            last=last,
            interval=timedelta(hours=1),
            retention_truncated=metadata.open_interest.truncated_at_venue_retention,
        )

    @staticmethod
    def _validate_series_coverage(
        *,
        label: str,
        requested_since: datetime | None,
        requested_until: datetime | None,
        actual_since: datetime | None,
        actual_until: datetime | None,
        first: datetime,
        last: datetime,
        interval: timedelta,
        retention_truncated: bool,
    ) -> None:
        if requested_since is not None and requested_since > first:
            raise SnapshotValidationError(
                f"{label} requested coverage begins after OHLCV replay"
            )
        if requested_until is not None and requested_until < last:
            raise SnapshotValidationError(
                f"{label} requested coverage ends before OHLCV replay"
            )
        if actual_since is None or actual_until is None:
            return
        if actual_until > last:
            raise SnapshotValidationError(f"{label} contains a post-OHLCV tail")
        prefix_gap = actual_since - first
        if prefix_gap > interval and not retention_truncated:
            raise SnapshotValidationError(f"{label} has an unexplained prefix gap")
        if last - actual_until > interval:
            raise SnapshotValidationError(f"{label} has an uncovered suffix gap")


__all__ = ["ReplayCoverage", "SnapshotReplaySource"]
