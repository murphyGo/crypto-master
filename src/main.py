"""Production entrypoint for the trading runtime (Phase 8.1).

Run::

    python -m src.main

or via the Fly.io ``trader`` process (see ``fly.toml``).

Wires together Settings, an exchange (Binance testnet for paper-mode
deploys), the proposal stack, paper trader, notification dispatcher,
activity log, and the ``TradingEngine``. Adds POSIX signal handlers
so SIGINT / SIGTERM trigger a graceful loop exit.

Live-mode wiring is deliberately not built here yet — the first
production deploy is paper-only per the Phase 8 plan. Adding live
support later is a small follow-up: switch the exchange to mainnet
and swap ``PaperTrader`` for ``LiveTrader``.

Related Requirements:
- FR-009: Live trading mode (deferred to a later sub-task)
- FR-010: Paper/live mode switching (paper-only here for now)
- FR-026: Automated feedback loop wiring (engine surfaces activity)
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
    FileNotifier,
    NotificationDispatcher,
)
from src.runtime.activity_log import ActivityLog
from src.runtime.engine import EngineConfig, TradingEngine
from src.strategy.loader import load_all_strategies
from src.strategy.performance import PerformanceTracker
from src.trading.paper import PaperTrader

logger = get_logger("crypto_master.main")


def build_exchange(settings: Settings) -> BaseExchange:
    """Pick a configured exchange (Binance preferred), in testnet mode.

    Phase 8.1 deploys paper-only, so we always use the testnet variant
    of whichever exchange has credentials. If both are configured,
    Binance wins by convention (deepest liquidity for the symbols in
    ``EngineConfig.altcoin_symbols`` defaults).
    """
    configured = settings.get_configured_exchanges()
    if "binance" in configured:
        return BinanceExchange(settings.binance, testnet=True)
    if "bybit" in configured:
        return BybitExchange(settings.bybit, testnet=True)
    raise RuntimeError(
        "No exchange configured. Set BINANCE_API_KEY/BINANCE_API_SECRET "
        "or BYBIT_API_KEY/BYBIT_API_SECRET (testnet keys are fine)."
    )


def build_engine(
    settings: Settings,
    exchange: BaseExchange,
    config: EngineConfig | None = None,
) -> TradingEngine:
    """Wire all the components and return a ready-to-run ``TradingEngine``.

    Splitting this out keeps ``main`` thin and makes it easy for an
    integration test or a one-shot ``python -c "..."`` to construct
    the engine without standing up an event loop.
    """
    config = config or EngineConfig()

    strategies = load_all_strategies()
    perf = PerformanceTracker()
    proposal_engine = ProposalEngine(
        exchange=exchange,
        strategies=strategies,
        performance_tracker=perf,
    )
    history = ProposalHistory()
    interaction = ProposalInteraction(history=history)
    paper_trader = PaperTrader(
        initial_balance={"USDT": Decimal(str(settings.paper_initial_balance))},
        exchange=exchange,
    )
    notifier = NotificationDispatcher(
        notifiers=[ConsoleNotifier(), FileNotifier()],
        min_score=config.auto_approve_threshold,
    )
    activity = ActivityLog()

    return TradingEngine(
        exchange=exchange,
        proposal_engine=proposal_engine,
        proposal_interaction=interaction,
        proposal_history=history,
        paper_trader=paper_trader,
        notification_dispatcher=notifier,
        activity_log=activity,
        config=config,
    )


async def run() -> None:
    """Build everything and run the engine forever (until SIGTERM/SIGINT)."""
    settings = get_settings()
    exchange = build_exchange(settings)
    await exchange.connect()

    engine = build_engine(settings, exchange)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(_signal_shutdown(engine, s)),
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
