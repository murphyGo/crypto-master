"""Append-only activity log for the trading engine (Phase 8.1).

Every meaningful step the engine takes — cycle started, proposal
generated, auto-decision, position opened/closed, monitor pass,
sleep, shutdown — is recorded as one JSON line. The dashboard reads
this file to surface what the engine is doing in real time.

The format mirrors :mod:`src.feedback.audit` (``AuditLog``): one JSON
object per line, independent open/append/close per write so concurrent
readers and writers don't corrupt earlier events. The append-only
shape means a crash leaves at most one partially-written final line —
which ``read_all`` skips with a warning.

Phase 10.4 routes the file through :class:`JsonlRotator` so writes
land in monthly files (``activity.YYYY-MM.jsonl``) and reads merge the
active month + the most-recent ``Settings.log_retention_months``
archives. The base path stored on ``self.path`` is now the rotator's
base (no extension), not a single concrete file.

Related Requirements:
- FR-009 / FR-010: Live + paper trading mode (production wiring)
- FR-026: Automated Feedback Loop (visibility into the loop)
- NFR-008: log retention (Phase 10.4).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.config import get_settings
from src.logger import get_logger
from src.runtime.jsonl_rotator import JsonlRotator
from src.utils.time import ensure_utc, now_utc

logger = get_logger("crypto_master.runtime.activity_log")


# Relative path used as a fallback marker; the real default is computed
# from ``Settings.data_dir`` at construction time so the file lands on
# whichever volume operations has mounted (Phase 10.5).
DEFAULT_ACTIVITY_PATH = Path("data/runtime/activity.jsonl")


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
    # history without re-deriving it from YAML diffs. ``details``
    # payload (structured-fields contract — pinned by
    # ``test_strategy_action_applied_event_payload``):
    #
    #     sub_account_id (str)
    #     strategy (str)             technique name
    #     prior_state (str)           StrategyAction value
    #     new_state (str)             StrategyAction value
    #     applied_by ("operator" | "system")
    #     evidence_snapshot (dict | None)
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


class ActivityLog:
    """Append-only JSONL activity log for the runtime engine.

    Stateless apart from the file path: every ``append`` is an
    independent open/write/close so concurrent dashboard reads don't
    race with engine writes.

    Usage::

        log = ActivityLog()
        log.append(
            ActivityEventType.CYCLE_STARTED,
            "Cycle 14 begin",
            details={"cycle_index": 14},
            cycle_id="abc-123",
        )
        events = log.tail(50)
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize the log.

        Args:
            path: Where to read from / append to. When supplied, this
                explicit path wins (tests should pass
                ``tmp_path / "activity.jsonl"``). A trailing
                ``.jsonl`` suffix is stripped to derive the rotator
                base so existing test fixtures keep working.
            data_dir: Optional override for the runtime data root.
                When ``path`` is not given, the activity log defaults
                to ``<data_dir>/runtime/activity`` (no extension — it
                is the rotator base; the actual files are
                ``activity.YYYY-MM.jsonl``). ``data_dir`` itself
                defaults to ``Settings().data_dir`` so the file lands
                on the persistent volume operations has mounted
                (Phase 10.5 — fly.toml mounts ``/data``).
        """
        if path is not None:
            # ``self.path`` is preserved for backward compatibility —
            # callers and tests still inspect it. Internally we work
            # off the rotator base, which is the same path with any
            # ``.jsonl`` suffix removed.
            self.path = path
            base = path.with_suffix("") if path.suffix == ".jsonl" else path
        else:
            root = data_dir if data_dir is not None else get_settings().data_dir
            base = root / "runtime" / "activity"
            # Keep ``self.path`` in the .jsonl form for callers that
            # reference it for display / log lines.
            self.path = base.with_name("activity.jsonl")

        retention = get_settings().log_retention_months
        self._rotator = JsonlRotator(base, retention_months=retention)

    def append(
        self,
        event_type: ActivityEventType,
        message: str = "",
        *,
        details: dict[str, Any] | None = None,
        cycle_id: str | None = None,
    ) -> ActivityEvent:
        """Append one event to the log and return it for chaining."""
        event = ActivityEvent(
            event_type=event_type,
            message=message,
            details=details or {},
            cycle_id=cycle_id,
        )
        # Pydantic round-trips through JSON to get a dict the rotator
        # can re-serialize uniformly (including datetime → ISO string).
        record = event.model_dump(mode="json")
        self._rotator.append(record)
        logger.debug(
            f"Activity: {event.event_type} {event.message} " f"cycle={event.cycle_id}"
        )
        return event

    def read_all(self) -> list[ActivityEvent]:
        """Load every event across the active month + retained archives.

        Skips malformed trailing lines (the only kind a crash can
        produce) with a warning. Empty / missing files return an
        empty list.
        """
        events: list[ActivityEvent] = []
        for payload in self._rotator.read_all():
            try:
                events.append(ActivityEvent(**payload))
            except ValueError as e:
                logger.warning(f"Skipping unparseable activity record: {e}")
        return events

    def tail(self, n: int = 100) -> list[ActivityEvent]:
        """Return the most recent ``n`` events in append order.

        The dashboard's timeline shows these top-to-bottom as oldest →
        newest within the slice. ``n`` ≤ 0 returns an empty list.
        """
        if n <= 0:
            return []
        events = self.read_all()
        return events[-n:] if len(events) > n else events

    def filter(
        self,
        *,
        cycle_id: str | None = None,
        event_type: ActivityEventType | str | None = None,
    ) -> list[ActivityEvent]:
        """Return events matching all supplied predicates.

        Args:
            cycle_id: Keep only events with this cycle id.
            event_type: Keep only events of this type. Accepts the
                enum or its raw string value.
        """
        events = self.read_all()
        if cycle_id is not None:
            events = [e for e in events if e.cycle_id == cycle_id]
        if event_type is not None:
            wanted = (
                event_type.value
                if isinstance(event_type, ActivityEventType)
                else event_type
            )
            events = [e for e in events if e.event_type == wanted]
        return events


__all__ = [
    "DEFAULT_ACTIVITY_PATH",
    "ActivityEvent",
    "ActivityEventType",
    "ActivityLog",
]
