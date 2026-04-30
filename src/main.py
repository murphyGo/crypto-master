"""Production entrypoint for the trading runtime.

Run::

    python -m src.main

or via the Fly.io ``trader`` process (see ``fly.toml``).

Wires together Settings, an exchange (testnet for paper, mainnet for
live per ``Settings.trading_mode``), the proposal stack, the trader
(``PaperTrader`` or ``LiveTrader``), notification dispatcher, activity
log, and the ``TradingEngine``. Adds POSIX signal handlers so
SIGINT / SIGTERM trigger a graceful loop exit.

Phase 10.1 wired live mode end-to-end. Both modes use the same
:class:`~src.trading.base.Trader` protocol so the engine is mode-
agnostic — flip ``TRADING_MODE=live`` and provide live API keys to
go from paper to live.

Related Requirements:
- FR-009: Live trading mode
- FR-010: Paper/live mode switching
- FR-026: Automated feedback loop wiring (engine surfaces activity)
- NFR-012: Live trading confirmation (delegated to ``LiveTrader``)
"""

from __future__ import annotations

import asyncio
import signal
from decimal import Decimal

from src.config import Settings, get_settings
from src.exchange.base import BaseExchange
from src.exchange.binance import BinanceExchange
from src.exchange.bybit import BybitExchange
from src.logger import get_logger
from src.proposal.engine import ProposalEngine
from src.proposal.interaction import ProposalHistory, ProposalInteraction
from src.proposal.notification import (
    ConsoleNotifier,
    EmailNotifier,
    FileNotifier,
    NotificationDispatcher,
    Notifier,
    SlackNotifier,
    TelegramNotifier,
)
from src.runtime.activity_log import ActivityLog
from src.runtime.engine import EngineConfig, TradingEngine
from src.strategy.loader import load_all_strategies
from src.strategy.performance import PerformanceTracker
from src.trading.base import Trader
from src.trading.live import LiveTrader
from src.trading.paper import PaperTrader
from src.trading.portfolio import PortfolioTracker

logger = get_logger("crypto_master.main")


def build_exchange(settings: Settings) -> BaseExchange:
    """Pick a configured exchange, testnet for paper, mainnet for live.

    Selection rules:

    * ``trading_mode == "live"``: validates exchange credentials are
      present and constructs a mainnet exchange (``testnet=False``).
      Raises a clear error if no live API keys are configured.
    * ``trading_mode == "paper"`` (default): testnet variant. Either
      live or testnet credentials count as "configured" — testnet keys
      alone are fine for paper deploys.

    If both Binance and Bybit are configured, Binance wins by
    convention (deepest liquidity for the symbols in
    ``EngineConfig.altcoin_symbols`` defaults).
    """
    if settings.trading_mode == "live":
        # Surfaces a friendly error if no live keys exist; the
        # alternative is a generic "not configured" error after the
        # engine has already started.
        settings.validate_for_live_trading()

        if settings.binance.api_key and settings.binance.api_secret:
            return BinanceExchange(settings.binance, testnet=False)
        if settings.bybit.api_key and settings.bybit.api_secret:
            return BybitExchange(settings.bybit, testnet=False)
        raise RuntimeError(
            "TRADING_MODE=live requires live (mainnet) API keys. "
            "Set BINANCE_API_KEY/BINANCE_API_SECRET or "
            "BYBIT_API_KEY/BYBIT_API_SECRET."
        )

    configured = settings.get_configured_exchanges()
    if "binance" in configured:
        return BinanceExchange(settings.binance, testnet=True)
    if "bybit" in configured:
        return BybitExchange(settings.bybit, testnet=True)
    raise RuntimeError(
        "No exchange configured. Set BINANCE_API_KEY/BINANCE_API_SECRET "
        "or BYBIT_API_KEY/BYBIT_API_SECRET (testnet keys are fine)."
    )


def build_trader(
    settings: Settings,
    exchange: BaseExchange,
    config: EngineConfig,
    *,
    activity_log: ActivityLog | None = None,
) -> Trader:
    """Build the right :class:`Trader` for ``Settings.trading_mode``.

    Live mode plugs the engine's auto-decide threshold into
    ``LiveTrader``'s confirmation callback so live execution shares
    the same accept/reject gate as paper proposals — no second prompt
    layered on top. The user controls live behaviour entirely through
    ``EngineConfig.auto_approve_threshold`` (the same field that
    drives notification gating). Per-trade SL/TP exits skip the
    callback inside ``LiveTrader.close_position`` because the user
    already pre-authorized those bounds at open time.

    ``activity_log`` is forwarded to :class:`PaperTrader` so paper-mode
    liquidation events (Phase 22.2 / DEBT-027) land in the same shared
    log the engine writes to. Live mode ignores the parameter — the
    real exchange surfaces liquidations natively.
    """
    if settings.trading_mode == "live":
        return LiveTrader(
            exchange=exchange,
            confirmation_callback=_engine_auto_confirmation,
        )

    return PaperTrader(
        initial_balance={"USDT": Decimal(str(settings.paper_initial_balance))},
        exchange=exchange,
        activity_log=activity_log,
        auto_deposit_on_liquidation=config.paper_auto_deposit_on_liquidation,
    )


async def _engine_auto_confirmation(position: object, action: str) -> bool:
    """Confirmation callback for live mode that approves automatically.

    The engine's auto-decide path has already filtered the proposal
    against ``EngineConfig.auto_approve_threshold``; if a Position has
    reached this point, it has been authorized for execution.
    Returning True here keeps the headless production loop unblocked.

    For interactive operator-driven sessions (``python -m src.main``
    with a TTY and a developer at the keyboard), passing the
    ``LiveTrader`` constructor's default ``confirmation_callback``
    instead gives the human-in-the-loop CLI prompt.
    """
    logger.info(
        f"Live {action} auto-confirmed by engine threshold gate: "
        f"{getattr(position, 'symbol', '?')} "
        f"side={getattr(position, 'side', '?')} "
        f"qty={getattr(position, 'quantity', '?')}"
    )
    return True


def build_engine(
    settings: Settings,
    exchange: BaseExchange,
    config: EngineConfig | None = None,
) -> TradingEngine:
    """Wire all the components and return a ready-to-run ``TradingEngine``.

    Splitting this out keeps ``main`` thin and makes it easy for an
    integration test or a one-shot ``python -c "..."`` to construct
    the engine without standing up an event loop.

    When ``config`` is omitted, all engine tunables are read from
    ``Settings``: cycle interval, auto-approve threshold, altcoin
    symbol list, balance, and per-symbol cap (Phase 10.2 / 12.1) plus
    monitor interval, bitcoin symbol, altcoin top-K, and actor name
    (Phase 13.2 / DEBT-003).
    """
    config = config or EngineConfig(
        cycle_interval_seconds=settings.engine_cycle_interval,
        auto_approve_threshold=settings.engine_auto_approve_threshold,
        altcoin_symbols=settings.engine_symbols,
        balance=settings.engine_balance,
        max_open_positions_per_symbol=(settings.engine_max_open_positions_per_symbol),
        monitor_interval_seconds=settings.engine_monitor_interval,
        bitcoin_symbol=settings.engine_bitcoin_symbol,
        altcoin_top_k=settings.engine_altcoin_top_k,
        actor=settings.engine_actor,
        # Phase 18.1 stale-quote sanity gate.
        fill_slippage_tolerance=settings.engine_fill_slippage_tolerance,
        reject_if_past_stop_loss=settings.engine_reject_if_past_stop_loss,
        # Phase 22.2 / DEBT-027 paper-mode liquidation visibility.
        paper_auto_deposit_on_liquidation=(settings.paper_auto_deposit_on_liquidation),
    )

    strategies = load_all_strategies()
    perf = PerformanceTracker()
    # Phase 12.3: share one ActivityLog instance between the proposal
    # engine (for ``LLM_TIMEOUT`` events), the paper trader (for
    # ``LIQUIDATED`` events — Phase 22.2 / DEBT-027), and the trading
    # engine (for everything else) so the dashboard sees all events on
    # the same rotated file.
    activity = ActivityLog()
    proposal_engine = ProposalEngine(
        exchange=exchange,
        strategies=strategies,
        performance_tracker=perf,
        activity_log=activity,
    )
    history = ProposalHistory()
    interaction = ProposalInteraction(history=history)
    trader = build_trader(settings, exchange, config, activity_log=activity)

    # Notifier list grows with optional push backends (Phase 11.3,
    # 12.4, 13.4). Console + File are always-on. Slack is opt-in via
    # ``SLACK_WEBHOOK_URL``; Telegram is opt-in via the pair
    # ``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_CHAT_ID`` (both required —
    # the notifier is not constructed unless both are set, so a
    # half-configured deploy does not fail at runtime); Email is
    # opt-in via the SMTP quintet (host/user/password/from/to — port
    # has a default of 587 for STARTTLS).
    notifiers: list[Notifier] = [ConsoleNotifier(), FileNotifier()]
    if settings.slack_webhook_url:
        notifiers.append(SlackNotifier(settings.slack_webhook_url))
        # Deliberately log presence only — never the URL itself.
        logger.info("Slack push notifier enabled.")
    if settings.telegram_bot_token and settings.telegram_chat_id:
        notifiers.append(
            TelegramNotifier(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
            )
        )
        # Deliberately log presence only — never the token or chat id.
        logger.info("Telegram push notifier enabled.")
    if all(
        [
            settings.email_smtp_host,
            settings.email_smtp_user,
            settings.email_smtp_password,
            settings.email_from,
            settings.email_to,
        ]
    ):
        # All five string fields are present — the type checker can't
        # see that ``all([...])`` narrows them, so assert non-None for
        # mypy. ``email_smtp_port`` has a non-optional default (587).
        assert settings.email_smtp_host is not None
        assert settings.email_smtp_user is not None
        assert settings.email_smtp_password is not None
        assert settings.email_from is not None
        assert settings.email_to is not None
        notifiers.append(
            EmailNotifier(
                host=settings.email_smtp_host,
                port=settings.email_smtp_port,
                user=settings.email_smtp_user,
                password=settings.email_smtp_password,
                from_addr=settings.email_from,
                to_addr=settings.email_to,
                # Phase 14.2 (DEBT-012): SMTP_SSL alternative for
                # providers without STARTTLS (Yahoo / AT&T / ProtonMail).
                # Default False keeps the STARTTLS path unchanged.
                use_ssl=settings.email_use_ssl,
            )
        )
        # Deliberately log presence only — never the password.
        logger.info("Email push notifier enabled.")
    notifier = NotificationDispatcher(
        notifiers=notifiers,
        min_score=config.auto_approve_threshold,
    )

    logger.info(
        f"Trading mode: {settings.trading_mode} "
        f"(trader={type(trader).__name__}, exchange={exchange.name}, "
        f"testnet={getattr(exchange, 'testnet', '?')})"
    )

    portfolio_tracker = PortfolioTracker()

    return TradingEngine(
        exchange=exchange,
        proposal_engine=proposal_engine,
        proposal_interaction=interaction,
        proposal_history=history,
        trader=trader,
        notification_dispatcher=notifier,
        activity_log=activity,
        config=config,
        portfolio_tracker=portfolio_tracker,
        mode=settings.trading_mode,
        quote_currency="USDT",
    )


def _purge_old_proposals(history: ProposalHistory, retention_months: int) -> int:
    """Archive proposal records older than ``retention_months``.

    Phase 11.4 startup hook. Called once per process boot from
    :func:`run`, before the engine starts cycling. Reuses
    :meth:`ProposalHistory.purge_old` (Phase 10.4) so the on-disk
    layout stays the same as the operator CLI in
    ``src.tools.purge_proposals``.

    The "0 records" case is intentionally silent — long-running deploys
    purge once early and then have nothing to do for the rest of the
    retention window, so logging on the empty path would be noise.

    Args:
        history: ``ProposalHistory`` to purge. The caller passes the
            same instance the engine wires into its dispatcher so the
            two views of ``data/proposals/`` agree.
        retention_months: Window in months. Records older than this
            move to ``<data_dir>/archive/<YYYY-MM>/``.

    Returns:
        The number of records archived this call (``0`` when nothing
        was old enough).
    """
    archived = history.purge_old(retention_months=retention_months)
    if archived:
        logger.info(
            f"Purged {len(archived)} proposal record(s) older than "
            f"{retention_months} months"
        )
    return len(archived)


async def run() -> None:
    """Build everything and run the engine forever (until SIGTERM/SIGINT)."""
    settings = get_settings()
    exchange = build_exchange(settings)
    await exchange.connect()

    engine = build_engine(settings, exchange)

    # Phase 11.4: archive proposal records older than retention before
    # the engine starts cycling. Constructs a second ``ProposalHistory``
    # view of the same on-disk dir as the one wired into ``build_engine``;
    # both resolve to ``Settings.data_dir / "proposals"`` (Phase 10.5).
    _purge_old_proposals(ProposalHistory(), settings.log_retention_months)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(_signal_shutdown(engine, s)),  # type: ignore[misc]
        )

    try:
        await engine.run_forever()
    finally:
        await exchange.disconnect()


async def _signal_shutdown(engine: TradingEngine, sig: signal.Signals) -> None:
    """Ask the engine to stop in response to a POSIX signal."""
    logger.info(f"Received {sig.name}; requesting engine shutdown...")
    await engine.stop()


def main() -> None:
    """Synchronous entrypoint used by ``python -m src.main``."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
