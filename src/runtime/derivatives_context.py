"""Engine-scoped, bounded public derivatives context service."""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, cast

from src.config import DerivativesDataConfig
from src.exchange.base import ExchangeAPIError
from src.exchange.derivatives import (
    ContextEvaluation,
    DerivativesDataError,
    DerivativesDataNotSupportedError,
    DerivativesDataSource,
    DerivativesDataValidationError,
    DerivativesErrorCode,
    FundingRate,
    MarketContextRequirements,
    OpenInterestPoint,
    RefreshSummary,
    SeriesKind,
    SeriesRefreshOutcome,
    SeriesSnapshot,
    SeriesStatus,
    UnsupportedFundingIntervalError,
)
from src.runtime.activity_events import ActivityEventType
from src.strategy.market_context import MarketContextBuilder

_TRANSIENT_CODES = {
    "network_transient",
    "rate_limited",
    "remote_5xx",
    "venue_unavailable",
}


class ActivityEventSink(Protocol):
    """Minimal append-only event port used by the service."""

    def append(
        self,
        event_type: ActivityEventType,
        message: str = "",
        *,
        details: dict[str, Any] | None = None,
        cycle_id: str | None = None,
    ) -> object: ...


class _BudgetExhausted(Exception):
    pass


@dataclass
class _Circuit:
    failures: int = 0
    opened_cycle: int | None = None

    def state_for(self, cycle_index: int) -> str:
        if self.opened_cycle is None:
            return "closed"
        if cycle_index <= self.opened_cycle + 1:
            return "open"
        return "half_open"

    def success(self) -> None:
        self.failures = 0
        self.opened_cycle = None

    def transient_failure(self, cycle_index: int) -> None:
        self.failures += 1
        if self.failures >= 3:
            self.opened_cycle = cycle_index


class _RollingBudget:
    def __init__(self, limit: int, *, window_seconds: float = 300.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._admissions: deque[float] = deque()

    def admit(self, now: float) -> bool:
        cutoff = now - self.window_seconds
        while self._admissions and self._admissions[0] <= cutoff:
            self._admissions.popleft()
        if len(self._admissions) >= self.limit:
            return False
        self._admissions.append(now)
        return True


@dataclass(frozen=True)
class _ClassifiedFailure:
    code: DerivativesErrorCode
    status: SeriesStatus
    transient: bool


class DerivativesContextService:
    """Refresh and serve bounded Funding/OI context without durable writes."""

    def __init__(
        self,
        source: DerivativesDataSource,
        config: DerivativesDataConfig,
        *,
        event_sink: ActivityEventSink | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
        builder: MarketContextBuilder | None = None,
    ) -> None:
        self._source = source
        self._config = config
        self._event_sink = event_sink
        self._clock = clock
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep
        self._random_uniform = random_uniform
        self._builder = builder or MarketContextBuilder()
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._budgets = {
            SeriesKind.FUNDING: _RollingBudget(config.funding_budget_5m),
            SeriesKind.OPEN_INTEREST: _RollingBudget(config.oi_history_budget_5m),
        }
        self._cache: dict[tuple[str, str, SeriesKind], SeriesSnapshot] = {}
        self._circuits: dict[tuple[str, str, SeriesKind], _Circuit] = {}
        self._inflight: dict[
            tuple[str, str, SeriesKind], asyncio.Task[SeriesRefreshOutcome]
        ] = {}
        self._connect_lock = asyncio.Lock()
        self._connected = False
        self._closed = False
        self._event_dedupe: set[tuple[str, str, SeriesKind]] = set()
        self._degraded: dict[tuple[str, SeriesKind], bool] = {}
        self._last_history_refresh: dict[tuple[str, str, SeriesKind], datetime] = {}
        self._last_history_tail: dict[tuple[str, str, SeriesKind], datetime] = {}

    @property
    def cache_size(self) -> int:
        """Expose cache cardinality for diagnostics/tests, never raw payloads."""
        return len(self._cache)

    async def refresh_cycle(
        self,
        *,
        cycle_id: str,
        cycle_index: int,
        symbols: Sequence[str],
    ) -> RefreshSummary:
        """Refresh all canonical symbols within the configured cycle deadline."""
        if self._closed:
            raise RuntimeError("derivatives context service is closed")
        canonical = tuple(sorted({_canonical_symbol(symbol) for symbol in symbols}))
        if len(canonical) > self._config.max_symbols:
            raise ValueError(
                f"derivatives symbol count {len(canonical)} exceeds "
                f"configured maximum {self._config.max_symbols}"
            )
        if not self._config.enabled or not canonical:
            return RefreshSummary(
                cycle_id=cycle_id,
                requested_count=0,
                completed_count=0,
                cached_count=0,
                unavailable_count=0,
                cancelled_count=0,
            )

        self._event_dedupe = {key for key in self._event_dedupe if key[0] != cycle_id}
        try:
            await self._ensure_connected()
        except Exception as exc:
            failure = _classify_failure(exc)
            connect_outcomes = tuple(
                self._failed_without_request(
                    cycle_id,
                    symbol,
                    series,
                    failure,
                    attempt_count=1,
                    circuit_state="closed",
                )
                for symbol in canonical
                for series in (SeriesKind.FUNDING, SeriesKind.OPEN_INTEREST)
            )
            return _summary(cycle_id, connect_outcomes)

        requests = [
            (symbol, series)
            for symbol in canonical
            for series in (SeriesKind.FUNDING, SeriesKind.OPEN_INTEREST)
        ]
        tasks = [
            self._task_for(
                cycle_id=cycle_id,
                cycle_index=cycle_index,
                symbol=symbol,
                series=series,
            )
            for symbol, series in requests
        ]
        deadline = (
            self._config.deadline_4_symbols_seconds
            if len(canonical) <= 4
            else self._config.deadline_20_symbols_seconds
        )
        done, pending = await asyncio.wait(tasks, timeout=deadline)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        outcomes: list[SeriesRefreshOutcome] = []
        for task in done:
            try:
                outcomes.append(task.result())
            except asyncio.CancelledError:
                continue
            except Exception:
                # The owned task normally converts failures itself. This final
                # boundary prevents one implementation fault from failing the
                # OHLCV cycle or leaking exception text into telemetry.
                continue
        completed_keys = {(item.symbol, item.series) for item in outcomes}
        for symbol, series in requests:
            if (symbol, series) in completed_keys:
                continue
            outcome = self._failed_without_request(
                cycle_id,
                symbol,
                series,
                _ClassifiedFailure(
                    code="deadline_exceeded",
                    status=SeriesStatus.UNAVAILABLE,
                    transient=False,
                ),
                attempt_count=0,
                circuit_state=self._circuit(symbol, series).state_for(cycle_index),
            )
            outcomes.append(outcome)
        outcomes.sort(key=lambda item: (item.symbol, item.series.value))
        return _summary(cycle_id, tuple(outcomes))

    def context_for(
        self,
        symbol: str,
        *,
        as_of: datetime,
        requirements: MarketContextRequirements | None = None,
    ) -> ContextEvaluation:
        canonical = _canonical_symbol(symbol)
        venue = self._source.name.lower()
        return self._builder.build(
            canonical,
            as_of=as_of,
            funding=self._cache.get((venue, canonical, SeriesKind.FUNDING)),
            open_interest=self._cache.get((venue, canonical, SeriesKind.OPEN_INTEREST)),
            requirements=requirements,
        )

    async def close(self) -> None:
        """Cancel owned work and close the dedicated public source once."""
        if self._closed:
            return
        self._closed = True
        tasks = tuple(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._inflight.clear()
        if self._connected:
            await self._source.disconnect()
            self._connected = False

    async def _ensure_connected(self) -> None:
        if self._connected:
            return
        async with self._connect_lock:
            if self._connected:
                return
            await self._source.connect()
            self._connected = True

    def _task_for(
        self,
        *,
        cycle_id: str,
        cycle_index: int,
        symbol: str,
        series: SeriesKind,
    ) -> asyncio.Task[SeriesRefreshOutcome]:
        key = (self._source.name.lower(), symbol, series)
        existing = self._inflight.get(key)
        if existing is not None and not existing.done():
            return existing
        task = asyncio.create_task(
            self._refresh_series(
                cycle_id=cycle_id,
                cycle_index=cycle_index,
                symbol=symbol,
                series=series,
            ),
            name=f"derivatives:{series.value}:{symbol}",
        )
        self._inflight[key] = task

        def forget(finished: asyncio.Task[SeriesRefreshOutcome]) -> None:
            self._forget_task(key, finished)

        task.add_done_callback(forget)
        return task

    def _forget_task(
        self,
        key: tuple[str, str, SeriesKind],
        task: asyncio.Task[SeriesRefreshOutcome],
    ) -> None:
        if self._inflight.get(key) is task:
            self._inflight.pop(key, None)

    async def _refresh_series(
        self,
        *,
        cycle_id: str,
        cycle_index: int,
        symbol: str,
        series: SeriesKind,
    ) -> SeriesRefreshOutcome:
        circuit = self._circuit(symbol, series)
        circuit_state = circuit.state_for(cycle_index)
        if circuit_state == "open":
            return self._failed_without_request(
                cycle_id,
                symbol,
                series,
                _ClassifiedFailure(
                    code="circuit_open",
                    status=SeriesStatus.UNAVAILABLE,
                    transient=False,
                ),
                attempt_count=0,
                circuit_state=circuit_state,
            )

        async with self._semaphore:
            try:
                snapshot, attempts = await self._load_series(symbol, series)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failure = _classify_failure(exc)
                attempts = int(getattr(exc, "attempt_count", 1))
                if failure.transient:
                    circuit.transient_failure(cycle_index)
                return self._failed_without_request(
                    cycle_id,
                    symbol,
                    series,
                    failure,
                    attempt_count=attempts,
                    circuit_state=circuit.state_for(cycle_index),
                )

        circuit.success()
        key = (self._source.name.lower(), symbol, series)
        self._cache[key] = snapshot
        outcome = SeriesRefreshOutcome(
            symbol=symbol,
            series=series,
            status=SeriesStatus.FRESH,
            attempt_count=attempts,
            circuit_state="closed",
        )
        self._emit_transition(cycle_id, snapshot, outcome)
        return outcome

    async def _load_series(
        self, symbol: str, series: SeriesKind
    ) -> tuple[SeriesSnapshot, int]:
        if series is SeriesKind.FUNDING:
            return await self._load_funding(symbol)
        return await self._load_open_interest(symbol)

    async def _load_funding(self, symbol: str) -> tuple[SeriesSnapshot, int]:
        now = _as_utc(self._now())
        existing = self._cache.get(
            (self._source.name.lower(), symbol, SeriesKind.FUNDING)
        )
        records = tuple(
            cast(FundingRate, record)
            for record in (() if existing is None else existing.records)
        )
        due = not records or records[-1].timestamp + timedelta(hours=8) <= now
        attempts = 0
        if due:
            history, used = await self._request_with_retry(
                SeriesKind.FUNDING,
                lambda: self._source.get_funding_rate_history(
                    symbol,
                    since=_datetime_ms(
                        now - timedelta(days=30)
                        if not records
                        else records[-1].timestamp + timedelta(milliseconds=1)
                    ),
                    until=_datetime_ms(now),
                    limit=1000,
                ),
            )
            attempts += used
            records = _merge_records(records, tuple(history), limit=1000)
        current, used = await self._request_with_retry(
            SeriesKind.FUNDING,
            lambda: self._source.get_funding_rate(symbol),
        )
        attempts += used
        if current.symbol != symbol:
            raise DerivativesDataValidationError("current funding symbol mismatch")
        if current.interval_hours not in {None, self._config.funding_interval_hours}:
            raise UnsupportedFundingIntervalError("funding interval is not 8h")
        if not records:
            raise DerivativesDataValidationError("funding history is empty")
        return (
            SeriesSnapshot(
                venue=self._source.name.lower(),
                symbol=symbol,
                series=SeriesKind.FUNDING,
                records=records,
                fetched_at=now,
                predicted_funding_rate=current.predicted_rate,
                predicted_funding_observed_at=(
                    current.observed_at if current.predicted_rate is not None else None
                ),
            ),
            attempts,
        )

    async def _load_open_interest(self, symbol: str) -> tuple[SeriesSnapshot, int]:
        now = _as_utc(self._now())
        existing = self._cache.get(
            (self._source.name.lower(), symbol, SeriesKind.OPEN_INTEREST)
        )
        records = tuple(
            cast(OpenInterestPoint, record)
            for record in (() if existing is None else existing.records)
        )
        history_key = (
            self._source.name.lower(),
            symbol,
            SeriesKind.OPEN_INTEREST,
        )
        last_history_refresh = self._last_history_refresh.get(history_key)
        due = (
            last_history_refresh is None
            or last_history_refresh + timedelta(hours=1) <= now
        )
        truncated = False if existing is None else existing.truncated_at_venue_retention
        attempts = 0
        history_tail = self._last_history_tail.get(history_key)
        if due:
            history, used = await self._request_with_retry(
                SeriesKind.OPEN_INTEREST,
                lambda: self._source.get_open_interest_history(
                    symbol,
                    timeframe=self._config.oi_timeframe,
                    since=_datetime_ms(
                        now - timedelta(hours=500)
                        if history_tail is None
                        else history_tail + timedelta(hours=1)
                    ),
                    until=_datetime_ms(now),
                    limit=500,
                ),
            )
            attempts += used
            if history.symbol != symbol:
                raise DerivativesDataValidationError("OI history symbol mismatch")
            truncated = history.truncated_at_venue_retention
            records = _merge_records(records, history.points, limit=500)
            if history.points:
                history_tail = history.points[-1].timestamp
        current, used = await self._request_with_retry(
            SeriesKind.OPEN_INTEREST,
            lambda: self._source.get_open_interest(symbol),
        )
        attempts += used
        if current.symbol != symbol:
            raise DerivativesDataValidationError("current OI symbol mismatch")
        records = _merge_records(records, (current,), limit=500)
        snapshot = SeriesSnapshot(
            venue=self._source.name.lower(),
            symbol=symbol,
            series=SeriesKind.OPEN_INTEREST,
            records=records,
            fetched_at=now,
            truncated_at_venue_retention=truncated,
        )
        if due:
            self._last_history_refresh[history_key] = now
            if history_tail is not None:
                self._last_history_tail[history_key] = history_tail
        return snapshot, attempts

    async def _request_with_retry(
        self,
        series: SeriesKind,
        request: Callable[[], Awaitable[Any]],
    ) -> tuple[Any, int]:
        max_attempts = 1 + self._config.retry_count
        for attempt in range(1, max_attempts + 1):
            if not self._budgets[series].admit(self._clock()):
                error = _BudgetExhausted()
                error.attempt_count = attempt - 1  # type: ignore[attr-defined]
                raise error
            try:
                return await request(), attempt
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failure = _classify_failure(exc)
                if not failure.transient or attempt >= max_attempts:
                    try:
                        exc.attempt_count = attempt  # type: ignore[attr-defined]
                    except (AttributeError, TypeError):
                        pass
                    raise
                ceiling = self._config.retry_base_seconds * attempt
                retry_after = getattr(exc, "retry_after_seconds", None)
                delay = self._random_uniform(0.0, ceiling)
                if failure.code == "rate_limited" and isinstance(
                    retry_after, (int, float)
                ):
                    delay = max(delay, max(0.0, float(retry_after)))
                await self._sleep(delay)
        raise AssertionError("retry loop did not return or raise")

    def _circuit(self, symbol: str, series: SeriesKind) -> _Circuit:
        key = (self._source.name.lower(), symbol, series)
        return self._circuits.setdefault(key, _Circuit())

    def _failed_without_request(
        self,
        cycle_id: str,
        symbol: str,
        series: SeriesKind,
        failure: _ClassifiedFailure,
        *,
        attempt_count: int,
        circuit_state: str,
    ) -> SeriesRefreshOutcome:
        key = (self._source.name.lower(), symbol, series)
        existing = self._cache.get(key)
        status = failure.status
        from_cache = False
        snapshot: SeriesSnapshot
        if (
            existing is not None
            and existing.records
            and status
            not in {
                SeriesStatus.UNSUPPORTED,
                SeriesStatus.UNSUPPORTED_INTERVAL,
            }
        ):
            age = (
                _as_utc(self._now()) - existing.records[-1].timestamp
            ).total_seconds()
            ceiling = (
                self._config.funding_max_age_seconds
                if series is SeriesKind.FUNDING
                else self._config.oi_max_age_seconds
            )
            status = SeriesStatus.CACHED if age <= ceiling else SeriesStatus.STALE
            from_cache = True
            snapshot = existing.model_copy(
                update={
                    "status": status,
                    "from_cache": True,
                    "error_code": failure.code,
                    "predicted_funding_rate": None,
                    "predicted_funding_observed_at": None,
                }
            )
        else:
            snapshot = SeriesSnapshot(
                venue=self._source.name.lower(),
                symbol=symbol,
                series=series,
                fetched_at=_as_utc(self._now()),
                status=status,
                error_code=failure.code,
            )
        self._cache[key] = snapshot
        outcome = SeriesRefreshOutcome(
            symbol=symbol,
            series=series,
            status=status,
            error_code=failure.code,
            attempt_count=attempt_count,
            circuit_state=cast(Any, circuit_state),
            from_cache=from_cache,
        )
        self._emit_transition(cycle_id, snapshot, outcome)
        return outcome

    def _emit_transition(
        self,
        cycle_id: str,
        snapshot: SeriesSnapshot,
        outcome: SeriesRefreshOutcome,
    ) -> None:
        if self._event_sink is None:
            return
        state_key = (snapshot.symbol, snapshot.series)
        fresh = outcome.status is SeriesStatus.FRESH
        if fresh and not self._degraded.get(state_key, False):
            return
        dedupe_key = (cycle_id, snapshot.symbol, snapshot.series)
        if dedupe_key in self._event_dedupe:
            return
        self._event_dedupe.add(dedupe_key)
        event_type = (
            ActivityEventType.DERIVATIVES_DATA_RECOVERED
            if fresh
            else ActivityEventType.DERIVATIVES_DATA_DEGRADED
        )
        self._degraded[state_key] = not fresh
        tail = snapshot.records[-1].timestamp if snapshot.records else None
        age = None
        if tail is not None:
            age = max(0.0, (_as_utc(self._now()) - tail).total_seconds())
        self._event_sink.append(
            event_type,
            details={
                "exchange": snapshot.venue,
                "symbol": snapshot.symbol,
                "series": snapshot.series.value,
                "status": outcome.status.value,
                "error_code": outcome.error_code,
                "data_timestamp": None if tail is None else tail.isoformat(),
                "data_age_seconds": age,
                "cache_status": "cached" if outcome.from_cache else "remote",
                "attempt_count": outcome.attempt_count,
                "circuit_state": outcome.circuit_state,
                "truncated_at_venue_retention": (snapshot.truncated_at_venue_retention),
            },
            cycle_id=cycle_id,
        )


def _classify_failure(exc: Exception) -> _ClassifiedFailure:
    if isinstance(exc, UnsupportedFundingIntervalError):
        return _ClassifiedFailure(
            "unsupported_interval", SeriesStatus.UNSUPPORTED_INTERVAL, False
        )
    if isinstance(exc, DerivativesDataNotSupportedError):
        return _ClassifiedFailure("unsupported_venue", SeriesStatus.UNSUPPORTED, False)
    if isinstance(exc, DerivativesDataValidationError):
        return _ClassifiedFailure(
            cast(DerivativesErrorCode, exc.code), SeriesStatus.UNAVAILABLE, False
        )
    if isinstance(exc, DerivativesDataError):
        return _ClassifiedFailure(
            cast(DerivativesErrorCode, exc.code), SeriesStatus.UNAVAILABLE, False
        )
    if isinstance(exc, _BudgetExhausted):
        return _ClassifiedFailure(
            "request_budget_exhausted", SeriesStatus.UNAVAILABLE, False
        )
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return _ClassifiedFailure("deadline_exceeded", SeriesStatus.UNAVAILABLE, False)
    if isinstance(exc, ExchangeAPIError):
        code = cast(DerivativesErrorCode, exc.code or "venue_unavailable")
        if code == "authentication_unexpected":
            return _ClassifiedFailure(code, SeriesStatus.UNAVAILABLE, False)
        return _ClassifiedFailure(
            code,
            SeriesStatus.UNAVAILABLE,
            code in _TRANSIENT_CODES,
        )
    return _ClassifiedFailure("internal_error", SeriesStatus.UNAVAILABLE, False)


def _merge_records(
    existing: tuple[Any, ...], incoming: tuple[Any, ...], *, limit: int
) -> tuple[Any, ...]:
    by_timestamp = {record.timestamp: record for record in existing}
    for record in incoming:
        by_timestamp[record.timestamp] = record
    records = tuple(by_timestamp[key] for key in sorted(by_timestamp))
    if len(records) > limit:
        records = records[-limit:]
    return records


def _summary(
    cycle_id: str, outcomes: tuple[SeriesRefreshOutcome, ...]
) -> RefreshSummary:
    return RefreshSummary(
        cycle_id=cycle_id,
        requested_count=len(outcomes),
        completed_count=sum(item.status is SeriesStatus.FRESH for item in outcomes),
        cached_count=sum(item.from_cache for item in outcomes),
        unavailable_count=sum(
            item.status
            in {
                SeriesStatus.STALE,
                SeriesStatus.UNAVAILABLE,
                SeriesStatus.UNSUPPORTED,
                SeriesStatus.UNSUPPORTED_INTERVAL,
            }
            for item in outcomes
        ),
        cancelled_count=sum(
            item.error_code == "deadline_exceeded" for item in outcomes
        ),
        outcomes=outcomes,
    )


def _canonical_symbol(symbol: str) -> str:
    canonical = symbol.strip().upper()
    if not canonical:
        raise ValueError("symbol cannot be empty")
    return canonical


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("runtime clock must return timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _datetime_ms(value: datetime) -> int:
    return int(_as_utc(value).timestamp() * 1000)


__all__ = ["ActivityEventSink", "DerivativesContextService"]
