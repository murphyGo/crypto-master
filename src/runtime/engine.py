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
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

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
from src.runtime.safety_score import (
    RuntimeSafetyScore,
    compute_runtime_safety_score,
    inputs_from_recent_activity_events,
)
from src.strategy.base import default_max_bars_held
from src.strategy.performance import (
    PerformanceRecord,
    PerformanceTracker,
    TradeHistory,
    TradeOutcome,
)
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID
from src.utils.time import now_utc

if TYPE_CHECKING:
    from src.exchange.base import BaseExchange
    from src.trading.base import Trader
    from src.trading.portfolio import Mode, PortfolioTracker
    from src.trading.sub_account import SubAccount
    from src.trading.sub_account_registry import SubAccountRegistry

logger = get_logger("crypto_master.runtime.engine")


# Timeframe → seconds for the time-stop wall-clock conversion. Kept
# local to the engine because the only caller today is ``_monitor``;
# if more sites grow the same need we can promote this to
# ``src/utils/time.py``. Values cover every label the strategy
# loader currently accepts; unknown labels fall back to 1h so the
# fallback keeps the trade alive for at least a default-sized
# window rather than collapsing to a pathological zero.
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

    Unknown labels return 1h (3600s) so a misconfigured strategy
    doesn't end up with a zero-length time-stop window — the
    activity log will still surface the unexpected timeframe via the
    ``POSITION_TIME_STOPPED`` event payload.
    """
    return _TIMEFRAME_TO_SECONDS.get(timeframe, 3600)


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
        self._strategy_lookup_cache = None
        self._runtime_policy_cache = {}
        self._runtime_safety_score_cache = None
        self._htf_trend_cache = {}
        self.activity_log.append(
            ActivityEventType.CYCLE_STARTED,
            f"Cycle {self._cycle_index} begin",
            details={"cycle_index": self._cycle_index},
            cycle_id=cycle_id,
        )

        result = CycleResult(cycle_id=cycle_id)

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

                await self._monitor(cycle_id, result, sub_account, trader, exchange)

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
            events.append(
                GateActivityEvent(
                    ActivityEventType.PROPOSAL_ACCEPTED,
                    f"Auto-accepted {proposal.symbol} {proposal.signal}",
                    _proposal_summary(proposal),
                    cycle_id,
                )
            )

            correlation_outcome = self._correlation_gate(
                proposal,
                record,
                trader,
                cycle_id,
            )
            events.extend(correlation_outcome.events)
            if correlation_outcome.decision == GateDecision.REJECTED:
                result.proposals_rejected += 1
                outcome = GateOutcome(
                    GateDecision.REJECTED,
                    correlation_outcome.reason,
                    events,
                    correlation_outcome.final_record,
                )
                self.proposal_history.save(outcome.final_record)
                for event in outcome.events:
                    self.activity_log.append(
                        event.event_type,
                        event.message,
                        details=event.details,
                        cycle_id=event.cycle_id,
                    )
                return

            trend_rejection = await self._trend_filter_gate(
                proposal,
                record,
                exchange or self.exchange,
                cycle_id,
            )
            if trend_rejection is not None:
                result.proposals_rejected += 1
                self.proposal_history.save(trend_rejection.final_record)
                for event in events + trend_rejection.events:
                    self.activity_log.append(
                        event.event_type,
                        event.message,
                        details=event.details,
                        cycle_id=event.cycle_id,
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
                result.proposals_rejected += 1
                self.proposal_history.save(pause_rejection.final_record)
                for event in events + pause_rejection.events:
                    self.activity_log.append(
                        event.event_type,
                        event.message,
                        details=event.details,
                        cycle_id=event.cycle_id,
                    )
                return

            # Phase 12.1: cross-cycle position cap. The composite
            # gate has accepted this proposal, but we may already be
            # at the per-symbol cap from previous cycles' open trades.
            # Block execution here and record a second rejection
            # reason on top of the existing composite-threshold one.
            policy = self._runtime_policy_for(sub_account)
            cap = policy.max_open_positions_per_symbol
            open_trades = trader.get_open_trades()
            total_cap = policy.max_open_positions_total
            if total_cap is not None and len(open_trades) >= total_cap:
                reason = (
                    f"total open-position cap {total_cap} reached on "
                    f"sub-account {proposal.sub_account_id} ({len(open_trades)} open)"
                )
                rejected_record = record.model_copy(
                    update={
                        "decision": ProposalDecision.REJECTED.value,
                        "rejection_reason": reason,
                        "decision_at": now_utc(),
                    }
                )
                result.proposals_rejected += 1
                outcome = GateOutcome(
                    GateDecision.REJECTED,
                    reason,
                    events
                    + [
                        GateActivityEvent(
                            ActivityEventType.PROPOSAL_REJECTED,
                            f"Total-cap rejected {proposal.symbol} {proposal.signal}",
                            {
                                **_proposal_summary(proposal),
                                "reason": reason,
                                "open_count": len(open_trades),
                                "cap": total_cap,
                            },
                            cycle_id,
                        )
                    ],
                    rejected_record,
                )
                self.proposal_history.save(outcome.final_record)
                for event in outcome.events:
                    self.activity_log.append(
                        event.event_type,
                        event.message,
                        details=event.details,
                        cycle_id=event.cycle_id,
                    )
                return
            existing = sum(
                1 for trade in open_trades if trade.symbol == proposal.symbol
            )
            if existing >= cap:
                reason = (
                    f"symbol {proposal.symbol} cap {cap} reached on "
                    f"sub-account {proposal.sub_account_id} ({existing} open)"
                )
                rejected_record = record.model_copy(
                    update={
                        "decision": ProposalDecision.REJECTED.value,
                        "rejection_reason": reason,
                        "decision_at": now_utc(),
                    }
                )
                result.proposals_rejected += 1
                outcome = GateOutcome(
                    GateDecision.REJECTED,
                    reason,
                    events
                    + [
                        GateActivityEvent(
                            ActivityEventType.PROPOSAL_REJECTED,
                            f"Cap-rejected {proposal.symbol} {proposal.signal}",
                            {
                                **_proposal_summary(proposal),
                                "reason": reason,
                                "open_count": existing,
                                "cap": cap,
                            },
                            cycle_id,
                        )
                    ],
                    rejected_record,
                )
                self.proposal_history.save(outcome.final_record)
                for event in outcome.events:
                    self.activity_log.append(
                        event.event_type,
                        event.message,
                        details=event.details,
                        cycle_id=event.cycle_id,
                    )
                return

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
            result.proposals_rejected += 1
            outcome = GateOutcome(
                GateDecision.REJECTED,
                record.rejection_reason,
                events
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
                record,
            )
            self.proposal_history.save(outcome.final_record)
            for event in outcome.events:
                self.activity_log.append(
                    event.event_type,
                    event.message,
                    details=event.details,
                    cycle_id=event.cycle_id,
                )

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
        self._strategy_lookup_cache = None
        result.positions_opened += 1
        self.activity_log.append(
            ActivityEventType.POSITION_OPENED,
            f"Opened {proposal.symbol} {proposal.signal} qty={trade.entry_quantity}",
            details={
                "proposal_id": proposal.proposal_id,
                "sub_account_id": proposal.sub_account_id,
                "trade_id": trade.id,
                "symbol": proposal.symbol,
                "side": proposal.signal,
                "entry_price": str(proposal.entry_price),
                "quantity": str(trade.entry_quantity),
                "leverage": proposal.leverage,
            },
            cycle_id=cycle_id,
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
        rejected_record = record.model_copy(
            update={
                "decision": ProposalDecision.REJECTED.value,
                "rejection_reason": reason,
                "decision_at": now_utc(),
            }
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

        rejected_record = record.model_copy(
            update={
                "decision": ProposalDecision.REJECTED.value,
                "rejection_reason": reason,
                "decision_at": now_utc(),
            }
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
        rejected_record = record.model_copy(
            update={
                "decision": ProposalDecision.REJECTED.value,
                "rejection_reason": reason,
                "decision_at": now_utc(),
            }
        )
        events.append(
            GateActivityEvent(
                ActivityEventType.PROPOSAL_REJECTED,
                f"Correlation-rejected {proposal.symbol} {proposal.signal}",
                {
                    **_proposal_summary(proposal),
                    "reason": reason,
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
                "detail": detail,
                "proposal_stop_loss": str(proposal.stop_loss),
            },
            cycle_id=cycle_id,
        )

    async def _monitor(
        self,
        cycle_id: str,
        result: CycleResult,
        sub_account: SubAccount | None,
        trader: Trader,
        exchange: BaseExchange | None = None,
    ) -> None:
        """Check SL/TP for every open paper position; close on hit.

        Per-trade ticker errors are logged and skipped — one stale
        symbol shouldn't block the rest of the monitor pass.

        After the SL/TP check, if neither bound triggered we evaluate
        the per-strategy time-stop (``TechniqueInfo.max_bars_held``,
        or :func:`default_max_bars_held` for the strategy's primary
        timeframe). The 12-day Fly paper run had 44 open vs 41 closed
        trades because trades only ever exited on SL/TP — strategies
        whose thesis decays fast (mean-reversion, ORB) sat
        indefinitely. The time-stop is *strictly* a fallback: SL and
        TP win when they fire on the same monitor pass.
        """
        open_trades = trader.get_open_trades()
        closed_count = 0
        account_exchange = exchange or self.exchange

        # Cache strategy lookups across the loop — multiple open
        # trades from the same technique are common, and each lookup
        # touches the proposal engine's strategy registry.
        time_stop_lookup_cache: dict[str, tuple[int, str] | None] = {}

        for trade in open_trades:
            if self._missing_position_state(trader, trade.id):
                message = (
                    f"Open trade {trade.id} has no in-memory position state; "
                    "operator reconciliation required before SL/TP monitoring"
                )
                self.activity_log.append(
                    ActivityEventType.MONITOR_ERRORED,
                    message,
                    details={
                        "trade_id": trade.id,
                        "sub_account_id": self._sub_account_id(sub_account),
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
                continue
            try:
                ticker = await account_exchange.get_ticker(trade.symbol)
            except Exception as e:
                self.activity_log.append(
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

            # SL/TP not hit — evaluate the per-strategy time-stop. The
            # SL/TP check above always runs first so a price that hits
            # the bound on the same monitor pass exits with the bound's
            # reason, not ``time_stop``.
            time_stopped = await self._maybe_time_stop(
                trade,
                ticker.price,
                trader,
                cycle_id,
                time_stop_lookup_cache,
            )
            if time_stopped:
                closed_count += 1

        result.positions_closed = closed_count
        self.activity_log.append(
            ActivityEventType.MONITOR_PASS,
            f"Monitor pass: {len(open_trades)} open, {closed_count} closed",
            details={
                "open_count": len(open_trades),
                "closed": closed_count,
                "sub_account_id": self._sub_account_id(sub_account),
            },
            cycle_id=cycle_id,
        )

    async def _maybe_time_stop(
        self,
        trade: TradeHistory,
        current_price: Decimal,
        trader: Trader,
        cycle_id: str,
        lookup_cache: dict[str, tuple[int, str] | None],
    ) -> bool:
        """Force-close ``trade`` if it has exceeded its time-stop window.

        Returns ``True`` when the trade was closed so ``_monitor`` can
        bump its ``closed_count``. Returns ``False`` when the trade is
        still inside its window or when the close call returned
        ``None`` (already gone).
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
        self.activity_log.append(
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

        Walks the proposal history because :class:`TradeHistory` does
        not carry the technique name directly. Returns ``None`` when no
        proposal links to the trade — the caller falls back to
        timeframe defaults.
        """
        record = self._find_proposal_record_for_trade(trade.id)
        if record is None:
            return None
        return record.proposal.technique_name

    def _resolve_time_stop_window(
        self, technique_name: str | None
    ) -> tuple[int, str] | None:
        """Resolve the ``(max_bars, timeframe)`` for a technique.

        ``technique_name=None`` (no linked proposal) and the
        unknown-technique branch both default to a ``"1h"`` timeframe
        so the runtime applies a consistent fallback. Returns ``None``
        only when ``max_bars`` would be non-positive — which the
        ``TechniqueInfo`` ``ge=1`` constraint prevents on legitimate
        overrides; the guard exists to keep the loop defensive.
        """
        timeframe = "1h"
        override: int | None = None
        if technique_name is not None:
            strategy = self.proposal_engine.strategies.get(technique_name)
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

    async def _record_portfolio_snapshot(
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
        account_exchange = exchange or self.exchange
        for trade in trader.get_open_trades():
            try:
                ticker = await account_exchange.get_ticker(trade.symbol)
            except Exception:
                continue
            current_prices[trade.symbol] = ticker.price

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
                "sub_account_id": trade.sub_account_id,
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

    def _active_sub_accounts(self) -> list[SubAccount | None]:
        if self.sub_account_registry is None:
            return [None]
        active: list[SubAccount | None] = list(self.sub_account_registry.list_active())
        return active

    def _sub_account_id(self, sub_account: SubAccount | None) -> str:
        return sub_account.id if sub_account is not None else DEFAULT_SUB_ACCOUNT_ID

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
    """Compact dict used as the ``details`` payload for proposal events."""
    return {
        "proposal_id": proposal.proposal_id,
        "sub_account_id": proposal.sub_account_id,
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
    "ErrorCategory",
    "TradingEngine",
]
