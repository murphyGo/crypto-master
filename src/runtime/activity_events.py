"""Pure activity-event vocabulary (CAH-13 / LAYER-F4).

This module holds the **pure** :class:`ActivityEvent` model and the
:class:`ActivityEventType` enum with *no* IO dependencies — no file
writes, no :class:`~src.runtime.jsonl_rotator.JsonlRotator`, no
``get_settings()``. The writer/reader adapter
(:class:`src.runtime.activity_log.ActivityLog`) imports these from here
and re-exports them for backward compatibility, so every existing
``from src.runtime.activity_log import ActivityEvent`` import path keeps
resolving unchanged.

Splitting the vocabulary out lets pure consumers — notably
:mod:`src.runtime.safety_score`, which only *reads* events — depend on
the model without transitively pulling in the IO machinery (the
LAYER-F4 import-hygiene fix).

Related Requirements:
- FR-009 / FR-010: Live + paper trading mode (production wiring)
- FR-026: Automated Feedback Loop (visibility into the loop)
- NFR-008: log retention (Phase 10.4).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.utils.time import ensure_utc, now_utc


class ActivityEventType(str, Enum):
    """Lifecycle events the engine emits.

    Values are stable strings — the dashboard filters on them and
    they are written as-is into the JSONL log.
    """

    # Process lifecycle
    STARTUP = "startup"
    SHUTDOWN = "shutdown"

    # Cycle lifecycle
    CYCLE_STARTED = "cycle_started"
    CYCLE_COMPLETED = "cycle_completed"
    CYCLE_ERRORED = "cycle_errored"
    SLEEPING = "sleeping"

    # Scan + propose
    SCAN_ERRORED = "scan_errored"
    PROPOSAL_GENERATED = "proposal_generated"
    PROPOSAL_ACCEPTED = "proposal_accepted"
    PROPOSAL_REJECTED = "proposal_rejected"

    # Execution
    POSITION_OPENED = "position_opened"
    POSITION_OPEN_ERRORED = "position_open_errored"

    # Monitoring
    MONITOR_PASS = "monitor_pass"
    POSITION_CLOSED = "position_closed"
    MONITOR_ERRORED = "monitor_errored"

    # Orphan auto-close watchdog (DEBT-058 follow-up). Emitted by
    # :meth:`~src.runtime.engine.TradingEngine._monitor` after a trade
    # has been observed in the ``_missing_position_state`` branch for
    # ``ORPHAN_AUTO_CLOSE_THRESHOLD`` consecutive monitor cycles. The
    # engine force-closes the persisted state via
    # ``Trader.force_close_orphan`` at the latest ticker price with
    # ``close_reason="orphan_force_close"`` so a perpetually orphaned
    # trade (the Fly 260h BNB short case) cannot drift indefinitely.
    # ``details`` payload (structured-fields contract — pinned by
    # ``test_strike_threshold_triggers_force_close``):
    #
    #     trade_id (str)
    #     sub_account_id (str)
    #     symbol (str)
    #     side ("long" | "short")
    #     entry_price (str Decimal)
    #     exit_price (str Decimal)
    #     pnl_percent (float)
    #     strikes (int)
    #     threshold (int)
    POSITION_ORPHAN_FORCE_CLOSED = "position_orphan_force_closed"

    # Per-strategy time-stop. Emitted from
    # :meth:`~src.runtime.engine.TradingEngine._monitor` when a trade
    # has exceeded its ``TechniqueInfo.max_bars_held`` (or the
    # timeframe-based default) without hitting SL or TP. The path
    # closes the position at the current ticker price with
    # ``reason="time_stop"`` and emits this event for the timeline.
    # ``details`` payload (structured-fields contract — pinned by
    # ``test_time_stop_emits_activity_event``):
    #
    #     trade_id (str)
    #     symbol (str)
    #     age_hours (float)        wall-clock age at close
    #     max_bars (int)           bar limit applied
    #     timeframe (str)          primary timeframe used for sizing
    #     technique_name (str)     so the dashboard can group by strategy
    POSITION_TIME_STOPPED = "position_time_stopped"

    # LLM reliability (Phase 12.3)
    # Emitted by :class:`~src.proposal.engine.ProposalEngine` whenever a
    # strategy raises ``ClaudeTimeoutError`` (after the wrapper has
    # exhausted its retries). The engine logs one event per
    # exhausted-retries timeout so the dashboard can show LLM
    # reliability over time.
    LLM_TIMEOUT = "llm_timeout"

    # Paper-trader liquidation (Phase 22.2 / DEBT-027). Emitted by
    # :class:`~src.trading.paper.PaperTrader.close_position` when a
    # closing trade's realized loss + exit fee exceeds the trader's
    # free balance. The previous behaviour silently clamped
    # ``balance.free`` to zero, hiding the over-leverage failure;
    # this event surfaces the shortfall to operators so paper-mode
    # forecasts include the same liquidation cliff that live mode
    # would experience. ``details`` payload (structured-fields
    # contract — pinned by ``test_under_water_close_emits_liquidated_event``):
    #     symbol (str)
    #     side ("long" | "short")
    #     entry (str Decimal)         entry price
    #     exit (str Decimal)          exit / liquidation price
    #     qty (str Decimal)           position quantity
    #     realized_pnl (str Decimal)  always negative for liquidation
    #     balance_before (str Decimal) free balance pre-close
    #     balance_after (str Decimal)  free balance post-close
    #                                 (negative when leverage > 1 unless
    #                                 paper_auto_deposit_on_liquidation
    #                                 clamp is in effect)
    LIQUIDATED = "liquidated"

    # Cold-start guard (Phase 24.2 / DEBT-034 follow-up). Emitted by
    # :class:`~src.proposal.engine.ProposalEngine._cold_start_blocks_live`
    # when live mode is configured but no applicable technique on the
    # symbol has accumulated enough closed trades to be promotable.
    # Without this event the dashboard sees no trace of why the bot
    # is intentionally idle on a fresh deployment — operators flip on
    # ``mode=live`` and the bot just goes quiet. The event payload
    # carries ``symbol`` and ``reason="cold_start_below_min_closed_trades"``
    # so the activity timeline shows the deliberate idle state.
    COLD_START_BLOCKED = "cold_start_blocked"

    # Notification dispatch failure (Phase 26.3 / DEBT-038). Emitted by
    # :class:`~src.runtime.engine.TradingEngine._handle_proposal` when
    # ``NotificationDispatcher.notify_proposal`` raises. The dispatcher
    # already isolates per-notifier failures internally; this event
    # surfaces failures of the dispatcher call itself (e.g. unexpected
    # programming errors, invalid proposal data) so the dashboard has
    # a structural signal that notifications are not landing. The
    # engine's policy is **emit-then-swallow**: the cycle continues so
    # one broken notifier path can't silence the trading loop. The
    # ``details`` payload (structured-fields contract — pinned by
    # ``test_notifier_failure_emits_notification_failed_event``):
    #
    #     proposal_id (str)        proposal whose notification failed
    #     symbol (str)             trading symbol on the proposal
    #     dispatcher_name (str)    ``type(dispatcher).__name__`` so
    #                              operators distinguish dispatcher
    #                              implementations across envs
    #     error_type (str)         exception class name
    #     error_message (str)      ``str(exception)`` — short
    NOTIFICATION_FAILED = "notification_failed"

    # Correlation governor advisory (Strategy Correlation Governor).
    # Emitted when a candidate proposal would duplicate symbol/strategy
    # exposure across sub-accounts. The gate may still be disabled, so
    # this event is the advisory operator surface and the safety-score
    # concentration signal.
    CORRELATION_WARNING = "correlation_warning"

    # Market-regime gating (market-regime unit). Emitted by
    # :class:`~src.runtime.engine.TradingEngine._market_regime_gate`
    # when a sub-account has ``market_regime.enabled: true`` and the
    # current classifier output for ``reference_symbol`` /
    # ``timeframe`` is not in ``allowed_regimes``. The proposal is
    # rejected and not executed. ``details`` payload (structured-fields
    # contract — pinned by ``test_market_regime_gate_emits_event``):
    #
    #     symbol (str)             reference symbol classified
    #     timeframe (str)          reference timeframe classified
    #     regime (str)             classifier label
    #     baseline (str Decimal)   SMA value at classification
    #     close (str Decimal)      last-candle close at classification
    #     policy_decision (str)    "block"
    #     sub_account_id (str)     account whose policy fired the gate
    MARKET_REGIME_BLOCKED = "market_regime_blocked"

    # Market-regime degraded fail-open (quant-trader audit follow-up).
    # Emitted by :class:`~src.runtime.engine.TradingEngine._market_regime_gate`
    # when the OHLCV fetch for the reference symbol raises. The gate
    # still fails open (returns ``None``) to match the
    # ``_trend_filter_gate`` precedent — a transient exchange error
    # must not silently halt trading — but the disablement is now
    # operator-visible on the dashboard so the silent-gate
    # anti-pattern (DEBT-061 family) cannot recur. ``details`` payload
    # (structured-fields contract — pinned by
    # ``test_ohlcv_fetch_failure_falls_open_and_emits_degraded_event``):
    #
    #     symbol (str)             reference symbol the fetch targeted
    #     timeframe (str)          reference timeframe the fetch targeted
    #     error_type (str)         exception class name
    #     sub_account_id (str)     account whose policy attempted the read
    #     policy_decision (str)    "pass_through_degraded"
    MARKET_REGIME_DEGRADED = "market_regime_degraded"

    # Runtime reconciliation (runtime-reconciliation unit). Emitted once
    # per engine startup, after open-position rehydration and before
    # the cycle loop, carrying the per-sub-account taxonomy breakdown
    # produced by ``src.runtime.reconciliation.compute_health_report``.
    # The dashboard banner is sourced from the most recent event of
    # this type. ``details`` payload (structured-fields contract —
    # pinned by ``test_startup_emits_reconciliation_health_report``):
    #
    #     report (dict)        per-sub-account breakdown
    #     totals (dict)        aggregate counts (open_trade_count,
    #                          state_counts, perf_links_resolved,
    #                          perf_links_missing,
    #                          any_locked_inconsistent,
    #                          classifications)
    RECONCILIATION_HEALTH_REPORT = "reconciliation_health_report"

    # Companion event emitted only when at least one sub-account's
    # ``locked_consistent`` is False. Always paired with a
    # ``RECONCILIATION_HEALTH_REPORT`` event in the same startup so the
    # dashboard can both (a) render the discrepancy as a Yellow banner
    # cause and (b) timeline-filter on the inconsistency itself.
    # ``details`` carries the inconsistent sub-accounts only:
    #
    #     sub_accounts (list[dict])
    #       sub_account_id, locked_sum (str), balance_locked (str|None)
    RECONCILIATION_LOCKED_INCONSISTENT = "reconciliation_locked_inconsistent"

    # Emitted once per live run (not dry-run) of
    # ``src.tools.backfill_paper_sl_tp``. ``details`` carries the
    # aggregated ``BackfillSummary`` counters plus the optional
    # ``sub_account`` filter that was applied. This is the operator's
    # confirmation that Step 3 of the reconciliation playbook landed.
    BACKFILL_PAPER_SL_TP_RAN = "backfill_paper_sl_tp_ran"

    # Emitted once per row closed by
    # ``src.tools.close_unrecoverable_paper_trades`` (live run only).
    # ``details`` payload:
    #     trade_id (str)
    #     sub_account_id (str)
    #     symbol (str | None)
    #     missing_fields (list[str])
    #     performance_record_id (str | None)   synthetic record's id
    RECONCILIATION_CLOSED_UNRECOVERABLE = "reconciliation_closed_unrecoverable"

    # Emitted once per live run (not dry-run) of
    # ``src.tools.repair_paper_trade_bounds_from_proposals``. This is
    # separate from ``BACKFILL_PAPER_SL_TP_RAN`` because the source of truth is
    # proposal history (``ProposalRecord.trade_id`` -> proposal SL/TP), not a
    # pre-existing ``PerformanceRecord`` link on the trade row.
    RECONCILIATION_REPAIRED_PAPER_BOUNDS = "reconciliation_repaired_paper_bounds"

    # Reconciliation health-check meta-event (Q4 follow-up / DEBT-061
    # silent-disable anti-pattern). Emitted by
    # :meth:`~src.runtime.engine.TradingEngine._run_reconciliation_health_check`
    # when ``compute_health_report`` raises. The engine policy is
    # log-and-continue (paper-mode resolution 2026-05-13 — a malformed
    # ledger must not keep the Fly machine from booting), but the
    # *failure itself* needs to be operator-visible so a chronically-
    # broken health check can be distinguished from a fresh deployment
    # that simply hasn't booted yet. The dashboard banner renders
    # Yellow when this is the most recent reconciliation event.
    # ``details`` payload (structured-fields contract — pinned by
    # ``test_startup_emits_health_check_failed_event``):
    #
    #     error_type (str)            exception class name, e.g.
    #                                 "RuntimeError"
    #     message (str)               ``str(exception)`` — short
    #     sub_account_id (str | None) optional account hint when the
    #                                 failure can be attributed to one
    #                                 sub-account; ``None`` when the
    #                                 crash happened before per-account
    #                                 iteration started
    RECONCILIATION_HEALTH_CHECK_FAILED = "reconciliation_health_check_failed"

    # Strategy-tuning applied-state change (strategy-tuning unit).
    # Emitted whenever the applied action for a ``(sub_account,
    # strategy)`` pair transitions — operator-initiated YAML reload
    # or (future) automated policy. The event payload carries the
    # transition tuple so dashboards / audit log can reconstruct the
    # history without re-deriving it from YAML diffs. Emitted by
    # ``engine._maybe_emit_strategy_action_transitions``; the shape is
    # exercised by
    # ``tests/test_runtime_engine.py::test_strategy_action_changed_emits_one_event_per_change``.
    # ``details`` payload (4-key contract):
    #
    #     sub_account (str)          sub-account id
    #     strategy (str)             technique name
    #     prior_action (str)         StrategyAction value
    #     new_action (str)           StrategyAction value
    STRATEGY_ACTION_APPLIED = "strategy_action_applied"

    # Strategy-tuning retune advisory (strategy-tuning unit). Emitted
    # by the runtime strategy-action gate when the applied state is
    # ``retune``: the proposal still flows through, but the dashboard
    # surfaces the flag so operators see which strategies are queued
    # for parameter / prompt work. ``details`` payload:
    #
    #     proposal_id (str)
    #     sub_account_id (str)
    #     technique_name (str)
    #     symbol (str)
    RETUNE_FLAGGED = "retune_flagged"

    # cross-account-risk-policy DEBT-068(d): operator manual freeze
    # engaged. Emitted for every proposal rejected because the operator
    # flipped ``runtime_flags.trading_freeze`` true in
    # ``config/runtime_flags.yaml`` (re-read at the top of each cycle).
    # The freeze is the EARLIEST reject in the gate stack and hard-blocks
    # in BOTH paper and live mode (manual kill — no paper-advisory
    # carve-out). A dedicated event type (vs. reusing ``PROPOSAL_REJECTED``)
    # lets dashboards chart the freeze window over time per spec
    # §"Activity events". ``details`` payload:
    #
    #     proposal_id (str)
    #     symbol (str)
    #     reason ("operator_freeze")
    OPERATOR_FREEZE_ENGAGED = "operator_freeze_engaged"

    # cross-account-risk-policy DEBT-068(e): stale-position age-cap
    # detection. Emitted from the MONITOR loop (not the proposal gate)
    # when an open trade's age exceeds the sub-account's
    # ``RiskPolicy.max_time_in_position_hours``. Covers every
    # ``stale_position_action`` where enforcement is informational or
    # blocked by the reconciliation resolution table:
    #   - ``alert_only``: emitted with ``resolution="alert_only"`` and no
    #     enforcement (position stays open).
    #   - ``block_new_entries``: emitted with ``resolution="block_new_entries"``
    #     so the operator sees the parked stale trade alongside the
    #     proposal-gate blocks (the gate itself rejects new entries).
    #   - ``auto_close`` downgraded by reconciliation ``degraded``: emitted
    #     with ``resolution="degraded_block_new_entries"`` — the configured
    #     auto-close is suppressed (exchange/ledger drift risk) and downgraded
    #     to block-new-entries behavior; operator action required.
    #   - ``auto_close`` blocked by reconciliation ``unrecoverable``: emitted
    #     with ``resolution="unrecoverable_operator_only"`` and
    #     ``priority="high"`` — never auto-closed; high-priority operator
    #     alert. ``details`` payload (structured-fields contract):
    #
    #     trade_id (str)
    #     sub_account_id (str)
    #     symbol (str)
    #     side ("long" | "short")
    #     age_hours (str)              wall-clock age at detection
    #     max_time_in_position_hours (int|float)
    #     stale_position_action (str)  configured action
    #     reconciliation_state (str)   classify_open_trade state
    #     resolution (str)             see above
    #     priority ("high")            only on the unrecoverable path
    STALE_POSITION_DETECTED = "stale_position_detected"

    # cross-account-risk-policy DEBT-068(e): stale-position auto-close.
    # Emitted from the MONITOR loop immediately after an ``auto_close``-
    # configured stale position (reconciliation OK) is closed at market.
    # The actual close is recorded as a ``POSITION_CLOSED`` event with
    # ``details.reason="stale_age_cap"`` via ``_record_closed_trade``; this
    # companion event carries the stale-specific context for the timeline.
    # ``details`` payload (structured-fields contract):
    #
    #     trade_id (str)
    #     sub_account_id (str)
    #     symbol (str)
    #     side ("long" | "short")
    #     age_hours (str)              wall-clock age at close
    #     max_time_in_position_hours (int|float)
    #     exit_price (str Decimal)
    #     reconciliation_state (str)   "monitorable" (the only state that
    #                                  reaches the auto-close path)
    STALE_POSITION_AUTO_CLOSED = "stale_position_auto_closed"

    # cross-account-risk-policy DEBT-068(g): paper-mode exposure-cap
    # advisory. Emitted by the per-account aggregate-cap gate
    # (``_account_aggregate_cap_gate``) and the opt-in global symbol/side
    # cap gate (``_global_aggregate_cap_gate``) when, in PAPER mode, a
    # configured cap WOULD be breached. Paper mode is advisory-only: the
    # event is emitted but the proposal still proceeds (the proposal
    # record is NOT downgraded, so the funnel still counts it as
    # ``proposal_opened``). This is paper-only by design — in LIVE mode
    # caps hard-block and the rejection's accompanying event stays
    # ``PROPOSAL_REJECTED`` with the matching ``gate_rejected_*_cap``
    # terminal. A dedicated event type (vs. reusing ``PROPOSAL_REJECTED``)
    # lets dashboards chart cap pressure over time per spec §"Activity
    # events" — caps are a persistent portfolio-condition gate.
    # ``details.advisory=True`` is KEPT as a back-compat discriminator and
    # a quick "this never blocked execution" flag. ``details`` payload
    # (structured-fields contract):
    #
    #     proposal_id (str)
    #     symbol (str)
    #     reason (str)                 human-readable breach summary
    #     gate_reason ("account_aggregate_cap" | "global_cap")
    #     advisory (True)              always True (paper-only event)
    #     mode ("paper")
    #     ... plus gate-specific cap totals / limits (e.g.
    #     gross_notional_total, open_stop_risk_total, sub_account_id for
    #     the per-account gate; open_positions_per_symbol_side_total,
    #     gross_notional_per_symbol_side_total, symbol, side for the
    #     global gate).
    RISK_CAP_ADVISORY = "risk_cap_advisory"

    # cross-account-risk-policy DEBT-068(g): portfolio kill switch tripped.
    # Emitted by the per-account kill-switch gate
    # (``_account_kill_switch_gate``: daily-loss, open-drawdown,
    # open-stop-risk) and the global kill-switch gate
    # (``_global_kill_switch_gate``: portfolio daily-loss / drawdown),
    # both routed through the shared ``_kill_switch_outcome`` tail. Unlike
    # caps, kill switches earn a dedicated event type in BOTH modes
    # because they are persistent portfolio-condition gates the spec
    # explicitly wants charted over time (spec §"Activity events" /
    # "Runtime Behavior"):
    #   - PAPER advisory branch: emitted with ``details.advisory=True``;
    #     the proposal proceeds (no record downgrade).
    #   - LIVE hard-block branch: emitted as the rejection's accompanying
    #     activity event. NOTE: only the emitted event type changes — the
    #     proposal RECORD's ``final_state`` stays the
    #     ``GATE_REJECTED_*_KILL_SWITCH`` terminal and the proposal funnel
    #     (which keys on ``final_state``, not event type) is UNCHANGED.
    # ``details`` payload (structured-fields contract):
    #
    #     proposal_id (str)
    #     symbol (str)
    #     reason (str)                 human-readable trip summary
    #     gate_reason (str)            e.g. "daily_loss_kill_switch",
    #                                  "open_drawdown_kill_switch",
    #                                  "open_stop_risk_kill_switch",
    #                                  "portfolio_kill_switch",
    #                                  "portfolio_daily_loss_kill_switch"
    #     advisory (bool)              True on the paper branch; absent/False
    #                                  on the live hard-block branch
    #     ... plus gate-specific metric/limit fields.
    RISK_KILL_SWITCH_TRIPPED = "risk_kill_switch_tripped"


class ActivityEvent(BaseModel):
    """A single activity log entry.

    Attributes:
        timestamp: When the event happened (UTC-aware ``now_utc()``
            per Phase 21.2). Legacy on-disk records may carry naive
            timestamps; readers that compare timestamps must coerce
            to UTC at the read boundary.
        event_type: One of :class:`ActivityEventType`.
        message: Short human-readable summary — what shows up in the
            dashboard's activity timeline.
        details: Free-form JSON-serializable payload. Conventional keys:
            ``proposal_id``, ``trade_id``, ``symbol``, ``score``, ``pnl``,
            ``error``. Engine appends whatever is useful per event.
        cycle_id: UUID linking events from the same cycle so the
            dashboard can group them. ``None`` for process-level events
            (startup, shutdown).
    """

    schema_version: int = 1
    timestamp: datetime = Field(default_factory=now_utc)
    event_type: ActivityEventType
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    cycle_id: str | None = None

    model_config = {"use_enum_values": True}

    @field_validator("timestamp", mode="after")
    @classmethod
    def _coerce_timestamp_to_utc(cls, value: datetime) -> datetime:
        """Coerce naive on-disk timestamps to UTC (DEBT-025 / Phase 21.2).

        Activity events written before the 21.2 sweep persist naive
        timestamps; mixing them with new aware timestamps in
        dashboard sorts raises ``TypeError``. ``ensure_utc`` makes
        every loaded ``ActivityEvent`` UTC-aware regardless of the
        on-disk shape.
        """
        return ensure_utc(value)


__all__ = [
    "ActivityEvent",
    "ActivityEventType",
]
