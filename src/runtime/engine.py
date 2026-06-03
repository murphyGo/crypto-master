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
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, Field

from src.exchange.base import ExchangeError
from src.logger import get_logger
from src.models import Position
from src.proposal.engine import Proposal, ProposalEngine
from src.proposal.interaction import (
    ProposalDecision,
    ProposalDecisionInput,
    ProposalFinalState,
    ProposalHistory,
    ProposalInteraction,
    ProposalRecord,
)
from src.proposal.notification import NotificationDispatcher
from src.runtime.activity_log import ActivityEvent, ActivityEventType, ActivityLog
from src.runtime.correlation_governor import (
    CorrelationExposure,
    CorrelationExposureSource,
    CorrelationGateConfig,
    CorrelationInputSet,
    CorrelationWarning,
    CorrelationWarningPolicy,
    evaluate_correlation_gate,
)
from src.runtime.gate_reason import GateReason
from src.runtime.market_regime import (
    DEFAULT_BEAR_BAND,
    DEFAULT_BULL_BAND,
    DEFAULT_SMA_PERIOD,
    RegimeClassification,
    classify_regime_detailed,
)
from src.runtime.position_monitor import (
    ORPHAN_AUTO_CLOSE_THRESHOLD as ORPHAN_AUTO_CLOSE_THRESHOLD,  # re-export
)
from src.runtime.position_monitor import (
    PositionMonitor,
)
from src.runtime.reconciliation import (
    classify_open_trade,
    compute_health_report,
)
from src.runtime.runtime_flags import (
    DEFAULT_RUNTIME_FLAGS_PATH,
    read_trading_freeze,
)
from src.runtime.safety_score import (
    RuntimeSafetyScore,
    compute_runtime_safety_score,
    inputs_from_recent_activity_events,
)
from src.runtime.snapshot_recorder import SnapshotRecorder
from src.runtime.strategy_action_snapshot import (
    DEFAULT_STRATEGY_ACTION_SNAPSHOT_PATH,
    AppliedStateMap,
    diff_snapshots,
    load_snapshot,
    save_snapshot,
)
from src.strategy.performance import TradeHistory
from src.strategy.tuning import PAUSE_REASON_GATE_CONFIG, StrategyAction
from src.trading.risk_sizing import RiskSizingRejection, compute_risk_budget_size
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID
from src.utils.time import ensure_utc, now_utc
from src.utils.trading_math import pnl_for_trade

if TYPE_CHECKING:
    from src.exchange.base import BaseExchange
    from src.trading.base import Trader
    from src.trading.portfolio import Mode, PortfolioTracker
    from src.trading.sub_account import SubAccount
    from src.trading.sub_account_registry import SubAccountRegistry

logger = get_logger("crypto_master.runtime.engine")


# CAH-15 Slice 2: the time-stop timeframe table + the orphan auto-close
# threshold moved to ``src/runtime/position_monitor.py`` with the monitor pass.
# ``ORPHAN_AUTO_CLOSE_THRESHOLD`` is re-exported via the import above so existing
# ``from src.runtime.engine import ORPHAN_AUTO_CLOSE_THRESHOLD`` callers/tests
# keep resolving.


# DEBT-066: default freshness window on the in-memory mark-price cache
# consumed by ``_build_cap_blocker_payload``. 300s (5 minutes) is calibrated
# against the default ``cycle_interval_seconds=300`` (``EngineConfig`` field
# above) — within one cycle window the cache is fresh by construction; a
# mark older than 5 minutes is allowed to fall back to ``None`` rather than
# masquerade as a current quote on a cap-rejection event.
MARK_PRICE_CACHE_DEFAULT_MAX_AGE_SECONDS: float = 300.0


@dataclass(frozen=True)
class MarkPriceEntry:
    """One sample in the DEBT-066 in-memory mark-price cache.

    Populated by the per-cycle ticker reads in ``_monitor`` and
    ``_record_portfolio_snapshot`` (which already happen for SL/TP
    checks and AssetSnapshot marks respectively — no new exchange
    calls). Consumed by ``_build_cap_blocker_payload`` via
    ``_get_cached_mark_price``.
    """

    price: Decimal
    observed_at: datetime


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
    runtime_safety_pause_min_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "When set, accepted proposals are blocked before execution if "
            "the recent runtime safety score is below this score. Default "
            "None preserves existing behavior."
        ),
    )
    bitcoin_symbol: str = "BTC/USDT"
    altcoin_symbols: list[str] = Field(
        # Mirrors src/config.py Settings.engine_symbols default. SOL/AVAX
        # removed 2026-05-10 pending strategy fixes (commit eb1ece5).
        default_factory=lambda: [
            "ETH/USDT",
            "BNB/USDT",
            "ADA/USDT",
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
    # Phase 24.1 / DEBT-033: freshness guard on the ticker that feeds
    # the stale-quote sanity gate. If the live ticker's ``timestamp``
    # is older than this threshold relative to ``now_utc()``, the gate
    # falls through with the same WARN that the exception path emits —
    # an old quote is no better than no quote, and silently using one
    # for the slippage / past-SL checks would defeat the gate's
    # purpose. Default 10 seconds gives normal exchange-poll latency
    # plenty of slack while still catching stuck or rate-limited
    # connections.
    max_ticker_age_seconds: float = Field(default=10.0, gt=0)
    # Phase 24.2 (DEBT-033 follow-up): when True, a stale ticker (age
    # > ``max_ticker_age_seconds``) or a ticker fetch failure causes
    # the proposal to be rejected outright with reason
    # ``stale_quote_no_live_data`` instead of falling through to the
    # fill at ``proposal.entry_price``. The original audit concern
    # was that fall-through fills silently proceed without a live
    # cross-check; this flag is the opt-in safety for live mode where
    # that risk is unacceptable. Default False preserves the existing
    # WARN-and-fall-through behaviour so paper / dev deployments are
    # unaffected; flip to True (or set ``ENGINE_REJECT_IF_STALE_QUOTE=true``
    # in the environment) to enforce the harder live-mode guarantee.
    reject_if_stale_quote: bool = Field(
        default=False,
        description=(
            "When True, reject the proposal entirely instead of falling "
            "through if the ticker exceeds max_ticker_age_seconds (or the "
            "ticker fetch fails). Default False preserves existing behavior; "
            "set True for live-mode safety so a fill never proceeds without "
            "a live cross-check."
        ),
    )
    # Phase 22.2 / DEBT-027 paper-trader liquidation visibility.
    # Default ``False`` lets ``PaperTrader.close_position`` record true
    # negative equity when an under-water close would push the free
    # balance below zero, closing the paper-vs-live forecasting gap.
    # Setting ``True`` re-enables the legacy ``balance.free = 0`` clamp
    # — intended only for testing scenarios that need a continuing run
    # after a paper liquidation. Either way, a ``LIQUIDATED`` activity
    # event is emitted so the shortfall is never silently swallowed.
    paper_auto_deposit_on_liquidation: bool = Field(default=False)
    correlation_gate_enabled: bool = Field(default=False)
    correlation_max_sub_accounts_per_symbol_side: int = Field(default=1, ge=1)
    correlation_max_sub_accounts_per_strategy_symbol_side: int = Field(
        default=1,
        ge=1,
    )
    # cross-account-risk-policy DEBT-068(d): path to the operator manual
    # freeze flag file. Re-read at the START of every ``run_cycle`` so an
    # operator can freeze a RUNNING engine without a restart. Defaults to
    # ``config/runtime_flags.yaml`` (project-root-relative, matching the
    # ``SubAccountRegistry`` config-path convention). Missing or malformed
    # file ⇒ NOT frozen (freeze is an explicit opt-in).
    runtime_flags_path: Path = Field(default=DEFAULT_RUNTIME_FLAGS_PATH)

    # strategy-tuning Slice 2 DEBT-069(d): durable snapshot of each
    # ``(sub_account, strategy)`` applied tuning-action, diffed once per
    # process at first cycle to emit ``STRATEGY_ACTION_APPLIED`` events on
    # any ``prior-state -> new-state`` transition (an operator editing the
    # YAML + restart). First run with no prior snapshot seeds silently.
    strategy_action_snapshot_path: Path = Field(
        default=DEFAULT_STRATEGY_ACTION_SNAPSHOT_PATH
    )


@dataclass(frozen=True)
class AccountRuntimePolicy:
    """Resolved runtime policy for one sub-account.

    Values come from ``EngineConfig`` defaults plus optional sub-account policy
    overrides. Keeping this resolved shape local to the engine prevents gate
    code from repeatedly reaching into YAML-facing model fields.
    """

    bitcoin_symbol: str
    altcoin_symbols: list[str]
    altcoin_top_k: int
    sizing_balance: Decimal
    risk_percent: Decimal | None
    leverage: int
    auto_approve_threshold: float
    max_open_positions_total: int | None
    max_open_positions_per_symbol: int
    runtime_safety_pause_min_score: int | None
    fill_slippage_tolerance: Decimal
    reject_if_past_stop_loss: bool
    reject_if_stale_quote: bool
    max_ticker_age_seconds: float
    correlation_gate_enabled: bool
    correlation_max_sub_accounts_per_symbol_side: int
    correlation_max_sub_accounts_per_strategy_symbol_side: int


class PolicyResolver:
    """Resolve one sub-account's runtime policy using field-level precedence."""

    def __init__(
        self,
        *,
        config: EngineConfig,
        sub_account: SubAccount | None,
        default_leverage: int,
    ) -> None:
        self.config = config
        self.sub_account = sub_account
        self.strategy_policy = (
            sub_account.strategy_policy if sub_account is not None else None
        )
        self.execution_policy = (
            sub_account.execution_policy if sub_account is not None else None
        )
        self.default_leverage = default_leverage

    def resolve(self) -> AccountRuntimePolicy:
        """Return the fully resolved policy artifact."""
        return AccountRuntimePolicy(
            bitcoin_symbol=self.bitcoin_symbol(),
            altcoin_symbols=self.altcoin_symbols(),
            altcoin_top_k=self.altcoin_top_k(),
            sizing_balance=self.sizing_balance(),
            risk_percent=self.risk_percent(),
            leverage=self.leverage(),
            auto_approve_threshold=self.auto_approve_threshold(),
            max_open_positions_total=self.max_open_positions_total(),
            max_open_positions_per_symbol=self.max_open_positions_per_symbol(),
            runtime_safety_pause_min_score=self.runtime_safety_pause_min_score(),
            fill_slippage_tolerance=self.fill_slippage_tolerance(),
            reject_if_past_stop_loss=self.reject_if_past_stop_loss(),
            reject_if_stale_quote=self.reject_if_stale_quote(),
            max_ticker_age_seconds=self.max_ticker_age_seconds(),
            correlation_gate_enabled=self.correlation_gate_enabled(),
            correlation_max_sub_accounts_per_symbol_side=(
                self.correlation_max_sub_accounts_per_symbol_side()
            ),
            correlation_max_sub_accounts_per_strategy_symbol_side=(
                self.correlation_max_sub_accounts_per_strategy_symbol_side()
            ),
        )

    def bitcoin_symbol(self) -> str:
        if (
            self.strategy_policy is not None
            and self.strategy_policy.bitcoin_symbol is not None
        ):
            return self.strategy_policy.bitcoin_symbol
        return self.config.bitcoin_symbol

    def altcoin_symbols(self) -> list[str]:
        if (
            self.strategy_policy is not None
            and self.strategy_policy.symbols is not None
        ):
            return list(self.strategy_policy.symbols)
        return list(self.config.altcoin_symbols)

    def altcoin_top_k(self) -> int:
        if self.strategy_policy is not None and self.strategy_policy.top_k is not None:
            return self.strategy_policy.top_k
        return self.config.altcoin_top_k

    def sizing_balance(self) -> Decimal:
        if self.sub_account is None:
            return self.config.balance
        return self.sub_account.effective_sizing_balance(self.config.balance)

    def risk_percent(self) -> Decimal | None:
        if self.sub_account is None:
            return None
        return self.sub_account.effective_risk_percent()

    def leverage(self) -> int:
        if self.sub_account is None:
            return int(self.default_leverage)
        cap = self.sub_account.effective_leverage_cap()
        if cap is None:
            return int(self.default_leverage)
        return min(int(self.default_leverage), cap)

    def auto_approve_threshold(self) -> float:
        override = (
            self.sub_account.effective_auto_approve_threshold()
            if self.sub_account is not None
            else None
        )
        return override if override is not None else self.config.auto_approve_threshold

    def max_open_positions_total(self) -> int | None:
        if self.sub_account is None:
            return None
        return self.sub_account.effective_max_open_positions_total()

    def max_open_positions_per_symbol(self) -> int:
        override = (
            self.sub_account.effective_max_open_positions_per_symbol()
            if self.sub_account is not None
            else None
        )
        if override is not None:
            return override
        return self.config.max_open_positions_per_symbol

    def runtime_safety_pause_min_score(self) -> int | None:
        if (
            self.execution_policy is not None
            and self.execution_policy.runtime_safety_pause_min_score is not None
        ):
            return self.execution_policy.runtime_safety_pause_min_score
        return self.config.runtime_safety_pause_min_score

    def fill_slippage_tolerance(self) -> Decimal:
        if (
            self.execution_policy is not None
            and self.execution_policy.fill_slippage_tolerance is not None
        ):
            return self.execution_policy.fill_slippage_tolerance
        return self.config.fill_slippage_tolerance

    def reject_if_past_stop_loss(self) -> bool:
        if (
            self.execution_policy is not None
            and self.execution_policy.reject_if_past_stop_loss is not None
        ):
            return self.execution_policy.reject_if_past_stop_loss
        return self.config.reject_if_past_stop_loss

    def reject_if_stale_quote(self) -> bool:
        if (
            self.execution_policy is not None
            and self.execution_policy.reject_if_stale_quote is not None
        ):
            return self.execution_policy.reject_if_stale_quote
        return self.config.reject_if_stale_quote

    def max_ticker_age_seconds(self) -> float:
        if (
            self.execution_policy is not None
            and self.execution_policy.max_ticker_age_seconds is not None
        ):
            return self.execution_policy.max_ticker_age_seconds
        return self.config.max_ticker_age_seconds

    def correlation_gate_enabled(self) -> bool:
        if (
            self.execution_policy is not None
            and self.execution_policy.correlation_gate_enabled is not None
        ):
            return self.execution_policy.correlation_gate_enabled
        return self.config.correlation_gate_enabled

    def correlation_max_sub_accounts_per_symbol_side(self) -> int:
        if (
            self.execution_policy is not None
            and self.execution_policy.correlation_max_sub_accounts_per_symbol_side
            is not None
        ):
            return self.execution_policy.correlation_max_sub_accounts_per_symbol_side
        return self.config.correlation_max_sub_accounts_per_symbol_side

    def correlation_max_sub_accounts_per_strategy_symbol_side(self) -> int:
        if (
            self.execution_policy is not None
            and self.execution_policy.correlation_max_sub_accounts_per_strategy_symbol_side
            is not None
        ):
            return (
                self.execution_policy.correlation_max_sub_accounts_per_strategy_symbol_side
            )
        return self.config.correlation_max_sub_accounts_per_strategy_symbol_side


# =============================================================================
# Cycle result (used for tests + the dashboard's per-cycle summary)
# =============================================================================


@dataclass
class CycleResult:
    """Summary of one ``run_cycle()`` invocation.

    Returned for testability and so the dashboard can render
    per-cycle stats without re-deriving them from the activity log.

    Proposal counters are stage counters, not mutually-exclusive
    final-state counters. ``proposals_accepted`` counts proposals
    accepted by the composite proposal decision gate. A later
    post-acceptance gate can still reject the fill, such as the
    per-symbol cap, stale-quote past-SL gate, slippage gate, or
    no-live-data gate. In those paths both ``proposals_accepted`` and
    ``proposals_rejected`` increment for the same proposal, and
    ``accepted + rejected`` is not expected to equal
    ``proposals_processed``.
    """

    cycle_id: str
    proposals_generated: int = 0
    proposals_accepted: int = 0
    proposals_rejected: int = 0
    positions_opened: int = 0
    positions_closed: int = 0
    errors: list[EngineError] = field(default_factory=list)


class GateDecision(str, Enum):
    """Final persistence decision after proposal gates finish."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class GateActivityEvent:
    """Activity event staged until the proposal gate envelope is persisted."""

    event_type: ActivityEventType
    message: str
    details: dict[str, Any]
    cycle_id: str

    def to_activity_event(self) -> ActivityEvent:
        return ActivityEvent(
            event_type=self.event_type,
            message=self.message,
            details=self.details,
            cycle_id=self.cycle_id,
        )


@dataclass(frozen=True)
class GateOutcome:
    """Final proposal gate outcome plus the ordered activity batch."""

    decision: GateDecision
    reason: str | None
    events: list[GateActivityEvent]
    final_record: ProposalRecord


# =============================================================================
# Errors
# =============================================================================


class ErrorCategory(str, Enum):
    """Structured runtime error categories."""

    BTC_SCAN = "btc_scan"
    ALT_SCAN = "alt_scan"
    SUB_ACCOUNT = "sub_account"
    POSITION_OPEN = "position_open"
    POSITION_STATE = "position_state"
    TICKER_MONITOR = "ticker_monitor"


@dataclass(frozen=True)
class EngineError:
    """Structured runtime error envelope for cycle results."""

    category: ErrorCategory
    symbol: str | None
    detail: str
    exception: Exception | None = None


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
        registry: SubAccountRegistry | None = None,
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
        self.sub_account_registry = registry
        self.notification_dispatcher = notification_dispatcher
        self.activity_log = activity_log
        self.config = config or EngineConfig()
        self.portfolio_tracker = portfolio_tracker
        self.mode = mode
        self.quote_currency = quote_currency

        # Inject the auto-decide callback. The ProposalInteraction
        # handed in by the caller is reused so its ProposalHistory
        # attachment stays the single persistence path. DEBT-041
        # (Phase 26.2): use the public setter rather than reaching
        # into ``_decision_callback`` directly.
        self.proposal_interaction = proposal_interaction
        self.proposal_interaction.set_decision_callback(self._auto_decide)

        # Wire per-notifier failure visibility (consistency-hardening
        # CH-03). The dispatcher's per-backend ``try/except`` previously
        # only logged a warning, so a Slack 5xx or Telegram 401 never
        # reached the activity log and never bumped the runtime safety
        # score. Setting the callback here surfaces every backend
        # failure as a NOTIFICATION_FAILED event tagged with the
        # backend class name. The dispatcher may be a fan-out wrapper
        # (e.g. ``RoutedNotificationDispatcher``) that delegates to
        # other dispatcher instances; set the callback on every
        # dispatcher we can reach so route-level failures surface too.
        for dispatcher in self._dispatchers_for_callback_wiring():
            dispatcher._on_notifier_failure = self._on_notifier_failure

        self._stop_event = asyncio.Event()
        self._cycle_index = 0
        # cross-account-risk-policy DEBT-068(d): operator manual freeze
        # state for the CURRENT cycle. Read ONCE at the top of
        # ``run_cycle`` from ``config/runtime_flags.yaml`` (one disk read
        # per cycle, NOT per proposal). When True, ``_handle_proposal``
        # rejects every proposal at the earliest gate in both paper and
        # live mode. Initialised False so an engine that never runs a
        # cycle is treated as not frozen.
        self._operator_freeze_active = False
        # strategy-tuning DEBT-069(d): the applied-action transition diff is a
        # ONCE-PER-PROCESS operation (it detects YAML edits that take effect on
        # restart, not per-cycle changes). Guarded by this flag so it runs at
        # the first ``run_cycle`` only.
        self._strategy_action_diff_done = False
        self._strategy_lookup_cache: dict[str, str] | None = None
        self._runtime_policy_cache: dict[str, AccountRuntimePolicy] = {}
        self._runtime_safety_score_cache: RuntimeSafetyScore | None = None
        # HTF trend filter cache. Keyed by ``(symbol, ymd)`` so the
        # natural date rollover invalidates entries; ``run_cycle`` also
        # clears at cycle start so very long-running processes never
        # serve a stale 1D direction even if the system clock drifts
        # without crossing midnight UTC. Value is
        # ``(direction, last_close, sma200)`` where ``direction`` is
        # ``"up"`` or ``"down"``.
        self._htf_trend_cache: dict[tuple[str, str], tuple[str, Decimal, Decimal]] = {}
        # P0-E: sibling-strategy de-duplication cache. Keyed by
        # ``(strategy_family, symbol, signal)`` and reset at every
        # ``run_cycle`` start. The value is the ``technique_name`` of
        # the first strategy in the family that won the gate this
        # cycle, recorded for traceability in the rejection event of
        # any later sibling that proposes the same (symbol, side).
        # A 12-day Fly paper run showed rsi_universal / rsi_4h /
        # rsi_15m firing identical AVAX/USDT shorts at 9.77 within
        # seven seconds of each other — effective 3x leverage on the
        # same losing thesis because the correlation gate keys on
        # ``technique_name`` and treats them as independent.
        self._accepted_family_signals: dict[tuple[str, str, str], str] = {}

        # CAH-15 Slice 2: the orphan-strike counter (``_orphan_strike_counts``)
        # is cross-cycle state that moved to ``PositionMonitor`` (constructed at
        # the end of ``__init__``). It is exposed via the ``_orphan_strike_counts``
        # property below so existing readers keep working.

        # market-regime classifier cache. Keyed by ``(reference_symbol,
        # timeframe)`` so two accounts pointing at the same BTC/USDT 4h
        # baseline share the OHLCV fetch; reset at the top of every
        # ``run_cycle`` alongside the HTF trend-filter cache so a long-
        # running process never serves a stale classification.
        self._market_regime_cache: dict[tuple[str, str], RegimeClassification] = {}

        # DEBT-066: in-memory mark-price cache. Populated by the
        # per-cycle ticker reads that already happen in
        # ``_monitor`` (SL/TP check) and ``_record_portfolio_snapshot``
        # (per-trade mark for the AssetSnapshot). Consumed by
        # ``_build_cap_blocker_payload`` so cap-rejection events can
        # surface ``unrealized_pnl_percent`` for blocking trades
        # without re-introducing the per-blocker
        # ``await exchange.get_ticker(...)`` hot-path tax. Freshness
        # is enforced at read time via ``_get_cached_mark_price`` —
        # the cache itself is allowed to keep stale entries (the
        # write path on the next cycle overwrites them, and a stale
        # symbol simply returns ``None`` instead of a stale mark).
        # Keyed by ``symbol``; we intentionally do *not* key by
        # sub_account_id because the mark for a symbol is the same
        # regardless of which account holds the position.
        self._mark_price_cache: dict[str, MarkPriceEntry] = {}

        # CAH-15 Slice 2: the monitor/exit/orphan collaborator. Unlike the
        # stateless SnapshotRecorder (rebuilt on demand), the monitor owns
        # cross-cycle ``_orphan_strike_counts`` so it is a single construct-once
        # instance. It receives the engine's ``_remember_mark_price`` directly
        # (ADR CHANGE B — never chained) plus the recorder-routing delegates
        # ``_record_closed_trade`` / ``_find_proposal_record_for_trade`` (which
        # resolve the live SnapshotRecorder each call), and the engine's
        # ``exchange`` as the per-trade-ticker fallback.
        self._position_monitor = PositionMonitor(
            activity_log=self.activity_log,
            proposal_engine=self.proposal_engine,
            default_exchange=self.exchange,
            remember_mark_price=self._remember_mark_price,
            record_closed_trade=self._record_closed_trade,
            find_proposal_record_for_trade=self._find_proposal_record_for_trade,
        )

    @property
    def _orphan_strike_counts(self) -> dict[str, int]:
        """Cross-cycle orphan-strike counter, owned by the position monitor.

        Exposed as a property (CAH-15 Slice 2) so the cache physically lives on
        :class:`PositionMonitor` while existing engine-level readers — including
        the orphan-watchdog tests — keep resolving ``engine._orphan_strike_counts``
        unchanged. The monitor reassigns its own dict each pass (the prune step),
        so this always reflects the live counter.
        """
        return self._position_monitor._orphan_strike_counts

    def _dispatchers_for_callback_wiring(self) -> list[NotificationDispatcher]:
        """Return every dispatcher that should surface per-notifier failures.

        ``RoutedNotificationDispatcher`` exposes the inner
        ``default_dispatcher`` and ``route_dispatchers``; both layers
        keep their own ``_notifiers`` and run their own ``try/except``
        per-backend, so the engine wires the failure callback onto each
        of them.
        """
        seen: set[int] = set()
        result: list[NotificationDispatcher] = []

        def visit(dispatcher: NotificationDispatcher) -> None:
            if id(dispatcher) in seen:
                return
            seen.add(id(dispatcher))
            result.append(dispatcher)
            inner = getattr(dispatcher, "default_dispatcher", None)
            if isinstance(inner, NotificationDispatcher):
                visit(inner)
            routes = getattr(dispatcher, "route_dispatchers", None)
            if isinstance(routes, dict):
                for route_dispatcher in routes.values():
                    if isinstance(route_dispatcher, NotificationDispatcher):
                        visit(route_dispatcher)

        visit(self.notification_dispatcher)
        return result

    def _on_notifier_failure(
        self,
        notifier_name: str,
        notification: Any,
        exc: BaseException,
    ) -> None:
        """Append a NOTIFICATION_FAILED activity event for a backend failure.

        Hooked into ``NotificationDispatcher`` constructors so per-backend
        failures (Slack 5xx, Telegram 401, SMTP timeout, …) feed the
        runtime safety score via ``recent_notification_failures``
        instead of being lost in the dispatcher's per-notifier
        ``logger.warning`` (consistency-hardening CH-03).
        """
        try:
            proposal = notification.proposal
            details = {
                "proposal_id": getattr(proposal, "proposal_id", None),
                "symbol": getattr(proposal, "symbol", None),
                "notifier_name": notifier_name,
                "dispatcher_name": type(self.notification_dispatcher).__name__,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        except Exception:  # pragma: no cover - defensive
            details = {
                "notifier_name": notifier_name,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        self.activity_log.append(
            ActivityEventType.NOTIFICATION_FAILED,
            f"Notifier {notifier_name} failed: {exc}",
            details=details,
        )

    def _current_runtime_safety_score(
        self,
        extra_events: list[ActivityEvent] | None = None,
    ) -> RuntimeSafetyScore:
        if extra_events is None and self._runtime_safety_score_cache is not None:
            return self._runtime_safety_score_cache
        events = self.activity_log.read_all()
        if extra_events:
            events.extend(extra_events)
        score = compute_runtime_safety_score(inputs_from_recent_activity_events(events))
        if extra_events is None:
            self._runtime_safety_score_cache = score
        return score

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
        # runtime-reconciliation §3: one health-check pass per startup,
        # after rehydration (the trader's constructor already ran by the
        # time we get here) and before the cycle loop. Resolution
        # 2026-05-13: async / log+continue — never fail-startup. Any
        # exception inside the helper is swallowed so a malformed
        # ledger can't keep the Fly machine from booting.
        self._run_reconciliation_health_check()
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
        # cross-account-risk-policy DEBT-068(d): re-read the operator
        # manual freeze flag ONCE per cycle so an operator can freeze a
        # RUNNING engine without a restart. Cached on ``self`` and read
        # by every ``_handle_proposal`` call this cycle (no per-proposal
        # disk read). Fail-safe to NOT frozen on missing/malformed file.
        self._operator_freeze_active = read_trading_freeze(
            self.config.runtime_flags_path
        )
        self._strategy_lookup_cache = None
        self._runtime_policy_cache = {}
        self._runtime_safety_score_cache = None
        self._htf_trend_cache = {}
        self._accepted_family_signals = {}
        self._market_regime_cache = {}
        self.activity_log.append(
            ActivityEventType.CYCLE_STARTED,
            f"Cycle {self._cycle_index} begin",
            details={"cycle_index": self._cycle_index},
            cycle_id=cycle_id,
        )

        result = CycleResult(cycle_id=cycle_id)

        # strategy-tuning DEBT-069(d): emit STRATEGY_ACTION_APPLIED events for
        # any applied-action transition since the previous run. Runs once per
        # process (first cycle); seeds silently on first deploy.
        self._maybe_emit_strategy_action_transitions(cycle_id)

        for sub_account in self._active_sub_accounts():
            sub_account_id = self._sub_account_id(sub_account)
            try:
                trader = self._trader_for_sub_account(sub_account_id)
                exchange = self._exchange_for_trader(trader)

                proposals = await self._scan(cycle_id, result, sub_account, exchange)
                for proposal in proposals:
                    await self._handle_proposal(
                        proposal, cycle_id, result, sub_account, trader, exchange
                    )

                await self._position_monitor.monitor(
                    cycle_id, result, sub_account, trader, exchange
                )

                await self._record_portfolio_snapshot(
                    cycle_id, sub_account, trader, exchange
                )
            except Exception as e:
                # Per-sub-account failure isolation (consistency-hardening
                # CH-03). Without this guard a single account's exception
                # — registry mismatch, trader bug, snapshot crash — would
                # propagate up out of ``run_cycle`` and skip scan, monitor,
                # and snapshot for every later account this cycle. The
                # outer ``_run_one_cycle_with_guard`` only catches at
                # cycle granularity, which is too coarse once multiple
                # sub-accounts share a runtime.
                logger.exception(f"Sub-account cycle failed for {sub_account_id}")
                self.activity_log.append(
                    ActivityEventType.CYCLE_ERRORED,
                    f"Sub-account {sub_account_id} cycle failed: {e}",
                    details={
                        "sub_account_id": sub_account_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    cycle_id=cycle_id,
                )
                result.errors.append(
                    EngineError(
                        category=ErrorCategory.SUB_ACCOUNT,
                        symbol=None,
                        detail=f"sub_account[{sub_account_id}]:{e}",
                        exception=e,
                    )
                )

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
        sub_account: SubAccount | None = None,
        exchange: BaseExchange | None = None,
    ) -> list[Proposal]:
        """Run the BTC + altcoin scans, returning all proposals collected.

        Per-call exchange / strategy errors are recorded as
        ``SCAN_ERRORED`` events and added to ``result.errors``, but
        they do not fail the cycle — one bad symbol shouldn't block
        the others.
        """
        proposals: list[Proposal] = []
        sub_account_id = self._sub_account_id(sub_account)
        policy = self._runtime_policy_for_id(sub_account_id)
        strategies = None
        if self.sub_account_registry is not None:
            available_strategies = list(self.proposal_engine.strategies.values())
            strategies = self.sub_account_registry.filter_strategies(
                sub_account_id, available_strategies
            )
        risk_percent = (
            float(policy.risk_percent) if policy.risk_percent is not None else None
        )
        account_exchange = exchange or self.exchange
        previous_proposal_exchange = getattr(self.proposal_engine, "exchange", None)
        proposal_exchange_swapped = previous_proposal_exchange is not None
        if proposal_exchange_swapped:
            self.proposal_engine.exchange = account_exchange

        try:
            try:
                btc = await self.proposal_engine.propose_bitcoin(
                    symbol=policy.bitcoin_symbol,
                    balance=policy.sizing_balance,
                    strategies=strategies,
                    risk_percent=risk_percent,
                    leverage=policy.leverage,
                    sub_account_id=sub_account_id,
                )
            except ExchangeError as e:
                self.activity_log.append(
                    ActivityEventType.SCAN_ERRORED,
                    f"Bitcoin scan failed: {e}",
                    details={
                        "symbol": policy.bitcoin_symbol,
                        "error": str(e),
                        "sub_account_id": sub_account_id,
                    },
                    cycle_id=cycle_id,
                )
                result.errors.append(
                    EngineError(
                        category=ErrorCategory.BTC_SCAN,
                        symbol=policy.bitcoin_symbol,
                        detail=str(e),
                        exception=e,
                    )
                )
                btc = None

            if btc is not None:
                proposals.append(btc)

            try:
                altcoins = await self.proposal_engine.propose_altcoins(
                    symbols=policy.altcoin_symbols,
                    balance=policy.sizing_balance,
                    top_k=policy.altcoin_top_k,
                    strategies=strategies,
                    risk_percent=risk_percent,
                    leverage=policy.leverage,
                    sub_account_id=sub_account_id,
                )
            except ExchangeError as e:
                self.activity_log.append(
                    ActivityEventType.SCAN_ERRORED,
                    f"Altcoin scan failed: {e}",
                    details={"error": str(e), "sub_account_id": sub_account_id},
                    cycle_id=cycle_id,
                )
                result.errors.append(
                    EngineError(
                        category=ErrorCategory.ALT_SCAN,
                        symbol=None,
                        detail=str(e),
                        exception=e,
                    )
                )
                altcoins = []
        finally:
            if proposal_exchange_swapped:
                self.proposal_engine.exchange = cast(
                    "BaseExchange", previous_proposal_exchange
                )

        proposals.extend(altcoins)
        result.proposals_generated += len(proposals)
        return proposals

    def _finalize_rejection(
        self,
        *,
        final_record: ProposalRecord,
        replay_events: list[GateActivityEvent],
        result: CycleResult,
    ) -> None:
        """Persist a rejected proposal record and replay its staged events.

        CAH-05: the invariant persist-and-replay tail shared by every gate
        rejection in :meth:`_handle_proposal`. The caller is responsible for
        passing the EXACT event list that site already iterates — ``outcome.
        events`` for sites that bake the running ``events`` list into the
        outcome (Shape A), or ``events + gate_outcome.events`` for sites that
        keep the gate's own events separate (Shape B). This helper does not
        concatenate; it only iterates ``replay_events`` verbatim so the two
        asymmetric shapes stay behavior-identical and events are neither
        double- nor under-counted.
        """
        result.proposals_rejected += 1
        self.proposal_history.save(final_record)
        for event in replay_events:
            self.activity_log.append(
                event.event_type,
                event.message,
                details=event.details,
                cycle_id=event.cycle_id,
            )

    async def _handle_proposal(
        self,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
        sub_account: SubAccount | None,
        trader: Trader,
        exchange: BaseExchange | None = None,
    ) -> None:
        """Persist + decide + (maybe) execute one proposal."""
        events = [
            GateActivityEvent(
                ActivityEventType.PROPOSAL_GENERATED,
                f"Proposal {proposal.symbol} {proposal.signal} "
                f"score={proposal.score.composite:.4f}",
                _proposal_summary(proposal),
                cycle_id,
            )
        ]

        # cross-account-risk-policy DEBT-068(d) — Operator manual freeze.
        # The EARLIEST reject in the gate stack (spec §"Runtime Behavior"
        # gate 1): if the operator flipped ``runtime_flags.trading_freeze``
        # true (read once per cycle into ``self._operator_freeze_active``),
        # reject EVERY proposal with ``reason="operator_freeze"`` ahead of
        # the score gate, correlation, regime, kill-switches, sizing, and
        # caps. Unlike the cap / kill-switch gates this is a MANUAL kill,
        # so it hard-blocks in BOTH paper and live mode — the operator
        # explicitly pulled the lever, so there is no lab-measurement
        # rationale to keep paper trading. We do NOT reuse
        # ``_kill_switch_outcome`` (which keeps paper advisory).
        if self._operator_freeze_active:
            self._reject_operator_freeze(proposal, cycle_id, result, events)
            return

        safety_score = self._current_runtime_safety_score(
            [event.to_activity_event() for event in events]
        )

        try:
            await self.notification_dispatcher.notify_proposal(
                proposal,
                safety_score=safety_score,
            )
        except Exception as e:
            # Phase 26.3 / DEBT-038: emit-then-swallow. The dispatcher
            # already isolates per-notifier failures (see
            # ``NotificationDispatcher.notify_proposal``); this branch
            # only fires when the dispatcher call itself raises (e.g.
            # programming error, invalid proposal data). Lead policy:
            # surface to the activity log so operators see the failure
            # in the dashboard, but continue the cycle — one broken
            # notification path must not silence the trading loop.
            logger.warning(f"Notification dispatch failed: {e}")
            events.append(
                GateActivityEvent(
                    ActivityEventType.NOTIFICATION_FAILED,
                    f"Notification dispatch failed for {proposal.symbol}: {e}",
                    {
                        "proposal_id": proposal.proposal_id,
                        "symbol": proposal.symbol,
                        "dispatcher_name": type(self.notification_dispatcher).__name__,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    cycle_id,
                )
            )

        record = await self.proposal_interaction.decide(
            proposal, actor=self.config.actor
        )

        if record.decision == ProposalDecision.ACCEPTED.value:
            result.proposals_accepted += 1
            # proposal-funnel-audit §1 State 3a: score gate accepted.
            # Subsequent gate rejections will overwrite ``final_state``;
            # the score-accepted bucket is for the in-flight transition
            # and the final terminal record when every gate accepts.
            record = record.mark(ProposalFinalState.SCORE_ACCEPTED)
            events.append(
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_ACCEPTED,
                    f"Auto-accepted {proposal.symbol} {proposal.signal}",
                    {
                        **_proposal_summary(proposal),
                        "reason": "score_above_threshold",
                    },
                    cycle_id,
                )
            )

            # DEBT-062: ``_correlation_gate`` runs BEFORE
            # ``_market_regime_gate``. When both gates would block, the
            # correlation rejection (directly actionable — "you already
            # have exposure here") must displace the regime rejection
            # (non-actionable — "this market is in the wrong state") on
            # the operator dashboard. Per-cycle regime cache means the
            # OHLCV fetch cost is unchanged by ordering.
            correlation_outcome = self._correlation_gate(
                proposal,
                record,
                trader,
                cycle_id,
            )
            events.extend(correlation_outcome.events)
            if correlation_outcome.decision == GateDecision.REJECTED:
                # Shape A: the running ``events`` list already carries the
                # correlation gate's events (extended above), so the replay
                # list is ``events`` itself — NOT ``events + outcome.events``.
                self._finalize_rejection(
                    final_record=correlation_outcome.final_record,
                    replay_events=events,
                    result=result,
                )
                return
            record = correlation_outcome.final_record

            regime_outcome = await self._market_regime_gate(
                proposal,
                record,
                sub_account,
                exchange or self.exchange,
                cycle_id,
            )
            if regime_outcome is not None:
                self._finalize_rejection(
                    final_record=regime_outcome.final_record,
                    replay_events=events + regime_outcome.events,
                    result=result,
                )
                return

            # cross-account-risk-policy §"Runtime Behavior" / DEBT-068(c):
            # the kill switches run BEFORE sizing and BEFORE the cap gates,
            # so a tripped account/portfolio limit short-circuits before any
            # sizing or aggregate-cap event fires. Order within each gate
            # (spec §"Runtime Behavior"): per-account daily-loss (c-2) →
            # per-account open-drawdown → per-account open-stop-risk (c-1),
            # then the global gate (portfolio daily-loss (c-2) → portfolio
            # open-drawdown (c-1)). The daily-loss checks live at the TOP of
            # their respective combined gates so the wiring here is
            # unchanged; both gates simply gained a higher-priority check.
            #
            # One earlier slot will precede these once shipped:
            #   - DEBT-068(d): operator manual freeze (earliest reject).
            # Still out of scope for this slice.
            account_kill_switch = await self._account_kill_switch_gate(
                proposal,
                record,
                sub_account,
                trader,
                cycle_id,
            )
            if account_kill_switch is not None:
                self._finalize_rejection(
                    final_record=account_kill_switch.final_record,
                    replay_events=events + account_kill_switch.events,
                    result=result,
                )
                return

            global_kill_switch = await self._global_kill_switch_gate(
                proposal,
                record,
                cycle_id,
            )
            if global_kill_switch is not None:
                self._finalize_rejection(
                    final_record=global_kill_switch.final_record,
                    replay_events=events + global_kill_switch.events,
                    result=result,
                )
                return

            proposal, risk_sizing_outcome = await self._risk_budget_sizing_gate(
                proposal,
                record,
                sub_account,
                trader,
                cycle_id,
            )
            if risk_sizing_outcome is not None:
                self._finalize_rejection(
                    final_record=risk_sizing_outcome.final_record,
                    replay_events=events + risk_sizing_outcome.events,
                    result=result,
                )
                return
            # strategy-tuning §"Runtime Behavior": enforce the applied
            # action for this ``(sub_account, strategy)`` pair. ``keep``
            # / ``promote`` pass through, ``retune`` emits an advisory
            # event and passes through, ``scout`` rewrites
            # ``proposal.quantity`` × ``scout_size_factor`` BEFORE the
            # downstream gates that consume the quantity (account
            # aggregate cap, stale-position block). ``shadow`` and
            # ``pause`` short-circuit with their own terminals.
            proposal, record, action_outcome = self._strategy_action_gate(
                proposal,
                record,
                sub_account,
                cycle_id,
            )
            if action_outcome is not None:
                self._finalize_rejection(
                    final_record=action_outcome.final_record,
                    replay_events=events + action_outcome.events,
                    result=result,
                )
                return

            trend_rejection = await self._trend_filter_gate(
                proposal,
                record,
                exchange or self.exchange,
                cycle_id,
            )
            if trend_rejection is not None:
                self._finalize_rejection(
                    final_record=trend_rejection.final_record,
                    replay_events=events + trend_rejection.events,
                    result=result,
                )
                return

            sibling_rejection = self._sibling_family_gate(
                proposal,
                record,
                cycle_id,
            )
            if sibling_rejection is not None:
                self._finalize_rejection(
                    final_record=sibling_rejection.final_record,
                    replay_events=events + sibling_rejection.events,
                    result=result,
                )
                return

            post_incident_safety_score = self._current_runtime_safety_score(
                [event.to_activity_event() for event in events]
            )
            pause_rejection = self._runtime_safety_pause_gate(
                proposal,
                record,
                sub_account,
                post_incident_safety_score,
                cycle_id,
            )
            if pause_rejection is not None:
                self._finalize_rejection(
                    final_record=pause_rejection.final_record,
                    replay_events=events + pause_rejection.events,
                    result=result,
                )
                return

            # Phase 12.1: cross-cycle position caps. The composite gate
            # has accepted this proposal, but we may already be at the
            # total or per-symbol cap from previous cycles' open trades.
            # Block execution here and record a second rejection reason on
            # top of the existing composite-threshold one. CAH-05: these
            # two caps are now extracted into ``_total_cap_gate`` /
            # ``_symbol_cap_gate`` to match the 13 sibling ``_*_gate``
            # methods; the total cap runs first (order preserved).
            total_cap_rejection = await self._total_cap_gate(
                proposal,
                record,
                sub_account,
                trader,
                cycle_id,
            )
            if total_cap_rejection is not None:
                self._finalize_rejection(
                    final_record=total_cap_rejection.final_record,
                    replay_events=events + total_cap_rejection.events,
                    result=result,
                )
                return

            symbol_cap_rejection = await self._symbol_cap_gate(
                proposal,
                record,
                sub_account,
                trader,
                cycle_id,
            )
            if symbol_cap_rejection is not None:
                self._finalize_rejection(
                    final_record=symbol_cap_rejection.final_record,
                    replay_events=events + symbol_cap_rejection.events,
                    result=result,
                )
                return

            # cross-account-risk-policy gates: per-account aggregate
            # cap and stale-position block. Both run after the existing
            # symbol-cap gate (DEBT-062 owns regime-vs-correlation
            # ordering). Paper-mode advisories return ``None`` and emit
            # an event; live-mode rejections short-circuit here.
            account_agg_rejection = self._account_aggregate_cap_gate(
                proposal, record, sub_account, trader, cycle_id
            )
            if account_agg_rejection is not None:
                self._finalize_rejection(
                    final_record=account_agg_rejection.final_record,
                    replay_events=events + account_agg_rejection.events,
                    result=result,
                )
                return

            stale_block_rejection = self._stale_position_block_gate(
                proposal, record, sub_account, trader, cycle_id
            )
            if stale_block_rejection is not None:
                self._finalize_rejection(
                    final_record=stale_block_rejection.final_record,
                    replay_events=events + stale_block_rejection.events,
                    result=result,
                )
                return

            # cross-account-risk-policy DEBT-068(b): opt-in global
            # symbol/side caps. Runs after the per-account aggregate cap
            # gate AND after ``_correlation_gate`` (which runs earlier at
            # line ~1160), satisfying the spec's "global caps checked
            # after per-account caps and after the correlation governor"
            # ordering. Inert unless ``GlobalRiskPolicy.enabled`` and at
            # least one cap is configured. Paper-mode advisories return
            # ``None`` and emit an event; live-mode rejections
            # short-circuit here.
            global_cap_rejection = self._global_aggregate_cap_gate(
                proposal, record, sub_account, cycle_id
            )
            if global_cap_rejection is not None:
                self._finalize_rejection(
                    final_record=global_cap_rejection.final_record,
                    replay_events=events + global_cap_rejection.events,
                    result=result,
                )
                return

            # proposal-funnel-audit §1 State 5: every gate accepted;
            # the record advances to ``proposal_opened``. ``_execute``
            # promotes to ``trade_opened`` on a successful fill, and
            # the post-execute stale-quote gate (inside ``_execute``)
            # rewrites the record back to
            # ``gate_rejected_stale_quote`` if it fires.
            record = record.mark(ProposalFinalState.PROPOSAL_OPENED)
            outcome = GateOutcome(GateDecision.ACCEPTED, None, events, record)
            self.proposal_history.save(outcome.final_record)
            for event in outcome.events:
                self.activity_log.append(
                    event.event_type,
                    event.message,
                    details=event.details,
                    cycle_id=event.cycle_id,
                )
            await self._execute(proposal, cycle_id, result, trader, exchange)
        else:
            # proposal-funnel-audit §1 State 3b: score gate rejection.
            rejected_record = record.mark(ProposalFinalState.SCORE_REJECTED)
            # Shape A: the score-reject event is concatenated onto the
            # running ``events`` list here, and the replay list is that
            # full concatenation.
            self._finalize_rejection(
                final_record=rejected_record,
                replay_events=events
                + [
                    GateActivityEvent(
                        ActivityEventType.PROPOSAL_REJECTED,
                        f"Auto-rejected {proposal.symbol} {proposal.signal}",
                        {
                            **_proposal_summary(proposal),
                            "reason": record.rejection_reason,
                        },
                        cycle_id,
                    )
                ],
                result=result,
            )

    async def _risk_budget_sizing_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        trader: Trader,
        cycle_id: str,
    ) -> tuple[Proposal, GateOutcome | None]:
        """Apply per-account risk-budget sizing or reject malformed sizing.

        DEBT-068(a): ``RiskPolicy.sizing_mode='risk_budget'`` replaces the
        strategy-produced fixed-notional quantity with
        ``equity * risk_budget_pct / stop_distance`` before downstream gates
        that consume ``proposal.quantity``. Account equity comes from the
        trader balance snapshot for the account quote currency, falling back
        only to an explicit ``CapitalPolicy.sizing_balance``.
        """
        if sub_account is None or sub_account.risk_policy.sizing_mode != "risk_budget":
            return proposal, None

        quote_currency = sub_account.capital_policy.quote_currency
        balances: dict[str, Decimal] = {}
        try:
            balances = await trader.get_balances()
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            logger.warning(
                "Risk-budget balance lookup failed for %s: %s",
                sub_account.id,
                exc,
            )

        account_equity = balances.get(quote_currency)
        if account_equity is None:
            account_equity = sub_account.capital_policy.sizing_balance

        sized = compute_risk_budget_size(
            account_equity=account_equity,
            entry_price=proposal.entry_price,
            stop_loss_price=proposal.stop_loss,
            side=proposal.signal,
            policy=sub_account.risk_policy,
        )
        if isinstance(sized, RiskSizingRejection):
            reason = f"risk_sizing: {sized.message}"
            details: dict[str, Any] = {
                **_proposal_summary(proposal),
                "reason": reason,
                "gate_reason": GateReason.RISK_SIZING.value,
                "risk_sizing_reason": sized.reason,
                "sub_account_id": sub_account.id,
                "quote_currency": quote_currency,
                "account_equity": (
                    str(account_equity) if account_equity is not None else None
                ),
                "sizing_mode": sub_account.risk_policy.sizing_mode,
            }
            if sized.details is not None:
                details.update(sized.details)
            rejected_record = record.reject(
                ProposalFinalState.GATE_REJECTED_RISK_SIZING, reason
            )
            return proposal, GateOutcome(
                GateDecision.REJECTED,
                reason,
                [
                    GateActivityEvent(
                        ActivityEventType.PROPOSAL_REJECTED,
                        f"Risk-sizing rejected {proposal.symbol} {proposal.signal}",
                        details,
                        cycle_id,
                    )
                ],
                rejected_record,
            )

        return proposal.model_copy(update={"quantity": sized}), None

    async def _execute(
        self,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
        trader: Trader,
        exchange: BaseExchange | None = None,
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
        rejection = await self._stale_quote_gate(
            proposal, cycle_id, result, exchange or self.exchange
        )
        if rejection is not None:
            return

        position = _proposal_to_position(proposal)
        try:
            trade = await trader.open_position(position)
        except Exception as e:
            # proposal-funnel-audit §1 State 6 (terminal ``open_errored``):
            # exchange / trader raised on the fill; the record stays in
            # ``proposal_opened`` per spec §1 State 6 and we promote it
            # to the explicit ``open_errored`` terminal so the funnel
            # surfaces fill failures distinctly from the silent "opened
            # but no fill" case the dashboard previously had to fuzzy-
            # join.
            try:
                existing = self.proposal_history.load(proposal.proposal_id)
                updated = existing.mark(ProposalFinalState.OPEN_ERRORED)
                self.proposal_history.save(updated)
            except Exception:  # pragma: no cover - defensive
                pass
            self.activity_log.append(
                ActivityEventType.POSITION_OPEN_ERRORED,
                f"Failed to open {proposal.symbol}: {e}",
                details={
                    "proposal_id": proposal.proposal_id,
                    "record_id": proposal.proposal_id,
                    "sub_account_id": proposal.sub_account_id,
                    "symbol": proposal.symbol,
                    "signal": proposal.signal,
                    "technique_name": proposal.technique_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                cycle_id=cycle_id,
            )
            result.errors.append(
                EngineError(
                    category=ErrorCategory.POSITION_OPEN,
                    symbol=proposal.symbol,
                    detail=str(e),
                    exception=e,
                )
            )
            return

        # Link the trade to its proposal record now; realized P&L is
        # filled in by ``_monitor`` once the trade closes.
        self.proposal_history.attach_trade(proposal.proposal_id, trade_id=trade.id)
        # proposal-funnel-audit §1 State 6: fill confirmed; promote
        # the record to ``trade_opened``. ``attach_trade`` already
        # persisted the trade-id link; this is a second small write
        # (load -> model_copy -> save) per the spec's "rewrite on each
        # transition" contract. ``ProposalHistory.save`` is atomic so a
        # crash between the two writes still leaves a coherent record.
        try:
            existing = self.proposal_history.load(proposal.proposal_id)
            updated = existing.mark(ProposalFinalState.TRADE_OPENED)
            self.proposal_history.save(updated)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(
                "Failed to promote proposal record %s to trade_opened: %s",
                proposal.proposal_id,
                e,
            )
        self._strategy_lookup_cache = None
        result.positions_opened += 1
        self.activity_log.append(
            ActivityEventType.POSITION_OPENED,
            f"Opened {proposal.symbol} {proposal.signal} qty={trade.entry_quantity}",
            details={
                "proposal_id": proposal.proposal_id,
                # proposal-funnel-audit §1 State 5: record_id join key.
                "record_id": proposal.proposal_id,
                "sub_account_id": proposal.sub_account_id,
                "technique_name": proposal.technique_name,
                "trade_id": trade.id,
                "symbol": proposal.symbol,
                "side": proposal.signal,
                "signal": proposal.signal,
                "entry_price": str(proposal.entry_price),
                "quantity": str(trade.entry_quantity),
                "leverage": proposal.leverage,
            },
            cycle_id=cycle_id,
        )

    @staticmethod
    def _open_stop_risk_sum(trades: list[TradeHistory]) -> Decimal:
        """Sum worst-case open stop-risk across trades.

        cross-account-risk-policy: ``sum(abs(entry - stop) * qty)`` over
        open positions — the total loss if every open stop fired at once.
        Factored out so :meth:`_account_aggregate_cap_gate` (per-account
        ``max_open_stop_risk`` cap) and :meth:`_account_kill_switch_gate`
        (per-account ``open_stop_risk_limit_pct`` kill switch) compute the
        identical numerator and cannot drift. Trades with no ``stop_loss``
        contribute zero.
        """
        return sum(
            (
                abs(trade.entry_price - trade.stop_loss) * trade.entry_quantity
                for trade in trades
                if trade.stop_loss is not None
            ),
            start=Decimal("0"),
        )

    async def _account_equity(
        self,
        sub_account: SubAccount,
        trader: Trader,
    ) -> Decimal | None:
        """Resolve current quote-currency equity for a sub-account.

        cross-account-risk-policy kill switches and risk-budget sizing
        denominate their limits in account equity. Sourced exactly like
        :meth:`_risk_budget_sizing_gate`: live ``trader.get_balances()``
        for the account quote currency, falling back to an explicit
        ``CapitalPolicy.sizing_balance`` only when the live balance is
        unavailable. Returns ``None`` when neither is available — callers
        treat that as "skip the gate" (fail-open: these are safety
        throttles, not preconditions).
        """
        quote_currency = sub_account.capital_policy.quote_currency
        balances: dict[str, Decimal] = {}
        try:
            balances = await trader.get_balances()
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            logger.warning(
                "Kill-switch balance lookup failed for %s: %s",
                sub_account.id,
                exc,
            )
        equity = balances.get(quote_currency)
        if equity is None:
            equity = sub_account.capital_policy.sizing_balance
        return equity

    def _open_unrealized_pnl(self, trades: list[TradeHistory]) -> Decimal:
        """Sum open unrealized PnL using the cached mark price per symbol.

        cross-account-risk-policy: mirrors
        :meth:`PortfolioTracker.calculate_unrealized_pnl` — reuses
        :func:`pnl_for_trade` against ``entry_quantity`` (already levered).
        Marks come from the SYNCHRONOUS mark-price cache
        (:meth:`_get_cached_mark_price`); no ``await exchange.get_ticker``
        on the gate hot path. A position whose symbol has no fresh mark is
        EXCLUDED from the sum (treated as zero contribution), matching
        ``calculate_unrealized_pnl``'s defensive choice. This makes the
        open-drawdown kill switch conservative-toward-not-blocking on stale
        data.
        """
        total = Decimal("0")
        for trade in trades:
            mark = self._get_cached_mark_price(trade.symbol)
            if mark is None:
                continue
            total += pnl_for_trade(
                entry=trade.entry_price,
                exit=mark,
                qty=trade.entry_quantity,
                side=trade.side,
            )
        return total

    @staticmethod
    def _utc_midnight_today() -> datetime:
        """UTC midnight (00:00:00) of the current day.

        cross-account-risk-policy §"Hysteresis and Reset Semantics" /
        DEBT-068(c-2). The daily-loss window opens at UTC midnight and
        auto-releases at the next rollover. Computed fresh from
        :func:`now_utc` on EVERY gate invocation (never cached across
        cycles) so the window advances with wall-clock time and the
        limit releases automatically once ``exit_time`` falls into the
        prior day.
        """
        now = now_utc()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    def _realized_pnl_today(self, trader: Trader, sub_account_id: str) -> Decimal:
        """Sum realized PnL on this sub-account since UTC midnight today.

        cross-account-risk-policy §"Kill Switches" / DEBT-068(c-2). The
        daily-loss state is RECONSTRUCTED from persisted trade history
        every cycle — there is no separate state file. Because today's
        closed losing trades remain on disk, an engine restart recomputes
        the identical figure and cannot be used to escape the limit
        (spec §"Hysteresis and Reset Semantics": "Engine restart does
        NOT clear daily-loss state").

        Aggregates the signed, net-of-fees :attr:`TradeHistory.pnl` field
        over the account's CLOSED trades whose ``exit_time`` is at or
        after :meth:`_utc_midnight_today`. Trades still open
        (``exit_time is None``) are excluded. The persisted ``exit_time``
        is coerced with :func:`ensure_utc` before the boundary comparison
        (same tz-defense as :meth:`_stale_position_block_gate`), so a
        legacy naive timestamp does not crash the gate.

        We deliberately do NOT use
        :meth:`TradeHistoryTracker.get_trades_by_date_range` — it filters
        on ``entry_time``, whereas the daily-loss window is defined on the
        EXIT (realization) timestamp. Closed trades are sourced via
        ``trader._trade_tracker.load_trades(self.mode)`` (the per-account,
        mode-scoped tracker the engine already owns) and filtered to this
        ``sub_account_id`` defensively, mirroring the per-account
        ``get_open_trades`` filter in :meth:`_account_kill_switch_gate`.
        """
        tracker = getattr(trader, "_trade_tracker", None)
        if tracker is None:
            return Decimal("0")
        midnight = self._utc_midnight_today()
        total = Decimal("0")
        for trade in tracker.load_trades(self.mode):
            if trade.sub_account_id != sub_account_id:
                continue
            if trade.status != "closed" or trade.exit_time is None:
                continue
            if ensure_utc(trade.exit_time) < midnight:
                continue
            if trade.pnl is not None:
                total += trade.pnl
        return total

    async def _account_daily_loss_check(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount,
        trader: Trader,
        equity: Decimal,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Per-account realized daily-loss kill switch.

        cross-account-risk-policy §"Kill Switches" / DEBT-068(c-2). Trips
        when realized PnL since UTC midnight is worse than
        ``-daily_loss_limit_pct * starting_equity_today``. Inert when
        ``daily_loss_limit_pct is None``.

        ``starting_equity_today`` is RECONSTRUCTED (lead decision, no
        state file): ``current_quote_balance - realized_pnl_today``, where
        ``current_quote_balance`` is the ``equity`` already resolved via
        :meth:`_account_equity` by the caller. Because both the balance
        and ``realized_pnl_today`` survive a restart on disk, the
        baseline — and therefore the trip decision — is identical after a
        restart.

        Returns the :meth:`_kill_switch_outcome` for a breach (live
        hard-block / paper advisory) or ``None`` when not configured or
        within the limit. The caller invokes this BEFORE the c-1
        drawdown / stop-risk checks so the daily-loss reason wins when a
        proposal would breach both (spec §"Runtime Behavior" order).
        """
        daily_loss_limit = sub_account.risk_policy.daily_loss_limit_pct
        if daily_loss_limit is None:
            return None

        realized_today = self._realized_pnl_today(trader, sub_account.id)
        # Reconstruct start-of-day equity from realized flows alone — no
        # state file, so it survives restart (a restart can't escape the
        # limit). Exact when a trade opens and closes the same UTC day.
        # A trade straddling midnight mis-attributes a single fee (entry
        # or exit) to the wrong day: sub-1-USDT per cross-midnight trade
        # at the project's notional scale, and Case B (opened yesterday,
        # closed today) leans the switch to trip slightly *earlier* — the
        # safe direction for a loss-limit control. Accepted approximation.
        starting_equity_today = equity - realized_today
        threshold = -(daily_loss_limit * starting_equity_today)
        if realized_today >= threshold:
            return None

        reason = (
            f"daily_loss_kill_switch: realized_today {realized_today:.2f} "
            f"< -({daily_loss_limit} * {starting_equity_today}) = {threshold:.2f}"
        )
        details: dict[str, Any] = {
            **_proposal_summary(proposal),
            "reason": reason,
            "gate_reason": GateReason.DAILY_LOSS_KILL_SWITCH.value,
            "sub_account_id": sub_account.id,
            "realized_pnl_today": str(realized_today),
            "current_quote_balance": str(equity),
            "starting_equity_today": str(starting_equity_today),
            "daily_loss_limit_pct": str(daily_loss_limit),
            "daily_loss_threshold": str(threshold),
            "mode": self.mode,
        }
        return self._kill_switch_outcome(
            proposal=proposal,
            record=record,
            cycle_id=cycle_id,
            reason=reason,
            details=details,
            final_state=(ProposalFinalState.GATE_REJECTED_DAILY_LOSS_KILL_SWITCH),
            advisory_label="Daily-loss kill-switch",
        )

    async def _account_kill_switch_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        trader: Trader,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Per-account kill switches — daily-loss, then open-drawdown, then stop-risk.

        cross-account-risk-policy §"Kill Switches". Three per-account
        checks, evaluated in spec §"Runtime Behavior" order; the FIRST
        breach wins so the rejection event names a single cause:

        0. **Realized daily-loss** (``daily_loss_limit_pct``, STATEFUL,
           DEBT-068(c-2)): trip when realized PnL since UTC midnight is
           worse than ``-pct * starting_equity_today``, where
           ``starting_equity_today`` is reconstructed as
           ``current_quote_balance - realized_pnl_today`` (no state file;
           survives restart). Delegated to :meth:`_account_daily_loss_check`.
           Runs AHEAD of the c-1 drawdown / stop-risk checks so a proposal
           breaching both is rejected with the daily-loss reason.
        1. **Open-drawdown** (``open_unrealized_drawdown_limit_pct``,
           stateless, DEBT-068(c-1)): trip when current open unrealized
           PnL is worse than ``-pct * equity``. Unrealized PnL is summed
           via :meth:`_open_unrealized_pnl` (cached marks; stale-symbol
           positions excluded).
        2. **Open-stop-risk** (``open_stop_risk_limit_pct``, stateless,
           DEBT-068(c-1)): trip when the summed ``abs(entry - stop) * qty``
           over open positions exceeds ``pct * equity`` (shared numerator
           via :meth:`_open_stop_risk_sum`).

        Each ``_pct`` field set to ``None`` makes its check inert. When
        ALL three are ``None`` the gate is a no-op. Equity comes from
        :meth:`_account_equity`; if unavailable the gate is skipped
        (returns ``None``, emits no event) — fail-open per the lead
        decision, since these are safety throttles rather than
        preconditions.

        Paper-vs-live: live mode hard-blocks into the matching kill-switch
        terminal; paper mode is advisory-with-event and lets the proposal
        proceed. DEBT-068(g): both branches emit the dedicated
        :attr:`ActivityEventType.RISK_KILL_SWITCH_TRIPPED` event (paper
        carries ``details.advisory=True``) via :meth:`_kill_switch_outcome`
        so dashboards can chart trip windows over time.
        """
        if sub_account is None:
            return None
        policy = sub_account.risk_policy
        daily_loss_limit = policy.daily_loss_limit_pct
        drawdown_limit = policy.open_unrealized_drawdown_limit_pct
        stop_risk_limit = policy.open_stop_risk_limit_pct
        if (
            daily_loss_limit is None
            and drawdown_limit is None
            and stop_risk_limit is None
        ):
            return None

        equity = await self._account_equity(sub_account, trader)
        if equity is None:
            # Fail-open: no equity reference means we cannot evaluate a
            # relative limit. Safety throttles must not block on a stale
            # balance snapshot.
            return None

        # Check 0: realized daily-loss (DEBT-068(c-2)) — runs first per
        # spec §"Runtime Behavior" so the daily-loss reason wins over a
        # simultaneous open-drawdown / stop-risk breach.
        daily_loss_outcome = await self._account_daily_loss_check(
            proposal,
            record,
            sub_account,
            trader,
            equity,
            cycle_id,
        )
        if daily_loss_outcome is not None:
            return daily_loss_outcome

        open_trades = [
            trade
            for trade in trader.get_open_trades()
            if trade.sub_account_id == sub_account.id
        ]

        # Check 1: open unrealized drawdown.
        if drawdown_limit is not None:
            unrealized = self._open_unrealized_pnl(open_trades)
            threshold = -(drawdown_limit * equity)
            if unrealized < threshold:
                reason = (
                    f"open_drawdown_kill_switch: unrealized {unrealized:.2f} "
                    f"< -({drawdown_limit} * {equity}) = {threshold:.2f}"
                )
                details: dict[str, Any] = {
                    **_proposal_summary(proposal),
                    "reason": reason,
                    "gate_reason": GateReason.OPEN_DRAWDOWN_KILL_SWITCH.value,
                    "sub_account_id": sub_account.id,
                    "unrealized_pnl_open": str(unrealized),
                    "equity": str(equity),
                    "open_unrealized_drawdown_limit_pct": str(drawdown_limit),
                    "drawdown_threshold": str(threshold),
                    "mode": self.mode,
                }
                return self._kill_switch_outcome(
                    proposal=proposal,
                    record=record,
                    cycle_id=cycle_id,
                    reason=reason,
                    details=details,
                    final_state=(
                        ProposalFinalState.GATE_REJECTED_OPEN_DRAWDOWN_KILL_SWITCH
                    ),
                    advisory_label="Open-drawdown kill-switch",
                )

        # Check 2: open stop-risk.
        if stop_risk_limit is not None:
            open_stop_risk = self._open_stop_risk_sum(open_trades)
            threshold = stop_risk_limit * equity
            if open_stop_risk > threshold:
                reason = (
                    f"open_stop_risk_kill_switch: open_stop_risk "
                    f"{open_stop_risk:.2f} > ({stop_risk_limit} * {equity}) "
                    f"= {threshold:.2f}"
                )
                details = {
                    **_proposal_summary(proposal),
                    "reason": reason,
                    "gate_reason": GateReason.OPEN_STOP_RISK_KILL_SWITCH.value,
                    "sub_account_id": sub_account.id,
                    "open_stop_risk": str(open_stop_risk),
                    "equity": str(equity),
                    "open_stop_risk_limit_pct": str(stop_risk_limit),
                    "stop_risk_threshold": str(threshold),
                    "mode": self.mode,
                }
                return self._kill_switch_outcome(
                    proposal=proposal,
                    record=record,
                    cycle_id=cycle_id,
                    reason=reason,
                    details=details,
                    final_state=(
                        ProposalFinalState.GATE_REJECTED_OPEN_STOP_RISK_KILL_SWITCH
                    ),
                    advisory_label="Open-stop-risk kill-switch",
                )

        return None

    async def _global_kill_switch_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Global (portfolio) kill switches — daily-loss, then open-drawdown.

        cross-account-risk-policy §"Global Kill Switches". Two
        cross-account checks, evaluated in spec §"Runtime Behavior" order;
        the daily-loss check runs FIRST so its reason wins over a
        simultaneous portfolio-drawdown breach:

        0. **Portfolio realized daily-loss** (``portfolio_daily_loss_limit_pct``,
           STATEFUL, DEBT-068(c-2)): trip when
           ``portfolio_realized_pnl_today`` is worse than
           ``-pct * portfolio_starting_equity_today``, where both terms are
           summed per-account — ``portfolio_realized_pnl_today`` = Σ
           :meth:`_realized_pnl_today` and
           ``portfolio_starting_equity_today`` = Σ
           ``(current_quote_balance - realized_pnl_today)``. Delegated to
           :meth:`_portfolio_daily_loss_check`.
        1. **Portfolio open-drawdown** (``portfolio_unrealized_drawdown_limit_pct``,
           stateless, DEBT-068(c-1)): trip when cross-account open
           unrealized PnL is worse than ``-pct * portfolio_equity``.

        Inert paths return ``None``: no registry, ``GlobalRiskPolicy``
        not ``enabled``, or BOTH limit fields unset (mirrors
        :meth:`_global_aggregate_cap_gate`'s ``policy.enabled``
        short-circuit). Portfolio equity is summed via
        :meth:`_account_equity` per enabled sub-account; if NO sub-account
        contributes a usable equity figure the gate is skipped (fail-open),
        matching the per-account gate. Open trades come from
        :meth:`_open_trades_for_correlation` (deduped cross-account) and
        the unrealized sum reuses :meth:`_open_unrealized_pnl` (cached
        marks; stale-symbol positions excluded).

        v1 assumes a SINGLE common quote currency (USDT). The first active
        sub-account's quote currency is taken as the reference; any
        sub-account whose quote currency differs is skipped from the
        portfolio sums with a one-line warning (known v1 limitation —
        cross-currency netting is out of scope for this slice).

        Paper-vs-live mirrors :meth:`_global_aggregate_cap_gate`: live
        hard-blocks into the matching portfolio terminal; paper is
        advisory-with-event and continues.
        """
        if self.sub_account_registry is None:
            return None
        policy = self.sub_account_registry.global_risk_policy()
        if not policy.enabled:
            return None
        daily_loss_limit = policy.portfolio_daily_loss_limit_pct
        drawdown_limit = policy.portfolio_unrealized_drawdown_limit_pct
        if daily_loss_limit is None and drawdown_limit is None:
            return None

        # Single pass over enabled sub-accounts: accumulate portfolio
        # equity (drawdown denominator) and the daily-loss terms. v1
        # single-quote-currency assumption — skip mismatches.
        reference_quote: str | None = None
        portfolio_equity = Decimal("0")
        portfolio_realized_today = Decimal("0")
        portfolio_starting_equity_today = Decimal("0")
        any_equity = False
        for sub in self.sub_account_registry.list_active():
            trader = self.sub_account_registry.get_trader(sub.id)
            equity = await self._account_equity(sub, trader)
            if equity is None:
                continue
            sub_quote = sub.capital_policy.quote_currency
            if reference_quote is None:
                reference_quote = sub_quote
            elif sub_quote != reference_quote:
                # v1 limitation: no cross-currency netting. Skip this
                # account from the portfolio sums rather than mixing units.
                logger.warning(
                    "Global kill switch: skipping sub-account %s "
                    "(quote %s != portfolio reference %s); v1 assumes a "
                    "single common quote currency",
                    sub.id,
                    sub_quote,
                    reference_quote,
                )
                continue
            portfolio_equity += equity
            any_equity = True
            if daily_loss_limit is not None:
                realized_today = self._realized_pnl_today(trader, sub.id)
                portfolio_realized_today += realized_today
                portfolio_starting_equity_today += equity - realized_today
        if not any_equity:
            # Fail-open: no usable portfolio equity reference.
            return None

        # Check 0: portfolio realized daily-loss (DEBT-068(c-2)) — first.
        if daily_loss_limit is not None:
            daily_loss_outcome = self._portfolio_daily_loss_check(
                proposal=proposal,
                record=record,
                cycle_id=cycle_id,
                daily_loss_limit=daily_loss_limit,
                portfolio_realized_today=portfolio_realized_today,
                portfolio_starting_equity_today=portfolio_starting_equity_today,
            )
            if daily_loss_outcome is not None:
                return daily_loss_outcome

        if drawdown_limit is None:
            return None

        open_trades = self._open_trades_for_correlation()
        portfolio_unrealized = self._open_unrealized_pnl(open_trades)
        threshold = -(drawdown_limit * portfolio_equity)
        if portfolio_unrealized >= threshold:
            return None

        reason = (
            f"portfolio_kill_switch: portfolio_unrealized "
            f"{portfolio_unrealized:.2f} < -({drawdown_limit} * "
            f"{portfolio_equity}) = {threshold:.2f}"
        )
        details: dict[str, Any] = {
            **_proposal_summary(proposal),
            "reason": reason,
            "gate_reason": GateReason.PORTFOLIO_KILL_SWITCH.value,
            "portfolio_unrealized_pnl": str(portfolio_unrealized),
            "portfolio_equity": str(portfolio_equity),
            "portfolio_unrealized_drawdown_limit_pct": str(drawdown_limit),
            "portfolio_drawdown_threshold": str(threshold),
            "mode": self.mode,
        }
        # DEBT-068(h): a PORTFOLIO trip is not owned by the proposer that
        # happened to trip it. Drop the proposer ``sub_account_id`` that
        # ``_proposal_summary`` injected so the event honestly carries no
        # owning account. This keeps the safety-score dedup correct (one
        # global condition counts once per cycle, not once per proposer)
        # and stops the f-1 per-account panel attributing the trip to a
        # proposer. The triggering proposal stays joinable via ``proposal_id``.
        details.pop("sub_account_id", None)
        return self._kill_switch_outcome(
            proposal=proposal,
            record=record,
            cycle_id=cycle_id,
            reason=reason,
            details=details,
            final_state=ProposalFinalState.GATE_REJECTED_PORTFOLIO_KILL_SWITCH,
            advisory_label="Portfolio kill-switch",
        )

    def _portfolio_daily_loss_check(
        self,
        *,
        proposal: Proposal,
        record: ProposalRecord,
        cycle_id: str,
        daily_loss_limit: Decimal,
        portfolio_realized_today: Decimal,
        portfolio_starting_equity_today: Decimal,
    ) -> GateOutcome | None:
        """Portfolio realized daily-loss kill switch.

        cross-account-risk-policy §"Global Kill Switches" / DEBT-068(c-2).
        Trips when ``portfolio_realized_pnl_today`` is worse than
        ``-portfolio_daily_loss_limit_pct * portfolio_starting_equity_today``.
        Both sums are precomputed by :meth:`_global_kill_switch_gate` over
        the enabled sub-accounts sharing the common quote currency. A trip
        blocks new entries on every sub-account.

        Returns the :meth:`_kill_switch_outcome` for a breach or ``None``
        when within the limit. Mirrors :meth:`_account_daily_loss_check`
        with portfolio-level terms.
        """
        threshold = -(daily_loss_limit * portfolio_starting_equity_today)
        if portfolio_realized_today >= threshold:
            return None

        reason = (
            f"portfolio_daily_loss_kill_switch: portfolio_realized_today "
            f"{portfolio_realized_today:.2f} < -({daily_loss_limit} * "
            f"{portfolio_starting_equity_today}) = {threshold:.2f}"
        )
        details: dict[str, Any] = {
            **_proposal_summary(proposal),
            "reason": reason,
            "gate_reason": GateReason.PORTFOLIO_DAILY_LOSS_KILL_SWITCH.value,
            "portfolio_realized_pnl_today": str(portfolio_realized_today),
            "portfolio_starting_equity_today": str(portfolio_starting_equity_today),
            "portfolio_daily_loss_limit_pct": str(daily_loss_limit),
            "portfolio_daily_loss_threshold": str(threshold),
            "mode": self.mode,
        }
        # DEBT-068(h): see _global_kill_switch_gate — a PORTFOLIO trip is
        # not owned by the proposer that tripped it. Drop the proposer
        # ``sub_account_id`` so the event carries no owning account.
        details.pop("sub_account_id", None)
        return self._kill_switch_outcome(
            proposal=proposal,
            record=record,
            cycle_id=cycle_id,
            reason=reason,
            details=details,
            final_state=(
                ProposalFinalState.GATE_REJECTED_PORTFOLIO_DAILY_LOSS_KILL_SWITCH
            ),
            advisory_label="Portfolio daily-loss kill-switch",
        )

    def _reject_operator_freeze(
        self,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
        events: list[GateActivityEvent],
    ) -> None:
        """Reject one proposal under the operator manual freeze.

        cross-account-risk-policy DEBT-068(d), spec §"Operator Manual
        Freeze" + §"Runtime Behavior" gate 1. The earliest reject — runs
        ahead of the score gate, so we persist a rejected
        :class:`ProposalRecord` directly (carrying
        :attr:`ProposalFinalState.GATE_REJECTED_OPERATOR_FREEZE`) without
        first running the score decision.

        Hard-blocks in BOTH paper and live mode — the operator pulled the
        lever, so unlike the cap / kill-switch gates there is no
        paper-advisory carve-out. Emits the dedicated
        :attr:`ActivityEventType.OPERATOR_FREEZE_ENGAGED` so dashboards can
        chart the freeze window over time; the per-proposal rejection
        detail uses ``reason="operator_freeze"``.
        """
        result.proposals_rejected += 1
        details = {
            "proposal_id": proposal.proposal_id,
            "symbol": proposal.symbol,
            "reason": "operator_freeze",
        }
        rejected_record = ProposalRecord(
            proposal=proposal,
            sub_account_id=proposal.sub_account_id,
            decision=ProposalDecision.REJECTED,
            decision_at=now_utc(),
            actor=self.config.actor,
            rejection_reason="operator_freeze",
            final_state=ProposalFinalState.GATE_REJECTED_OPERATOR_FREEZE,
        )
        self.proposal_history.save(rejected_record)

        freeze_event = GateActivityEvent(
            ActivityEventType.OPERATOR_FREEZE_ENGAGED,
            f"Operator freeze rejected {proposal.symbol} {proposal.signal}",
            details,
            cycle_id,
        )
        for event in events + [freeze_event]:
            self.activity_log.append(
                event.event_type,
                event.message,
                details=event.details,
                cycle_id=event.cycle_id,
            )

    def _kill_switch_outcome(
        self,
        *,
        proposal: Proposal,
        record: ProposalRecord,
        cycle_id: str,
        reason: str,
        details: dict[str, Any],
        final_state: ProposalFinalState,
        advisory_label: str,
    ) -> GateOutcome | None:
        """Build the paper-advisory / live-hard-block outcome for a kill switch.

        Shared tail for :meth:`_account_kill_switch_gate` /
        :meth:`_global_kill_switch_gate`. Paper mode emits a
        ``RISK_KILL_SWITCH_TRIPPED`` advisory (``details.advisory=True``)
        and returns ``None`` so the proposal proceeds; live mode returns a
        rejecting :class:`GateOutcome` carrying ``final_state``.

        DEBT-068(g): kill switches are persistent portfolio-condition
        gates, so BOTH the paper advisory AND the live hard-block emit the
        dedicated :attr:`ActivityEventType.RISK_KILL_SWITCH_TRIPPED` event
        (vs. the old ``PROPOSAL_REJECTED`` reuse) so dashboards can chart
        trip windows over time. Only the EMITTED event type changes — the
        live branch's rejection ``final_state`` stays ``final_state`` (the
        ``GATE_REJECTED_*_KILL_SWITCH`` terminal) so the proposal funnel,
        which keys on ``final_state``, is unchanged.
        """
        if self.mode == "paper":
            self.activity_log.append(
                ActivityEventType.RISK_KILL_SWITCH_TRIPPED,
                f"{advisory_label} advisory (paper) for {proposal.symbol}",
                details={**details, "advisory": True},
                cycle_id=cycle_id,
            )
            return None

        rejected_record = record.reject(final_state, reason)
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.RISK_KILL_SWITCH_TRIPPED,
                    f"{advisory_label} rejected {proposal.symbol} {proposal.signal}",
                    details,
                    cycle_id,
                )
            ],
            rejected_record,
        )

    async def _total_cap_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        trader: Trader,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Reject when the sub-account total open-position cap is reached.

        CAH-05: extracted verbatim from the inline Phase 12.1 cross-cycle
        cap block in :meth:`_handle_proposal` to match the 13 sibling
        ``_*_gate`` methods. Returns ``None`` when no total cap is
        configured or the account is below it; returns a rejecting
        :class:`GateOutcome` (carrying only this gate's own event, like the
        siblings) when ``len(open_trades) >= max_open_positions_total``.
        Runs BEFORE :meth:`_symbol_cap_gate` (order preserved).
        """
        policy = self._runtime_policy_for(sub_account)
        open_trades = trader.get_open_trades()
        total_cap = policy.max_open_positions_total
        if total_cap is None or len(open_trades) < total_cap:
            return None

        reason = (
            f"total open-position cap {total_cap} reached on "
            f"sub-account {proposal.sub_account_id} ({len(open_trades)} open)"
        )
        # proposal-funnel-audit §1 State 4: total-cap rejection.
        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_TOTAL_CAP, reason
        )
        blocking_trades = await self._build_cap_blocker_payload(
            open_trades=open_trades,
            cap=total_cap,
            reason="total_cap",
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_REJECTED,
                    f"Total-cap rejected {proposal.symbol} {proposal.signal}",
                    {
                        **_proposal_summary(proposal),
                        "reason": reason,
                        "gate_reason": GateReason.TOTAL_CAP.value,
                        "open_count": len(open_trades),
                        "cap": total_cap,
                        "blocking_trades": blocking_trades,
                    },
                    cycle_id,
                )
            ],
            rejected_record,
        )

    async def _symbol_cap_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        trader: Trader,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Reject when the per-symbol open-position cap is reached.

        CAH-05: extracted verbatim from the inline Phase 12.1 cross-cycle
        cap block in :meth:`_handle_proposal` to match the 13 sibling
        ``_*_gate`` methods. Returns ``None`` when the symbol is below the
        per-symbol cap; returns a rejecting :class:`GateOutcome` (carrying
        only this gate's own event, like the siblings) when
        ``existing >= max_open_positions_per_symbol``. Runs AFTER
        :meth:`_total_cap_gate` (order preserved).
        """
        policy = self._runtime_policy_for(sub_account)
        cap = policy.max_open_positions_per_symbol
        open_trades = trader.get_open_trades()
        existing = sum(1 for trade in open_trades if trade.symbol == proposal.symbol)
        if existing < cap:
            return None

        reason = (
            f"symbol {proposal.symbol} cap {cap} reached on "
            f"sub-account {proposal.sub_account_id} ({existing} open)"
        )
        # proposal-funnel-audit §1 State 4: symbol-cap rejection.
        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_SYMBOL_CAP, reason
        )
        # Filter to the per-symbol blockers only — these are the trades
        # that actually count against the per-symbol cap; the dashboard's
        # diagnostic panel must not list trades on other symbols as the
        # blocker.
        symbol_blockers = [
            trade for trade in open_trades if trade.symbol == proposal.symbol
        ]
        blocking_trades = await self._build_cap_blocker_payload(
            open_trades=symbol_blockers,
            cap=cap,
            reason="symbol_cap",
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_REJECTED,
                    f"Cap-rejected {proposal.symbol} {proposal.signal}",
                    {
                        **_proposal_summary(proposal),
                        "reason": reason,
                        "gate_reason": GateReason.SYMBOL_CAP.value,
                        "open_count": existing,
                        "cap": cap,
                        "blocking_trades": blocking_trades,
                    },
                    cycle_id,
                )
            ],
            rejected_record,
        )

    def _account_aggregate_cap_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        trader: Trader,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Reject when the per-account aggregate caps would be breached.

        cross-account-risk-policy §"Per-Account Caps". Sums the open
        notional and worst-case stop-risk on this sub-account's open
        trades and compares the post-fill total against
        ``RiskPolicy.max_gross_notional`` /
        ``RiskPolicy.max_open_stop_risk``. Returns ``None`` when neither
        cap is configured or both caps fit; returns a populated
        :class:`GateOutcome` when either cap would be breached.

        Paper-vs-live (resolved 2026-05-13): caps hard-block in live;
        in paper they are advisory-with-event. ``self.mode`` selects the
        branch — paper mode lets the proposal continue (returns
        ``None``) but appends an activity event so operators see the
        would-be rejection. DEBT-068(g): the paper advisory now emits the
        dedicated :attr:`ActivityEventType.RISK_CAP_ADVISORY` event
        (``details.advisory=True`` kept as a back-compat discriminator).
        ``RISK_CAP_ADVISORY`` is paper-only by name: live mode produces a
        rejection record with ``gate_rejected_account_aggregate_cap`` and
        keeps the ``PROPOSAL_REJECTED`` accompanying event.
        """
        if sub_account is None:
            return None
        policy = sub_account.risk_policy
        if policy.max_gross_notional is None and policy.max_open_stop_risk is None:
            return None

        open_trades = [
            trade
            for trade in trader.get_open_trades()
            if trade.sub_account_id == sub_account.id
        ]

        gross_notional = sum(
            (trade.entry_price * trade.entry_quantity for trade in open_trades),
            start=Decimal("0"),
        )
        open_stop_risk = self._open_stop_risk_sum(open_trades)

        # The new proposal contributes only when sized. Sizing happens
        # downstream of this gate so we use the proposal's declared
        # notional / stop-risk as an estimate; the proposal-runtime
        # already populates these fields prior to the gate stack.
        new_notional = proposal.entry_price * Decimal(str(proposal.quantity))
        new_stop_risk = (
            abs(proposal.entry_price - proposal.stop_loss)
            * Decimal(str(proposal.quantity))
            if proposal.stop_loss is not None
            else Decimal("0")
        )

        notional_total = gross_notional + new_notional
        stop_risk_total = open_stop_risk + new_stop_risk

        breaches: list[str] = []
        if (
            policy.max_gross_notional is not None
            and notional_total > policy.max_gross_notional
        ):
            breaches.append(
                f"gross_notional {notional_total:.2f} > "
                f"max {policy.max_gross_notional}"
            )
        if (
            policy.max_open_stop_risk is not None
            and stop_risk_total > policy.max_open_stop_risk
        ):
            breaches.append(
                f"open_stop_risk {stop_risk_total:.2f} > "
                f"max {policy.max_open_stop_risk}"
            )
        if not breaches:
            return None

        reason = "account_aggregate_cap: " + "; ".join(breaches)
        details: dict[str, Any] = {
            **_proposal_summary(proposal),
            "reason": reason,
            "gate_reason": GateReason.ACCOUNT_AGGREGATE_CAP.value,
            "sub_account_id": sub_account.id,
            "gross_notional_total": str(notional_total),
            "open_stop_risk_total": str(stop_risk_total),
            "max_gross_notional": (
                str(policy.max_gross_notional)
                if policy.max_gross_notional is not None
                else None
            ),
            "max_open_stop_risk": (
                str(policy.max_open_stop_risk)
                if policy.max_open_stop_risk is not None
                else None
            ),
            "mode": self.mode,
        }

        if self.mode == "paper":
            # Advisory-only in paper: emit the event but let the
            # proposal proceed. The proposal record itself is NOT
            # downgraded to a rejection so the funnel still counts it
            # as ``proposal_opened`` — matches the spec's paper-first
            # "advisory-with-event" resolution.
            self.activity_log.append(
                ActivityEventType.RISK_CAP_ADVISORY,
                f"Aggregate-cap advisory (paper) for {proposal.symbol}",
                details={**details, "advisory": True},
                cycle_id=cycle_id,
            )
            return None

        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_ACCOUNT_AGGREGATE_CAP, reason
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_REJECTED,
                    (
                        f"Account aggregate-cap rejected "
                        f"{proposal.symbol} {proposal.signal}"
                    ),
                    details,
                    cycle_id,
                )
            ],
            rejected_record,
        )

    def _stale_position_block_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        trader: Trader,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Block new entries when a stale position is parked on the account.

        cross-account-risk-policy §"Stale-Position Age Caps" — the
        ``block_new_entries`` action. When the sub-account has an open
        trade whose age exceeds ``max_time_in_position_hours``, all
        new entries on this account are rejected until the stale trade
        closes. ``auto_close`` and ``alert_only`` actions are handled
        elsewhere (monitor loop / dashboard) and bypass this gate.

        Returns ``None`` when ``stale_position_action`` is not
        ``"block_new_entries"`` or when no stale trade exists. In paper
        mode the gate is advisory-with-event: same path as
        :meth:`_account_aggregate_cap_gate` — appends an
        :attr:`ActivityEventType.PROPOSAL_REJECTED` event with
        ``details.advisory=True`` as the discriminator but lets the
        proposal proceed. NOTE (DEBT-068(g)): this gate intentionally
        stays on ``PROPOSAL_REJECTED`` and is NOT migrated to
        ``RISK_CAP_ADVISORY`` — stale-position state already has its own
        dedicated ``STALE_POSITION_*`` event family (DEBT-068(e)) emitted
        from the monitor loop; the (g) cap-advisory migration is scoped to
        the aggregate-notional caps only.
        """
        if sub_account is None:
            return None
        policy = sub_account.risk_policy
        if (
            policy.stale_position_action != "block_new_entries"
            or policy.max_time_in_position_hours is None
        ):
            return None

        cap_hours = policy.max_time_in_position_hours
        now = now_utc()
        stale_trades = []
        for trade in trader.get_open_trades():
            if trade.sub_account_id != sub_account.id:
                continue
            # Defensive: other call sites (line ~2374 here, and
            # ``correlation_governor.py``) normalize ``entry_time`` via
            # ``ensure_utc`` before doing tz-aware arithmetic. Slice 1
            # missed this site; a naive datetime would crash with
            # ``TypeError: can't subtract offset-naive and offset-aware``.
            age_hours = (now - ensure_utc(trade.entry_time)).total_seconds() / 3600.0
            if age_hours > cap_hours:
                stale_trades.append((trade, age_hours))
        if not stale_trades:
            return None

        oldest_trade, oldest_age = max(stale_trades, key=lambda pair: pair[1])
        reason = (
            f"stale_position_block: trade {oldest_trade.id} on "
            f"{oldest_trade.symbol} is {oldest_age:.2f}h old "
            f"(> cap {cap_hours}h)"
        )
        details: dict[str, Any] = {
            **_proposal_summary(proposal),
            "reason": reason,
            "gate_reason": GateReason.STALE_POSITION_BLOCK.value,
            "sub_account_id": sub_account.id,
            "oldest_trade_id": oldest_trade.id,
            "oldest_trade_symbol": oldest_trade.symbol,
            "oldest_trade_age_hours": f"{oldest_age:.4f}",
            "max_time_in_position_hours": cap_hours,
            "mode": self.mode,
        }

        if self.mode == "paper":
            self.activity_log.append(
                ActivityEventType.PROPOSAL_REJECTED,
                f"Stale-position advisory (paper) for {proposal.symbol}",
                details={**details, "advisory": True},
                cycle_id=cycle_id,
            )
            return None

        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_STALE_POSITION_BLOCK, reason
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_REJECTED,
                    (
                        f"Stale-position-block rejected "
                        f"{proposal.symbol} {proposal.signal}"
                    ),
                    details,
                    cycle_id,
                )
            ],
            rejected_record,
        )

    def _global_aggregate_cap_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Reject when an opt-in global symbol/side cap would be breached.

        cross-account-risk-policy §"Global Symbol/Side Caps" /
        DEBT-068(b). Where :meth:`_account_aggregate_cap_gate` sums one
        sub-account's exposure, this gate aggregates across ALL active
        sub-accounts and compares the post-fill cross-account totals
        against the top-level :class:`GlobalRiskPolicy` caps:

        - ``max_open_positions_per_symbol_side``: count of cross-account
          open trades on ``(proposal.symbol, proposal.signal)``, plus 1
          for the new proposal.
        - ``max_gross_notional_per_symbol_side``: summed
          ``entry_price * entry_quantity`` on that ``(symbol, side)``,
          plus the new proposal's notional.
        - ``max_gross_notional_per_symbol``: same but across BOTH sides
          on ``proposal.symbol``.

        ``cap_resolution`` arbitrates a breach (DEBT-068(c)):
        ``first_come_first_serve`` always blocks the proposing account
        (v1 behaviour). ``lowest_priority_loses`` admits the proposal iff,
        for EVERY breached cap, the proposing account strictly outranks at
        least one OTHER existing holder on that cap's key (lower
        ``account_priority`` index == higher priority; unlisted == lowest).
        An admit overrides the raw breach (soft ceiling); the AND across
        caps is conservative (any cap that arbitrates to block blocks all).
        Empty ``account_priority`` or an unlisted proposer collapses to
        FCFS-equivalent (always block on breach).

        Inert paths return ``None``: no registry, ``enabled=False``, or
        all three cap fields unset. Paper mode is advisory-with-event
        (DEBT-068(g): emit a :attr:`ActivityEventType.RISK_CAP_ADVISORY`
        event with ``details.advisory=True`` and continue) exactly like
        :meth:`_account_aggregate_cap_gate`; live mode hard-blocks into
        :attr:`ProposalFinalState.GATE_REJECTED_GLOBAL_CAP` and keeps its
        ``PROPOSAL_REJECTED`` accompanying event.

        Ordering: the spec requires global caps run AFTER the per-account
        caps AND after the correlation governor. ``_correlation_gate``
        runs earlier in ``_handle_proposal`` (line ~1160, before the
        per-account gates), so wiring this gate after
        ``_stale_position_block_gate`` satisfies both constraints.
        """
        if self.sub_account_registry is None:
            return None
        policy = self.sub_account_registry.global_risk_policy()
        if not policy.enabled:
            return None
        if (
            policy.max_open_positions_per_symbol_side is None
            and policy.max_gross_notional_per_symbol_side is None
            and policy.max_gross_notional_per_symbol is None
        ):
            return None

        symbol = proposal.symbol
        side = proposal.signal

        # Cross-account open trades, deduped across active traders.
        open_trades = self._open_trades_for_correlation()
        symbol_side_trades = [
            trade
            for trade in open_trades
            if trade.symbol == symbol and trade.side == side
        ]
        symbol_trades = [trade for trade in open_trades if trade.symbol == symbol]

        # +1 for the new proposal on the matching (symbol, side).
        open_positions_total = len(symbol_side_trades) + 1

        new_notional = proposal.entry_price * Decimal(str(proposal.quantity))
        symbol_side_notional_total = (
            sum(
                (
                    trade.entry_price * trade.entry_quantity
                    for trade in symbol_side_trades
                ),
                start=Decimal("0"),
            )
            + new_notional
        )
        symbol_notional_total = (
            sum(
                (trade.entry_price * trade.entry_quantity for trade in symbol_trades),
                start=Decimal("0"),
            )
            + new_notional
        )

        # Each breached cap carries the trade list whose distinct
        # sub-account holders arbitrate it (DEBT-068(c)): the per-symbol-side
        # caps look at ``symbol_side_trades``; the per-symbol cap looks at
        # ``symbol_trades`` (both long and short on the symbol).
        breaches: list[str] = []
        breached_caps: list[tuple[str, list[TradeHistory], Decimal]] = []
        if (
            policy.max_open_positions_per_symbol_side is not None
            and open_positions_total > policy.max_open_positions_per_symbol_side
        ):
            breaches.append(
                f"open_positions_per_symbol_side {open_positions_total} > "
                f"max {policy.max_open_positions_per_symbol_side}"
            )
            breached_caps.append(
                (
                    "open_positions_per_symbol_side",
                    symbol_side_trades,
                    Decimal(open_positions_total)
                    - Decimal(policy.max_open_positions_per_symbol_side),
                )
            )
        if (
            policy.max_gross_notional_per_symbol_side is not None
            and symbol_side_notional_total > policy.max_gross_notional_per_symbol_side
        ):
            breaches.append(
                f"gross_notional_per_symbol_side {symbol_side_notional_total:.2f} > "
                f"max {policy.max_gross_notional_per_symbol_side}"
            )
            breached_caps.append(
                (
                    "gross_notional_per_symbol_side",
                    symbol_side_trades,
                    symbol_side_notional_total
                    - policy.max_gross_notional_per_symbol_side,
                )
            )
        if (
            policy.max_gross_notional_per_symbol is not None
            and symbol_notional_total > policy.max_gross_notional_per_symbol
        ):
            breaches.append(
                f"gross_notional_per_symbol {symbol_notional_total:.2f} > "
                f"max {policy.max_gross_notional_per_symbol}"
            )
            breached_caps.append(
                (
                    "gross_notional_per_symbol",
                    symbol_trades,
                    symbol_notional_total - policy.max_gross_notional_per_symbol,
                )
            )
        if not breaches:
            return None

        # Arbitration (DEBT-068(c)): decide whether a raw breach actually
        # blocks. ``first_come_first_serve`` keeps the v1 hard-block; under
        # ``lowest_priority_loses`` the proposing account is admitted iff, for
        # EVERY breached cap, it strictly outranks at least one OTHER existing
        # holder on that cap's key (AND-conservative across caps).
        proposer_id = self._sub_account_id(sub_account)
        priority = policy.account_priority

        def _rank(account: str) -> float:
            # Earlier in account_priority == higher priority (lower rank).
            # Unlisted accounts sink to the lowest possible rank.
            try:
                return float(priority.index(account))
            except ValueError:
                return float("inf")

        proposer_rank = _rank(proposer_id)
        proposer_listed = proposer_id in priority

        arbitration_by_cap: dict[str, dict[str, Any]] = {}
        admit_overall = True
        for cap_name, cap_trades, overshoot in breached_caps:
            # Distinct OTHER holders on this cap's key (self-excluded).
            holder_ids = {
                trade.sub_account_id
                for trade in cap_trades
                if trade.sub_account_id != proposer_id
            }
            # Admit this cap iff the proposer STRICTLY outranks some other
            # holder (ties do not count; empty holders => block).
            admit_for_cap = any(proposer_rank < _rank(holder) for holder in holder_ids)
            if not admit_for_cap:
                admit_overall = False
            arbitration_by_cap[cap_name] = {
                "holders": [
                    {
                        "account": holder,
                        "rank": (
                            None
                            if _rank(holder) == float("inf")
                            else int(_rank(holder))
                        ),
                    }
                    for holder in sorted(holder_ids, key=_rank)
                ],
                "overshoot": str(overshoot),
                "admitted": admit_for_cap,
            }

        if policy.cap_resolution == "first_come_first_serve":
            block_overall = True
            arbitration_outcome = "n/a"
        else:
            block_overall = not admit_overall
            arbitration_outcome = "blocked" if block_overall else "admitted"

        # Per-cap overshoot summary for the details payload.
        overshoots = [overshoot for _, _, overshoot in breached_caps]
        cap_overshoot = {
            "total": str(sum(overshoots, start=Decimal("0"))),
            "max": str(max(overshoots)),
        }

        reason = "global_cap: " + "; ".join(breaches)
        details: dict[str, Any] = {
            **_proposal_summary(proposal),
            "reason": reason,
            "gate_reason": GateReason.GLOBAL_CAP.value,
            "symbol": symbol,
            "side": side,
            "open_positions_per_symbol_side_total": open_positions_total,
            "gross_notional_per_symbol_side_total": str(symbol_side_notional_total),
            "gross_notional_per_symbol_total": str(symbol_notional_total),
            "max_open_positions_per_symbol_side": (
                policy.max_open_positions_per_symbol_side
            ),
            "max_gross_notional_per_symbol_side": (
                str(policy.max_gross_notional_per_symbol_side)
                if policy.max_gross_notional_per_symbol_side is not None
                else None
            ),
            "max_gross_notional_per_symbol": (
                str(policy.max_gross_notional_per_symbol)
                if policy.max_gross_notional_per_symbol is not None
                else None
            ),
            "mode": self.mode,
            # DEBT-068(c) arbitration trail.
            "cap_resolution": policy.cap_resolution,
            "arbitration_outcome": arbitration_outcome,
            "proposer_account": proposer_id,
            "proposer_rank": (None if not proposer_listed else int(proposer_rank)),
            "proposer_listed": proposer_listed,
            "existing_holders": sorted(
                {
                    trade.sub_account_id
                    for _, cap_trades, _ in breached_caps
                    for trade in cap_trades
                    if trade.sub_account_id != proposer_id
                }
            ),
            "arbitration_by_cap": arbitration_by_cap,
            "cap_overshoot": cap_overshoot,
        }

        # DEBT-068(c): under ``lowest_priority_loses`` an arbitration that
        # admits overrides the raw breach. The proposal is ADMITTED even
        # though a cap was technically exceeded — a priority-driven soft
        # ceiling. In live mode this overshoot must NOT be silent, so emit an
        # informational RISK_CAP_ADVISORY (advisory=False) before proceeding.
        if not block_overall:
            if self.mode != "paper":
                self.activity_log.append(
                    ActivityEventType.RISK_CAP_ADVISORY,
                    (
                        f"Global-cap admitted by priority (live) for "
                        f"{proposal.symbol} {proposal.signal}"
                    ),
                    details={**details, "advisory": False},
                    cycle_id=cycle_id,
                )
            return None

        if self.mode == "paper":
            # Advisory-only in paper (policy.paper_mode == "advisory"):
            # emit the would-block event but let the proposal proceed so
            # strategy-isolated paper measurements are not contaminated
            # by portfolio-level throttling. The proposal record is NOT
            # downgraded — it still lands in ``proposal_opened``.
            self.activity_log.append(
                ActivityEventType.RISK_CAP_ADVISORY,
                f"Global-cap advisory (paper) for {proposal.symbol}",
                details={**details, "advisory": True},
                cycle_id=cycle_id,
            )
            return None

        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_GLOBAL_CAP, reason
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_REJECTED,
                    (f"Global-cap rejected {proposal.symbol} {proposal.signal}"),
                    details,
                    cycle_id,
                )
            ],
            rejected_record,
        )

    def _sibling_family_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Reject sibling-strategy proposals (same family, symbol, side, cycle).

        P0-E sibling de-duplication. Two strategies that share a
        non-None ``TechniqueInfo.strategy_family`` are treated as
        cadence variants of the same logic — when both fire the same
        ``(symbol, signal-side)`` in the same cycle, the engine keeps
        only the first one and rejects the rest. The correlation gate
        keys on ``technique_name`` so it sees siblings as independent
        and does not catch this fan-out on its own.

        Returns ``None`` (pass) when:

        * the strategy is unknown to the proposal engine — fail open
          rather than block on a registry-lookup glitch, and
        * ``info.strategy_family is None`` — strategies that have not
          opted into family grouping are never deduped against any
          other strategy (preserves all existing single-cadence
          strategies' behaviour).

        Per-cycle state lives in ``_accepted_family_signals``, which
        is wiped at every ``run_cycle`` start next to
        ``_htf_trend_cache``. The cache value records the
        ``technique_name`` of the first-pass winner so the rejection
        event can name it for traceability.

        Only proposals that have already been accepted by every prior
        gate (composite, correlation, trend filter) reach this point,
        so adding to the cache on first pass is safe — we are
        recording "this family already won this cycle for this
        (symbol, side)".
        """
        strategy = self.proposal_engine.strategies.get(proposal.technique_name)
        if strategy is None:
            return None
        family = strategy.info.strategy_family
        if family is None:
            return None

        key = (family, proposal.symbol, proposal.signal)
        first_winner = self._accepted_family_signals.get(key)
        if first_winner is None:
            self._accepted_family_signals[key] = proposal.technique_name
            return None

        reason = f"sibling_strategy_dedup:{family}"
        # proposal-funnel-audit §1 State 4: sibling-family dedup rejection.
        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_SIBLING_FAMILY, reason
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_REJECTED,
                    f"Sibling-dedup rejected {proposal.symbol} {proposal.signal}",
                    {
                        **_proposal_summary(proposal),
                        "reason": reason,
                        "gate_reason": GateReason.SIBLING_FAMILY_DEDUP.value,
                        "family": family,
                        "symbol": proposal.symbol,
                        "signal": proposal.signal,
                        "first_winner_technique": first_winner,
                    },
                    cycle_id,
                )
            ],
            rejected_record,
        )

    def _runtime_safety_pause_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        safety_score: RuntimeSafetyScore,
        cycle_id: str,
    ) -> GateOutcome | None:
        pause_min_score = self._runtime_policy_for(
            sub_account
        ).runtime_safety_pause_min_score
        if pause_min_score is None or safety_score.score >= pause_min_score:
            return None

        reason = (
            f"runtime safety score {safety_score.score} below pause minimum "
            f"{pause_min_score}"
        )
        # proposal-funnel-audit §1 State 4: runtime-safety-pause rejection.
        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_RUNTIME_SAFETY_PAUSE, reason
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_REJECTED,
                    f"Runtime-safety rejected {proposal.symbol} {proposal.signal}",
                    {
                        **_proposal_summary(proposal),
                        "reason": reason,
                        "gate_reason": GateReason.RUNTIME_SAFETY_PAUSED.value,
                        "runtime_safety_score": safety_score.score,
                        "runtime_safety_band": safety_score.band.value,
                        "runtime_safety_pause_min_score": pause_min_score,
                    },
                    cycle_id,
                )
            ],
            rejected_record,
        )

    async def _trend_filter_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        exchange: BaseExchange | None,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Reject counter-trend signals against the 1D SMA200 trend.

        Returns ``None`` when the gate should not block the proposal:

        * the strategy is not flagged ``counter_trend`` in its
          ``TechniqueInfo`` (trend-following / balanced strategies are
          out of scope here),
        * the strategy is unknown to the proposal engine (cannot read
          ``counter_trend`` — fail open rather than block on a lookup
          glitch),
        * no exchange is available for the OHLCV fetch,
        * fewer than 200 daily candles are returned (warm-up — refusing
          to trade simply because history is short would silently
          disable new symbols), or
        * the OHLCV fetch raises (transient errors must not silently
          disable trading; a WARN is logged for the operator).

        For counter_trend strategies with sufficient 1D history:

        * ``signal == "short"`` AND ``last_close > SMA200`` (uptrend)
          rejects with reason ``counter_trend_short_in_uptrend``.
        * ``signal == "long"``  AND ``last_close < SMA200`` (downtrend)
          rejects with reason ``counter_trend_long_in_downtrend``.

        Cached per-cycle on ``(symbol, ymd)`` so a single 1D fetch
        serves every proposal sharing the symbol; the cache is wiped
        at ``run_cycle`` start.
        """
        strategy = self.proposal_engine.strategies.get(proposal.technique_name)
        if strategy is None:
            return None
        if not strategy.info.counter_trend:
            return None
        if exchange is None:
            return None

        cache_key = (proposal.symbol, now_utc().strftime("%Y-%m-%d"))
        cached = self._htf_trend_cache.get(cache_key)
        if cached is not None:
            direction, last_close, sma200 = cached
        else:
            try:
                ohlcv = await exchange.get_ohlcv(
                    proposal.symbol, timeframe="1d", limit=200
                )
            except Exception as e:
                logger.warning(
                    "trend_filter_fetch_failed: symbol=%s proposal_id=%s "
                    "error_type=%s error=%s",
                    proposal.symbol,
                    proposal.proposal_id,
                    type(e).__name__,
                    e,
                )
                return None
            if len(ohlcv) < 200:
                # Insufficient history — do not block the proposal. The
                # gate is purely additive; refusing to trade fresh
                # listings would be a regression.
                return None
            last_close = ohlcv[-1].close
            closes = [c.close for c in ohlcv[-200:]]
            sma200 = sum(closes, Decimal("0")) / Decimal(len(closes))
            direction = "up" if last_close > sma200 else "down"
            self._htf_trend_cache[cache_key] = (direction, last_close, sma200)

        if proposal.signal == "short" and direction == "up":
            reason = "counter_trend_short_in_uptrend"
        elif proposal.signal == "long" and direction == "down":
            reason = "counter_trend_long_in_downtrend"
        else:
            return None

        # proposal-funnel-audit §1 State 4: trend-filter rejection.
        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_TREND_FILTER, reason
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_REJECTED,
                    f"Trend-filter rejected {proposal.symbol} {proposal.signal}",
                    {
                        **_proposal_summary(proposal),
                        "reason": reason,
                        "gate_reason": GateReason.TREND_FILTER_BLOCKED.value,
                        "htf_timeframe": "1d",
                        "htf_last_close": str(last_close),
                        "htf_sma200": str(sma200),
                        "htf_direction": direction,
                    },
                    cycle_id,
                )
            ],
            rejected_record,
        )

    async def _market_regime_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        exchange: BaseExchange | None,
        cycle_id: str,
    ) -> GateOutcome | None:
        """Reject proposals whose market regime is not allowed.

        Returns ``None`` when the gate should not block the proposal:

        * the sub-account has no ``market_regime`` policy or
          ``market_regime.enabled`` is ``False`` (back-compat default),
        * no exchange is available for the OHLCV fetch, or
        * the OHLCV fetch raises (transient errors must not silently
          disable trading; a WARN is logged for the operator).

        For enabled accounts with a successful classifier read:

        * if ``classification.regime`` is in ``allowed_regimes``, return
          ``None`` (pass-through).
        * otherwise build a ``GateOutcome`` whose event carries the
          spec §4 payload — ``symbol``, ``timeframe``, ``regime``,
          ``baseline``, ``close``, ``policy_decision``, ``sub_account_id``.

        ``unknown`` BLOCKS by default per spec §3 — the policy must
        explicitly list ``unknown`` in ``allowed_regimes`` to allow
        pass-through when the classifier cannot answer.

        Per-cycle caching is keyed on ``(reference_symbol, timeframe)``
        so two accounts pointing at the same baseline share a single
        OHLCV fetch.
        """
        if sub_account is None:
            return None
        policy = sub_account.market_regime
        if not policy.enabled:
            return None
        if exchange is None:
            return None

        cache_key = (policy.reference_symbol, policy.timeframe)
        classification = self._market_regime_cache.get(cache_key)
        if classification is None:
            try:
                # +5 candles of headroom over ``DEFAULT_SMA_PERIOD`` so
                # the classifier always sees the full lookback even if
                # an exchange shaves one or two candles off the limit.
                ohlcv = await exchange.get_ohlcv(
                    policy.reference_symbol,
                    # ``BaseExchange.get_ohlcv`` types ``timeframe`` as
                    # a narrow Literal, but the sub-account policy is
                    # a free-form ``str`` (operator-configured YAML).
                    # The same shape exists in
                    # ``ProposalEngine._get_ohlcv``; follow the same
                    # ``type: ignore`` precedent.
                    timeframe=policy.timeframe,  # type: ignore[arg-type]
                    limit=DEFAULT_SMA_PERIOD + 5,
                )
            except Exception as e:
                logger.warning(
                    "market_regime_fetch_failed: symbol=%s timeframe=%s "
                    "proposal_id=%s error_type=%s error=%s",
                    policy.reference_symbol,
                    policy.timeframe,
                    proposal.proposal_id,
                    type(e).__name__,
                    e,
                )
                # Quant-trader audit follow-up: fail-open is the right
                # default for transient fetch errors (matches
                # ``_trend_filter_gate`` precedent), but the silent
                # disablement must still surface on the operator
                # dashboard. The event payload is pinned by
                # ``test_ohlcv_fetch_failure_falls_open_and_emits_degraded_event``.
                self.activity_log.append(
                    ActivityEventType.MARKET_REGIME_DEGRADED,
                    (
                        f"Market-regime gate degraded for "
                        f"{policy.reference_symbol} {policy.timeframe} "
                        f"({type(e).__name__}); passing proposal through"
                    ),
                    details={
                        "symbol": policy.reference_symbol,
                        "timeframe": policy.timeframe,
                        "error_type": type(e).__name__,
                        "sub_account_id": sub_account.id,
                        "policy_decision": "pass_through_degraded",
                    },
                    cycle_id=cycle_id,
                )
                return None
            classification = classify_regime_detailed(
                ohlcv,
                sma_period=DEFAULT_SMA_PERIOD,
                bull_band=DEFAULT_BULL_BAND,
                bear_band=DEFAULT_BEAR_BAND,
                timeframe=policy.timeframe,
            )
            self._market_regime_cache[cache_key] = classification

        regime = classification.regime
        if regime in policy.allowed_regimes:
            return None

        reason = f"market_regime_blocked_{regime}"
        details: dict[str, Any] = {
            **_proposal_summary(proposal),
            "symbol": policy.reference_symbol,
            "timeframe": policy.timeframe,
            "regime": regime,
            "baseline": (
                str(classification.baseline)
                if classification.baseline is not None
                else None
            ),
            "close": (
                str(classification.close) if classification.close is not None else None
            ),
            "policy_decision": "block",
            "sub_account_id": sub_account.id,
            "reason": reason,
            "allowed_regimes": list(policy.allowed_regimes),
        }
        if classification.reason is not None:
            details["classifier_reason"] = classification.reason
        # proposal-funnel-audit §1 State 4: market-regime rejection.
        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_MARKET_REGIME, reason
        )
        # ``details`` already carries ``proposal_id`` / ``record_id`` /
        # ``sub_account_id`` via ``_proposal_summary``; ``gate_reason``
        # is the spec §1 canonical discriminator string.
        details["gate_reason"] = GateReason.MARKET_REGIME_BLOCKED.value
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            [
                GateActivityEvent(
                    ActivityEventType.MARKET_REGIME_BLOCKED,
                    f"Market-regime gate blocked {proposal.symbol} "
                    f"({regime} not in {list(policy.allowed_regimes)})",
                    details,
                    cycle_id,
                )
            ],
            rejected_record,
        )

    def _strategy_action_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        sub_account: SubAccount | None,
        cycle_id: str,
    ) -> tuple[Proposal, ProposalRecord, GateOutcome | None]:
        """Enforce the applied strategy-tuning action on a proposal.

        strategy-tuning §"Runtime Behavior". Sequenced after the
        correlation gate so the upstream regime / correlation gates
        still get a chance to reject before we either rewrite size
        (``scout``) or persist a shadow record. The gate is a no-op
        for accounts that have not opted in
        (``strategy_tuning.enabled=False``) or for strategies whose
        applied action is ``keep`` / ``promote``.

        Returns a triple ``(proposal, record, outcome)``:

        * ``proposal`` is the (possibly resized) proposal that the
          caller threads through downstream gates / the executor.
          Only ``scout`` modifies the quantity; every other action
          returns the input unchanged.
        * ``record`` is the (possibly updated) :class:`ProposalRecord`.
          For ``shadow`` the record carries ``shadow=True`` and
          ``final_state=SHADOW_RECORDED``; for ``pause`` it carries
          ``decision=REJECTED`` and the dedicated pause terminal.
        * ``outcome`` is ``None`` when the proposal should continue
          through the downstream gate chain (``keep`` / ``promote`` /
          ``scout`` / ``retune``). For ``shadow`` and ``pause`` the
          outcome is non-``None`` and the caller short-circuits.

        ``shadow`` is a *terminal* but not a rejection: the gate
        returns a :class:`GateOutcome` whose ``decision`` is
        :attr:`GateDecision.REJECTED` (since no trade opens) but the
        record's ``final_state`` is :attr:`SHADOW_RECORDED` rather
        than a ``gate_rejected_*`` bucket — funnel counters separate
        "measured-only" from "blocked".
        """
        if sub_account is None or not sub_account.strategy_tuning.enabled:
            return proposal, record, None

        policy = sub_account.strategy_tuning
        action = policy.applied_action_for(proposal.technique_name)

        # ``keep`` / ``promote`` are runtime no-ops. ``promote`` is a
        # recommendation-only signal — applying it requires an
        # operator moving the strategy to a different sub-account
        # (operator-only resolution 2026-05-13), so at runtime it
        # behaves exactly like ``keep`` here.
        if action in (StrategyAction.KEEP, StrategyAction.PROMOTE):
            return proposal, record, None

        if action == StrategyAction.RETUNE:
            # ``retune`` flows through; the dashboard reads the
            # advisory event to surface the Retune badge.
            self.activity_log.append(
                ActivityEventType.RETUNE_FLAGGED,
                f"Retune advisory for {proposal.technique_name} on {proposal.symbol}",
                details={
                    "proposal_id": proposal.proposal_id,
                    "sub_account_id": proposal.sub_account_id,
                    "technique_name": proposal.technique_name,
                    "symbol": proposal.symbol,
                },
                cycle_id=cycle_id,
            )
            return proposal, record, None

        if action == StrategyAction.SCOUT:
            factor = policy.scout_size_factor_for(proposal.technique_name)
            scaled_qty = proposal.quantity * factor
            resized = proposal.model_copy(update={"quantity": scaled_qty})
            self.activity_log.append(
                ActivityEventType.PROPOSAL_ACCEPTED,
                (
                    f"Scout-scaled {proposal.symbol} {proposal.signal} "
                    f"qty={proposal.quantity}->{scaled_qty} (×{factor})"
                ),
                details={
                    **_proposal_summary(resized),
                    "reason": "strategy_action_scout",
                    "scout_size_factor": str(factor),
                    "original_quantity": str(proposal.quantity),
                    "scaled_quantity": str(scaled_qty),
                },
                cycle_id=cycle_id,
            )
            return resized, record, None

        if action == StrategyAction.SHADOW:
            shadow_record = record.model_copy(
                update={
                    "shadow": True,
                    "decision": ProposalDecision.REJECTED.value,
                    "rejection_reason": "strategy_action_shadow",
                    "decision_at": now_utc(),
                    "final_state": ProposalFinalState.SHADOW_RECORDED.value,
                }
            )
            event = GateActivityEvent(
                ActivityEventType.PROPOSAL_REJECTED,
                f"Shadow-recorded {proposal.symbol} {proposal.signal}",
                {
                    **_proposal_summary(proposal),
                    "reason": "strategy_action_shadow",
                    "gate_reason": GateReason.STRATEGY_ACTION_SHADOW.value,
                    "shadow": True,
                },
                cycle_id,
            )
            return (
                proposal,
                shadow_record,
                GateOutcome(
                    GateDecision.REJECTED,
                    "strategy_action_shadow",
                    [event],
                    shadow_record,
                ),
            )

        if action == StrategyAction.PAUSE:
            reason = GateReason.STRATEGY_ACTION_PAUSE.value
            paused_record = record.reject(
                ProposalFinalState.GATE_REJECTED_STRATEGY_ACTION_PAUSE, reason
            )
            event = GateActivityEvent(
                ActivityEventType.PROPOSAL_REJECTED,
                f"Strategy-pause rejected {proposal.symbol} {proposal.signal}",
                {
                    **_proposal_summary(proposal),
                    "reason": reason,
                    "gate_reason": reason,
                    # DEBT-069(f): observability-only discriminator. The gate
                    # fires on the OPERATOR-APPLIED action, so every gate pause
                    # is config-driven; the evidence-vs-config corroboration is
                    # computed dashboard-side by joining this against the live
                    # recommender. Never branches the block decision.
                    "pause_reason": PAUSE_REASON_GATE_CONFIG,
                },
                cycle_id,
            )
            return (
                proposal,
                paused_record,
                GateOutcome(
                    GateDecision.REJECTED,
                    reason,
                    [event],
                    paused_record,
                ),
            )

        # Defensive: unknown enum value. Fail open — leave the
        # proposal untouched rather than silently dropping it.
        return proposal, record, None

    def _correlation_gate(
        self,
        proposal: Proposal,
        record: ProposalRecord,
        trader: Trader,
        cycle_id: str,
    ) -> GateOutcome:
        """Emit advisory correlation warnings or reject when opt-in gate is enabled."""
        del trader  # Existing exposure is collected engine-wide when possible.
        policy = self._runtime_policy_for_id(proposal.sub_account_id)
        existing = CorrelationInputSet.from_trade_history(
            self._open_trades_for_correlation(),
            strategy_lookup=self._strategy_lookup_for_open_trades(),
        ).open_only()
        candidate = _proposal_to_correlation_exposure(proposal)
        decision = evaluate_correlation_gate(
            existing,
            candidate,
            config=CorrelationGateConfig(
                enabled=policy.correlation_gate_enabled,
                warning_policy=CorrelationWarningPolicy(
                    max_sub_accounts_per_symbol_side=(
                        policy.correlation_max_sub_accounts_per_symbol_side
                    ),
                    max_sub_accounts_per_strategy_symbol_side=(
                        policy.correlation_max_sub_accounts_per_strategy_symbol_side
                    ),
                ),
            ),
        )
        if not decision.warnings:
            return GateOutcome(GateDecision.ACCEPTED, None, [], record)

        warning_details = _correlation_warning_details(decision.warnings)
        events = [
            GateActivityEvent(
                ActivityEventType.CORRELATION_WARNING,
                f"Correlation warning for {proposal.symbol} {proposal.signal}",
                {
                    **_proposal_summary(proposal),
                    "warnings": warning_details,
                    "gate_enabled": policy.correlation_gate_enabled,
                },
                cycle_id,
            )
        ]
        if decision.allowed:
            return GateOutcome(GateDecision.ACCEPTED, None, events, record)

        reason = decision.reason
        # proposal-funnel-audit §1 State 4: correlation rejection.
        rejected_record = record.reject(
            ProposalFinalState.GATE_REJECTED_CORRELATION, reason
        )
        events.append(
            GateActivityEvent(
                ActivityEventType.PROPOSAL_REJECTED,
                f"Correlation-rejected {proposal.symbol} {proposal.signal}",
                {
                    **_proposal_summary(proposal),
                    "reason": reason,
                    "gate_reason": GateReason.CORRELATION_BLOCKED.value,
                    "warnings": warning_details,
                },
                cycle_id,
            )
        )
        return GateOutcome(
            GateDecision.REJECTED,
            reason,
            events,
            rejected_record,
        )

    def _open_trades_for_correlation(self) -> list[TradeHistory]:
        """Collect open trades across active sub-account traders."""
        if self.sub_account_registry is None:
            traders = [self.trader]
        else:
            traders = [
                self.sub_account_registry.get_trader(sub_account.id)
                for sub_account in self.sub_account_registry.list_active()
            ]

        trades: list[TradeHistory] = []
        seen: set[str] = set()
        for trader in traders:
            for trade in trader.get_open_trades():
                if trade.status != "open" or trade.id in seen:
                    continue
                seen.add(trade.id)
                trades.append(trade)
        return trades

    def _strategy_lookup_for_open_trades(self) -> dict[str, str]:
        """Map open trade ids to proposal technique names when available."""
        if self._strategy_lookup_cache is not None:
            return dict(self._strategy_lookup_cache)
        lookup: dict[str, str] = {}
        for record in self.proposal_history.list_all():
            if record.trade_id is None:
                continue
            lookup[record.trade_id] = record.proposal.technique_name
        self._strategy_lookup_cache = dict(lookup)
        return lookup

    def _remember_mark_price(self, symbol: str, price: Decimal) -> None:
        """DEBT-066: write-through helper for the in-memory mark cache.

        Called from the existing per-cycle ticker fetch sites (``_monitor``
        and ``_record_portfolio_snapshot``) so cap-rejection events can
        consume a fresh mark for the blocking trade's symbol without a
        new ``await exchange.get_ticker(...)`` on the hot path. Always
        overwrites — the freshness check is on the read side.
        """
        self._mark_price_cache[symbol] = MarkPriceEntry(
            price=price,
            observed_at=now_utc(),
        )

    def _get_cached_mark_price(
        self,
        symbol: str,
        *,
        max_age_seconds: float = MARK_PRICE_CACHE_DEFAULT_MAX_AGE_SECONDS,
    ) -> Decimal | None:
        """DEBT-066: return the cached mark for ``symbol`` if it is fresh.

        Returns ``None`` when the symbol has never been observed in the
        cache, or when the cached observation is older than
        ``max_age_seconds`` relative to ``now_utc()``. A stale entry is
        intentionally left in place — the next ticker fetch overwrites
        it via :meth:`_remember_mark_price`. The cap-rejection consumer
        treats ``None`` as "no live cross-check available" and falls
        back to ``unrealized_pnl_percent=None``, matching the pre-cache
        behaviour for un-observed symbols.
        """
        entry = self._mark_price_cache.get(symbol)
        if entry is None:
            return None
        age = (now_utc() - entry.observed_at).total_seconds()
        if age > max_age_seconds:
            return None
        return entry.price

    async def _build_cap_blocker_payload(
        self,
        *,
        open_trades: list[TradeHistory],
        cap: int,
        reason: str,
    ) -> list[dict[str, Any]]:
        """Build the ``blocking_trades`` array for a cap-rejection event.

        Per proposal-funnel-audit spec §3, every cap rejection
        (``total_cap`` / ``symbol_cap``) carries a list of the existing
        open trades that count toward the cap so operators can
        immediately answer "which position is blocking?". Per-blocker
        fields:

        * ``trade_id`` — ``TradeHistory.id`` of the blocker.
        * ``symbol`` / ``side`` / ``entry_price`` / ``entry_time`` —
          read straight off the trade row.
        * ``age_seconds`` — ``now_utc() - entry_time`` at decision
          time (UTC-aware subtraction; on-disk rows are coerced to
          UTC by the ``TradeHistory`` validator).
        * ``unrealized_pnl_percent`` — DEBT-066: now sourced from the
          in-memory mark-price cache populated by the existing
          per-cycle ticker reads in ``_monitor`` and
          ``_record_portfolio_snapshot``. Zero new exchange calls on
          the cap-rejection hot path. When the cache has a fresh entry
          for the blocking trade's symbol, the field is computed as
          ``(mark - entry)/entry * 100`` (long) or ``(entry - mark)/entry
          * 100`` (short) — the same price-move metric the autopsy /
          backtest engines use, mirroring ``pnl_for_trade``. When the
          cache has no fresh entry (uncached or older than
          ``MARK_PRICE_CACHE_DEFAULT_MAX_AGE_SECONDS``), the field
          falls back to ``None`` to match the pre-cache contract —
          operators still get the first-order signal (``entry_price``
          + ``age_seconds`` + ``monitorable`` + ``symbol``).
        * ``monitorable`` — coordinate from
          :func:`src.runtime.reconciliation.classify_open_trade`;
          ``True`` iff the row's classified state is ``MONITORABLE``.
          A blocker that is *not* monitorable is the exact "blocked
          by a position the engine cannot close" case spec §3 calls
          out.
        * ``technique_name`` — joined back through the proposal
          history (`trade_id` -> `technique_name`) when available;
          ``None`` for orphan trades.
        * ``proposal_record_id`` — the blocker's proposal id when the
          link is intact; ``None`` otherwise.
        """
        strategy_lookup = self._strategy_lookup_for_open_trades()
        # ``trade_id -> proposal_id`` join. The strategy lookup above
        # only carries ``trade_id -> technique_name``; rebuild the
        # proposal-id map here so we can populate
        # ``proposal_record_id`` for the blocker payload.
        proposal_id_by_trade: dict[str, str] = {}
        for record in self.proposal_history.list_all():
            if record.trade_id is None:
                continue
            proposal_id_by_trade[record.trade_id] = record.proposal.proposal_id

        now = now_utc()
        payload: list[dict[str, Any]] = []
        for trade in open_trades:
            entry_time = ensure_utc(trade.entry_time)
            age_seconds = int((now - entry_time).total_seconds())

            # DEBT-066: consume the in-memory mark-price cache populated
            # upstream by the per-cycle ticker reads. ``_get_cached_mark_
            # price`` enforces the freshness window — a stale or missing
            # symbol falls back to ``None`` so the cap-rejection event
            # never reports a misleading mark.
            unrealized_pnl_percent: float | None = None
            mark = self._get_cached_mark_price(trade.symbol)
            if mark is not None and trade.entry_price > 0:
                if trade.side == "long":
                    price_move = mark - trade.entry_price
                else:  # short
                    price_move = trade.entry_price - mark
                unrealized_pnl_percent = float(
                    (price_move / trade.entry_price) * Decimal("100")
                )

            # Classify the row via the runtime-reconciliation taxonomy
            # so we can surface the "blocked by an unmonitorable open"
            # case. The classifier wants the on-disk row shape; the
            # in-memory ``TradeHistory`` carries equivalent fields.
            row = {
                "id": trade.id,
                "symbol": trade.symbol,
                "side": trade.side,
                "entry_price": (
                    str(trade.entry_price) if trade.entry_price is not None else None
                ),
                "entry_quantity": (
                    str(trade.entry_quantity)
                    if trade.entry_quantity is not None
                    else None
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
            monitorable = classification.state == "monitorable"

            payload.append(
                {
                    "trade_id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "entry_price": str(trade.entry_price),
                    "entry_time": entry_time.isoformat(),
                    "age_seconds": age_seconds,
                    "unrealized_pnl_percent": unrealized_pnl_percent,
                    "monitorable": monitorable,
                    "technique_name": strategy_lookup.get(trade.id),
                    "proposal_record_id": proposal_id_by_trade.get(trade.id),
                    "cap_value": cap,
                    "current_open_count": len(open_trades),
                    "reason": reason,
                }
            )
        return payload

    async def _stale_quote_gate(
        self,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
        exchange: BaseExchange | None = None,
    ) -> str | None:
        """Reject the fill if the live ticker has gone stale on the proposal.

        Phase 18.1 sanity gate. Returns the rejection reason string if
        the proposal should be skipped, or ``None`` if execution should
        proceed (either the gates passed or the ticker fetch failed and
        we are falling through to fill).

        On rejection: overwrites the proposal record with
        ``decision="rejected"``, emits a ``PROPOSAL_REJECTED`` activity
        event with structured ``entry_price``, ``live_price``, and
        ``drift_bps`` fields for post-mortem reconstruction, and bumps
        ``result.proposals_rejected``. The composite gate has already
        incremented ``proposals_accepted`` by this point, so the cycle
        summary records both sides of the post-acceptance gate.
        """
        policy = self._runtime_policy_for_id(proposal.sub_account_id)
        account_exchange = exchange or self.exchange
        try:
            ticker = await account_exchange.get_ticker(proposal.symbol)
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
            # Phase 24.2 / DEBT-033 follow-up: opt-in hard rejection
            # when there is no live data to cross-check against. Live
            # mode operators flip this on so a fill never proceeds
            # at ``proposal.entry_price`` without a fresh quote.
            if policy.reject_if_stale_quote:
                reason = "stale_quote_no_live_data"
                self._record_no_live_data_rejection(
                    proposal=proposal,
                    cycle_id=cycle_id,
                    result=result,
                    reason=reason,
                    detail=f"ticker_fetch_failed:{type(e).__name__}",
                )
                return reason
            return None

        # Phase 24.1 / DEBT-033: ticker freshness threshold. A
        # successfully-fetched but old ticker (rate-limited adapter,
        # cached response, frozen connection) is no better than a
        # failed fetch for the slippage / past-SL checks below. Fall
        # through with the same WARN that the exception path emits so
        # the gate's effectiveness is observable in the logs and the
        # operator decides whether to harden the freshness threshold
        # via ``EngineConfig.max_ticker_age_seconds``.
        ticker_ts = ticker.timestamp
        # CAH-01 [BUGFIX] / DEBT-033: a None ticker timestamp is
        # unverifiable freshness — the venue gave us no sample time. It
        # is *less* trustworthy than a real timestamp, not maximally
        # fresh, so it must not flow into the past-SL / slippage checks
        # below as if it were 0 seconds old. Mirror the over-age branch:
        # WARN + fall through normally, but HARD-REJECT when
        # ``reject_if_stale_quote`` is True so the operator's fail-closed
        # switch still applies.
        if ticker_ts is None:
            logger.warning(
                "stale_quote_check_failed: symbol=%s proposal_id=%s "
                "error_type=stale_ticker error=ticker timestamp missing "
                "(unverifiable freshness)",
                proposal.symbol,
                proposal.proposal_id,
            )
            if policy.reject_if_stale_quote:
                reason = "stale_quote_no_live_data"
                self._record_no_live_data_rejection(
                    proposal=proposal,
                    cycle_id=cycle_id,
                    result=result,
                    reason=reason,
                    detail="ticker_timestamp_missing",
                )
                return reason
            return None
        if ticker_ts.tzinfo is None:
            # Phase 21 contract: exchange adapters produce UTC-aware
            # timestamps via ``from_unix_ms``. Naive timestamps reach
            # this code only from older fixtures; treat as UTC for the
            # freshness comparison rather than crash the gate.
            ticker_ts = ticker_ts.replace(tzinfo=now_utc().tzinfo)
        age_seconds = (now_utc() - ticker_ts).total_seconds()
        if age_seconds > policy.max_ticker_age_seconds:
            logger.warning(
                "stale_quote_check_failed: symbol=%s proposal_id=%s "
                "error_type=stale_ticker error=ticker age %.2fs "
                "exceeds max_ticker_age_seconds=%.2f",
                proposal.symbol,
                proposal.proposal_id,
                age_seconds,
                policy.max_ticker_age_seconds,
            )
            # Phase 24.2 / DEBT-033 follow-up: opt-in hard rejection
            # on stale quote. Same reasoning as the exception branch
            # above — when ``reject_if_stale_quote`` is True the gate
            # blocks the fill rather than silently letting it proceed
            # against a known-stale tape.
            if policy.reject_if_stale_quote:
                reason = "stale_quote_no_live_data"
                self._record_no_live_data_rejection(
                    proposal=proposal,
                    cycle_id=cycle_id,
                    result=result,
                    reason=reason,
                    detail=(
                        f"ticker_age_seconds={age_seconds:.2f} "
                        f"max={policy.max_ticker_age_seconds:.2f}"
                    ),
                )
                return reason
            return None

        live_price = ticker.price
        entry = proposal.entry_price
        sl = proposal.stop_loss

        # Past-SL gate: only run when explicitly enabled. Side dispatch
        # is keyed off ``proposal.signal`` (the spec) — never inferred
        # from the entry/SL ordering, which would silently flip on a
        # short with the same numeric layout.
        if policy.reject_if_past_stop_loss:
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
            if drift > policy.fill_slippage_tolerance:
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
        numeric trio (``entry_price``, ``live_price``, ``drift_bps``)
        that the dashboard / audit reports need to reconstruct the
        rejection distribution.

        **Timestamp coherence contract (DEBT-025 / Phase 21.3)**:
        every ``datetime`` that lands in the rejection payload is
        UTC-aware:

        * ``ProposalRecord.decision_at`` — set to :func:`now_utc`
          (UTC-aware by construction).
        * ``ProposalRecord.proposal.created_at`` — typed ``datetime``;
          the ``Proposal._coerce_created_at_to_utc`` field validator
          coerces naive on-disk values to UTC at the read boundary
          (Phase 21.2).
        * ``ActivityEvent.timestamp`` — defaulted to :func:`now_utc`
          and validated via ``_coerce_timestamp_to_utc`` (Phase 21.2).
        * ``ticker.timestamp`` (the live-quote sample feeding
          ``live_price``) — produced by exchange adapters via
          :func:`from_unix_ms` (Phase 21.1), so the candle-side clock
          is UTC-aware before it ever reaches this function.

        The callers (:meth:`_stale_quote_gate`) read ``ticker.price``
        only; the candle ``timestamp`` is not currently embedded in
        the ``details`` payload (out of scope per Phase 21.3 — no new
        payload fields). The contract above is the regression surface
        the Phase 21.3 tests pin.
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
        # DEBT-028 (Phase 22.1): ``ProposalHistory.save`` routes through
        # ``atomic_write_text``, so the load → model_copy → save
        # sequence below leaves the previous (ACCEPTED) record intact
        # if the rewrite crashes mid-save instead of producing a
        # truncated file.
        try:
            existing = self.proposal_history.load(proposal.proposal_id)
            # proposal-funnel-audit §1 State 4 (presented at State 4 in
            # the UI even though it fires inside ``_execute`` —
            # open-decision §6 stale-quote resolution, 2026-05-13).
            updated = existing.reject(
                ProposalFinalState.GATE_REJECTED_STALE_QUOTE, reason
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
                "gate_reason": GateReason.STALE_QUOTE_NO_LIVE_DATA.value,
                "proposal_stop_loss": str(proposal.stop_loss),
                "live_price": str(live_price),
                "drift_bps": drift_bps,
            },
            cycle_id=cycle_id,
        )

    def _record_no_live_data_rejection(
        self,
        *,
        proposal: Proposal,
        cycle_id: str,
        result: CycleResult,
        reason: str,
        detail: str,
    ) -> None:
        """Persist + log a rejection caused by missing live data.

        Phase 24.2 / DEBT-033 follow-up. When
        ``EngineConfig.reject_if_stale_quote`` is True, both the ticker
        fetch failure path and the freshness-threshold path divert here
        instead of falling through to the fill. The persisted record
        and activity event mirror :meth:`_record_stale_quote_rejection`
        but omit ``live_price`` / ``drift_bps`` (no live tape was
        available to populate them) and carry a ``detail`` field
        describing whether it was a fetch failure or a stale ticker so
        post-mortems can distinguish the two.
        """
        try:
            existing = self.proposal_history.load(proposal.proposal_id)
            # proposal-funnel-audit §1 State 4: presented at State 4 in
            # the UI per open-decision §6 stale-quote resolution
            # (2026-05-13).
            updated = existing.reject(
                ProposalFinalState.GATE_REJECTED_STALE_QUOTE, reason
            )
            self.proposal_history.save(updated)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(
                "Failed to overwrite proposal record %s with no-live-data "
                "rejection: %s",
                proposal.proposal_id,
                e,
            )

        # Same accounting as ``_record_stale_quote_rejection``: the
        # proposal was already counted as accepted by score; this
        # rejection happens at the execution gate.
        result.proposals_rejected += 1

        self.activity_log.append(
            ActivityEventType.PROPOSAL_REJECTED,
            (
                f"No-live-data rejected {proposal.symbol} {proposal.signal} "
                f"({reason})"
            ),
            details={
                **_proposal_summary(proposal),
                "reason": reason,
                "gate_reason": GateReason.STALE_QUOTE_NO_LIVE_DATA.value,
                "detail": detail,
                "proposal_stop_loss": str(proposal.stop_loss),
            },
            cycle_id=cycle_id,
        )

    def _make_snapshot_recorder(self) -> SnapshotRecorder:
        """Build a :class:`SnapshotRecorder` from the engine's live config.

        CAH-15 Slice 1 (ADR 0001): the persistence concern lives in the
        recorder, but the recorder is **stateless** (it owns none of the
        six per-cycle caches — quant-confirmed) so it is rebuilt on demand
        rather than captured at construction. Rebuilding reads the engine's
        current ``portfolio_tracker`` / ``mode`` / ``quote_currency`` /
        ``exchange`` so a caller that mutates those attributes after
        ``__init__`` (tests, future runtime reconfiguration) sees live
        values with no capture-staleness bug. ``_remember_mark_price`` is
        passed as the write-through callback so the engine-owned
        ``_mark_price_cache`` stays the single source of truth (ADR
        cache-ownership contract + quant CHANGE B — injected directly,
        never chained).
        """
        return SnapshotRecorder(
            proposal_history=self.proposal_history,
            activity_log=self.activity_log,
            proposal_engine=self.proposal_engine,
            portfolio_tracker=self.portfolio_tracker,
            default_exchange=self.exchange,
            remember_mark_price=self._remember_mark_price,
            mode=self.mode,
            quote_currency=self.quote_currency,
        )

    async def _record_portfolio_snapshot(
        self,
        cycle_id: str,
        sub_account: SubAccount | None,
        trader: Trader,
        exchange: BaseExchange | None = None,
    ) -> None:
        """Delegate to :meth:`SnapshotRecorder.record_portfolio_snapshot`."""
        await self._make_snapshot_recorder().record_portfolio_snapshot(
            cycle_id, sub_account, trader, exchange
        )

    def _record_closed_trade(
        self,
        trade: TradeHistory,
        reason: str,
        cycle_id: str,
    ) -> None:
        """Delegate to :meth:`SnapshotRecorder.record_closed_trade`."""
        self._make_snapshot_recorder().record_closed_trade(trade, reason, cycle_id)

    def _save_performance_record(
        self,
        proposal_record: ProposalRecord,
        trade: TradeHistory,
        reason: str,
    ) -> None:
        """Delegate to the recorder's per-trade ``PerformanceRecord`` write."""
        self._make_snapshot_recorder()._save_performance_record(
            proposal_record, trade, reason
        )

    def _find_proposal_record_for_trade(self, trade_id: str) -> ProposalRecord | None:
        """Delegate to :meth:`SnapshotRecorder.find_proposal_record_for_trade`."""
        return self._make_snapshot_recorder().find_proposal_record_for_trade(trade_id)

    def _run_reconciliation_health_check(self) -> None:
        """Emit ``RECONCILIATION_HEALTH_REPORT`` once at startup.

        runtime-reconciliation §3. The pass is read-only (the helper
        only walks the on-disk ledger + perf records + balances
        snapshot) so it is safe to invoke synchronously from
        ``run_forever`` before the cycle loop. The taxonomy is
        recomputed on every startup — state is never persisted —
        because perf-record presence and ledger contents can drift
        between restarts.

        Failures are logged and swallowed: a malformed ledger must not
        keep the engine from booting (Resolution 2026-05-13 paper-mode
        policy; live-mode tightening is a future concern). The
        dashboard banner is sourced from this event so even a partial
        / empty report is preferable to no signal at all.
        """
        try:
            data_dir = self._reconciliation_data_dir()
            sub_account_ids = [
                self._sub_account_id(sub_account)
                for sub_account in self._active_sub_accounts()
            ]
            report = compute_health_report(data_dir, sub_account_ids)
        except Exception as exc:
            # Q4 follow-up: log-and-continue is still the contract
            # (paper-mode resolution 2026-05-13 — never fail-startup),
            # but the failure itself must be operator-visible so a
            # chronically-broken health check can't masquerade as a
            # fresh deployment. Emit the meta-event before returning;
            # the dashboard banner will render Yellow with a CTA when
            # this is the most recent reconciliation event.
            logger.warning("Reconciliation health check failed: %s", exc, exc_info=True)
            self.activity_log.append(
                ActivityEventType.RECONCILIATION_HEALTH_CHECK_FAILED,
                f"Reconciliation health check failed: {exc}",
                details={
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "sub_account_id": None,
                },
            )
            return

        totals = report.get("totals", {})
        state_counts = totals.get("state_counts", {}) or {}
        open_count = int(totals.get("open_trade_count", 0))
        unrecoverable = int(state_counts.get("unrecoverable", 0))
        degraded = int(state_counts.get("degraded", 0))

        message = (
            f"Reconciliation: {open_count} open trade(s); "
            f"degraded={degraded}, unrecoverable={unrecoverable}"
        )
        if unrecoverable > 0:
            logger.warning(message)
        elif degraded > 0:
            logger.info(message)
        else:
            logger.info(message)

        self.activity_log.append(
            ActivityEventType.RECONCILIATION_HEALTH_REPORT,
            message,
            details=report,
        )

        # NFR-008: surface locked-vs-snapshot drift as its own event so
        # the dashboard can filter and the safety score can pick it up
        # without scanning the full health-report payload.
        inconsistent: list[dict[str, Any]] = []
        for sub_account_id, per_account in report.get("report", {}).items():
            if not per_account.get("locked_consistent", True):
                inconsistent.append(
                    {
                        "sub_account_id": sub_account_id,
                        "locked_sum": per_account.get("locked_sum"),
                        "balance_locked": per_account.get("balance_locked"),
                        "balance_snapshot_present": per_account.get(
                            "balance_snapshot_present"
                        ),
                    }
                )
        if inconsistent:
            self.activity_log.append(
                ActivityEventType.RECONCILIATION_LOCKED_INCONSISTENT,
                (
                    f"Locked margin drift on {len(inconsistent)} sub-account(s); "
                    "operator review required"
                ),
                details={"sub_accounts": inconsistent},
            )

    def _reconciliation_data_dir(self) -> Any:
        """Return the engine's effective data-root for reconciliation reads.

        Prefer the trader's ``TradeHistoryTracker.data_dir`` parent (the
        same root the runtime writes against) so tests with a tmp
        ``data_dir`` don't have to monkeypatch ``Settings``. Falls back
        to ``Settings.data_dir`` when the trader doesn't expose a
        tracker (mock traders in unit tests).
        """
        tracker = getattr(self.trader, "_trade_tracker", None)
        tracker_dir = getattr(tracker, "data_dir", None)
        if isinstance(tracker_dir, Path):
            # ``TradeHistoryTracker.data_dir`` is ``<data_dir>/trades``;
            # walk up one level to recover the engine data root.
            return tracker_dir.parent
        from src.config import get_settings

        return get_settings().data_dir

    def _active_sub_accounts(self) -> list[SubAccount | None]:
        if self.sub_account_registry is None:
            return [None]
        active: list[SubAccount | None] = list(self.sub_account_registry.list_active())
        return active

    def _sub_account_id(self, sub_account: SubAccount | None) -> str:
        return sub_account.id if sub_account is not None else DEFAULT_SUB_ACCOUNT_ID

    def _current_applied_state_map(self) -> AppliedStateMap:
        """Snapshot the applied tuning-action per ``(sub_account, strategy)``.

        strategy-tuning DEBT-069(d). For every active sub-account, records the
        applied action for the union of (a) the strategies registered on the
        proposal engine and (b) any strategy named in the policy's
        ``strategy_overrides``. Including the registered strategies (which
        default to ``keep``) means that REMOVING an override — e.g. flipping a
        strategy back from ``scout`` to the ``keep`` default — is still a
        detectable ``scout -> keep`` transition rather than a silent
        disappearance. Sub-accounts with no policy (the ``None`` /
        registry-less case) contribute nothing — there is no applied state to
        diff.
        """
        registered = set(self.proposal_engine.strategies.keys())
        result: AppliedStateMap = {}
        for sub_account in self._active_sub_accounts():
            if sub_account is None:
                continue
            policy = sub_account.strategy_tuning
            names = registered | set(policy.strategy_overrides.keys())
            if not names:
                continue
            result[sub_account.id] = {
                name: policy.applied_action_for(name).value for name in sorted(names)
            }
        return result

    def _maybe_emit_strategy_action_transitions(self, cycle_id: str) -> None:
        """Emit ``STRATEGY_ACTION_APPLIED`` for applied-action transitions.

        strategy-tuning DEBT-069(d). Once per process: load the prior snapshot,
        diff against the current applied state, emit one event per changed
        ``(sub_account, strategy)``, then persist the new snapshot.

        First run (no prior snapshot) seeds the snapshot and emits NOTHING so a
        fresh deploy does not storm the activity log. The whole operation is
        wrapped defensively — a snapshot IO failure must never take the cycle
        down.
        """
        if self._strategy_action_diff_done:
            return
        self._strategy_action_diff_done = True

        path = self.config.strategy_action_snapshot_path
        try:
            current = self._current_applied_state_map()
            prior = load_snapshot(path)
            if prior is not None:
                for transition in diff_snapshots(prior, current):
                    self.activity_log.append(
                        ActivityEventType.STRATEGY_ACTION_APPLIED,
                        (
                            f"Applied action for {transition.strategy} on "
                            f"{transition.sub_account_id}: "
                            f"{transition.prior_action} -> {transition.new_action}"
                        ),
                        details={
                            "sub_account": transition.sub_account_id,
                            "strategy": transition.strategy,
                            "prior_action": transition.prior_action,
                            "new_action": transition.new_action,
                        },
                        cycle_id=cycle_id,
                    )
            save_snapshot(current, path)
        except Exception:  # pragma: no cover - defensive: never crash the cycle
            logger.exception("strategy-action transition emitter failed")

    def _trader_for_sub_account(self, sub_account_id: str) -> Trader:
        if self.sub_account_registry is None:
            return self.trader
        return self.sub_account_registry.get_trader(sub_account_id)

    def _exchange_for_trader(self, trader: Trader) -> BaseExchange:
        trader_vars = vars(trader)
        if "_exchange" not in trader_vars and "exchange" not in trader_vars:
            return self.exchange
        exchange = getattr(trader, "exchange", None)
        if exchange is None:
            return self.exchange
        return cast("BaseExchange", exchange)

    def _runtime_policy_for_id(self, sub_account_id: str) -> AccountRuntimePolicy:
        cached = self._runtime_policy_cache.get(sub_account_id)
        if cached is not None:
            return cached
        if self.sub_account_registry is None:
            policy = self._runtime_policy_for(None)
            self._runtime_policy_cache[sub_account_id] = policy
            return policy
        try:
            policy = self._runtime_policy_for(
                self.sub_account_registry.get(sub_account_id)
            )
        except Exception:
            policy = self._runtime_policy_for(None)
        self._runtime_policy_cache[sub_account_id] = policy
        return policy

    def _runtime_policy_for(
        self,
        sub_account: SubAccount | None,
    ) -> AccountRuntimePolicy:
        return PolicyResolver(
            config=self.config,
            sub_account=sub_account,
            default_leverage=self._default_runtime_leverage(),
        ).resolve()

    def _default_runtime_leverage(self) -> int:
        default = getattr(getattr(self.proposal_engine, "config", None), "leverage", 1)
        return int(default)

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
        threshold = self._runtime_policy_for_id(
            proposal.sub_account_id
        ).auto_approve_threshold
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


def _proposal_to_correlation_exposure(proposal: Proposal) -> CorrelationExposure:
    return CorrelationExposure(
        source=CorrelationExposureSource.RUNTIME,
        exposure_id=f"proposal:{proposal.proposal_id}",
        sub_account_id=proposal.sub_account_id,
        strategy_id=proposal.technique_name,
        symbol=proposal.symbol,
        side=proposal.signal,
        opened_at=now_utc(),
        entry_price=proposal.entry_price,
        quantity=proposal.quantity,
        notional=abs(proposal.entry_price * proposal.quantity),
    )


def _correlation_warning_details(
    warnings: list[CorrelationWarning],
) -> list[dict[str, object]]:
    return [
        {
            "warning_type": warning.warning_type.value,
            "symbol": warning.symbol,
            "side": warning.side,
            "strategy_id": warning.strategy_id,
            "sub_account_ids": warning.sub_account_ids,
            "exposure_ids": warning.exposure_ids,
            "total_notional": str(warning.total_notional),
            "message": warning.message,
        }
        for warning in warnings
    ]


def _proposal_summary(proposal: Proposal) -> dict[str, object]:
    """Compact dict used as the ``details`` payload for proposal events.

    ``record_id`` is included as a stable funnel-join key per the
    proposal-funnel-audit spec §2. Each proposal maps 1:1 to a single
    ``ProposalRecord`` on disk so the join key equals
    ``proposal.proposal_id``; the dashboard joins activity events on
    this field to collapse "accepted-then-blocked" proposals into one
    funnel row.
    """
    return {
        "proposal_id": proposal.proposal_id,
        "record_id": proposal.proposal_id,
        "sub_account_id": proposal.sub_account_id,
        "symbol": proposal.symbol,
        "side": proposal.signal,
        "signal": proposal.signal,
        "technique": proposal.technique_name,
        "technique_name": proposal.technique_name,
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
    "ErrorCategory",
    "TradingEngine",
]
