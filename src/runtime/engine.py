"""Trading engine orchestrator (Phase 8.1).

The ``TradingEngine`` runs an asyncio loop that, on each cycle:

1. Asks the ``ProposalEngine`` for a Bitcoin proposal and the top-K
   altcoin proposals.
2. Routes each proposal through ``ProposalInteraction`` with an
   auto-decision callback that accepts when the composite score meets
   ``EngineConfig.auto_approve_threshold`` and rejects otherwise.
   This reuses the existing persistence path so every proposal lands
   in ``data/proposals/`` as ACCEPTED or REJECTED with a reason.
3. Notifies via ``NotificationDispatcher`` (the dispatcher's own
   ``min_score`` filter still gates the noisy ones away from console
   / Slack-style backends).
4. For accepted proposals: opens a paper position and links the
   resulting trade id back to the proposal record (no realized P&L
   yet — that's filled in at close time).
5. Polls open positions for SL/TP hits; closes any that triggered
   and writes the realized P&L back to the originating proposal
   record.
6. Sleeps until the next cycle, but interruptibly: ``stop()`` flips
   a flag and the sleep wakes immediately for graceful shutdown.

The engine writes every step to an :class:`ActivityLog` (`Phase 8.1
companion module`) so the dashboard can show what's happening
without polling internal engine state.

Related Requirements:
- FR-009 / FR-010: Live + paper trading mode (production wiring)
- FR-013: User accept/reject (auto-mode in headless deploy)
- FR-014: Proposal history with realized outcome
- FR-015: Notification on good opportunities
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.exchange.base import ExchangeError
from src.logger import get_logger
from src.models import Position
from src.proposal.engine import Proposal, ProposalEngine
from src.proposal.interaction import (
    ProposalDecision,
    ProposalDecisionInput,
    ProposalHistory,
    ProposalInteraction,
)
from src.proposal.notification import NotificationDispatcher
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.strategy.performance import TradeHistory

if TYPE_CHECKING:
    from src.exchange.base import BaseExchange
    from src.trading.paper import PaperTrader

logger = get_logger("crypto_master.runtime.engine")


# =============================================================================
# Config
# =============================================================================


class EngineConfig(BaseModel):
    """Tunables for the production loop.

    All fields are env-overridable in production via pydantic-settings;
    the engine instance receives the resolved object at construction.
    """

    cycle_interval_seconds: int = Field(default=300, ge=10)
    monitor_interval_seconds: int = Field(default=60, ge=10)
    auto_approve_threshold: float = Field(default=1.0, ge=0.0)
    bitcoin_symbol: str = "BTC/USDT"
    altcoin_symbols: list[str] = Field(
        default_factory=lambda: [
            "ETH/USDT",
            "SOL/USDT",
            "BNB/USDT",
            "ADA/USDT",
            "AVAX/USDT",
        ]
    )
    altcoin_top_k: int = Field(default=3, ge=1)
    balance: Decimal = Decimal("10000")
    actor: str = "auto-engine"


# =============================================================================
# Cycle result (used for tests + the dashboard's per-cycle summary)
# =============================================================================


@dataclass
class CycleResult:
    """Summary of one ``run_cycle()`` invocation.

    Returned for testability and so the dashboard can render
    per-cycle stats without re-deriving them from the activity log.
    """

    cycle_id: str
    proposals_generated: int = 0
    proposals_accepted: int = 0
    proposals_rejected: int = 0
    positions_opened: int = 0
    positions_closed: int = 0
    errors: list[str] = field(default_factory=list)


# =============================================================================
# Errors
# =============================================================================


class EngineError(Exception):
    """Base exception for runtime engine errors."""


# =============================================================================
# Engine
# =============================================================================


class TradingEngine:
    """Orchestrates the production scan → decide → execute → monitor loop."""

    def __init__(
        self,
        *,
        exchange: BaseExchange,
        proposal_engine: ProposalEngine,
        proposal_interaction: ProposalInteraction,
        proposal_history: ProposalHistory,
        paper_trader: PaperTrader,
        notification_dispatcher: NotificationDispatcher,
        activity_log: ActivityLog,
        config: EngineConfig | None = None,
    ) -> None:
        """Initialize the engine.

        Args:
            exchange: Connected exchange (used for ticker fetches in
                the monitor pass).
            proposal_engine: Pre-built ``ProposalEngine``.
            proposal_interaction: ``ProposalInteraction`` that owns
                ``ProposalHistory`` writes. The engine swaps in its
                own auto-decide callback before the loop starts.
            proposal_history: Same instance the interaction wraps.
                Held separately so the engine can call
                ``attach_trade`` / ``attach_outcome`` directly.
            paper_trader: Where accepted proposals are executed.
            notification_dispatcher: Notify backend(s) for accepted
                proposals.
            activity_log: Where to record cycle / proposal / trade events.
            config: Tunables. Defaults to ``EngineConfig()``.
        """
        self.exchange = exchange
        self.proposal_engine = proposal_engine
        self.proposal_history = proposal_history
        self.paper_trader = paper_trader
        self.notification_dispatcher = notification_dispatcher
        self.activity_log = activity_log
        self.config = config or EngineConfig()

        # Inject the auto-decide callback. The ProposalInteraction
        # handed in by the caller is reused so its ProposalHistory
        # attachment stays the single persistence path.
        self.proposal_interaction = proposal_interaction
        self.proposal_interaction._decision_callback = self._auto_decide  # type: ignore[attr-defined]

        self._stop_event = asyncio.Event()
        self._cycle_index = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        """Run cycles until ``stop()`` is called.

        Wraps every cycle in try/except so a single bad cycle doesn't
        kill the loop; the error is logged to the activity log and the
        engine sleeps before retrying. Sleep is interruptible — calling
        ``stop()`` wakes the engine immediately.
        """
        self.activity_log.append(
            ActivityEventType.STARTUP,
            "Trading engine started",
            details={
                "cycle_interval_seconds": self.config.cycle_interval_seconds,
                "auto_approve_threshold": self.config.auto_approve_threshold,
            },
        )
        try:
            while not self._stop_event.is_set():
                await self._run_one_cycle_with_guard()
                if self._stop_event.is_set():
                    break
                await self._interruptible_sleep(self.config.cycle_interval_seconds)
        finally:
            self.activity_log.append(
                ActivityEventType.SHUTDOWN,
                "Trading engine stopped",
            )

    async def stop(self) -> None:
        """Signal the loop to exit at the next safe point.

        Wakes the engine if it is currently sleeping; if it is
        mid-cycle, the cycle finishes first and then the loop exits.
        """
        self._stop_event.set()

    async def run_cycle(self) -> CycleResult:
        """Execute exactly one cycle and return its summary.

        Public for testability; ``run_forever`` calls this internally.
        Errors raised here propagate — ``_run_one_cycle_with_guard``
        in the long-running loop catches them.
        """
        cycle_id = str(uuid.uuid4())
        self._cycle_index += 1
        self.activity_log.append(
            ActivityEventType.CYCLE_STARTED,
            f"Cycle {self._cycle_index} begin",
            details={"cycle_index": self._cycle_index},
            cycle_id=cycle_id,
        )

        result = CycleResult(cycle_id=cycle_id)

        proposals = await self._scan(cycle_id, result)
        for proposal in proposals:
            await self._handle_proposal(proposal, cycle_id, result)

        await self._monitor(cycle_id, result)

        self.activity_log.append(
            ActivityEventType.CYCLE_COMPLETED,
            f"Cycle {self._cycle_index} complete",
            details={
                "proposals": result.proposals_generated,
                "accepted": result.proposals_accepted,
                "rejected": result.proposals_rejected,
                "opened": result.positions_opened,
                "closed": result.positions_closed,
            },
            cycle_id=cycle_id,
        )
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run_one_cycle_with_guard(self) -> CycleResult | None:
        """Run a cycle, catching any exception so the loop survives."""
        try:
            return await self.run_cycle()
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("Cycle failed")
            self.activity_log.append(
                ActivityEventType.CYCLE_ERRORED,
                f"Cycle failed: {e}",
                details={"error": str(e), "error_type": type(e).__name__},
            )
            return None

    async def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep for ``seconds`` or until ``stop()`` flips the event.

        Implemented as ``wait_for(stop_event.wait(), timeout=seconds)``
        so the timeout is the normal-case path and the wait completes
        early on shutdown.
        """
        self.activity_log.append(
            ActivityEventType.SLEEPING,
            f"Sleeping {seconds:.0f}s until next cycle",
            details={"seconds": seconds},
        )
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass  # normal sleep completion

    async def _scan(
        self,
        cycle_id: str,
        result: CycleResult,
    ) -> list[Proposal]:
        """Run the BTC + altcoin scans, returning all proposals collected.

        Per-call exchange / strategy errors are recorded as
        ``SCAN_ERRORED`` events and added to ``result.errors``, but
        they do not fail the cycle — one bad symbol shouldn't block
        the others.
        """
        proposals: list[Proposal] = []

        try:
            btc = await self.proposal_engine.propose_bitcoin(
                symbol=self.config.bitcoin_symbol,
                balance=self.config.balance,
            )
        except ExchangeError as e:
            self.activity_log.append(
                ActivityEventType.SCAN_ERRORED,
                f"Bitcoin scan failed: {e}",
                details={"symbol": self.config.bitcoin_symbol, "error": str(e)},
                cycle_id=cycle_id,
            )
            result.errors.append(f"btc:{e}")
            btc = None

        if btc is not None:
            proposals.append(btc)

        try:
            altcoins = await self.proposal_engine.propose_altcoins(
                symbols=self.config.altcoin_symbols,
                balance=self.config.balance,
                top_k=self.config.altcoin_top_k,
            )
        except ExchangeError as e:
            self.activity_log.append(
                ActivityEventType.SCAN_ERRORED,
                f"Altcoin scan failed: {e}",
                details={"error": str(e)},
                cycle_id=cycle_id,
            )
            result.errors.append(f"alt:{e}")
            altcoins = []

        proposals.extend(altcoins)
        result.proposals_generated = len(proposals)
        return proposals

    async def _handle_proposal(
        self,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
    ) -> None:
        """Persist + decide + (maybe) execute one proposal."""
        self.activity_log.append(
            ActivityEventType.PROPOSAL_GENERATED,
            f"Proposal {proposal.symbol} {proposal.signal} "
            f"score={proposal.score.composite:.4f}",
            details=_proposal_summary(proposal),
            cycle_id=cycle_id,
        )

        try:
            await self.notification_dispatcher.notify_proposal(proposal)
        except Exception as e:  # pragma: no cover - notifier isolated by dispatcher
            logger.warning(f"Notification dispatch failed: {e}")

        record = await self.proposal_interaction.present(
            proposal, actor=self.config.actor
        )

        if record.decision == ProposalDecision.ACCEPTED.value:
            result.proposals_accepted += 1
            self.activity_log.append(
                ActivityEventType.PROPOSAL_ACCEPTED,
                f"Auto-accepted {proposal.symbol} {proposal.signal}",
                details=_proposal_summary(proposal),
                cycle_id=cycle_id,
            )
            await self._execute(proposal, cycle_id, result)
        else:
            result.proposals_rejected += 1
            self.activity_log.append(
                ActivityEventType.PROPOSAL_REJECTED,
                f"Auto-rejected {proposal.symbol} {proposal.signal}",
                details={
                    **_proposal_summary(proposal),
                    "reason": record.rejection_reason,
                },
                cycle_id=cycle_id,
            )

    async def _execute(
        self,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
    ) -> None:
        """Open a paper position for an accepted proposal."""
        position = _proposal_to_position(proposal)
        try:
            trade = self.paper_trader.open_position(position)
        except Exception as e:
            self.activity_log.append(
                ActivityEventType.POSITION_OPEN_ERRORED,
                f"Failed to open {proposal.symbol}: {e}",
                details={
                    "proposal_id": proposal.proposal_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                cycle_id=cycle_id,
            )
            result.errors.append(f"open:{e}")
            return

        # Link the trade to its proposal record now; realized P&L is
        # filled in by ``_monitor`` once the trade closes.
        self.proposal_history.attach_trade(proposal.proposal_id, trade_id=trade.id)
        result.positions_opened += 1
        self.activity_log.append(
            ActivityEventType.POSITION_OPENED,
            f"Opened {proposal.symbol} {proposal.signal} qty={trade.entry_quantity}",
            details={
                "proposal_id": proposal.proposal_id,
                "trade_id": trade.id,
                "symbol": proposal.symbol,
                "side": proposal.signal,
                "entry_price": str(proposal.entry_price),
                "quantity": str(trade.entry_quantity),
                "leverage": proposal.leverage,
            },
            cycle_id=cycle_id,
        )

    async def _monitor(
        self,
        cycle_id: str,
        result: CycleResult,
    ) -> None:
        """Check SL/TP for every open paper position; close on hit.

        Per-trade ticker errors are logged and skipped — one stale
        symbol shouldn't block the rest of the monitor pass.
        """
        open_trades = self.paper_trader.get_open_trades()
        closed_count = 0

        for trade in open_trades:
            try:
                ticker = await self.exchange.get_ticker(trade.symbol)
            except Exception as e:
                self.activity_log.append(
                    ActivityEventType.MONITOR_ERRORED,
                    f"Ticker fetch failed for {trade.symbol}: {e}",
                    details={"trade_id": trade.id, "error": str(e)},
                    cycle_id=cycle_id,
                )
                result.errors.append(f"ticker:{trade.symbol}:{e}")
                continue

            should_exit, reason = self.paper_trader.check_exit_conditions(
                trade.id, ticker.price
            )
            if not should_exit or reason is None:
                continue

            closed_trade = self.paper_trader.close_position(
                trade.id, ticker.price, reason=reason
            )
            if closed_trade is None:
                continue

            closed_count += 1
            self._record_closed_trade(closed_trade, reason, cycle_id)

        result.positions_closed = closed_count
        self.activity_log.append(
            ActivityEventType.MONITOR_PASS,
            f"Monitor pass: {len(open_trades)} open, {closed_count} closed",
            details={"open_count": len(open_trades), "closed": closed_count},
            cycle_id=cycle_id,
        )

    def _record_closed_trade(
        self,
        trade: TradeHistory,
        reason: str,
        cycle_id: str,
    ) -> None:
        """Log a closed trade and write realized P&L back to its proposal."""
        proposal_id = self._find_proposal_for_trade(trade.id)
        pnl_percent = trade.pnl_percent if trade.pnl_percent is not None else 0.0
        if proposal_id is not None:
            self.proposal_history.attach_outcome(
                proposal_id,
                trade_id=trade.id,
                pnl_percent=pnl_percent,
            )

        self.activity_log.append(
            ActivityEventType.POSITION_CLOSED,
            f"Closed {trade.symbol} ({reason}) pnl={pnl_percent:.2f}%",
            details={
                "trade_id": trade.id,
                "proposal_id": proposal_id,
                "symbol": trade.symbol,
                "side": trade.side,
                "reason": reason,
                "pnl_percent": pnl_percent,
                "exit_price": (
                    str(trade.exit_price) if trade.exit_price is not None else None
                ),
            },
            cycle_id=cycle_id,
        )

    def _find_proposal_for_trade(self, trade_id: str) -> str | None:
        """Look up which ProposalRecord owns a given trade id.

        ``ProposalHistory`` stores ``trade_id`` on every record; we
        scan ``list_all`` and return the first match. With realistic
        proposal volumes (tens to low hundreds) this is cheap; if it
        ever bites, ``ProposalHistory`` can grow an index.
        """
        for record in self.proposal_history.list_all():
            if record.trade_id == trade_id:
                return record.proposal.proposal_id
        return None

    async def _auto_decide(
        self,
        proposal: Proposal,
    ) -> ProposalDecisionInput:
        """Auto-decision callback wired into ``ProposalInteraction``.

        Accepts when the composite score meets the configured
        threshold; rejects otherwise with a reason string the
        dashboard surfaces verbatim.
        """
        composite = proposal.score.composite
        threshold = self.config.auto_approve_threshold
        if composite >= threshold:
            return ProposalDecisionInput(accepted=True)
        return ProposalDecisionInput(
            accepted=False,
            reason=(f"composite {composite:.4f} below threshold {threshold:.4f}"),
        )


# =============================================================================
# Helpers
# =============================================================================


def _proposal_to_position(proposal: Proposal) -> Position:
    """Translate a ``Proposal`` into a ``Position`` for the trader.

    The proposal already carries fully-priced fields (entry / SL / TP /
    qty / leverage). ``Position`` is the trader-side data model.
    """
    return Position(
        symbol=proposal.symbol,
        side=proposal.signal,
        quantity=proposal.quantity,
        entry_price=proposal.entry_price,
        stop_loss=proposal.stop_loss,
        take_profit=proposal.take_profit,
        leverage=proposal.leverage,
    )


def _proposal_summary(proposal: Proposal) -> dict[str, object]:
    """Compact dict used as the ``details`` payload for proposal events."""
    return {
        "proposal_id": proposal.proposal_id,
        "symbol": proposal.symbol,
        "side": proposal.signal,
        "technique": proposal.technique_name,
        "score": proposal.score.composite,
        "confidence": proposal.score.confidence,
        "expected_value": proposal.score.expected_value,
        "sample_size": proposal.score.sample_size,
        "entry_price": str(proposal.entry_price),
        "rr": proposal.risk_reward_ratio,
    }


__all__ = [
    "CycleResult",
    "EngineConfig",
    "EngineError",
    "TradingEngine",
]
