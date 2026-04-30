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
    ProposalRecord,
)
from src.proposal.notification import NotificationDispatcher
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.strategy.performance import (
    PerformanceRecord,
    TradeHistory,
    TradeOutcome,
)
from src.utils.time import now_utc

if TYPE_CHECKING:
    from src.exchange.base import BaseExchange
    from src.trading.base import Trader
    from src.trading.portfolio import Mode, PortfolioTracker

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
    # Phase 12.1 cross-cycle position cap. Prevents accumulation of
    # multiple open positions on the same symbol across consecutive
    # cycles (Phase 10.6's ``_dedup_by_symbol`` only de-dupes within
    # a single cycle). Hard cap at the execution gate; proposal
    # generation continues unchanged so the audit record is still
    # written.
    max_open_positions_per_symbol: int = Field(default=1, ge=1)
    # Phase 18.1 stale-quote sanity gate. Between auto-approval and
    # ``trader.open_position``, the engine fetches a fresh ticker and
    # rejects the fill if live has crossed the proposal's SL or has
    # drifted beyond ``fill_slippage_tolerance`` (50 bps default).
    # Eliminates the "instant stop-out" class of losers caused by
    # chasulang / Claude CLI proposal-to-fill latency. Defaults are
    # deliberately conservative (reject_if_past_stop_loss=True) so the
    # smoking-gun bug closes without an env flip.
    fill_slippage_tolerance: Decimal = Field(default=Decimal("0.005"), ge=0)
    reject_if_past_stop_loss: bool = True


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
        trader: Trader,
        notification_dispatcher: NotificationDispatcher,
        activity_log: ActivityLog,
        config: EngineConfig | None = None,
        portfolio_tracker: PortfolioTracker | None = None,
        mode: Mode = "paper",
        quote_currency: str = "USDT",
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
            trader: Where accepted proposals are executed. Either a
                :class:`PaperTrader` or :class:`LiveTrader` — both
                satisfy :class:`~src.trading.base.Trader`. The engine
                does not introspect which.
            notification_dispatcher: Notify backend(s) for accepted
                proposals.
            activity_log: Where to record cycle / proposal / trade events.
            config: Tunables. Defaults to ``EngineConfig()``.
            portfolio_tracker: Optional snapshot recorder. When set,
                the engine records an ``AssetSnapshot`` at the end of
                every cycle so the dashboard's Trading page can show
                current equity. ``None`` (default) keeps tests and
                anyone who builds the engine ad-hoc unaffected.
            mode: ``"paper"`` or ``"live"`` — passed through to the
                snapshot recorder. The trader implementation already
                knows which mode it is, but the protocol intentionally
                hides that, so the engine takes the mode label as a
                separate argument.
            quote_currency: Currency used to denominate equity in the
                recorded snapshots. Defaults to ``"USDT"``.
        """
        self.exchange = exchange
        self.proposal_engine = proposal_engine
        self.proposal_history = proposal_history
        self.trader = trader
        self.notification_dispatcher = notification_dispatcher
        self.activity_log = activity_log
        self.config = config or EngineConfig()
        self.portfolio_tracker = portfolio_tracker
        self.mode = mode
        self.quote_currency = quote_currency

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

        await self._record_portfolio_snapshot(cycle_id)

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

            # Phase 12.1: cross-cycle position cap. The composite
            # gate has accepted this proposal, but we may already be
            # at the per-symbol cap from previous cycles' open trades.
            # Block execution here and record a second rejection
            # reason on top of the existing composite-threshold one.
            cap = self.config.max_open_positions_per_symbol
            existing = sum(
                1
                for trade in self.trader.get_open_trades()
                if trade.symbol == proposal.symbol
            )
            if existing >= cap:
                reason = (
                    f"symbol {proposal.symbol} cap {cap} reached "
                    f"({existing} open)"
                )
                result.proposals_rejected += 1
                self.activity_log.append(
                    ActivityEventType.PROPOSAL_REJECTED,
                    f"Cap-rejected {proposal.symbol} {proposal.signal}",
                    details={
                        **_proposal_summary(proposal),
                        "reason": reason,
                        "open_count": existing,
                        "cap": cap,
                    },
                    cycle_id=cycle_id,
                )
                return

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
        """Open a paper position for an accepted proposal.

        Phase 18.1: between auto-approval and ``trader.open_position``,
        the engine fetches a fresh ticker and applies two gates against
        the live price:

        1. **Past-SL gate** (when ``reject_if_past_stop_loss=True``):
           reject if the live price has already crossed the proposal's
           stop-loss in the trade direction.
        2. **Slippage gate**: reject if absolute drift between live and
           ``proposal.entry_price`` exceeds ``fill_slippage_tolerance``.

        On rejection, the proposal record is overwritten with
        ``decision="rejected"`` and a structured rejection activity
        event is emitted; ``trader.open_position`` is not called.
        Otherwise the fill proceeds at ``proposal.entry_price`` exactly
        as before — no silent switch to live (would corrupt R/R math).
        Ticker fetch failures fall through to fill (preserve existing
        behaviour; transient exchange errors must not silently disable
        trading).
        """
        rejection = await self._stale_quote_gate(proposal, cycle_id, result)
        if rejection is not None:
            return

        position = _proposal_to_position(proposal)
        try:
            trade = await self.trader.open_position(position)
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

    async def _stale_quote_gate(
        self,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
    ) -> str | None:
        """Reject the fill if the live ticker has gone stale on the proposal.

        Phase 18.1 sanity gate. Returns the rejection reason string if
        the proposal should be skipped, or ``None`` if execution should
        proceed (either the gates passed or the ticker fetch failed and
        we are falling through to fill).

        On rejection: overwrites the proposal record with
        ``decision="rejected"``, emits a ``PROPOSAL_REJECTED`` activity
        event with structured ``proposal_entry``, ``live_price``, and
        ``drift_bps`` fields for post-mortem reconstruction, and bumps
        ``result.proposals_rejected`` while leaving
        ``proposals_accepted`` untouched (the cycle summary records both
        sides of the gate).
        """
        try:
            ticker = await self.exchange.get_ticker(proposal.symbol)
        except Exception as e:
            # Transient exchange errors fall through to fill so a brief
            # outage does not silently disable trading. The WARN is the
            # operator's signal.
            logger.warning(
                "stale_quote_check_failed: symbol=%s proposal_id=%s "
                "error_type=%s error=%s",
                proposal.symbol,
                proposal.proposal_id,
                type(e).__name__,
                e,
            )
            return None

        live_price = ticker.price
        entry = proposal.entry_price
        sl = proposal.stop_loss

        # Past-SL gate: only run when explicitly enabled. Side dispatch
        # is keyed off ``proposal.signal`` (the spec) — never inferred
        # from the entry/SL ordering, which would silently flip on a
        # short with the same numeric layout.
        if self.config.reject_if_past_stop_loss:
            past_sl = (proposal.signal == "long" and live_price <= sl) or (
                proposal.signal == "short" and live_price >= sl
            )
            if past_sl:
                reason = "stale_quote_past_sl"
                self._record_stale_quote_rejection(
                    proposal=proposal,
                    cycle_id=cycle_id,
                    result=result,
                    reason=reason,
                    live_price=live_price,
                )
                return reason

        # Slippage gate. Symmetric absolute drift over a non-zero entry.
        if entry > 0:
            drift = abs(live_price - entry) / entry
            if drift > self.config.fill_slippage_tolerance:
                reason = "slippage_exceeds_tolerance"
                self._record_stale_quote_rejection(
                    proposal=proposal,
                    cycle_id=cycle_id,
                    result=result,
                    reason=reason,
                    live_price=live_price,
                )
                return reason

        return None

    def _record_stale_quote_rejection(
        self,
        *,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
        reason: str,
        live_price: Decimal,
    ) -> None:
        """Persist + log a stale-quote rejection for the dashboard.

        The proposal record was already written ACCEPTED by
        :meth:`ProposalInteraction.present`; overwrite it here with the
        rejected verdict so post-mortems see the final outcome at the
        canonical persistence path. The activity event carries the
        numeric trio (``proposal_entry``, ``live_price``, ``drift_bps``)
        that the dashboard / audit reports need to reconstruct the
        rejection distribution.
        """
        # Drift is reported in basis points for readability; entry > 0
        # is checked at call sites that need it, but defend here too so
        # the activity payload is always populated.
        if proposal.entry_price > 0:
            drift = abs(live_price - proposal.entry_price) / proposal.entry_price
            drift_bps = float(drift) * 10_000
        else:
            drift_bps = 0.0

        # Overwrite the record. ``ProposalInteraction.present`` saved
        # ACCEPTED; we replace it with REJECTED + the reason so the
        # canonical history reflects the final verdict.
        try:
            existing = self.proposal_history.load(proposal.proposal_id)
            updated = existing.model_copy(
                update={
                    "decision": ProposalDecision.REJECTED.value,
                    "rejection_reason": reason,
                    "decision_at": now_utc(),
                }
            )
            self.proposal_history.save(updated)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(
                "Failed to overwrite proposal record %s with stale-quote "
                "rejection: %s",
                proposal.proposal_id,
                e,
            )

        # The composite gate already incremented ``proposals_accepted``
        # (the proposal *was* accepted by score); we add ``+1`` to
        # ``proposals_rejected`` here so the cycle summary records both
        # sides of the gate. Same pattern as Phase 12.1's per-symbol cap
        # (see ``_handle_proposal``'s cap-rejection branch).
        result.proposals_rejected += 1

        self.activity_log.append(
            ActivityEventType.PROPOSAL_REJECTED,
            f"Stale-quote rejected {proposal.symbol} {proposal.signal} ({reason})",
            details={
                **_proposal_summary(proposal),
                "reason": reason,
                "proposal_entry": str(proposal.entry_price),
                "proposal_stop_loss": str(proposal.stop_loss),
                "live_price": str(live_price),
                "drift_bps": drift_bps,
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
        open_trades = self.trader.get_open_trades()
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

            should_exit, reason = self.trader.check_exit_conditions(
                trade.id, ticker.price
            )
            if not should_exit or reason is None:
                continue

            closed_trade = await self.trader.close_position(
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

    async def _record_portfolio_snapshot(self, cycle_id: str) -> None:
        """Capture balances + open-position marks into ``AssetSnapshot``.

        Called at the end of every cycle when ``portfolio_tracker`` is
        wired. Errors (balance fetch network failures, ticker fetches,
        disk write hiccups) are swallowed and logged so the cycle
        finishes cleanly — a missed snapshot is recoverable; a crashed
        cycle is not.
        """
        if self.portfolio_tracker is None:
            return

        try:
            balances = await self.trader.get_balances()
        except Exception as e:  # pragma: no cover - defensive
            self.activity_log.append(
                ActivityEventType.MONITOR_ERRORED,
                f"Snapshot balance fetch failed: {e}",
                details={"error": str(e), "phase": "balances"},
                cycle_id=cycle_id,
            )
            return

        current_prices: dict[str, Decimal] = {}
        for trade in self.trader.get_open_trades():
            try:
                ticker = await self.exchange.get_ticker(trade.symbol)
            except Exception:
                continue
            current_prices[trade.symbol] = ticker.price

        try:
            self.portfolio_tracker.record_snapshot(
                mode=self.mode,
                quote_currency=self.quote_currency,
                balances=balances,
                current_prices=current_prices,
            )
        except Exception as e:  # pragma: no cover - defensive
            self.activity_log.append(
                ActivityEventType.MONITOR_ERRORED,
                f"Snapshot persist failed: {e}",
                details={"error": str(e), "phase": "persist"},
                cycle_id=cycle_id,
            )

    def _record_closed_trade(
        self,
        trade: TradeHistory,
        reason: str,
        cycle_id: str,
    ) -> None:
        """Log a closed trade and write realized P&L back to its proposal."""
        proposal_record = self._find_proposal_record_for_trade(trade.id)
        proposal_id = proposal_record.proposal.proposal_id if proposal_record else None
        pnl_percent = trade.pnl_percent if trade.pnl_percent is not None else 0.0
        if proposal_id is not None:
            self.proposal_history.attach_outcome(
                proposal_id,
                trade_id=trade.id,
                pnl_percent=pnl_percent,
            )

        if proposal_record is not None:
            self._save_performance_record(proposal_record, trade, reason)

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

    def _save_performance_record(
        self,
        proposal_record: ProposalRecord,
        trade: TradeHistory,
        reason: str,
    ) -> None:
        """Write a closed-trade PerformanceRecord so the dashboard sees it.

        The proposal carries the technique/timeframe/signal/prices that
        were ranked at proposal time; the trade carries the realised
        outcome. Combine them into a single row under
        ``data/performance/<technique>/`` so the Analysis Techniques
        dashboard's per-technique aggregates (win rate, avg P&L, total
        P&L) actually move.

        Failures are logged and swallowed — a missed performance row
        is recoverable; a crashed cycle is not.
        """
        tracker = getattr(self.proposal_engine, "performance_tracker", None)
        if tracker is None:
            return

        proposal = proposal_record.proposal
        outcome = self._classify_close_reason(reason)
        try:
            record = PerformanceRecord(
                technique_name=proposal.technique_name,
                technique_version=proposal.technique_version,
                symbol=proposal.symbol,
                timeframe=proposal.timeframe,
                signal=proposal.signal,
                entry_price=proposal.entry_price,
                stop_loss=proposal.stop_loss,
                take_profit=proposal.take_profit,
                confidence=proposal.score.confidence,
                analysis_timestamp=proposal.created_at,
                outcome=outcome,
                exit_price=trade.exit_price,
                exit_timestamp=trade.exit_time,
                pnl_percent=trade.pnl_percent,
                quantity=trade.entry_quantity,
                leverage=trade.leverage,
                fees=trade.fees,
                actual_entry_price=trade.entry_price,
                actual_exit_price=trade.exit_price,
                mode=trade.mode,
                trade_id=trade.id,
                profile_name=proposal.profile_name,
            )
            tracker.save_record(record)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(
                "Failed to persist performance record for trade %s: %s",
                trade.id,
                e,
            )

    @staticmethod
    def _classify_close_reason(reason: str) -> TradeOutcome:
        """Map an engine close reason onto a ``TradeOutcome`` enum value."""
        if reason == "take_profit":
            return TradeOutcome.WIN
        if reason == "stop_loss":
            return TradeOutcome.LOSS
        return TradeOutcome.BREAKEVEN

    def _find_proposal_record_for_trade(self, trade_id: str) -> ProposalRecord | None:
        """Look up the full ``ProposalRecord`` that owns a given trade id.

        ``ProposalHistory`` stores ``trade_id`` on every record; we
        scan ``list_all`` and return the first match. With realistic
        proposal volumes (tens to low hundreds) this is cheap; if it
        ever bites, ``ProposalHistory`` can grow an index.
        """
        for record in self.proposal_history.list_all():
            if record.trade_id == trade_id:
                return record
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
