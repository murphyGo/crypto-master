"""Deterministic tests for the bounded derivatives context service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from time import perf_counter

import pytest

from src.config import DerivativesDataConfig
from src.exchange.base import ExchangeAPIError
from src.exchange.derivatives import (
    CurrentFundingRate,
    DerivativesDataNotSupportedError,
    FundingRate,
    OpenInterestHistory,
    OpenInterestPoint,
    SeriesKind,
    SeriesStatus,
)
from src.runtime.activity_events import ActivityEventType
from src.runtime.derivatives_context import DerivativesContextService

UTC = timezone.utc


class MutableClock:
    def __init__(self) -> None:
        self.wall = datetime(2026, 7, 19, 0, tzinfo=UTC)
        self.monotonic = 0.0

    def now(self) -> datetime:
        return self.wall

    def tick(self, seconds: float) -> None:
        self.wall += timedelta(seconds=seconds)
        self.monotonic += seconds


class FakeSource:
    name = "binance"

    def __init__(self, clock: MutableClock) -> None:
        self.clock = clock
        self.connected = 0
        self.disconnected = 0
        self.calls: list[tuple[str, str]] = []
        self.funding_failures = 0
        self.unsupported_funding = False
        self.bad_funding_interval = False
        self.block = False
        self.latency_seconds = 0.0
        self.active = 0
        self.peak = 0

    async def connect(self) -> None:
        self.connected += 1

    async def disconnect(self) -> None:
        self.disconnected += 1

    async def _enter(self, endpoint: str, symbol: str) -> None:
        self.calls.append((endpoint, symbol))
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if self.block:
                await asyncio.Event().wait()
            else:
                await asyncio.sleep(self.latency_seconds)
        finally:
            self.active -= 1

    async def get_funding_rate(self, symbol: str) -> CurrentFundingRate:
        await self._enter("funding_current", symbol)
        if self.unsupported_funding:
            raise DerivativesDataNotSupportedError("not supported")
        if self.funding_failures:
            self.funding_failures -= 1
            raise ExchangeAPIError("redacted", code="network_transient")
        return CurrentFundingRate(
            symbol=symbol,
            observed_at=self.clock.now(),
            rate=Decimal("0.0001"),
            predicted_rate=Decimal("0.0002"),
            interval_hours=4 if self.bad_funding_interval else 8,
        )

    async def get_funding_rate_history(
        self,
        symbol: str,
        since: int = 0,
        limit: int = 1000,
        *,
        until: int | None = None,
    ) -> list[FundingRate]:
        assert isinstance(since, int)
        assert until is None or isinstance(until, int)
        await self._enter("funding_history", symbol)
        return [
            FundingRate(
                symbol=symbol,
                timestamp=self.clock.now() - timedelta(hours=8),
                rate=Decimal("0.0001"),
            )
        ]

    async def get_open_interest(self, symbol: str) -> OpenInterestPoint:
        await self._enter("oi_current", symbol)
        return OpenInterestPoint(
            symbol=symbol,
            timestamp=self.clock.now(),
            open_interest=Decimal("100"),
        )

    async def get_open_interest_history(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: int | None = None,
        limit: int = 500,
        *,
        until: int | None = None,
    ) -> OpenInterestHistory:
        assert since is None or isinstance(since, int)
        assert until is None or isinstance(until, int)
        await self._enter("oi_history", symbol)
        point = OpenInterestPoint(
            symbol=symbol,
            timestamp=self.clock.now() - timedelta(hours=1),
            open_interest=Decimal("90"),
        )
        return OpenInterestHistory(
            symbol=symbol,
            requested_since=(
                None if since is None else datetime.fromtimestamp(since / 1000, tz=UTC)
            ),
            requested_until=(
                None if until is None else datetime.fromtimestamp(until / 1000, tz=UTC)
            ),
            actual_since=point.timestamp,
            actual_until=point.timestamp,
            points=(point,),
        )


class EventSink:
    def __init__(self) -> None:
        self.events: list[tuple[ActivityEventType, dict, str | None]] = []

    def append(
        self,
        event_type: ActivityEventType,
        message: str = "",
        *,
        details: dict | None = None,
        cycle_id: str | None = None,
    ) -> object:
        self.events.append((event_type, details or {}, cycle_id))
        return object()


def _service(
    source: FakeSource,
    clock: MutableClock,
    *,
    sink: EventSink | None = None,
    **overrides: object,
) -> DerivativesContextService:
    config = DerivativesDataConfig(enabled=True, **overrides)
    return DerivativesContextService(
        source,
        config,
        event_sink=sink,
        clock=lambda: clock.monotonic,
        now=clock.now,
        sleep=lambda _: asyncio.sleep(0),
        random_uniform=lambda _low, _high: 0,
    )


@pytest.mark.asyncio
async def test_disabled_service_constructs_no_connection_or_request() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    service = DerivativesContextService(
        source,
        DerivativesDataConfig(),
        now=clock.now,
    )
    summary = await service.refresh_cycle(
        cycle_id="disabled", cycle_index=1, symbols=["BTC/USDT"]
    )
    assert summary.requested_count == 0
    assert source.connected == 0
    assert source.calls == []


@pytest.mark.asyncio
async def test_refresh_builds_context_and_closes_exactly_once() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    service = _service(source, clock)
    summary = await service.refresh_cycle(
        cycle_id="one", cycle_index=1, symbols=["btc/usdt", "BTC/USDT"]
    )
    evaluation = service.context_for("BTC/USDT", as_of=clock.now())
    assert summary.completed_count == 2
    assert evaluation.context is not None
    assert len(evaluation.context.funding) == 1
    assert len(evaluation.context.open_interest) == 2
    assert service.cache_size == 2
    await service.close()
    await service.close()
    assert source.disconnected == 1


@pytest.mark.asyncio
async def test_transient_request_retries_with_bounded_attempts() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    source.funding_failures = 2
    service = _service(source, clock)
    summary = await service.refresh_cycle(
        cycle_id="retry", cycle_index=1, symbols=["BTC/USDT"]
    )
    funding = next(
        item for item in summary.outcomes if item.series is SeriesKind.FUNDING
    )
    assert funding.status is SeriesStatus.FRESH
    assert funding.attempt_count == 4  # history once + current three attempts


@pytest.mark.asyncio
async def test_budget_exhaustion_is_non_retryable_and_does_not_leak_raw_error() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    sink = EventSink()
    service = _service(
        source,
        clock,
        sink=sink,
        funding_budget_5m=1,
        oi_history_budget_5m=1,
    )
    summary = await service.refresh_cycle(
        cycle_id="budget", cycle_index=1, symbols=["BTC/USDT"]
    )
    assert {item.error_code for item in summary.outcomes} == {
        "request_budget_exhausted"
    }
    assert all("redacted" not in str(details) for _, details, _ in sink.events)


@pytest.mark.asyncio
async def test_circuit_skips_one_cycle_then_half_open_recovers() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    sink = EventSink()
    service = _service(source, clock, sink=sink, retry_count=0)
    source.funding_failures = 3
    for cycle in range(1, 4):
        await service.refresh_cycle(
            cycle_id=str(cycle), cycle_index=cycle, symbols=["BTC/USDT"]
        )
    before_skip = len([call for call in source.calls if call[0] == "funding_current"])
    skipped = await service.refresh_cycle(
        cycle_id="4", cycle_index=4, symbols=["BTC/USDT"]
    )
    assert (
        next(
            item for item in skipped.outcomes if item.series is SeriesKind.FUNDING
        ).error_code
        == "circuit_open"
    )
    assert (
        len([call for call in source.calls if call[0] == "funding_current"])
        == before_skip
    )
    recovered = await service.refresh_cycle(
        cycle_id="5", cycle_index=5, symbols=["BTC/USDT"]
    )
    assert (
        next(
            item for item in recovered.outcomes if item.series is SeriesKind.FUNDING
        ).status
        is SeriesStatus.FRESH
    )
    assert any(
        event[0] is ActivityEventType.DERIVATIVES_DATA_RECOVERED
        for event in sink.events
    )


@pytest.mark.asyncio
async def test_unsupported_funding_does_not_displace_open_interest() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    source.unsupported_funding = True
    service = _service(source, clock)
    summary = await service.refresh_cycle(
        cycle_id="unsupported", cycle_index=1, symbols=["BTC/USDT"]
    )
    statuses = {item.series: item.status for item in summary.outcomes}
    assert statuses[SeriesKind.FUNDING] is SeriesStatus.UNSUPPORTED
    assert statuses[SeriesKind.OPEN_INTEREST] is SeriesStatus.FRESH


@pytest.mark.asyncio
async def test_unsupported_interval_preserves_open_interest() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    source.bad_funding_interval = True
    service = _service(source, clock)
    summary = await service.refresh_cycle(
        cycle_id="interval", cycle_index=1, symbols=["BTC/USDT"]
    )
    statuses = {item.series: item.status for item in summary.outcomes}
    assert statuses[SeriesKind.FUNDING] is SeriesStatus.UNSUPPORTED_INTERVAL
    assert statuses[SeriesKind.OPEN_INTEREST] is SeriesStatus.FRESH


@pytest.mark.asyncio
async def test_last_known_good_expires_without_being_displaced() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    service = _service(source, clock, retry_count=0)
    await service.refresh_cycle(cycle_id="fresh", cycle_index=1, symbols=["BTC/USDT"])
    clock.tick(9 * 60 * 60 + 1)
    source.funding_failures = 1
    summary = await service.refresh_cycle(
        cycle_id="expired", cycle_index=2, symbols=["BTC/USDT"]
    )
    funding = next(
        item for item in summary.outcomes if item.series is SeriesKind.FUNDING
    )
    assert funding.status is SeriesStatus.STALE
    context = service.context_for("BTC/USDT", as_of=clock.now()).context
    assert context is not None
    assert context.funding == ()
    assert context.funding_availability.status is SeriesStatus.STALE


@pytest.mark.asyncio
async def test_deadline_cancels_and_awaits_every_owned_task() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    source.block = True
    service = _service(
        source,
        clock,
        deadline_4_symbols_seconds=0.01,
        deadline_20_symbols_seconds=0.01,
    )
    summary = await service.refresh_cycle(
        cycle_id="deadline", cycle_index=1, symbols=["BTC/USDT"]
    )
    assert summary.cancelled_count == 2
    assert source.active == 0
    await service.close()


@pytest.mark.asyncio
async def test_four_and_twenty_symbol_load_stays_within_semaphore_for_100_cycles() -> (
    None
):
    for count in (4, 20):
        clock = MutableClock()
        source = FakeSource(clock)
        service = _service(source, clock)
        symbols = [f"COIN{index}/USDT" for index in range(count)]
        cycles = 100
        for cycle in range(cycles):
            result = await service.refresh_cycle(
                cycle_id=f"{count}-{cycle}",
                cycle_index=cycle,
                symbols=symbols,
            )
            assert result.cancelled_count == 0
            assert result.completed_count == count * 2
            clock.tick(300)
        assert source.peak <= 4
        await service.close()


@pytest.mark.parametrize(("count", "p95_budget_seconds"), [(4, 5.0), (20, 15.0)])
@pytest.mark.asyncio
async def test_latency_injecting_load_records_percentiles_without_task_leaks(
    count: int,
    p95_budget_seconds: float,
) -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    source.latency_seconds = 0.001
    service = _service(source, clock)
    symbols = [f"COIN{index}/USDT" for index in range(count)]
    samples: list[float] = []

    for cycle in range(100):
        started = perf_counter()
        result = await service.refresh_cycle(
            cycle_id=f"latency-{count}-{cycle}",
            cycle_index=cycle,
            symbols=symbols,
        )
        samples.append(perf_counter() - started)
        assert result.cancelled_count == 0
        assert result.completed_count == count * 2
        clock.tick(300)

    ordered = sorted(samples)
    p50 = median(ordered)
    p95 = ordered[94]
    maximum = ordered[-1]
    print(
        "derivatives_load "
        f"symbols={count} cycles=100 "
        f"p50={p50:.6f}s p95={p95:.6f}s max={maximum:.6f}s "
        f"semaphore_peak={source.peak}"
    )
    assert p95 <= p95_budget_seconds
    assert source.peak <= 4
    assert source.active == 0

    await service.close()
    assert source.active == 0
    assert not service._inflight


@pytest.mark.asyncio
async def test_open_interest_history_refreshes_on_one_hour_cadence() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    service = _service(source, clock)
    await service.refresh_cycle(cycle_id="first", cycle_index=1, symbols=["BTC/USDT"])
    assert len([call for call in source.calls if call[0] == "oi_history"]) == 1

    clock.tick(3599)
    await service.refresh_cycle(cycle_id="early", cycle_index=2, symbols=["BTC/USDT"])
    assert len([call for call in source.calls if call[0] == "oi_history"]) == 1

    clock.tick(1)
    await service.refresh_cycle(cycle_id="due", cycle_index=3, symbols=["BTC/USDT"])
    assert len([call for call in source.calls if call[0] == "oi_history"]) == 2


@pytest.mark.asyncio
async def test_events_use_exact_safe_allowlist_and_degrade_once_per_cycle() -> None:
    clock = MutableClock()
    source = FakeSource(clock)
    source.unsupported_funding = True
    sink = EventSink()
    service = _service(source, clock, sink=sink)
    await service.refresh_cycle(cycle_id="safe", cycle_index=1, symbols=["BTC/USDT"])
    degraded = [
        event
        for event in sink.events
        if event[0] is ActivityEventType.DERIVATIVES_DATA_DEGRADED
    ]
    assert len(degraded) == 1
    assert set(degraded[0][1]) == {
        "exchange",
        "symbol",
        "series",
        "status",
        "error_code",
        "data_timestamp",
        "data_age_seconds",
        "cache_status",
        "attempt_count",
        "circuit_state",
        "truncated_at_venue_retention",
    }
