"""Configuration management module for Crypto Master.

This module provides centralized configuration management using Pydantic Settings.
All configuration is loaded from environment variables and .env file.

Related Requirements:
- NFR-004: Environment Variable Management
- NFR-011: API Key Protection
"""

import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class BinanceConfig(BaseSettings):
    """Binance exchange configuration.

    Environment variables:
    - BINANCE_API_KEY: API key for Binance (live/mainnet)
    - BINANCE_API_SECRET: API secret for Binance (live/mainnet)
    - BINANCE_TESTNET_API_KEY: API key for Binance testnet
    - BINANCE_TESTNET_API_SECRET: API secret for Binance testnet
    - BINANCE_MARKET_TYPE: Market type (spot/futures)
    - BINANCE_TESTNET: Whether to use testnet
    """

    api_key: str = ""
    api_secret: str = ""
    testnet_api_key: str = ""
    testnet_api_secret: str = ""
    market_type: Literal["spot", "futures"] = "futures"
    testnet: bool = True

    model_config = SettingsConfigDict(env_prefix="BINANCE_")

    def is_configured(self) -> bool:
        """Check if API credentials are configured.

        Returns True if either live or testnet credentials are set.
        """
        has_live = bool(self.api_key and self.api_secret)
        has_testnet = bool(self.testnet_api_key and self.testnet_api_secret)
        return has_live or has_testnet

    def get_credentials(self, testnet: bool | None = None) -> tuple[str, str]:
        """Get appropriate API credentials for the runtime mode.

        ``testnet`` (when provided) overrides ``self.testnet`` so callers
        such as :class:`src.exchange.binance.BinanceExchange` can align
        credential selection with the runtime sandbox flag they were
        constructed with — the legacy ``BINANCE_TESTNET`` env field is
        only the default, the exchange instance's mode is the source of
        truth.

        Returns testnet credentials when the resolved mode is testnet and
        testnet keys are set; otherwise returns live credentials. The
        fallback path preserves prior behaviour when only one credential
        set is configured.

        Args:
            testnet: Optional override for the runtime testnet mode.

        Returns:
            Tuple of (api_key, api_secret).
        """
        resolved_testnet = self.testnet if testnet is None else testnet
        if resolved_testnet and self.testnet_api_key:
            return self.testnet_api_key, self.testnet_api_secret
        return self.api_key, self.api_secret


class BybitConfig(BaseSettings):
    """Bybit exchange configuration.

    Environment variables:
    - BYBIT_API_KEY: API key for Bybit (live/mainnet)
    - BYBIT_API_SECRET: API secret for Bybit (live/mainnet)
    - BYBIT_TESTNET_API_KEY: API key for Bybit testnet
    - BYBIT_TESTNET_API_SECRET: API secret for Bybit testnet
    - BYBIT_TESTNET: Whether to use testnet
    """

    api_key: str = ""
    api_secret: str = ""
    testnet_api_key: str = ""
    testnet_api_secret: str = ""
    testnet: bool = True

    model_config = SettingsConfigDict(env_prefix="BYBIT_")

    def is_configured(self) -> bool:
        """Check if API credentials are configured.

        Returns True if either live or testnet credentials are set.
        """
        has_live = bool(self.api_key and self.api_secret)
        has_testnet = bool(self.testnet_api_key and self.testnet_api_secret)
        return has_live or has_testnet

    def get_credentials(self, testnet: bool | None = None) -> tuple[str, str]:
        """Get appropriate API credentials for the runtime mode.

        ``testnet`` (when provided) overrides ``self.testnet`` so callers
        such as :class:`src.exchange.bybit.BybitExchange` can align
        credential selection with the runtime sandbox flag they were
        constructed with — the legacy ``BYBIT_TESTNET`` env field is only
        the default, the exchange instance's mode is the source of truth.

        Returns testnet credentials when the resolved mode is testnet and
        testnet keys are set; otherwise returns live credentials. The
        fallback path preserves prior behaviour when only one credential
        set is configured.

        Args:
            testnet: Optional override for the runtime testnet mode.

        Returns:
            Tuple of (api_key, api_secret).
        """
        resolved_testnet = self.testnet if testnet is None else testnet
        if resolved_testnet and self.testnet_api_key:
            return self.testnet_api_key, self.testnet_api_secret
        return self.api_key, self.api_secret


class ExchangeCredential(BaseModel):
    """Named exchange credential set for multi-account live mode.

    ``ref`` is the stable sub-account binding key (for example
    ``binance_main`` or ``binance_alt``). Secrets remain env-sourced;
    this model only carries the loaded values in memory.
    """

    ref: str
    exchange: Literal["binance", "bybit"]
    api_key: str
    api_secret: str
    testnet: bool = False
    market_type: Literal["spot", "futures"] = "futures"

    def to_binance_config(self) -> BinanceConfig:
        """Convert to the existing Binance adapter config shape."""
        return BinanceConfig(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet,
            market_type=self.market_type,
        )

    def to_bybit_config(self) -> BybitConfig:
        """Convert to the existing Bybit adapter config shape."""
        return BybitConfig(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet,
        )


class Settings(BaseSettings):
    """Main application settings.

    Loads configuration from environment variables and .env file.
    Nested exchange configurations are loaded with their respective prefixes.
    """

    # Trading Mode
    trading_mode: Literal["paper", "live"] = "paper"

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_file: Path = Path("data/logs/crypto-master.log")

    # Data Storage
    data_dir: Path = Path("data")

    # Paper Trading Configuration
    paper_initial_balance: float = Field(default=10000.0, gt=0)
    # Phase 22.2 / DEBT-027 paper-trader liquidation visibility opt-out.
    # Default ``False`` lets ``PaperTrader`` record true negative equity
    # when an under-water close would push free balance below zero
    # (closes the paper-vs-live forecasting gap). Setting ``True``
    # re-enables the legacy ``balance.free = 0`` clamp — intended only
    # for testing scenarios that need a continuing run past a paper
    # liquidation. Either way the engine logs a ``LIQUIDATED`` activity
    # event so the shortfall surfaces on the dashboard.
    paper_auto_deposit_on_liquidation: bool = Field(default=False)

    # Risk Management
    max_leverage: int = Field(default=10, ge=1, le=125)
    max_position_size_pct: float = Field(default=10.0, gt=0, le=100)
    default_stop_loss_pct: float = Field(default=2.0, gt=0, le=100)

    # Trading Engine Tunables (Phase 10.2)
    # Defaults match ``src.runtime.engine.EngineConfig`` so existing
    # deployments don't change behaviour without an explicit env setting.
    engine_cycle_interval: int = Field(default=300, ge=10)
    engine_auto_approve_threshold: float = Field(default=1.0, ge=0.0)
    engine_runtime_safety_pause_min_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    # ``NoDecode`` prevents pydantic-settings from JSON-parsing the env
    # string before the validator runs; without it,
    # ``ENGINE_SYMBOLS=BTC/USDT,ETH/USDT`` raises a JSON decode error.
    engine_symbols: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "ETH/USDT",
            "SOL/USDT",
            "BNB/USDT",
            "ADA/USDT",
            "AVAX/USDT",
        ]
    )
    engine_balance: Decimal = Field(default=Decimal("10000"))
    # Phase 12.1 cross-cycle position cap. Hard cap on open positions
    # per symbol applied at the engine execution gate. Default 1
    # matches pre-12.1 implicit behaviour for the per-cycle dedup;
    # raise only if you want intentional pyramiding.
    engine_max_open_positions_per_symbol: int = Field(default=1, ge=1)

    # Phase 13.2 (DEBT-003): the remaining ``EngineConfig`` fields are
    # also env-overridable. Defaults match
    # ``src.runtime.engine.EngineConfig`` so existing deployments do
    # not change behaviour without an explicit env setting.
    # Seconds between SL/TP monitor polls of open positions inside
    # one cycle. Minimum 10. Default 60.
    engine_monitor_interval: int = Field(default=60, ge=10)
    # Symbol used for the per-cycle Bitcoin proposal scan. Altcoin
    # scans come from ``engine_symbols``. Default "BTC/USDT".
    engine_bitcoin_symbol: str = Field(default="BTC/USDT")
    # Top-K cap on altcoin proposals retained per cycle (proposal
    # engine ranks by composite score, then truncates). Minimum 1.
    # Default 3.
    engine_altcoin_top_k: int = Field(default=3, ge=1)
    # Minimum seconds between Claude-backed prompt strategy executions
    # per (strategy, symbol). Default 0 preserves historical behaviour;
    # Fly can raise this to keep prompt strategies out of the hot path.
    engine_prompt_strategy_min_interval_seconds: int = Field(default=0, ge=0)
    # Actor name stamped onto auto-decided proposals + activity log
    # events. Default "auto-engine".
    engine_actor: str = Field(default="auto-engine")

    # Phase 18.1 stale-quote sanity gate at proposal fill. Defaults
    # match ``src.runtime.engine.EngineConfig`` so existing deployments
    # do not change behaviour without an explicit env setting.
    # Maximum absolute drift between the live ticker price and
    # ``proposal.entry_price`` tolerated at fill, expressed as a
    # fraction (50 bps = 0.005). Drift beyond this threshold causes
    # the engine to reject the fill with
    # ``decision_reason="slippage_exceeds_tolerance"``. Minimum 0
    # (== reject any drift). Default 0.005.
    engine_fill_slippage_tolerance: Decimal = Field(default=Decimal("0.005"), ge=0)
    # When True, the engine fetches a fresh ticker before each fill
    # and rejects the proposal if live has already crossed the
    # proposal's stop-loss in the trade direction. Default True
    # (closes the smoking-gun stale-quote bug without an env flip).
    engine_reject_if_past_stop_loss: bool = Field(default=True)
    # Phase 24.2 (DEBT-033 follow-up): opt-in hard rejection when the
    # stale-quote gate has no live data to cross-check against
    # (ticker fetch failure or ticker older than
    # ``ENGINE_MAX_TICKER_AGE_SECONDS``). Default False preserves the
    # existing WARN-and-fall-through behaviour; flip to True for live
    # mode where a fill at ``proposal.entry_price`` without a live
    # cross-check is unacceptable. See
    # ``EngineConfig.reject_if_stale_quote`` for the runtime semantics.
    engine_reject_if_stale_quote: bool = Field(default=False)
    engine_max_ticker_age_seconds: float = Field(default=10.0, gt=0)
    engine_correlation_gate_enabled: bool = Field(default=False)
    engine_correlation_max_sub_accounts_per_symbol_side: int = Field(default=1, ge=1)
    engine_correlation_max_sub_accounts_per_strategy_symbol_side: int = Field(
        default=1,
        ge=1,
    )

    # Phase 17.2 (DEBT-019): backtest engine circuit breaker. Defaults
    # match ``src.backtest.engine.BacktestConfig``'s
    # ``per_bar_timeout`` / ``max_parse_failures`` so existing
    # deployments don't change behaviour without an explicit env
    # setting. ``per_bar_timeout`` wraps every per-bar
    # ``strategy.analyze`` call in ``asyncio.wait_for``;
    # ``max_parse_failures`` is the consecutive-failure ceiling
    # before the engine raises ``BacktestAbortedError``. DEBT-022 adds
    # a cumulative failure-rate counterpart for intermittent failures
    # that never saturate the consecutive counter.
    # DEBT-020: default 600s = chasulang's 480s per-call ceiling
    # (``claude_timeout_seconds`` in ``strategies/chasulang_ict_smc.md``,
    # applied per ``analyze()`` call by ``src/strategy/loader.py``)
    # plus 120s headroom for parsing/validation/disk I/O. Lowering
    # this below the strategy's ``claude_timeout_seconds`` will trip
    # the breaker on every bar.
    engine_backtest_per_bar_timeout: float = Field(default=600.0, ge=1.0)
    engine_backtest_max_parse_failures: int = Field(default=5, ge=1)
    engine_backtest_min_cumulative_parse_failures: int = Field(default=50, ge=1)
    engine_backtest_max_cumulative_parse_failure_rate: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    # Phase 25.2: active-use freshness window for the snapshot-pinned
    # baseline regenerator (``scripts/backtest_baselines.py``). A
    # snapshot whose ``fetched_at`` is older than this fails the run
    # loud unless the operator opts in to ``--refresh-snapshot``. 30
    # days matches the quant-recommended promotion-gate window;
    # ``src.backtest.snapshot.DEFAULT_MAX_AGE_DAYS`` (90) stays as the
    # absolute stale ceiling for general-purpose snapshot consumers.
    engine_baseline_max_snapshot_age_days: int = Field(default=30, ge=1)

    # Log Retention (Phase 10.4)
    # ``JsonlRotator`` keeps the active month + this many archive
    # months merged into ``read_all``. Older rotated files stay on
    # disk untouched but are not surfaced to the application. The
    # same value also drives ``ProposalHistory.purge_old`` (one file
    # per proposal, age-based purge into ``proposals/archive/<YYYY-MM>/``).
    log_retention_months: int = Field(default=12, ge=1)

    # Notification Push Backend (Phase 11.3)
    # Slack incoming-webhook URL. When unset (default), no Slack
    # notifier is registered and the dispatcher falls back to the
    # Console + File backends only. The URL itself is a secret —
    # the application MUST NOT log it. Generate one at
    # https://api.slack.com/messaging/webhooks.
    slack_webhook_url: str | None = Field(default=None)
    # Optional per-route Slack webhooks for sub-account notification
    # overrides. Format:
    # ``NOTIFICATION_SLACK_WEBHOOK_URLS=experimental=https://hooks...``.
    # Multiple entries are comma-separated. JSON objects are also
    # accepted for secret managers that prefer a single structured env
    # value. Route keys are referenced by ``notification_route`` in
    # ``config/sub_accounts.yaml``.
    notification_slack_webhook_urls: Annotated[dict[str, str], NoDecode] = Field(
        default_factory=dict
    )

    # Telegram Notification Backend (Phase 12.4)
    # Bot token + chat id pair for the Telegram Bot API. Both must be
    # set for the notifier to register; if either is missing the
    # dispatcher silently skips the Telegram backend. The bot token is
    # equivalent to a secret API key (anyone with it can drive the
    # bot) and ``TELEGRAM_CHAT_ID`` reveals the destination chat — the
    # application MUST NOT log either value. Create a bot via
    # @BotFather and obtain the chat id from the bot's first update
    # (https://api.telegram.org/bot<TOKEN>/getUpdates).
    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)

    # Email Notification Backend (Phase 13.4)
    # SMTP settings for the email notifier. ALL six fields below must
    # be set for the backend to register; if any is missing the
    # dispatcher silently skips email and falls back to the other
    # backends (matches Slack/Telegram opt-in pattern). The password is
    # a secret — the application MUST NOT log it. STARTTLS is the
    # default (port 587). For an SMTP-over-SSL provider (Yahoo Mail,
    # AT&T, ProtonMail), set ``EMAIL_USE_SSL=true`` AND
    # ``EMAIL_SMTP_PORT=465`` so the notifier uses ``smtplib.SMTP_SSL``
    # and skips the STARTTLS handshake (Phase 14.2 / DEBT-012).
    email_smtp_host: str | None = Field(default=None)
    email_smtp_port: int = Field(default=587, ge=1, le=65535)
    email_smtp_user: str | None = Field(default=None)
    email_smtp_password: str | None = Field(default=None)
    email_from: str | None = Field(default=None)
    email_to: str | None = Field(default=None)
    # Phase 14.2 (DEBT-012): when True, the notifier uses
    # ``smtplib.SMTP_SSL`` on the configured port (typically 465) and
    # skips the STARTTLS upgrade. Default False keeps the existing
    # STARTTLS path (port 587) untouched for backward compatibility.
    email_use_ssl: bool = Field(default=False)

    # Claude CLI Timeout / Retry (Phase 12.3)
    # Base timeout for one ``claude -p`` invocation in seconds.
    # On timeout the wrapper retries up to ``claude_cli_max_retries``
    # times, multiplying the timeout by 1.5x each retry (e.g.
    # 120s → 180s → 270s). After the final timeout the wrapper raises
    # ``ClaudeTimeoutError`` and the proposal engine falls back to
    # neutral (no proposal) for that strategy. Minimum 10s to keep the
    # subprocess from being killed before it can even start.
    claude_cli_timeout_seconds: int = Field(default=120, ge=10)
    # Maximum number of retries on timeout. ``0`` means no retry — the
    # wrapper times out exactly once and propagates. Default 1 (one
    # retry) matches the most common operational case where Claude
    # Code occasionally hits a slow path on first call.
    claude_cli_max_retries: int = Field(default=1, ge=0)
    # Optional model alias/full name passed to ``claude --model``.
    # Empty string preserves Claude CLI's configured default.
    claude_cli_model: str = ""

    # Exchange Configurations (nested)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    bybit: BybitConfig = Field(default_factory=BybitConfig)
    exchange_credentials: dict[str, ExchangeCredential] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("engine_symbols", mode="before")
    @classmethod
    def _parse_engine_symbols(cls, v: object) -> object:
        """Parse ``ENGINE_SYMBOLS`` from a comma-separated env string.

        Pydantic-settings hands env values in as strings; the engine
        wants a ``list[str]``. Empty / blank entries are stripped so
        ``"ETH/USDT, ,SOL/USDT"`` cleans up to two symbols.
        Non-string inputs (e.g. a ``list`` set programmatically in
        tests) pass through untouched.
        """
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("notification_slack_webhook_urls", mode="before")
    @classmethod
    def _parse_notification_slack_webhook_urls(cls, v: object) -> object:
        """Parse route-specific Slack webhook refs from env input."""
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        if not stripped:
            return {}
        if stripped.startswith("{"):
            parsed = json.loads(stripped)
            if not isinstance(parsed, dict):
                raise ValueError(
                    "NOTIFICATION_SLACK_WEBHOOK_URLS JSON must be an object"
                )
            return {str(key): str(value) for key, value in parsed.items()}

        routes: dict[str, str] = {}
        for item in stripped.split(","):
            part = item.strip()
            if not part:
                continue
            if "=" not in part:
                raise ValueError(
                    "NOTIFICATION_SLACK_WEBHOOK_URLS entries must use route=url"
                )
            route, url = part.split("=", 1)
            route = route.strip()
            url = url.strip()
            if not route or not url:
                raise ValueError(
                    "NOTIFICATION_SLACK_WEBHOOK_URLS route and url must be non-empty"
                )
            routes[route] = url
        return routes

    @model_validator(mode="after")
    def _load_exchange_credentials(self) -> "Settings":
        """Populate named credential refs from legacy and EXCHANGE_* env vars."""
        explicit = _parse_named_exchange_credentials(os.environ)
        credentials: dict[str, ExchangeCredential] = {
            **self.exchange_credentials,
            **explicit,
        }

        if self.binance.api_key and self.binance.api_secret:
            if "binance_main" in explicit:
                raise ValueError(
                    "Conflicting credentials: legacy BINANCE_API_KEY/SECRET and "
                    "EXCHANGE_BINANCE_MAIN_* are both set"
                )
            credentials["binance_main"] = ExchangeCredential(
                ref="binance_main",
                exchange="binance",
                api_key=self.binance.api_key,
                api_secret=self.binance.api_secret,
                testnet=False,
                market_type=self.binance.market_type,
            )

        if self.bybit.api_key and self.bybit.api_secret:
            if "bybit_main" in explicit:
                raise ValueError(
                    "Conflicting credentials: legacy BYBIT_API_KEY/SECRET and "
                    "EXCHANGE_BYBIT_MAIN_* are both set"
                )
            credentials["bybit_main"] = ExchangeCredential(
                ref="bybit_main",
                exchange="bybit",
                api_key=self.bybit.api_key,
                api_secret=self.bybit.api_secret,
                testnet=False,
            )

        self.exchange_credentials = credentials
        return self

    def validate_for_live_trading(self) -> None:
        """Validate that configuration is suitable for live trading.

        Raises:
            ValueError: If live trading is enabled but no exchange is configured.
        """
        if self.trading_mode != "live":
            return

        has_live_named_credential = any(
            not credential.testnet for credential in self.exchange_credentials.values()
        )
        if (
            not (self.binance.api_key and self.binance.api_secret)
            and not (self.bybit.api_key and self.bybit.api_secret)
            and not has_live_named_credential
        ):
            raise ValueError(
                "Live trading requires at least one live exchange credential. "
                "Set BINANCE_API_KEY/BINANCE_API_SECRET, "
                "BYBIT_API_KEY/BYBIT_API_SECRET, or an EXCHANGE_<REF> "
                "credential with TESTNET=false."
            )

    def get_configured_exchanges(self) -> list[str]:
        """Return list of exchanges that have API credentials configured."""
        exchanges = []
        if self.binance.is_configured():
            exchanges.append("binance")
        if self.bybit.is_configured():
            exchanges.append("bybit")
        return exchanges

    def get_configured_exchange_refs(self) -> list[str]:
        """Return named exchange credential refs available for sub-accounts."""
        return sorted(self.exchange_credentials)


_EXCHANGE_ENV_RE = re.compile(
    r"^EXCHANGE_(?P<ref>[A-Z0-9_]+)_(?P<field>API_KEY|API_SECRET|TESTNET|EXCHANGE|MARKET_TYPE)$"
)


def _parse_named_exchange_credentials(
    env: os._Environ[str] | dict[str, str],
) -> dict[str, ExchangeCredential]:
    """Parse Phase 19.4 ``EXCHANGE_<REF>_*`` env vars."""
    grouped: dict[str, dict[str, str]] = {}
    for key, value in env.items():
        match = _EXCHANGE_ENV_RE.match(key)
        if match is None:
            continue
        ref = match.group("ref").lower()
        field = match.group("field").lower()
        grouped.setdefault(ref, {})[field] = value

    credentials: dict[str, ExchangeCredential] = {}
    for ref, values in grouped.items():
        api_key = values.get("api_key", "")
        api_secret = values.get("api_secret", "")
        if not api_key or not api_secret:
            continue
        exchange = values.get("exchange") or _infer_exchange_from_ref(ref)
        if exchange not in {"binance", "bybit"}:
            raise ValueError(
                f"EXCHANGE_{ref.upper()}_EXCHANGE must be 'binance' or 'bybit'"
            )
        testnet = values.get("testnet", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        market_type = values.get("market_type", "futures")
        if market_type not in {"spot", "futures"}:
            raise ValueError(
                f"EXCHANGE_{ref.upper()}_MARKET_TYPE must be 'spot' or 'futures'"
            )
        credentials[ref] = ExchangeCredential(
            ref=ref,
            exchange=exchange,  # type: ignore[arg-type]
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            market_type=market_type,  # type: ignore[arg-type]
        )
    return credentials


def _infer_exchange_from_ref(ref: str) -> str:
    if ref.startswith("binance"):
        return "binance"
    if ref.startswith("bybit"):
        return "bybit"
    raise ValueError(
        f"Cannot infer exchange for EXCHANGE_{ref.upper()}_*; set "
        f"EXCHANGE_{ref.upper()}_EXCHANGE=binance or bybit"
    )


# Module-level singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the application settings singleton.

    Returns:
        Settings: The application settings instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload of settings from environment.

    Useful for testing or when environment variables change.

    Returns:
        Settings: A fresh Settings instance.
    """
    global _settings
    _settings = None
    return get_settings()
