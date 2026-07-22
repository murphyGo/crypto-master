"""Binance exchange implementation for Crypto Master.

Related Requirements:
- FR-016: Binance Integration - Execute trades and query data through Binance API
- FR-019: Exchange Abstraction - Common interface for all exchanges
- FR-020: Historical Chart Data Query - OHLCV data collection
- CON-002: Rate Limit Compliance - Comply with exchange rate limits

CAH-11: the shared ccxt-adapter logic lives in ``src.exchange.ccxt_base``.
This adapter overrides only the genuinely-divergent surface: client
construction (spot/futures branch + ``adjustForTimeDifference`` option),
the OHLCV per-page cap, the exchange ``name``, and the config/logger wiring.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, NoReturn, cast

import ccxt.async_support as ccxt
from ccxt.base.errors import (
    AuthenticationError,
    ExchangeNotAvailable,
    NetworkError,
    RateLimitExceeded,
)
from ccxt.base.errors import (
    BaseError as CCXTBaseError,
)
from ccxt.base.errors import (
    ExchangeError as CCXTExchangeError,
)
from pydantic import ValidationError

from src.config import BinanceConfig
from src.exchange.base import ExchangeAPIError
from src.exchange.ccxt_base import CCXTClient, CcxtExchange
from src.exchange.derivatives import (
    CurrentFundingRate,
    DerivativesDataContiguityError,
    DerivativesDataValidationError,
    FundingRate,
    OpenInterestHistory,
    OpenInterestPoint,
    UnsupportedFundingIntervalError,
)
from src.exchange.factory import register_exchange
from src.logger import get_logger
from src.utils.time import from_unix_ms, now_utc

logger = get_logger("crypto_master.exchange.binance")


@register_exchange("binance")
class BinanceExchange(CcxtExchange):
    """Binance exchange implementation using ccxt.

    Supports both spot and futures markets based on config.market_type.
    Uses ccxt's built-in rate limiting for API compliance.

    Related Requirements:
    - FR-016: Binance Integration
    - FR-019: Exchange Abstraction
    - FR-010: Paper Trading Mode (via testnet)
    - CON-002: Rate Limit Compliance
    """

    name = "binance"
    logger = logger
    supports_derivatives_data = True

    # Binance allows up to 1500 candles per OHLCV page.
    OHLCV_LIMIT = 1500
    FUNDING_HISTORY_LIMIT = 1000
    FUNDING_INTERVAL_MS = 8 * 60 * 60 * 1000
    OI_HISTORY_LIMIT = 500
    OI_INTERVAL_MS = 60 * 60 * 1000

    # API URLs (for reference - ccxt handles routing via sandbox parameter)
    MAINNET_URL = "https://api.binance.com"
    TESTNET_SPOT_URL = "https://testnet.binance.vision"
    TESTNET_FUTURES_URL = "https://testnet.binancefutures.com"

    def __init__(self, config: BinanceConfig, testnet: bool = False) -> None:
        """Initialize BinanceExchange.

        Args:
            config: Binance configuration with API credentials and market type
            testnet: Whether to use testnet (sandbox) mode
        """
        super().__init__(config=config, testnet=testnet)
        self.config: BinanceConfig = config

    def _build_client(self, api_key: str, api_secret: str) -> CCXTClient:
        """Construct the configured ccxt client for Binance.

        Chooses ``binanceusdm`` (futures) or ``binance`` (spot) based on
        ``config.market_type`` and sets ``adjustForTimeDifference`` — the
        connect divergence vs the single-client venues (CAH-11).

        Args:
            api_key: Credential selected against the runtime sandbox flag.
            api_secret: Credential selected against the runtime sandbox flag.

        Returns:
            A configured (not yet validated) ccxt async client.
        """
        # Choose client class based on market type
        if self.config.market_type == "futures":
            exchange_class = ccxt.binanceusdm
        else:
            exchange_class = ccxt.binance

        client_config: dict[str, Any] = {
            "sandbox": self.testnet,
            "enableRateLimit": True,
            "options": {
                "defaultType": self.config.market_type,
                "adjustForTimeDifference": True,
            },
        }
        if api_key or api_secret:
            client_config["apiKey"] = api_key
            client_config["secret"] = api_secret

        # DEBT-005: ccxt is untyped, so the constructed client is Any; cast to
        # the CCXTClient Protocol the base operates against.
        return cast(
            CCXTClient,
            exchange_class(client_config),
        )

    async def get_funding_rate(self, symbol: str) -> CurrentFundingRate:
        """Fetch and normalize Binance's current funding-rate view."""
        client = self._ensure_connected()
        try:
            raw = await client.fetch_funding_rate(symbol)
        except (NetworkError, CCXTExchangeError) as exc:
            self._raise_derivatives_api_error("current funding", exc)
        return self._map_current_funding(symbol, raw)

    async def get_open_interest(self, symbol: str) -> OpenInterestPoint:
        """Fetch and normalize Binance's current open interest."""
        client = self._ensure_connected()
        try:
            raw = await client.fetch_open_interest(symbol)
        except (NetworkError, CCXTExchangeError) as exc:
            self._raise_derivatives_api_error("current open interest", exc)
        return self._map_open_interest_point(symbol, raw)

    async def get_funding_rate_history(
        self,
        symbol: str,
        since: int,
        limit: int = FUNDING_HISTORY_LIMIT,
        *,
        until: int | None = None,
    ) -> list[FundingRate]:
        """Fetch settled 8h funding history using actual-page cursors."""
        self._validate_history_request(since=since, until=until, limit=limit)
        client = self._ensure_connected()
        cursor = since
        collected: dict[int, FundingRate] = {}

        while len(collected) < limit:
            page_limit = min(self.FUNDING_HISTORY_LIMIT, limit - len(collected))
            params = {"endTime": until} if until is not None else {}
            try:
                raw_page = await client.fetch_funding_rate_history(
                    symbol=symbol,
                    since=cursor,
                    limit=page_limit,
                    params=params,
                )
            except (NetworkError, CCXTExchangeError) as exc:
                self._raise_derivatives_api_error("funding history", exc)

            if not raw_page:
                break
            page = sorted(
                (self._map_funding_rate(symbol, item) for item in raw_page),
                key=lambda point: point.timestamp,
            )
            eligible = [
                point
                for point in page
                if self._datetime_ms(point.timestamp) >= since
                and (until is None or self._datetime_ms(point.timestamp) <= until)
            ]
            if not eligible:
                if until is not None and self._datetime_ms(page[0].timestamp) > until:
                    break
                raise DerivativesDataValidationError(
                    "funding history page did not advance the requested cursor"
                )

            for point in eligible:
                collected.setdefault(self._datetime_ms(point.timestamp), point)
                if len(collected) >= limit:
                    break

            last_received_ms = self._datetime_ms(eligible[-1].timestamp)
            if until is not None and last_received_ms >= until:
                break
            next_cursor = last_received_ms + self.FUNDING_INTERVAL_MS
            if next_cursor <= cursor:
                raise DerivativesDataValidationError(
                    "funding history page did not advance the requested cursor"
                )
            cursor = next_cursor

        result = [collected[key] for key in sorted(collected)][:limit]
        self._validate_funding_grid(result)
        return result

    async def get_open_interest_history(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: int | None = None,
        limit: int = OI_HISTORY_LIMIT,
        *,
        until: int | None = None,
    ) -> OpenInterestHistory:
        """Fetch 1h OI history and expose retention-shortened coverage."""
        if timeframe != "1h":
            raise DerivativesDataValidationError(
                "Binance derivatives context supports only 1h OI history",
                code="unsupported_interval",
            )
        self._validate_history_request(since=since, until=until, limit=limit)
        client = self._ensure_connected()
        cursor = since
        collected: dict[int, OpenInterestPoint] = {}

        while len(collected) < limit:
            page_limit = min(self.OI_HISTORY_LIMIT, limit - len(collected))
            params = {"endTime": until} if until is not None else {}
            try:
                raw_page = await client.fetch_open_interest_history(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=cursor,
                    limit=page_limit,
                    params=params,
                )
            except (NetworkError, CCXTExchangeError) as exc:
                self._raise_derivatives_api_error("open-interest history", exc)

            if not raw_page:
                break
            page = sorted(
                (self._map_open_interest_point(symbol, item) for item in raw_page),
                key=lambda point: point.timestamp,
            )
            eligible = [
                point
                for point in page
                if (since is None or self._datetime_ms(point.timestamp) >= since)
                and (until is None or self._datetime_ms(point.timestamp) <= until)
            ]
            if not eligible:
                if until is not None and self._datetime_ms(page[0].timestamp) > until:
                    break
                raise DerivativesDataValidationError(
                    "open-interest history page did not advance the requested cursor"
                )

            for point in eligible:
                collected.setdefault(self._datetime_ms(point.timestamp), point)
                if len(collected) >= limit:
                    break

            last_received_ms = self._datetime_ms(eligible[-1].timestamp)
            if until is not None and last_received_ms >= until:
                break
            next_cursor = last_received_ms + self.OI_INTERVAL_MS
            if cursor is not None and next_cursor <= cursor:
                raise DerivativesDataValidationError(
                    "open-interest history page did not advance the requested cursor"
                )
            cursor = next_cursor

        points = tuple(collected[key] for key in sorted(collected))[:limit]
        self._validate_oi_grid(points)
        actual_since = points[0].timestamp if points else None
        actual_until = points[-1].timestamp if points else None
        truncated = False
        if since is not None and points:
            expected_first = self._ceil_to_grid(since, self.OI_INTERVAL_MS)
            truncated = self._datetime_ms(points[0].timestamp) > expected_first

        try:
            return OpenInterestHistory(
                symbol=symbol,
                requested_since=from_unix_ms(since) if since is not None else None,
                requested_until=from_unix_ms(until) if until is not None else None,
                actual_since=actual_since,
                actual_until=actual_until,
                truncated_at_venue_retention=truncated,
                points=points,
            )
        except ValidationError as exc:
            raise DerivativesDataValidationError(
                "open-interest history failed normalized validation"
            ) from exc

    @classmethod
    def _map_current_funding(
        cls, symbol: str, raw: dict[str, Any]
    ) -> CurrentFundingRate:
        cls._require_mapping(raw, "current funding")
        cls._validate_response_symbol(symbol, raw.get("symbol"))
        interval_hours = cls._parse_funding_interval(raw.get("interval"))
        if interval_hours is not None and interval_hours != 8:
            raise UnsupportedFundingIntervalError(
                "Binance funding interval is not the supported 8h interval"
            )
        raw_timestamp = raw.get("timestamp")
        observed_at = (
            cls._required_timestamp(raw_timestamp, "timestamp")
            if raw_timestamp is not None
            else now_utc()
        )
        next_timestamp = raw.get("nextFundingTimestamp")
        try:
            return CurrentFundingRate(
                symbol=symbol,
                observed_at=observed_at,
                rate=cls._required_decimal(raw.get("fundingRate"), "fundingRate"),
                predicted_rate=cls._optional_decimal(
                    raw.get("nextFundingRate"), "nextFundingRate"
                ),
                next_funding_at=(
                    cls._required_timestamp(next_timestamp, "nextFundingTimestamp")
                    if next_timestamp is not None
                    else None
                ),
                interval_hours=interval_hours,
            )
        except ValidationError as exc:
            raise DerivativesDataValidationError(
                "current funding failed normalized validation"
            ) from exc

    @classmethod
    def _map_funding_rate(cls, symbol: str, raw: Any) -> FundingRate:
        cls._require_mapping(raw, "funding history")
        cls._validate_response_symbol(symbol, raw.get("symbol"))
        try:
            return FundingRate(
                symbol=symbol,
                timestamp=cls._required_timestamp(raw.get("timestamp"), "timestamp"),
                rate=cls._required_decimal(raw.get("fundingRate"), "fundingRate"),
            )
        except ValidationError as exc:
            raise DerivativesDataValidationError(
                "funding history point failed normalized validation"
            ) from exc

    @classmethod
    def _map_open_interest_point(cls, symbol: str, raw: Any) -> OpenInterestPoint:
        cls._require_mapping(raw, "open interest")
        cls._validate_response_symbol(symbol, raw.get("symbol"))
        try:
            return OpenInterestPoint(
                symbol=symbol,
                timestamp=cls._required_timestamp(raw.get("timestamp"), "timestamp"),
                open_interest=cls._required_decimal(
                    raw.get("openInterestAmount"), "openInterestAmount"
                ),
                open_interest_value=cls._optional_decimal(
                    raw.get("openInterestValue"), "openInterestValue"
                ),
            )
        except ValidationError as exc:
            raise DerivativesDataValidationError(
                "open-interest point failed normalized validation"
            ) from exc

    @staticmethod
    def _require_mapping(raw: Any, operation: str) -> None:
        if not isinstance(raw, dict):
            raise DerivativesDataValidationError(
                f"{operation} response was not an object"
            )

    @staticmethod
    def _validate_response_symbol(requested: str, received: Any) -> None:
        if received is None:
            return
        if not isinstance(received, str):
            raise DerivativesDataValidationError("response symbol was not text")
        canonical = received.split(":", maxsplit=1)[0]
        if canonical != requested:
            raise DerivativesDataValidationError(
                "response symbol did not match the requested symbol"
            )

    @staticmethod
    def _required_decimal(value: Any, field: str) -> Decimal:
        if value is None or isinstance(value, bool):
            raise DerivativesDataValidationError(f"{field} was missing or invalid")
        try:
            result = Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise DerivativesDataValidationError(f"{field} was invalid") from exc
        if not result.is_finite():
            raise DerivativesDataValidationError(f"{field} was not finite")
        return result

    @classmethod
    def _optional_decimal(cls, value: Any, field: str) -> Decimal | None:
        if value is None:
            return None
        return cls._required_decimal(value, field)

    @staticmethod
    def _required_timestamp(value: Any, field: str) -> datetime:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DerivativesDataValidationError(f"{field} was missing or invalid")
        try:
            timestamp_ms = int(value)
        except (ArithmeticError, OSError, OverflowError, ValueError) as exc:
            raise DerivativesDataValidationError(f"{field} was invalid") from exc
        if timestamp_ms < 0 or timestamp_ms != value:
            raise DerivativesDataValidationError(f"{field} was invalid")
        try:
            return from_unix_ms(timestamp_ms)
        except (ArithmeticError, OSError, OverflowError, ValueError) as exc:
            raise DerivativesDataValidationError(f"{field} was invalid") from exc

    @staticmethod
    def _parse_funding_interval(value: Any) -> int | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.endswith("h"):
            raise DerivativesDataValidationError("funding interval was invalid")
        try:
            hours = int(value[:-1])
        except ValueError as exc:
            raise DerivativesDataValidationError(
                "funding interval was invalid"
            ) from exc
        if hours <= 0:
            raise DerivativesDataValidationError("funding interval was invalid")
        return hours

    @classmethod
    def _validate_history_request(
        cls, *, since: int | None, until: int | None, limit: int
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise DerivativesDataValidationError("history limit must be positive")
        for name, value in (("since", since), ("until", until)):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise DerivativesDataValidationError(
                    f"history {name} must be a non-negative UTC millisecond timestamp"
                )
            if value is not None:
                cls._required_timestamp(value, f"history {name}")
        if since is not None and until is not None and until < since:
            raise DerivativesDataValidationError(
                "history until must be on or after since"
            )

    @classmethod
    def _validate_funding_grid(cls, points: list[FundingRate]) -> None:
        timestamps = [cls._datetime_ms(point.timestamp) for point in points]
        if any(timestamp % cls.FUNDING_INTERVAL_MS for timestamp in timestamps):
            raise UnsupportedFundingIntervalError(
                "funding history is not aligned to the supported 8h UTC grid"
            )
        for previous, current in zip(timestamps, timestamps[1:], strict=False):
            delta = current - previous
            if delta == cls.FUNDING_INTERVAL_MS:
                continue
            if delta > cls.FUNDING_INTERVAL_MS and delta % cls.FUNDING_INTERVAL_MS == 0:
                raise DerivativesDataContiguityError(
                    "funding history contains a missing 8h interval"
                )
            raise UnsupportedFundingIntervalError(
                "funding history spacing is not the supported 8h interval"
            )

    @classmethod
    def _validate_oi_grid(cls, points: tuple[OpenInterestPoint, ...]) -> None:
        timestamps = [cls._datetime_ms(point.timestamp) for point in points]
        if any(timestamp % cls.OI_INTERVAL_MS for timestamp in timestamps):
            raise DerivativesDataContiguityError(
                "open-interest history is not aligned to the 1h UTC grid"
            )
        for previous, current in zip(timestamps, timestamps[1:], strict=False):
            if current - previous != cls.OI_INTERVAL_MS:
                raise DerivativesDataContiguityError(
                    "open-interest history contains a missing 1h interval"
                )

    @staticmethod
    def _datetime_ms(value: datetime) -> int:
        return int(value.timestamp() * 1000)

    @staticmethod
    def _ceil_to_grid(value: int, interval: int) -> int:
        return ((value + interval - 1) // interval) * interval

    @staticmethod
    def _raise_derivatives_api_error(operation: str, exc: CCXTBaseError) -> NoReturn:
        if isinstance(exc, RateLimitExceeded):
            code = "rate_limited"
            category = "rate limited"
        elif isinstance(exc, ExchangeNotAvailable):
            code = "venue_unavailable"
            category = "venue unavailable"
        elif isinstance(exc, NetworkError):
            code = "network_transient"
            category = "network failure"
        elif isinstance(exc, AuthenticationError):
            code = "authentication_unexpected"
            category = "unexpected authentication failure"
        else:
            code = "remote_5xx"
            category = "exchange API failure"
        raise ExchangeAPIError(
            f"Binance {operation} {category}",
            code=code,
        ) from exc
