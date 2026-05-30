"""SnapshotRecorder — persistence/snapshotting collaborator for ``TradingEngine``.

CAH-15 Slice 1 (ADR 0001 — ``docs/adr/0001-trading-engine-decomposition.md``).
Owns the engine's persistence concern, extracted verbatim from the God-Object:
the end-of-cycle portfolio snapshot, closed-trade logging, the per-trade
``PerformanceRecord`` write, the close-reason→outcome map, and the
proposal-record lookup.

It participates in **no** gate and owns **no** per-cycle cache (quant-confirmed
in ADR §2: none of these five methods reads any of the six per-cycle caches).
Its only shared-state touch is the DEBT-066 mark-price write-through in
``record_portfolio_snapshot``, performed through an injected
``remember_mark_price`` callback so ``_mark_price_cache`` stays engine-owned
(ADR cache-ownership contract + quant CHANGE B: the callback is the engine's
``_remember_mark_price``, injected directly — never chained through another
collaborator).

Because the recorder is stateless, the engine rebuilds it on demand from its
live ``portfolio_tracker`` / ``mode`` / ``quote_currency`` / ``exchange`` so a
caller that mutates those attributes after construction sees current values
with no capture-staleness bug.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING

from src.logger import get_logger
from src.runtime.activity_log import ActivityEventType
from src.strategy.performance import (
    PerformanceRecord,
    PerformanceTracker,
    TradeHistory,
    TradeOutcome,
)
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID

if TYPE_CHECKING:
    from src.exchange.base import BaseExchange
    from src.proposal.engine import ProposalEngine
    from src.proposal.interaction import ProposalHistory, ProposalRecord
    from src.runtime.activity_log import ActivityLog
    from src.trading.base import Trader
    from src.trading.portfolio import Mode, PortfolioTracker
    from src.trading.sub_account import SubAccount

logger = get_logger("crypto_master.runtime.snapshot_recorder")


class SnapshotRecorder:
    """Records portfolio snapshots and closed-trade outcomes to disk."""

    def __init__(
        self,
        *,
        proposal_history: ProposalHistory,
        activity_log: ActivityLog,
        proposal_engine: ProposalEngine,
        portfolio_tracker: PortfolioTracker | None,
        default_exchange: BaseExchange,
        remember_mark_price: Callable[[str, Decimal], None],
        mode: Mode = "paper",
        quote_currency: str = "USDT",
    ) -> None:
        """Wire the recorder's dependencies.

        Args:
            proposal_history: Source for the proposal-record lookup used to
                attach realised P&L back to the originating proposal.
            activity_log: Where ``POSITION_CLOSED`` / ``MONITOR_ERRORED``
                events are appended.
            proposal_engine: Holds the ``performance_tracker`` the per-trade
                ``PerformanceRecord`` is written through.
            portfolio_tracker: Optional snapshot recorder. ``None`` skips the
                snapshot entirely (parity with the un-wired engine).
            default_exchange: Fallback exchange for per-trade ticker reads
                when no account-scoped exchange is passed to
                ``record_portfolio_snapshot`` (was ``engine.exchange``).
            remember_mark_price: The engine's ``_remember_mark_price``
                write-through callback (ADR CHANGE B — injected directly so
                the engine-owned ``_mark_price_cache`` stays the single source
                of truth and is never written via a chained collaborator).
            mode: ``"paper"`` / ``"live"`` label denominating the snapshot.
            quote_currency: Currency used to denominate snapshot equity.
        """
        self.proposal_history = proposal_history
        self.activity_log = activity_log
        self.proposal_engine = proposal_engine
        self.portfolio_tracker = portfolio_tracker
        self.default_exchange = default_exchange
        self._remember_mark_price = remember_mark_price
        self.mode = mode
        self.quote_currency = quote_currency

    @staticmethod
    def _sub_account_id(sub_account: SubAccount | None) -> str:
        return sub_account.id if sub_account is not None else DEFAULT_SUB_ACCOUNT_ID

    async def record_portfolio_snapshot(
        self,
        cycle_id: str,
        sub_account: SubAccount | None,
        trader: Trader,
        exchange: BaseExchange | None = None,
    ) -> None:
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
            balances = await trader.get_balances()
        except Exception as e:  # pragma: no cover - defensive
            self.activity_log.append(
                ActivityEventType.MONITOR_ERRORED,
                f"Snapshot balance fetch failed: {e}",
                details={"error": str(e), "phase": "balances"},
                cycle_id=cycle_id,
            )
            return

        current_prices: dict[str, Decimal] = {}
        account_exchange = exchange or self.default_exchange
        for trade in trader.get_open_trades():
            try:
                ticker = await account_exchange.get_ticker(trade.symbol)
            except Exception:
                continue
            current_prices[trade.symbol] = ticker.price
            # DEBT-066: write-through to the in-memory mark cache so
            # cap-rejection events can compute ``unrealized_pnl_percent``
            # for blocking trades from this same ticker read.
            self._remember_mark_price(trade.symbol, ticker.price)

        try:
            sub_account_id = self._sub_account_id(sub_account)
            tracker = self.portfolio_tracker
            if (
                getattr(tracker, "sub_account_id", DEFAULT_SUB_ACCOUNT_ID)
                != sub_account_id
            ):
                from src.trading.portfolio import PortfolioTracker

                tracker = PortfolioTracker(
                    data_dir=tracker.data_dir,
                    sub_account_id=sub_account_id,
                )
            tracker.record_snapshot(
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

    def record_closed_trade(
        self,
        trade: TradeHistory,
        reason: str,
        cycle_id: str,
    ) -> None:
        """Log a closed trade and write realized P&L back to its proposal."""
        proposal_record = self.find_proposal_record_for_trade(trade.id)
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
                # proposal-funnel-audit §1 State 7: ``record_id`` is the
                # canonical funnel-join key. For now each proposal maps
                # 1:1 to its record so the two ids coincide; the
                # separate field exists so dashboards can switch joins
                # without re-tagging events.
                "record_id": proposal_id,
                "sub_account_id": trade.sub_account_id,
                "technique_name": (
                    proposal_record.proposal.technique_name
                    if proposal_record is not None
                    else None
                ),
                "symbol": trade.symbol,
                "side": trade.side,
                "signal": trade.side,
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
        if (
            isinstance(tracker, PerformanceTracker)
            and tracker.sub_account_id != trade.sub_account_id
        ):
            tracker = PerformanceTracker(
                data_dir=tracker.data_dir,
                sub_account_id=trade.sub_account_id,
            )

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
                sub_account_id=trade.sub_account_id,
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

    def find_proposal_record_for_trade(self, trade_id: str) -> ProposalRecord | None:
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
