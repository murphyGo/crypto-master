"""DEBT-090: exercise real adapter boundaries without exchange traffic."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from ccxt.base.errors import (
    DDoSProtection,
    ExchangeNotAvailable,
    RateLimitExceeded,
    RequestTimeout,
)

from src.config import BinanceConfig, BybitConfig, DerivativesDataConfig
from src.exchange import request_backoff
from src.exchange.base import ExchangeAPIError, ExchangeConnectionError
from src.exchange.binance import BinanceExchange
from src.exchange.bybit import BybitExchange
from src.models import OrderRequest
from src.runtime.derivatives_context import DerivativesContextService


def adapter(venue="binance", *, market="futures", testnet=True):
    exchange = (
        BinanceExchange(BinanceConfig(market_type=market), testnet=testnet)
        if venue == "binance"
        else BybitExchange(BybitConfig(), testnet=testnet)
    )
    exchange._client = AsyncMock()
    exchange._client.last_response_headers = None
    return exchange


CALLS = [
    ("get_ohlcv", ("BTC/USDT", "1h"), "fetch_ohlcv"),
    ("get_ticker", ("BTC/USDT",), "fetch_ticker"),
    ("get_balance", (), "fetch_balance"),
    (
        "create_order",
        (
            OrderRequest(
                symbol="BTC/USDT", side="buy", type="market", quantity=Decimal("1")
            ),
        ),
        "create_market_order",
    ),
    (
        "create_order",
        (
            OrderRequest(
                symbol="BTC/USDT",
                side="buy",
                type="limit",
                quantity=Decimal("1"),
                price=Decimal("100"),
            ),
        ),
        "create_limit_order",
    ),
    ("cancel_order", ("order-1", "BTC/USDT"), "cancel_order"),
    ("get_order", ("order-1", "BTC/USDT"), "fetch_order"),
    ("get_open_orders", (), "fetch_open_orders"),
]


@pytest.mark.parametrize("venue", ["binance", "bybit"])
@pytest.mark.parametrize(
    "error_type", [DDoSProtection, RequestTimeout, ExchangeNotAvailable]
)
@pytest.mark.parametrize("method,args,ccxt_method", CALLS)
async def test_network_failures_are_domain_errors_without_resubmission(
    venue, error_type, method, args, ccxt_method
):
    exchange = adapter(venue)
    request = getattr(exchange._client, ccxt_method)
    request.side_effect = error_type("synthetic transport failure")

    with pytest.raises(ExchangeAPIError):
        await getattr(exchange, method)(*args)

    request.assert_awaited_once()


async def test_ban_suppresses_sibling_account_and_protective_order_requests():
    first, second = adapter(), adapter()
    first._client.fetch_ohlcv.side_effect = DDoSProtection("synthetic HTTP 418")
    with pytest.raises(ExchangeAPIError):
        await first.get_ohlcv("BTC/USDT", "1h")

    for method, args, ccxt_method in CALLS:
        with pytest.raises(ExchangeAPIError) as caught:
            await getattr(second, method)(*args)
        assert caught.value.code == "RATE_LIMIT"
        assert 0 < caught.value.retry_after_seconds <= 120
        getattr(second._client, ccxt_method).assert_not_awaited()


@pytest.fixture
def clock(monkeypatch):
    state = SimpleNamespace(wall=1793304000.0, monotonic=1000.0)
    monkeypatch.setattr(
        request_backoff,
        "time",
        SimpleNamespace(time=lambda: state.wall, monotonic=lambda: state.monotonic),
    )
    return state


@pytest.mark.parametrize(
    "header,offset,expected",
    [
        ("17", None, 17),
        ("NaN", None, 120),
        ("inf", None, 120),
        ("-10", None, 120),
        ("0", None, 120),
        ("bad date", None, 120),
        ("http-date", None, 240),
        (None, 900, 900),
        ("1200", 900, 1200),
        ("17", 900, 900),
        (None, -900, 120),
    ],
)
async def test_retry_hints_are_honored_without_replaying_requests(
    clock, header, offset, expected
):
    exchange = adapter()
    if header == "http-date":
        header = format_datetime(
            datetime.fromtimestamp(clock.wall + 240, tz=timezone.utc)
        )
    message = "synthetic HTTP 418"
    if offset is not None:
        message += f" IP banned until {int((clock.wall + offset) * 1000)}"

    async def fail(*args, **kwargs):
        exchange._client.last_response_headers = {"rEtRy-AfTeR": header}
        raise DDoSProtection(message)

    exchange._client.fetch_ohlcv.side_effect = fail
    with pytest.raises(ExchangeAPIError) as caught:
        await exchange.get_ohlcv("BTC/USDT", "1h")
    assert caught.value.retry_after_seconds == expected
    assert "IP banned" not in str(caught.value)

    # A jump in wall time cannot prematurely reopen a known monotonic deadline.
    clock.wall += 100000
    clock.monotonic += expected - 0.1
    with pytest.raises(ExchangeAPIError):
        await exchange.get_ohlcv("BTC/USDT", "1h")
    exchange._client.fetch_ohlcv.assert_awaited_once()
    clock.monotonic += 0.1
    exchange._client.fetch_ohlcv.side_effect = None
    exchange._client.fetch_ohlcv.return_value = []
    assert await exchange.get_ohlcv("BTC/USDT", "1h") == []
    assert exchange._client.fetch_ohlcv.await_count == 2


async def test_stale_response_headers_are_not_reused(clock):
    exchange = adapter()
    exchange._client.last_response_headers = {"Retry-After": "9000"}
    exchange._client.fetch_ohlcv.side_effect = RateLimitExceeded("429")
    with pytest.raises(ExchangeAPIError) as caught:
        await exchange.get_ohlcv("BTC/USDT", "1h")
    assert caught.value.retry_after_seconds == 60


async def test_scope_isolation_and_new_instance_persistence(clock):
    exchange = adapter()
    exchange._client.fetch_ohlcv.side_effect = DDoSProtection("418")
    with pytest.raises(ExchangeAPIError):
        await exchange.get_ohlcv("BTC/USDT", "1h")
    await exchange.disconnect()

    replacement = adapter()
    with pytest.raises(ExchangeAPIError):
        await replacement.get_ohlcv("BTC/USDT", "1h")
    replacement._client.fetch_ohlcv.assert_not_awaited()
    for independent in (
        adapter("bybit"),
        adapter(market="spot"),
        adapter(testnet=False),
    ):
        independent._client.fetch_ohlcv.return_value = []
        assert await independent.get_ohlcv("BTC/USDT", "1h") == []
        independent._client.fetch_ohlcv.assert_awaited_once()


async def test_connect_honors_ban_and_reconnect_does_not_reset_it(clock, monkeypatch):
    exchange = adapter()
    client = exchange._client
    monkeypatch.setattr(exchange, "_build_client", lambda *args: client)
    client.load_markets.side_effect = DDoSProtection("418")
    with pytest.raises(ExchangeConnectionError):
        await exchange.connect()
    await exchange.disconnect()
    with pytest.raises(ExchangeConnectionError):
        await exchange.connect()
    client.load_markets.assert_awaited_once()


DERIVATIVES_CALLS = [
    ("get_funding_rate", {}, "fetch_funding_rate"),
    ("get_open_interest", {}, "fetch_open_interest"),
    (
        "get_funding_rate_history",
        {"since": 1793232000000},
        "fetch_funding_rate_history",
    ),
    (
        "get_open_interest_history",
        {"since": 1793232000000},
        "fetch_open_interest_history",
    ),
]


@pytest.mark.parametrize("method,kwargs,ccxt_method", DERIVATIVES_CALLS)
async def test_derivatives_share_futures_cooldown_even_on_spot_adapter(
    clock, method, kwargs, ccxt_method
):
    spot = adapter(market="spot")
    request = getattr(spot._client, ccxt_method)
    request.side_effect = DDoSProtection("secret-url HTTP 418")
    with pytest.raises(ExchangeAPIError) as caught:
        await getattr(spot, method)("BTC/USDT", **kwargs)
    assert caught.value.code == "rate_limited"
    assert caught.value.retry_after_seconds == 120
    assert "secret-url" not in str(caught.value)
    with pytest.raises(ExchangeAPIError):
        await getattr(spot, method)("BTC/USDT", **kwargs)
    request.assert_awaited_once()

    futures = adapter()
    with pytest.raises(ExchangeAPIError):
        await futures.get_ohlcv("BTC/USDT", "1h")
    futures._client.fetch_ohlcv.assert_not_awaited()
    spot._client.fetch_ohlcv.return_value = []
    assert await spot.get_ohlcv("BTC/USDT", "1h") == []


async def test_cancellation_propagates_without_cooldown():
    exchange = adapter()
    exchange._client.fetch_ohlcv.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await exchange.get_ohlcv("BTC/USDT", "1h")
    exchange._client.fetch_ohlcv.side_effect = None
    exchange._client.fetch_ohlcv.return_value = []
    assert await exchange.get_ohlcv("BTC/USDT", "1h") == []


async def test_inflight_response_cannot_shorten_ban(clock):
    first, second = adapter(), adapter()
    entered, release = asyncio.Event(), asyncio.Event()

    async def later_failure(*args, **kwargs):
        entered.set()
        await release.wait()
        raise RateLimitExceeded("429")

    second._client.fetch_ohlcv.side_effect = later_failure
    pending = asyncio.create_task(second.get_ohlcv("BTC/USDT", "1h"))
    await entered.wait()
    first._client.fetch_ohlcv.side_effect = DDoSProtection("418")
    with pytest.raises(ExchangeAPIError):
        await first.get_ohlcv("BTC/USDT", "1h")
    release.set()
    with pytest.raises(ExchangeAPIError) as caught:
        await pending
    assert caught.value.retry_after_seconds == 120
    with pytest.raises(ExchangeAPIError):
        await second.get_ohlcv("BTC/USDT", "1h")
    second._client.fetch_ohlcv.assert_awaited_once()


def test_registry_capacity_never_evicts_an_active_ban(clock):
    for i in range(request_backoff.MAX_SCOPES):
        request_backoff.record_backoff(
            (f"venue-{i}", "spot", True), DDoSProtection("418"), None
        )
    with pytest.raises(request_backoff.RequestBackoff):
        request_backoff.check_backoff(("new-venue", "spot", True))
    request_backoff.record_backoff(
        ("new-venue", "spot", True), DDoSProtection("418"), None
    )
    assert len(request_backoff._deadlines) == request_backoff.MAX_SCOPES
    with pytest.raises(request_backoff.RequestBackoff):
        request_backoff.check_backoff(("venue-0", "spot", True))
    clock.monotonic += 120
    request_backoff.check_backoff(("new-venue", "spot", True))
    assert request_backoff._deadlines == {}


@pytest.mark.parametrize("series", ["funding", "oi"])
async def test_history_next_page_is_suppressed_after_an_inflight_sibling_ban(
    clock, series
):
    history, other = adapter(), adapter()
    other._client.fetch_ohlcv.side_effect = DDoSProtection("418")
    raw = {"symbol": "BTC/USDT:USDT", "timestamp": 1793232000000}
    raw.update(
        {"fundingRate": "0.0001"}
        if series == "funding"
        else {"openInterestAmount": "100"}
    )

    async def first_page(*args, **kwargs):
        with pytest.raises(ExchangeAPIError):
            await other.get_ohlcv("BTC/USDT", "1h")
        return [raw]

    request = (
        history._client.fetch_funding_rate_history
        if series == "funding"
        else history._client.fetch_open_interest_history
    )
    request.side_effect = first_page
    method = (
        history.get_funding_rate_history
        if series == "funding"
        else history.get_open_interest_history
    )
    with pytest.raises(ExchangeAPIError) as caught:
        await method("BTC/USDT", since=1793232000000, limit=2)
    assert caught.value.code == "rate_limited"
    request.assert_awaited_once()


async def test_derivative_retry_after_is_bounded_by_refresh_deadline(
    clock, monkeypatch
):
    exchange = adapter()
    monkeypatch.setattr(exchange, "connect", AsyncMock())
    exchange._client.fetch_funding_rate.side_effect = DDoSProtection("418")
    exchange._client.fetch_open_interest.side_effect = DDoSProtection("418")
    exchange._client.fetch_funding_rate_history.side_effect = DDoSProtection("418")
    exchange._client.fetch_open_interest_history.side_effect = DDoSProtection("418")
    service = DerivativesContextService(
        exchange,
        DerivativesDataConfig(
            enabled=True,
            deadline_4_symbols_seconds=0.02,
            deadline_20_symbols_seconds=0.02,
        ),
    )
    try:
        summary = await asyncio.wait_for(
            service.refresh_cycle(cycle_id="ban", cycle_index=1, symbols=["BTC/USDT"]),
            timeout=1,
        )
        assert summary.cancelled_count == 2
        assert (
            exchange._client.fetch_funding_rate.await_count
            + exchange._client.fetch_open_interest.await_count
            + exchange._client.fetch_funding_rate_history.await_count
            + exchange._client.fetch_open_interest_history.await_count
            == 1
        )
        context = service.context_for(
            "BTC/USDT", as_of=datetime.now(timezone.utc)
        ).context
        assert context is not None
        assert context.funding == ()
        assert context.open_interest == ()
        assert context.funding_availability.error_code == "deadline_exceeded"
        assert context.open_interest_availability.error_code == "deadline_exceeded"
    finally:
        await service.close()
