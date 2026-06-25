"""PositionMonitor — open-position monitor/exit collaborator for ``TradingEngine``.

CAH-15 Slice 2 (ADR 0001 — ``docs/adr/0001-trading-engine-decomposition.md``).
Owns the per-cycle monitor pass: SL/TP exit checks, the per-strategy time-stop,
the stale-position age-cap action, and the orphan force-close watchdog (the
ENG-F6 ``_handle_orphan_trade`` extraction of the branch previously inlined in
``_monitor``).

Unlike :class:`SnapshotRecorder` (Slice 1, stateless, rebuilt on demand), the
monitor owns **cross-cycle** state — ``_orphan_strike_counts`` — and is therefore
a **single construct-once instance** held by the engine. That cache counts
*consecutive* monitor cycles a trade is observed orphaned and force-closes after
``ORPHAN_AUTO_CLOSE_THRESHOLD`` strikes; it is pruned to currently-open trades at
the top of every pass but **never reset** (resetting it per cycle would defeat the
watchdog — the Fly 260h BNB regression). ``_orphan_strike_counts`` moves WITH the
monitor precisely because it sits *outside* the engine's per-cycle reset loop.

Collaborators are injected as callables so the monitor never reaches back into the
engine's internals (ADR cache-ownership contract + quant CHANGE B):

- ``remember_mark_price`` — the engine's ``_remember_mark_price`` write-through, so
  the engine-owned ``_mark_price_cache`` stays the single source of truth. Injected
  directly, **not** chained through the recorder (CHANGE B): the monitor's SL/TP
  ticker read (which precedes the close) writes the mark at the same point in the
  pass as today, so a same-cycle cap-blocker read is unaffected.
- ``record_closed_trade`` / ``find_proposal_record_for_trade`` — the engine
  delegates that route to the live :class:`SnapshotRecorder` (Slice 1).

The monitor is the **sole owner of ``closed_count`` → ``result.positions_closed``**
(ADR CHANGE A): all four close rungs (SL/TP, time-stop, stale-age, orphan
force-close) bump a single local counter, mutually exclusive via ``continue``, and
the one write to ``result.positions_closed`` happens at end of pass — no rung can
double-count or double-close.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from src.runtime.activity_log import ActivityEventType
from src.runtime.reconciliation import OpenTradeState, classify_open_trade
from src.strategy.base import default_max_bars_held
from src.strategy.performance import TradeHistory
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID
from src.utils.time import ensure_utc, now_utc

if TYPE_CHECKING:
    from src.exchange.base import BaseExchange
    from src.proposal.engine import ProposalEngine
    from src.proposal.interaction import ProposalRecord
    from src.runtime.activity_log import ActivityLog
    from src.runtime.engine import CycleResult
    from src.trading.base import Trader
    from src.trading.sub_account import SubAccount


# Timeframe → seconds for the time-stop wall-clock conversion. Monitor-local
# because the only caller is the time-stop rung; if more sites grow the same
# need it can be promoted to ``src/utils/time.py``. Values cover every label
# the strategy loader currently accepts; unknown labels fall back to 1h so the
# fallback keeps the trade alive for at least a default-sized window rather
# than collapsing to a pathological zero.
_TIMEFRAME_TO_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
    "1w": 604800,
}


def _timeframe_to_seconds(timeframe: str) -> int:
    """Return the wall-clock second count for one ``timeframe`` candle.

    Unknown labels return 1h (3600s) so a misconfigured strategy doesn't end up
    with a zero-length time-stop window — the activity log will still surface
    the unexpected timeframe via the ``POSITION_TIME_STOPPED`` event payload.
    """
    return _TIMEFRAME_TO_SECONDS.get(timeframe, 3600)


# DEBT-058 follow-up: number of consecutive monitor cycles a trade may be
# observed in the orphan (``_missing_position_state == True``) branch before the
# monitor force-closes it at the latest ticker price. Picked at K=5 so transient
# rehydration races (one cycle orphan, recovers next) never trip the watchdog,
# while a genuinely stuck trade (the Fly 260h BNB short) is force-closed within a
# handful of monitor passes rather than drifting indefinitely.
ORPHAN_AUTO_CLOSE_THRESHOLD = 5


# DEBT-071: age-keyed, restart-safe orphan backstop. ``_orphan_strike_counts``
# is in-memory and rebuilt fresh per process, so on a host that restarts often
# (the Fly machine restarted 38x in 35 days) the 5-strike *consecutive
# in-process* counter never accumulates and the watchdog NEVER force-closes —
# all orphan events sit at ``strike_count=1`` forever. This dedicated cap is an
# ALWAYS-ON second trigger keyed on the persisted ``trade.entry_time`` (which
# survives restarts): any orphan older than ``ORPHAN_MAX_AGE`` is force-closed
# on the FIRST qualifying cycle regardless of strike count. It is deliberately
# NOT the DEBT-068(e) ``max_time_in_position_hours`` stale-age cap — that one is
# opt-in (per-sub-account ``RiskPolicy``) and reconciliation-gated, so it can't
# guarantee convergence; this constant must always apply. The two orphan
# triggers coexist: a young orphan keeps the 5-strike grace (a genuinely
# transient single-process rehydration blip), while an orphan older than this
# cap is force-closed immediately.
ORPHAN_MAX_AGE = timedelta(hours=24)


class PositionMonitor:
    """Monitors open positions for exits and force-closes orphaned trades."""

    def __init__(
        self,
        *,
        activity_log: ActivityLog,
        proposal_engine: ProposalEngine,
        default_exchange: BaseExchange,
        remember_mark_price: Callable[[str, Decimal], None],
        record_closed_trade: Callable[[TradeHistory, str, str], None],
        find_proposal_record_for_trade: Callable[[str], ProposalRecord | None],
    ) -> None:
        """Wire the monitor's dependencies.

        Args:
            activity_log: Where monitor / exit / orphan events are appended.
            proposal_engine: Strategy registry source for the time-stop window
                resolution (``strategies.get(name).info``).
            default_exchange: Fallback exchange for ticker reads when no
                account-scoped exchange is passed to :meth:`monitor` (was
                ``engine.exchange``). Captured once — the engine never
                reassigns it after construction.
            remember_mark_price: The engine's ``_remember_mark_price``
                write-through (ADR CHANGE B — injected directly, never chained).
            record_closed_trade: The engine delegate routing to the live
                :class:`SnapshotRecorder.record_closed_trade`.
            find_proposal_record_for_trade: The engine delegate routing to the
                live :class:`SnapshotRecorder.find_proposal_record_for_trade`.
        """
        self._activity_log = activity_log
        self._proposal_engine = proposal_engine
        self._default_exchange = default_exchange
        self._remember_mark_price = remember_mark_price
        self._record_closed_trade = record_closed_trade
        self._find_proposal_record_for_trade = find_proposal_record_for_trade

        # DEBT-058 follow-up: count consecutive monitor cycles each open trade
        # has been seen as an orphan (missing in-memory position state). After
        # ``ORPHAN_AUTO_CLOSE_THRESHOLD`` strikes the monitor force-closes at the
        # latest ticker price with ``reason="orphan_force_close"`` so the trade
        # cannot drift indefinitely. CROSS-CYCLE: pruned in :meth:`monitor`,
        # never reset — it is the watchdog's only memory of consecutive strikes.
        self._orphan_strike_counts: dict[str, int] = {}

    @staticmethod
    def _sub_account_id(sub_account: SubAccount | None) -> str:
        return sub_account.id if sub_account is not None else DEFAULT_SUB_ACCOUNT_ID

    async def monitor(
        self,
        cycle_id: str,
        result: CycleResult,
        sub_account: SubAccount | None,
        trader: Trader,
        exchange: BaseExchange | None = None,
    ) -> None:
        """Check SL/TP for every open position; close on hit.

        Per-trade ticker errors are logged and skipped — one stale symbol
        shouldn't block the rest of the monitor pass.

        After the SL/TP check, if neither bound triggered we evaluate the
        per-strategy time-stop (``TechniqueInfo.max_bars_held``, or
        :func:`default_max_bars_held` for the strategy's primary timeframe).
        The 12-day Fly paper run had 44 open vs 41 closed trades because trades
        only ever exited on SL/TP — strategies whose thesis decays fast
        (mean-reversion, ORB) sat indefinitely. The time-stop is *strictly* a
        fallback: SL and TP win when they fire on the same monitor pass.
        """
        from src.runtime.engine import EngineError, ErrorCategory

        open_trades = trader.get_open_trades()
        closed_count = 0
        account_exchange = exchange or self._default_exchange

        # DEBT-058 follow-up: prune the orphan-strike counter to only trades
        # that are currently open. A trade that closed (SL/TP, time-stop, manual
        # close) on a previous cycle leaves a stale entry that would otherwise
        # persist forever — and would double-count if the same id ever recurred.
        open_trade_ids = {trade.id for trade in open_trades}
        self._orphan_strike_counts = {
            trade_id: strikes
            for trade_id, strikes in self._orphan_strike_counts.items()
            if trade_id in open_trade_ids
        }

        # Cache strategy lookups across the loop — multiple open trades from the
        # same technique are common, and each lookup touches the proposal
        # engine's strategy registry.
        time_stop_lookup_cache: dict[str, tuple[int, str] | None] = {}

        for trade in open_trades:
            if self._missing_position_state(trader, trade.id):
                # DEBT-058 / ENG-F6: orphan watchdog. An orphaned trade never
                # proceeds to SL/TP — always continue after handling it.
                if await self._handle_orphan_trade(
                    trade=trade,
                    trader=trader,
                    account_exchange=account_exchange,
                    sub_account=sub_account,
                    result=result,
                    cycle_id=cycle_id,
                ):
                    closed_count += 1
                continue
            # State recovered (e.g. late rehydration ran) — drop any stale
            # strike count so the watchdog won't prematurely force-close on the
            # next orphan blip.
            self._orphan_strike_counts.pop(trade.id, None)

            try:
                ticker = await account_exchange.get_ticker(trade.symbol)
            except Exception as e:
                self._activity_log.append(
                    ActivityEventType.MONITOR_ERRORED,
                    f"Ticker fetch failed for {trade.symbol}: {e}",
                    details={"trade_id": trade.id, "error": str(e)},
                    cycle_id=cycle_id,
                )
                result.errors.append(
                    EngineError(
                        category=ErrorCategory.TICKER_MONITOR,
                        symbol=trade.symbol,
                        detail=str(e),
                        exception=e,
                    )
                )
                continue

            # DEBT-066: write-through the freshly-fetched mark so
            # ``_build_cap_blocker_payload`` can compute ``unrealized_pnl_percent``
            # for cap-rejection events without re-fetching on the hot path.
            self._remember_mark_price(trade.symbol, ticker.price)

            should_exit, reason = trader.check_exit_conditions(trade.id, ticker.price)
            if should_exit and reason is not None:
                closed_trade = await trader.close_position(
                    trade.id, ticker.price, reason=reason
                )
                if closed_trade is None:
                    continue

                closed_count += 1
                self._record_closed_trade(closed_trade, reason, cycle_id)
                continue

            # SL/TP not hit — evaluate the per-strategy time-stop. The SL/TP
            # check above always runs first so a price that hits the bound on the
            # same monitor pass exits with the bound's reason, not ``time_stop``.
            time_stopped = await self._maybe_time_stop(
                trade,
                ticker.price,
                trader,
                cycle_id,
                time_stop_lookup_cache,
            )
            if time_stopped:
                closed_count += 1
                continue

            # cross-account-risk-policy DEBT-068(e): stale-position age cap.
            # Strictly a further fallback after SL/TP and the per-strategy
            # time-stop — a trade closed by either of those this pass hit a
            # ``continue`` above and never reaches here, so there is no
            # double-close. Only the ``auto_close`` action (with reconciliation
            # OK) actually closes; the other actions emit a detect/operator event
            # and leave the trade open.
            stale_closed = await self._maybe_stale_age_action(
                trade,
                ticker.price,
                sub_account,
                trader,
                cycle_id,
            )
            if stale_closed:
                closed_count += 1

        result.positions_closed = closed_count
        self._activity_log.append(
            ActivityEventType.MONITOR_PASS,
            f"Monitor pass: {len(open_trades)} open, {closed_count} closed",
            details={
                "open_count": len(open_trades),
                "closed": closed_count,
                "sub_account_id": self._sub_account_id(sub_account),
            },
            cycle_id=cycle_id,
        )

    async def _handle_orphan_trade(
        self,
        *,
        trade: TradeHistory,
        trader: Trader,
        account_exchange: BaseExchange,
        sub_account: SubAccount | None,
        result: CycleResult,
        cycle_id: str,
    ) -> bool:
        """Orphan force-close watchdog for one open trade (ENG-F6 extraction).

        Two coexisting force-close triggers:

        - **Strike counter** (DEBT-058): counts consecutive in-process orphan
          observations in ``_orphan_strike_counts`` (cross-cycle; pruned in
          :meth:`monitor`, never reset) and force-closes once
          ``ORPHAN_AUTO_CLOSE_THRESHOLD`` strikes accumulate. This protects a
          genuinely transient single-process rehydration blip on a young trade.
        - **Age backstop** (DEBT-071): an always-on, restart-safe trigger keyed
          on the persisted ``trade.entry_time``. Because the strike counter is
          in-memory and never accumulates across the frequent host restarts,
          the 5-strike guard was structurally unreachable — so any orphan older
          than ``ORPHAN_MAX_AGE`` is force-closed on the FIRST qualifying cycle
          regardless of strike count. This branch MUST live here (not in
          :meth:`_maybe_stale_age_action`), because :meth:`monitor` ``continue``s
          past the stale-age rung the moment a trade is orphaned.

        Returns ``True`` iff a force-close actually closed the trade (so
        :meth:`monitor` bumps ``closed_count``); every failure rung returns
        ``False`` and leaves the strike counter intact so the next cycle
        retries. The caller always ``continue``s after an orphan.
        """
        from src.runtime.engine import EngineError, ErrorCategory

        strikes = self._orphan_strike_counts.get(trade.id, 0) + 1
        self._orphan_strike_counts[trade.id] = strikes

        # DEBT-071: age is read from the PERSISTED entry time so it survives
        # process restarts. ``ensure_utc`` normalises the legacy naive rows
        # (and the ISO-with-offset rows) before the aware-vs-aware subtraction.
        trade_age = now_utc() - ensure_utc(trade.entry_time)
        age_force_close = trade_age >= ORPHAN_MAX_AGE

        message = (
            f"Open trade {trade.id} has no in-memory position state; "
            f"operator reconciliation required before SL/TP monitoring "
            f"(strike {strikes}/{ORPHAN_AUTO_CLOSE_THRESHOLD}, "
            f"age {trade_age.total_seconds() / 3600:.2f}h)"
        )
        self._activity_log.append(
            ActivityEventType.MONITOR_ERRORED,
            message,
            details={
                "trade_id": trade.id,
                "sub_account_id": self._sub_account_id(sub_account),
                "strike_count": strikes,
                "threshold": ORPHAN_AUTO_CLOSE_THRESHOLD,
                "age_hours": f"{trade_age.total_seconds() / 3600:.4f}",
                "max_age_hours": ORPHAN_MAX_AGE.total_seconds() / 3600,
                "age_force_close": age_force_close,
            },
            cycle_id=cycle_id,
        )
        result.errors.append(
            EngineError(
                category=ErrorCategory.POSITION_STATE,
                symbol=trade.symbol,
                detail=f"orphan_open_trade:{trade.id}",
            )
        )

        # Force-close when EITHER trigger fires: the 5-strike consecutive
        # in-process grace OR the always-on age backstop.
        if strikes < ORPHAN_AUTO_CLOSE_THRESHOLD and not age_force_close:
            return False

        # Threshold reached — force-close at the latest ticker. Failure to fetch
        # the ticker leaves the strike counter intact so the next cycle retries.
        try:
            ticker = await account_exchange.get_ticker(trade.symbol)
        except Exception as e:
            self._activity_log.append(
                ActivityEventType.MONITOR_ERRORED,
                (f"Orphan force-close ticker fetch failed for " f"{trade.symbol}: {e}"),
                details={
                    "trade_id": trade.id,
                    "sub_account_id": self._sub_account_id(sub_account),
                    "error": str(e),
                    "phase": "orphan_ticker_fetch_failed",
                },
                cycle_id=cycle_id,
            )
            return False

        # DEBT-066: write-through to the mark cache even on the orphan-force-close
        # path. The ticker is the same shape as the SL/TP monitor's.
        self._remember_mark_price(trade.symbol, ticker.price)

        force_close = getattr(trader, "force_close_orphan", None)
        if not callable(force_close):
            # Defensive: a Trader implementation without the watchdog hook can't
            # be force-closed. Surface the gap and leave the strike count intact
            # so the next cycle keeps recording the orphan.
            self._activity_log.append(
                ActivityEventType.MONITOR_ERRORED,
                (
                    f"Trader missing force_close_orphan; cannot "
                    f"auto-close orphaned trade {trade.id}"
                ),
                details={
                    "trade_id": trade.id,
                    "sub_account_id": self._sub_account_id(sub_account),
                    "phase": "orphan_force_close_unsupported",
                },
                cycle_id=cycle_id,
            )
            return False

        try:
            closed_trade = await force_close(trade.id, ticker.price)
        except Exception as e:
            self._activity_log.append(
                ActivityEventType.MONITOR_ERRORED,
                (f"Orphan force-close failed for {trade.id}: {e}"),
                details={
                    "trade_id": trade.id,
                    "sub_account_id": self._sub_account_id(sub_account),
                    "error": str(e),
                    "phase": "orphan_force_close_failed",
                },
                cycle_id=cycle_id,
            )
            return False

        # Drop the strike count and emit the high-severity event so the dashboard
        # surfaces the watchdog action.
        self._orphan_strike_counts.pop(trade.id, None)
        pnl_percent = (
            closed_trade.pnl_percent
            if closed_trade is not None and closed_trade.pnl_percent is not None
            else 0.0
        )
        # DEBT-071: record which trigger fired. ``strike`` keeps the legacy
        # 5-consecutive-strike semantics; ``age`` is the restart-safe backstop
        # that fires on the first qualifying cycle even at strike 1.
        trigger = "strike" if strikes >= ORPHAN_AUTO_CLOSE_THRESHOLD else "age"
        self._activity_log.append(
            ActivityEventType.POSITION_ORPHAN_FORCE_CLOSED,
            (
                f"Orphan force-closed {trade.symbol} {trade.side} "
                f"after {strikes} strikes "
                f"({trade_age.total_seconds() / 3600:.2f}h, trigger={trigger}) "
                f"at {ticker.price}"
            ),
            details={
                "trade_id": trade.id,
                "sub_account_id": self._sub_account_id(sub_account),
                "symbol": trade.symbol,
                "side": trade.side,
                "entry_price": str(trade.entry_price),
                "exit_price": str(ticker.price),
                "pnl_percent": pnl_percent,
                "strikes": strikes,
                "threshold": ORPHAN_AUTO_CLOSE_THRESHOLD,
                "age_hours": f"{trade_age.total_seconds() / 3600:.4f}",
                "max_age_hours": ORPHAN_MAX_AGE.total_seconds() / 3600,
                "trigger": trigger,
            },
            cycle_id=cycle_id,
        )
        return closed_trade is not None

    async def _maybe_time_stop(
        self,
        trade: TradeHistory,
        current_price: Decimal,
        trader: Trader,
        cycle_id: str,
        lookup_cache: dict[str, tuple[int, str] | None],
    ) -> bool:
        """Force-close ``trade`` if it has exceeded its time-stop window.

        Returns ``True`` when the trade was closed so :meth:`monitor` can bump
        its ``closed_count``. Returns ``False`` when the trade is still inside
        its window or when the close call returned ``None`` (already gone).
        """
        technique_name = self._technique_name_for_trade(trade)
        cache_key = technique_name or "__unknown__"
        cached = lookup_cache.get(cache_key)
        if cache_key not in lookup_cache:
            cached = self._resolve_time_stop_window(technique_name)
            lookup_cache[cache_key] = cached

        if cached is None:
            return False
        max_bars, timeframe = cached

        bar_seconds = _timeframe_to_seconds(timeframe)
        max_age_seconds = max_bars * bar_seconds
        age_seconds = (now_utc() - trade.entry_time).total_seconds()
        if age_seconds < max_age_seconds:
            return False

        closed_trade = await trader.close_position(
            trade.id, current_price, reason="time_stop"
        )
        if closed_trade is None:
            return False

        age_hours = round(age_seconds / 3600, 2)
        self._activity_log.append(
            ActivityEventType.POSITION_TIME_STOPPED,
            (
                f"Time-stop closed {trade.symbol} after "
                f"{age_hours}h ({max_bars} bars on {timeframe})"
            ),
            details={
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "age_hours": age_hours,
                "max_bars": max_bars,
                "timeframe": timeframe,
                "technique_name": technique_name,
            },
            cycle_id=cycle_id,
        )
        self._record_closed_trade(closed_trade, "time_stop", cycle_id)
        return True

    def _technique_name_for_trade(self, trade: TradeHistory) -> str | None:
        """Best-effort lookup of the technique that produced ``trade``.

        Walks the proposal history because :class:`TradeHistory` does not carry
        the technique name directly. Returns ``None`` when no proposal links to
        the trade — the caller falls back to timeframe defaults.
        """
        record = self._find_proposal_record_for_trade(trade.id)
        if record is None:
            return None
        return record.proposal.technique_name

    def _resolve_time_stop_window(
        self, technique_name: str | None
    ) -> tuple[int, str] | None:
        """Resolve the ``(max_bars, timeframe)`` for a technique.

        ``technique_name=None`` (no linked proposal) and the unknown-technique
        branch both default to a ``"1h"`` timeframe so the runtime applies a
        consistent fallback. Returns ``None`` only when ``max_bars`` would be
        non-positive — which the ``TechniqueInfo`` ``ge=1`` constraint prevents
        on legitimate overrides; the guard exists to keep the loop defensive.
        """
        timeframe = "1h"
        override: int | None = None
        if technique_name is not None:
            strategy = self._proposal_engine.strategies.get(technique_name)
            if strategy is not None:
                info = strategy.info
                if info.timeframes:
                    timeframe = info.timeframes[0]
                override = info.max_bars_held

        max_bars = (
            override if override is not None else default_max_bars_held(timeframe)
        )
        if max_bars <= 0:
            return None
        return max_bars, timeframe

    @staticmethod
    def _missing_position_state(trader: Trader, trade_id: str) -> bool:
        get_open_position = getattr(trader, "get_open_position", None)
        if not callable(get_open_position):
            return False
        try:
            return get_open_position(trade_id) is None
        except Exception:
            return False

    async def _maybe_stale_age_action(
        self,
        trade: TradeHistory,
        current_price: Decimal,
        sub_account: SubAccount | None,
        trader: Trader,
        cycle_id: str,
    ) -> bool:
        """Enforce the stale-position age cap for one open trade.

        cross-account-risk-policy §"Stale-Position Age Caps" (DEBT-068(e)).
        Slots into :meth:`monitor` as a *further* fallback after SL/TP and the
        per-strategy time-stop: if the trade has already been closed this pass it
        never reaches here, so there is no double-close.

        A position is STALE when its age exceeds the sub-account's
        ``RiskPolicy.max_time_in_position_hours`` (same comparison as
        ``_stale_position_block_gate``). Behavior per ``stale_position_action``:

        - ``auto_close``: consult the reconciliation state first (resolution
          table below). On ``monitorable`` / ``legacy_no_perf_link``
          (reconciliation OK) close at market with ``reason="stale_age_cap"`` and
          emit ``STALE_POSITION_AUTO_CLOSED``. On ``degraded`` do NOT close —
          downgrade to block-new-entries and emit ``STALE_POSITION_DETECTED`` with
          ``resolution="degraded_block_new_entries"``. On ``unrecoverable`` never
          close — emit a high-priority ``STALE_POSITION_DETECTED`` with
          ``resolution="unrecoverable_operator_only"``.
        - ``block_new_entries``: the proposal gate already rejects new entries;
          here we only emit a ``STALE_POSITION_DETECTED`` event
          (``resolution="block_new_entries"``) so the parked stale trade is
          operator-visible from the monitor timeline.
        - ``alert_only``: emit ``STALE_POSITION_DETECTED``
          (``resolution="alert_only"``); no enforcement.

        The auto-close fires in BOTH paper and live: it is the strategy's own
        configured risk policy (an enforcement action), not a lab-measurement
        proposal advisory.

        Returns ``True`` iff the trade was closed (so :meth:`monitor` can bump
        ``closed_count``); ``False`` for the detect-only / blocked paths.
        """
        if sub_account is None:
            return False
        policy = sub_account.risk_policy
        action = policy.stale_position_action
        cap_hours = policy.max_time_in_position_hours
        if action is None or cap_hours is None:
            return False

        now = now_utc()
        age_hours = (now - ensure_utc(trade.entry_time)).total_seconds() / 3600.0
        if age_hours <= cap_hours:
            return False

        sub_account_id = sub_account.id
        base_details: dict[str, Any] = {
            "trade_id": trade.id,
            "sub_account_id": sub_account_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "age_hours": f"{age_hours:.4f}",
            "max_time_in_position_hours": cap_hours,
            "stale_position_action": action,
        }

        if action == "alert_only":
            self._activity_log.append(
                ActivityEventType.STALE_POSITION_DETECTED,
                (
                    f"Stale position {trade.symbol} {trade.side} is "
                    f"{age_hours:.2f}h old (> cap {cap_hours}h); alert_only"
                ),
                details={
                    **base_details,
                    "reconciliation_state": self._classify_trade_reconciliation(
                        trade
                    ).value,
                    "resolution": "alert_only",
                },
                cycle_id=cycle_id,
            )
            return False

        if action == "block_new_entries":
            # Enforcement lives in ``_stale_position_block_gate`` (proposal gate).
            # The monitor only surfaces the parked stale trade so the operator
            # sees it on the timeline alongside the gate blocks.
            self._activity_log.append(
                ActivityEventType.STALE_POSITION_DETECTED,
                (
                    f"Stale position {trade.symbol} {trade.side} is "
                    f"{age_hours:.2f}h old (> cap {cap_hours}h); "
                    f"new entries blocked"
                ),
                details={
                    **base_details,
                    "reconciliation_state": self._classify_trade_reconciliation(
                        trade
                    ).value,
                    "resolution": "block_new_entries",
                },
                cycle_id=cycle_id,
            )
            return False

        # action == "auto_close": consult the reconciliation resolution table
        # BEFORE closing.
        recon_state = self._classify_trade_reconciliation(trade)

        if recon_state == OpenTradeState.UNRECOVERABLE:
            # NEVER auto-close. High-priority operator-only alert.
            self._activity_log.append(
                ActivityEventType.STALE_POSITION_DETECTED,
                (
                    f"Stale position {trade.symbol} {trade.side} is "
                    f"{age_hours:.2f}h old (> cap {cap_hours}h) but "
                    f"reconciliation is UNRECOVERABLE; auto-close suppressed, "
                    f"operator resolution required"
                ),
                details={
                    **base_details,
                    "reconciliation_state": recon_state.value,
                    "resolution": "unrecoverable_operator_only",
                    "priority": "high",
                },
                cycle_id=cycle_id,
            )
            return False

        if recon_state == OpenTradeState.DEGRADED:
            # Do NOT auto-close (exchange/ledger drift risk). Downgrade to
            # block-new-entries behavior and emit an operator-action event.
            self._activity_log.append(
                ActivityEventType.STALE_POSITION_DETECTED,
                (
                    f"Stale position {trade.symbol} {trade.side} is "
                    f"{age_hours:.2f}h old (> cap {cap_hours}h) but "
                    f"reconciliation is DEGRADED; auto-close downgraded to "
                    f"block-new-entries"
                ),
                details={
                    **base_details,
                    "reconciliation_state": recon_state.value,
                    "resolution": "degraded_block_new_entries",
                    "priority": "high",
                },
                cycle_id=cycle_id,
            )
            return False

        # Reconciliation OK (monitorable / legacy_no_perf_link) — proceed with
        # the auto-close at market.
        closed_trade = await trader.close_position(
            trade.id, current_price, reason="stale_age_cap"
        )
        if closed_trade is None:
            return False

        self._activity_log.append(
            ActivityEventType.STALE_POSITION_AUTO_CLOSED,
            (
                f"Auto-closed stale position {trade.symbol} {trade.side} "
                f"after {age_hours:.2f}h (> cap {cap_hours}h) at {current_price}"
            ),
            details={
                **base_details,
                "reconciliation_state": recon_state.value,
                "exit_price": str(current_price),
            },
            cycle_id=cycle_id,
        )
        # ``record_closed_trade`` emits the canonical ``POSITION_CLOSED`` event
        # with ``details.reason="stale_age_cap"`` and writes the realized P&L
        # back to the proposal + performance record.
        self._record_closed_trade(closed_trade, "stale_age_cap", cycle_id)
        return True

    @staticmethod
    def _classify_trade_reconciliation(trade: TradeHistory) -> OpenTradeState:
        """Return the runtime-reconciliation state for an open trade.

        cross-account-risk-policy §"Coordination with runtime-reconciliation".
        Builds the on-disk row shape that
        :func:`src.runtime.reconciliation.classify_open_trade` expects from the
        in-memory :class:`TradeHistory` (mirrors the row build in
        ``_build_cap_blocker_payload``) and returns the classified state.
        ``perf_record_ids`` is passed empty: the perf-link cross-check never
        *downgrades* the state (a perf-link miss stays ``monitorable`` /
        ``legacy_no_perf_link``), and the stale-age resolution table only cares
        about the ``degraded`` / ``unrecoverable`` distinction.
        """
        row = {
            "id": trade.id,
            "symbol": trade.symbol,
            "side": trade.side,
            "entry_price": (
                str(trade.entry_price) if trade.entry_price is not None else None
            ),
            "entry_quantity": (
                str(trade.entry_quantity) if trade.entry_quantity is not None else None
            ),
            "stop_loss": (
                str(trade.stop_loss) if trade.stop_loss is not None else None
            ),
            "take_profit": (
                str(trade.take_profit) if trade.take_profit is not None else None
            ),
            "performance_record_id": trade.performance_record_id,
            "sub_account_id": trade.sub_account_id,
        }
        classification = classify_open_trade(row, set())
        return OpenTradeState(classification.state)
