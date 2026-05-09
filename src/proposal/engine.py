"""Trading proposal engine.

Given an exchange, a population of analysis techniques, and historical
performance data, ``ProposalEngine`` produces ``Proposal`` objects:
fully-priced trade ideas (entry / SL / TP / quantity / leverage)
ranked by a composite score combining the analysis confidence with
the underlying technique's demonstrated edge.

Two top-level entry points map directly to the requirements:

* ``propose_bitcoin`` (FR-011) — single-symbol focused proposal,
  defaults to ``BTC/USDT``.
* ``propose_altcoins`` (FR-012) — multi-symbol scan returning the
  top-K highest-scoring proposals.

Both share a private ``_propose_for_symbol`` worker that does the
real work: fetch OHLCV → pick best technique → run analysis →
size the position via ``TradingStrategy`` → score the result.

The engine is intentionally **headless** — it returns data, not
user-facing output. CLI display, accept/reject handling, and
proposal history are 6.2's concern; notifications are 6.3's.
Keeping 6.1 free of I/O makes it trivially testable and reusable
across the eventual Streamlit dashboard, CLI, and notification
paths.

Related Requirements:
- FR-011: Bitcoin Trading Proposal
- FR-012: Altcoin Trading Proposal
- FR-005: Analysis Technique Performance Tracking (consumed)
- FR-006/7/8: R/R, leverage, SL/TP — delegated to ``TradingStrategy``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.ai.exceptions import ClaudeTimeoutError
from src.exchange.base import BaseExchange, ExchangeError
from src.logger import get_logger
from src.models import OHLCV, AnalysisResult
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.strategy.base import BaseStrategy, StrategyError
from src.strategy.performance import PerformanceTracker, TechniquePerformance
from src.strategy.prompt_filters import should_run_prompt_strategy
from src.trading.strategy import TradingStrategy, TradingValidationError
from src.utils.pydantic_mixins import UtcTimestampMixin
from src.utils.time import ensure_utc, now_utc
from src.utils.trading_types import PositionSide

logger = get_logger("crypto_master.proposal.engine")


Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"]


# =============================================================================
# Errors
# =============================================================================


class ProposalEngineError(Exception):
    """Base exception for proposal-engine errors."""


# =============================================================================
# Models
# =============================================================================


class ProposalScore(BaseModel):
    """Why a proposal ranks where it does.

    All factors are surfaced (not just the composite) so callers can
    explain the ranking to the user — e.g. "this scored low because
    the technique only has 3 trades of history."

    Attributes:
        confidence: Analysis confidence in [0, 1].
        win_rate: Technique win rate in [0, 1], 0 if no history.
        sample_size: Number of closed trades the technique has.
        expected_value: Per-trade expected P&L (% of entry).
            From ``TechniquePerformance.avg_pnl_percent``; 0 if no history.
        sample_factor: ``min(1, sample_size / min_trades_for_full_score)``.
            Approaches 1 as the technique accumulates history.
        edge_factor: ``max(0, expected_value)``. Negative-EV techniques
            contribute zero — we never want to recommend a known loser.
        composite: Final ranking number — higher is better.
    """

    confidence: float
    win_rate: float
    sample_size: int
    expected_value: float
    sample_factor: float
    edge_factor: float
    composite: float


class Proposal(UtcTimestampMixin, BaseModel):
    """A trade idea ready for the user-interaction layer.

    Attributes:
        proposal_id: UUID generated at construction.
        created_at: When the proposal was built.
        symbol: Trading pair, e.g. ``"BTC/USDT"``.
        timeframe: Candle timeframe used for the analysis.
        technique_name / technique_version: Which technique fired.
        profile_name: Trading profile applied, if any.
        sub_account_id: Capital bucket this proposal belongs to. Defaults
            to ``"default"`` so legacy serialized histories load unchanged.
        signal: ``"long"`` or ``"short"`` — neutral signals never
            become proposals.
        entry_price / stop_loss / take_profit: Trade prices from the
            analysis (not slippage-adjusted; that happens at fill time).
        quantity / leverage: Sizing from ``TradingStrategy.create_position``.
        risk_reward_ratio: ``|tp − entry| / |entry − sl|``.
        score: Why this proposal ranks where it does.
        reasoning: Free-form analysis reasoning from the technique.
    """

    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=now_utc)
    symbol: str
    timeframe: str
    technique_name: str
    technique_version: str
    profile_name: str | None = None
    sub_account_id: str = "default"
    signal: PositionSide
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    quantity: Decimal
    leverage: int
    risk_reward_ratio: float
    score: ProposalScore
    reasoning: str = ""


class ProposalEngineConfig(BaseModel):
    """Tunables for the engine.

    Defaults are deliberately conservative. The score formula is
    documented on ``ProposalScore``.

    Attributes:
        timeframe: Candle timeframe used for fresh analysis.
        ohlcv_limit: How many candles to fetch per symbol. The
            strategy decides how much warm-up it needs internally;
            this is the upper bound.
        default_balance: Balance assumed for sizing when the caller
            doesn't supply one.
        leverage: Leverage applied to all proposals from this engine.
        risk_percent: Percent of balance risked per proposal.
        min_trades_for_full_score: Sample-size threshold above which
            the score's ``sample_factor`` saturates at 1.0.
        no_history_score_factor: When a technique has zero history,
            its composite is ``confidence × this``. Lets a brand-new
            system still produce proposals while making it clear they
            are unproven.
    """

    timeframe: Timeframe = "1h"
    ohlcv_limit: int = Field(default=200, ge=20)
    default_balance: Decimal = Decimal("10000")
    leverage: int = Field(default=1, ge=1, le=125)
    risk_percent: float = Field(default=1.0, gt=0, le=100)
    min_trades_for_full_score: int = Field(default=20, ge=1)
    no_history_score_factor: float = Field(default=0.5, ge=0, le=1)
    multi_technique_per_symbol: bool = True
    """If True (default, Phase 10.6), every applicable technique is run
    per symbol and the highest-composite candidate per symbol survives
    the per-symbol dedup. If False, the legacy single-best-technique
    path (``_select_best_technique``) is used unchanged. Per-symbol
    dedup is a real-money safety guard: without it, the runtime engine
    would open N positions per symbol per cycle at N× the intended
    risk_percent."""

    # Phase 24.1 / DEBT-034: cold-start guard on live promotion.
    # When ``mode == "live"`` and no applicable technique has at least
    # ``min_closed_trades_for_live_promotion`` closed trades, the
    # engine returns no proposal for the symbol — real money does not
    # go to a technique whose composite is the cold-start placeholder
    # ``confidence × no_history_score_factor`` (where ties otherwise
    # fall to alphabetical name order). In paper mode the behavior is
    # unchanged so techniques can still bootstrap their performance
    # history.
    mode: Literal["paper", "live"] = "paper"
    min_closed_trades_for_live_promotion: int = Field(default=5, ge=0)
    prompt_strategy_min_interval_seconds: int = Field(default=0, ge=0)
    """Minimum seconds between prompt-based strategy executions per
    ``(strategy, symbol)``. ``0`` preserves the historical behaviour.
    Operators can raise this in long-running runtimes so Claude-backed
    prompt strategies do not consume tokens on every engine cycle."""


# =============================================================================
# Helpers
# =============================================================================


def _dedup_by_symbol(candidates: list[Proposal]) -> dict[str, Proposal]:
    """Phase 10.6: keep only the highest-composite proposal per symbol.

    Group key is the symbol alone — never ``(symbol, side)``. If two
    techniques produced opposing signals on the same pair (long vs
    short conflict), the higher-composite one still wins; we never
    let both through, because the runtime engine would otherwise open
    a synthetic hedge at 2× ``risk_percent`` (real-money defect).

    Replacement is on **strict** composite improvement so the iteration
    order of ``candidates`` provides the tiebreaker, matching the
    deterministic lex-by-name order of ``_select_all_techniques``.
    """
    best: dict[str, Proposal] = {}
    for candidate in candidates:
        existing = best.get(candidate.symbol)
        if existing is None or candidate.score.composite > existing.score.composite:
            best[candidate.symbol] = candidate
    return best


# =============================================================================
# Engine
# =============================================================================


class ProposalEngine:
    """Produce ranked trading proposals from techniques + market data.

    Stateless across calls: every ``propose_*`` invocation re-fetches
    OHLCV and re-evaluates technique performance, so callers always
    see current data. The engine does **not** open the exchange
    connection — pass in a connected ``BaseExchange`` (or use
    ``async with`` yourself).
    """

    def __init__(
        self,
        exchange: BaseExchange,
        strategies: dict[str, BaseStrategy],
        performance_tracker: PerformanceTracker | None = None,
        trading_strategy: TradingStrategy | None = None,
        config: ProposalEngineConfig | None = None,
        activity_log: ActivityLog | None = None,
    ) -> None:
        """Initialize the engine.

        Args:
            exchange: Connected exchange used to fetch fresh OHLCV.
            strategies: ``{name: BaseStrategy}`` — the population the
                engine picks from. Typically the result of
                ``load_all_strategies()``.
            performance_tracker: Source of historical performance data.
                If omitted, a fresh ``PerformanceTracker()`` is used,
                which reads from ``data/performance/``.
            trading_strategy: Position-sizing helper. Defaults to a
                fresh ``TradingStrategy()`` with settings-derived config.
            config: Engine tunables. Defaults to ``ProposalEngineConfig()``.
            activity_log: Optional activity log (Phase 12.3). When
                supplied, the engine emits ``LLM_TIMEOUT`` events
                whenever a strategy raises :class:`ClaudeTimeoutError`
                so the dashboard can surface LLM reliability. Default
                ``None`` keeps backward compatibility for tests and
                callers that do not need activity logging.
        """
        self.exchange = exchange
        self.strategies = strategies
        self.performance_tracker = performance_tracker or PerformanceTracker()
        self.trading_strategy = trading_strategy or TradingStrategy()
        self.config = config or ProposalEngineConfig()
        self.activity_log = activity_log
        self._prompt_strategy_last_run_at: dict[tuple[str, str], datetime] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def propose_bitcoin(
        self,
        symbol: str = "BTC/USDT",
        balance: Decimal | None = None,
        timeframe: str | None = None,
        strategies: list[BaseStrategy] | None = None,
        risk_percent: float | None = None,
        leverage: int | None = None,
        sub_account_id: str = "default",
    ) -> Proposal | None:
        """FR-011: best-technique proposal for a single symbol.

        Returns ``None`` when the chosen technique produced a neutral
        signal, when no technique exists for the symbol, or when the
        resulting trade fails sizing/validation. Exchange errors
        propagate — single-symbol intent means the caller should hear
        about them.

        When ``ProposalEngineConfig.multi_technique_per_symbol`` is True
        (Phase 10.6 default), every applicable technique is run for the
        symbol and the highest-composite candidate is returned. When
        False, the legacy single-best-technique path is used unchanged.
        Either way the contract is the same: at most one proposal per
        symbol, never more — opening multiple positions on the same
        pair from concurrent technique signals would multiply
        ``risk_percent`` by N (real-money defect).
        """
        tf = timeframe or self.config.timeframe
        bal = balance or self.config.default_balance

        # Per-call OHLCV cache (Phase 11.2 / DEBT-002). Keyed by
        # ``(symbol, timeframe)`` so multi-TF strategies share fetches
        # across timeframes too. Lifetime is exactly this invocation —
        # the next call gets a fresh dict so strategies always see
        # current candles.
        cache: dict[tuple[str, str], list[OHLCV]] = {}

        if not self.config.multi_technique_per_symbol:
            return await self._propose_for_symbol(
                symbol=symbol,
                timeframe=tf,
                balance=bal,
                ohlcv_cache=cache,
                strategies=strategies,
                risk_percent=risk_percent,
                leverage=leverage,
                sub_account_id=sub_account_id,
            )

        # Multi-technique path: run every applicable technique, dedup
        # by symbol (highest composite wins), return the single
        # survivor.
        candidates = await self._propose_all_for_symbol(
            symbol=symbol,
            timeframe=tf,
            balance=bal,
            ohlcv_cache=cache,
            strategies=strategies,
            risk_percent=risk_percent,
            leverage=leverage,
            sub_account_id=sub_account_id,
        )
        if not candidates:
            return None
        deduped = _dedup_by_symbol(candidates)
        return deduped.get(symbol)

    async def propose_altcoins(
        self,
        symbols: list[str],
        balance: Decimal | None = None,
        timeframe: str | None = None,
        top_k: int = 3,
        strategies: list[BaseStrategy] | None = None,
        risk_percent: float | None = None,
        leverage: int | None = None,
        sub_account_id: str = "default",
    ) -> list[Proposal]:
        """FR-012: scan symbols and return the top-K highest-scored.

        A single bad symbol (exchange error, strategy crash, neutral
        analysis) is logged and skipped — the scan continues so one
        flaky pair doesn't kill the whole batch.

        Args:
            symbols: Symbols to scan, e.g. ``["ETH/USDT", "SOL/USDT"]``.
            balance: Sizing balance applied to every proposal.
            timeframe: Override the engine's default timeframe.
            top_k: Maximum number of proposals returned.

        Returns:
            Up to ``top_k`` proposals, sorted by composite score
            descending. Empty if nothing qualified.
        """
        if top_k < 1:
            raise ProposalEngineError("top_k must be >= 1")

        tf = timeframe or self.config.timeframe
        bal = balance or self.config.default_balance

        # Per-call OHLCV cache (Phase 11.2 / DEBT-002). Shared across
        # every symbol in this scan so a multi-TF strategy that overlaps
        # symbols doesn't refetch the same ``(symbol, tf)`` pair.
        cache: dict[tuple[str, str], list[OHLCV]] = {}

        candidates: list[Proposal] = []
        for symbol in symbols:
            try:
                if self.config.multi_technique_per_symbol:
                    per_symbol = await self._propose_all_for_symbol(
                        symbol=symbol,
                        timeframe=tf,
                        balance=bal,
                        ohlcv_cache=cache,
                        strategies=strategies,
                        risk_percent=risk_percent,
                        leverage=leverage,
                        sub_account_id=sub_account_id,
                    )
                    candidates.extend(per_symbol)
                else:
                    proposal = await self._propose_for_symbol(
                        symbol=symbol,
                        timeframe=tf,
                        balance=bal,
                        ohlcv_cache=cache,
                        strategies=strategies,
                        risk_percent=risk_percent,
                        leverage=leverage,
                        sub_account_id=sub_account_id,
                    )
                    if proposal is not None:
                        candidates.append(proposal)
            except ExchangeError as e:
                logger.warning(f"Exchange error scanning {symbol}: {e}; skipping")
                continue
            except StrategyError as e:
                logger.warning(f"Strategy error on {symbol}: {e}; skipping")
                continue

        # Order matters (Phase 10.6): dedup by symbol FIRST so each
        # symbol contributes at most one proposal, then top-K across
        # the cross-symbol set. Sorting first then deduping would
        # change the K-th selection — see the dev plan for FR-012's
        # diversification semantic.
        if self.config.multi_technique_per_symbol:
            deduped = list(_dedup_by_symbol(candidates).values())
        else:
            # Legacy path already returns ≤ 1 per symbol from
            # ``_propose_for_symbol`` — nothing to dedup.
            deduped = candidates

        deduped.sort(key=lambda p: p.score.composite, reverse=True)
        return deduped[:top_k]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _propose_for_symbol(
        self,
        symbol: str,
        timeframe: str,
        balance: Decimal,
        ohlcv_cache: dict[tuple[str, str], list[OHLCV]] | None = None,
        strategies: list[BaseStrategy] | None = None,
        risk_percent: float | None = None,
        leverage: int | None = None,
        sub_account_id: str = "default",
    ) -> Proposal | None:
        """Build a proposal for one symbol, or return None if unfit.

        Legacy single-best-technique path — used when
        ``ProposalEngineConfig.multi_technique_per_symbol`` is False
        and preserved bit-for-bit so the opt-out is a clean back-compat
        switch.

        Exchange errors propagate; strategy errors and validation
        errors return None (logged) so this method is safe to call
        from the multi-symbol scanner with try/except per symbol.

        ``ohlcv_cache`` is the per-call cache threaded from the public
        entry point (Phase 11.2 / DEBT-002). When omitted, a fresh
        local dict is used so direct callers (e.g. tests) still work.
        """
        if self._cold_start_blocks_live(symbol, strategies=strategies):
            return None
        selection = self._select_best_technique(symbol, strategies=strategies)
        if selection is None:
            logger.info(f"No applicable technique for {symbol}; skipping proposal")
            return None
        strategy, perf = selection
        return await self._build_proposal_for_strategy(
            symbol=symbol,
            timeframe=timeframe,
            balance=balance,
            strategy=strategy,
            perf=perf,
            ohlcv_cache=ohlcv_cache if ohlcv_cache is not None else {},
            risk_percent=risk_percent,
            leverage=leverage,
            sub_account_id=sub_account_id,
        )

    async def _propose_all_for_symbol(
        self,
        symbol: str,
        timeframe: str,
        balance: Decimal,
        ohlcv_cache: dict[tuple[str, str], list[OHLCV]] | None = None,
        strategies: list[BaseStrategy] | None = None,
        risk_percent: float | None = None,
        leverage: int | None = None,
        sub_account_id: str = "default",
    ) -> list[Proposal]:
        """Phase 10.6: run every applicable technique for ``symbol``.

        Returns one ``Proposal`` per applicable technique that produced
        a non-neutral, sizing-valid result. Caller is responsible for
        per-symbol dedup (the entry points
        ``propose_bitcoin`` / ``propose_altcoins`` enforce ≤ 1 proposal
        per symbol). Exchange errors propagate; strategy / validation
        errors are logged and skipped per technique so one flaky
        technique can't block the rest.

        ``ohlcv_cache`` is the per-call cache threaded from the public
        entry point (Phase 11.2 / DEBT-002). When omitted, a fresh
        local dict is used so direct callers (e.g. tests) still work.
        """
        if self._cold_start_blocks_live(symbol, strategies=strategies):
            return []
        selections = self._select_all_techniques(symbol, strategies=strategies)
        if not selections:
            logger.info(f"No applicable technique for {symbol}; skipping proposal")
            return []

        cache = ohlcv_cache if ohlcv_cache is not None else {}
        proposals: list[Proposal] = []
        for strategy, perf in selections:
            proposal = await self._build_proposal_for_strategy(
                symbol=symbol,
                timeframe=timeframe,
                balance=balance,
                strategy=strategy,
                perf=perf,
                ohlcv_cache=cache,
                risk_percent=risk_percent,
                leverage=leverage,
                sub_account_id=sub_account_id,
            )
            if proposal is not None:
                proposals.append(proposal)
        return proposals

    async def _build_proposal_for_strategy(
        self,
        *,
        symbol: str,
        timeframe: str,
        balance: Decimal,
        strategy: BaseStrategy,
        perf: TechniquePerformance | None,
        ohlcv_cache: dict[tuple[str, str], list[OHLCV]],
        risk_percent: float | None = None,
        leverage: int | None = None,
        sub_account_id: str = "default",
    ) -> Proposal | None:
        """Run ``strategy`` against fresh OHLCV and build a Proposal.

        Returns ``None`` for neutral signals, strategy crashes,
        empty-multi-TF-primary, and sizing-validation failures.
        Exchange errors propagate so the multi-symbol scanner can
        skip the symbol uniformly.
        """
        if self._should_skip_prompt_strategy(strategy, symbol):
            return None

        # Exchange calls propagate — let propose_altcoins decide how to
        # handle per-symbol failures (the existing per-symbol skip in
        # ``propose_altcoins`` covers both single-TF and multi-TF fetch
        # failures uniformly).
        #
        # Phase 11.2 / DEBT-002: every fetch goes through ``ohlcv_cache``
        # (keyed by ``(symbol, timeframe)``) so N applicable techniques
        # share at most M fetches per symbol, and so all techniques in
        # the same call see the same candle T (no temporal drift if a
        # candle rolls mid-cycle).
        ohlcv_context = await self._fetch_and_validate_ohlcv(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            ohlcv_cache=ohlcv_cache,
        )
        if ohlcv_context is None:
            return None
        primary_timeframe, primary_ohlcv, ohlcv_by_tf, current_price = ohlcv_context

        if not self._prompt_trigger_allows(
            strategy,
            symbol,
            primary_ohlcv,
            ohlcv_by_timeframe=ohlcv_by_tf,
            current_price=current_price,
        ):
            return None
        self._mark_prompt_strategy_run(strategy, symbol)
        try:
            if ohlcv_by_tf is not None:
                analysis = await strategy.analyze(
                    primary_ohlcv,
                    symbol,
                    primary_timeframe,
                    ohlcv_by_timeframe=ohlcv_by_tf,
                    current_price=current_price,
                )
            else:
                analysis = await strategy.analyze(
                    primary_ohlcv,
                    symbol,
                    primary_timeframe,
                )
        except StrategyError as e:
            self._handle_strategy_error(e, strategy, symbol)
            return None

        if analysis.signal == "neutral":
            logger.info(f"{strategy.name} returned neutral on {symbol}; " "no proposal")
            return None

        try:
            position = self.trading_strategy.create_position(
                analysis=analysis,
                symbol=symbol,
                balance=balance,
                leverage=leverage if leverage is not None else self.config.leverage,
                risk_percent=(
                    risk_percent
                    if risk_percent is not None
                    else self.config.risk_percent
                ),
            )
        except TradingValidationError as e:
            logger.info(f"Position rejected for {symbol} via {strategy.name}: {e}")
            return None

        rr = analysis.risk_reward_ratio or 0.0
        score = self._score(analysis, perf)

        return Proposal(
            symbol=symbol,
            timeframe=primary_timeframe,
            technique_name=strategy.name,
            technique_version=strategy.version,
            sub_account_id=sub_account_id,
            signal=position.side,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss or analysis.stop_loss,
            take_profit=position.take_profit or analysis.take_profit,
            quantity=position.quantity,
            leverage=position.leverage,
            risk_reward_ratio=rr,
            score=score,
            reasoning=analysis.reasoning,
        )

    async def _fetch_and_validate_ohlcv(
        self,
        *,
        strategy: BaseStrategy,
        symbol: str,
        timeframe: str,
        ohlcv_cache: dict[tuple[str, str], list[OHLCV]],
    ) -> tuple[str, list[OHLCV], dict[str, list[OHLCV]] | None, Decimal | None] | None:
        """Fetch cached OHLCV and return the primary stream for analysis."""
        if strategy.info.requires_multi_timeframe and strategy.info.timeframes:
            tfs = strategy.info.timeframes
            ohlcv_by_tf: dict[str, list[OHLCV]] = {}
            for tf in tfs:
                ohlcv_by_tf[tf] = await self._fetch_ohlcv_cached(
                    symbol=symbol,
                    timeframe=tf,
                    ohlcv_cache=ohlcv_cache,
                )
            primary_tf = tfs[-1]
            primary_ohlcv = ohlcv_by_tf[primary_tf]
            if not primary_ohlcv:
                logger.warning(
                    f"Multi-TF fetch returned no candles on {symbol} for "
                    f"{primary_tf}; skipping proposal"
                )
                return None
            return primary_tf, primary_ohlcv, ohlcv_by_tf, primary_ohlcv[-1].close

        primary_ohlcv = await self._fetch_ohlcv_cached(
            symbol=symbol,
            timeframe=timeframe,
            ohlcv_cache=ohlcv_cache,
        )
        current_price = primary_ohlcv[-1].close if primary_ohlcv else None
        return timeframe, primary_ohlcv, None, current_price

    async def _fetch_ohlcv_cached(
        self,
        *,
        symbol: str,
        timeframe: str,
        ohlcv_cache: dict[tuple[str, str], list[OHLCV]],
    ) -> list[OHLCV]:
        key = (symbol, timeframe)
        cached = ohlcv_cache.get(key)
        if cached is not None:
            return cached
        fetched = await self.exchange.get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,  # type: ignore[arg-type]
            limit=self.config.ohlcv_limit,
        )
        ohlcv_cache[key] = fetched
        return fetched

    def _prompt_trigger_allows(
        self,
        strategy: BaseStrategy,
        symbol: str,
        primary_ohlcv: list[OHLCV],
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None,
        current_price: Decimal | None,
    ) -> bool:
        decision = should_run_prompt_strategy(
            strategy,
            primary_ohlcv,
            ohlcv_by_timeframe=ohlcv_by_timeframe,
            current_price=current_price,
        )
        if decision.allowed:
            return True

        logger.info(
            "Skipping prompt strategy %s on %s: trigger filter blocked (%s)",
            strategy.name,
            symbol,
            decision.reason,
        )
        return False

    def _should_skip_prompt_strategy(self, strategy: BaseStrategy, symbol: str) -> bool:
        """Return True when a prompt strategy is still inside cooldown."""
        min_interval = self.config.prompt_strategy_min_interval_seconds
        if min_interval <= 0 or strategy.info.technique_type != "prompt":
            return False

        key = (strategy.name, symbol)
        last_run_at = self._prompt_strategy_last_run_at.get(key)
        if last_run_at is None:
            return False

        elapsed = (now_utc() - ensure_utc(last_run_at)).total_seconds()
        if elapsed >= min_interval:
            return False

        logger.info(
            "Skipping prompt strategy %s on %s: cooldown %.0fs remaining",
            strategy.name,
            symbol,
            min_interval - elapsed,
        )
        return True

    def _mark_prompt_strategy_run(self, strategy: BaseStrategy, symbol: str) -> None:
        """Record prompt strategy execution time before token-spending work."""
        if (
            self.config.prompt_strategy_min_interval_seconds <= 0
            or strategy.info.technique_type != "prompt"
        ):
            return
        self._prompt_strategy_last_run_at[(strategy.name, symbol)] = now_utc()

    def _handle_strategy_error(
        self,
        error: StrategyError,
        strategy: BaseStrategy,
        symbol: str,
    ) -> None:
        """Log a strategy failure and emit ``LLM_TIMEOUT`` for timeouts.

        Phase 12.3: when ``error`` is a :class:`ClaudeTimeoutError` and
        an :class:`ActivityLog` is wired in, this records one
        ``LLM_TIMEOUT`` event so the dashboard can show LLM reliability
        over time. The ``timeout_seconds`` attribute on the error
        captures the *final* (post-retry) timeout the wrapper gave up
        at, which is the most informative number for an operator
        triaging "should I bump ``CLAUDE_CLI_TIMEOUT_SECONDS``?".

        Phase 14.1: the event also carries ``attempt_number`` (1-indexed
        attempt that raised) and ``final_timeout_seconds`` (alias of
        ``timeout_seconds`` for clarity in the dashboard) so operators
        can distinguish "first-attempt fail, no retry path firing"
        from "every attempt timed out — bump the per-strategy override".
        The original ``timeout_seconds`` key is preserved for
        back-compat with downstream readers that already parse it.
        """
        logger.warning(f"Strategy {strategy.name} failed on {symbol}: {error}")
        if not isinstance(error, ClaudeTimeoutError):
            return
        if self.activity_log is None:
            return
        self.activity_log.append(
            ActivityEventType.LLM_TIMEOUT,
            f"LLM timeout: {strategy.name} on {symbol}",
            details={
                "strategy_name": strategy.name,
                "strategy_version": strategy.version,
                "symbol": symbol,
                "timeout_seconds": error.timeout_seconds,
                "attempt_number": error.attempt_number,
                "final_timeout_seconds": error.timeout_seconds,
            },
        )

    def _select_best_technique(
        self,
        symbol: str,
        strategies: list[BaseStrategy] | None = None,
    ) -> tuple[BaseStrategy, TechniquePerformance | None] | None:
        """Pick the technique most likely to produce a useful proposal.

        Filters strategies down to those whose ``info.symbols``
        includes the target symbol (or has no symbol filter), then
        ranks them by:

        1. ``edge_factor`` (positive expected value), descending.
        2. ``total_trades``, descending — more data wins ties.
        3. Lex-first by name, descending — deterministic last resort.

        If no strategy has any history at all, returns the
        lex-first applicable strategy with ``perf=None`` so the caller
        can still produce a confidence-driven proposal.
        """
        population = (
            strategies if strategies is not None else list(self.strategies.values())
        )
        applicable = [
            s for s in population if not s.info.symbols or symbol in s.info.symbols
        ]
        if not applicable:
            return None

        ranked: list[tuple[BaseStrategy, TechniquePerformance]] = []
        for strategy in applicable:
            perf = self.performance_tracker.get_performance(
                strategy.name, strategy.version
            )
            ranked.append((strategy, perf))

        any_history = any(perf.total_trades > 0 for _, perf in ranked)
        if not any_history:
            # Cold-start: nobody has run yet. Pick deterministically.
            applicable.sort(key=lambda s: s.name)
            return (applicable[0], None)

        def key(
            item: tuple[BaseStrategy, TechniquePerformance],
        ) -> tuple[float, int, str]:
            strategy, perf = item
            edge = max(0.0, perf.avg_pnl_percent)
            # Negate numeric fields so larger values sort first in an
            # ascending sort; ``strategy.name`` stays positive so the
            # lex-first name wins ties deterministically.
            return (-edge, -perf.total_trades, strategy.name)

        ranked.sort(key=key)
        best_strategy, best_perf = ranked[0]
        return (best_strategy, best_perf if best_perf.total_trades > 0 else None)

    def _cold_start_blocks_live(
        self,
        symbol: str,
        strategies: list[BaseStrategy] | None = None,
    ) -> bool:
        """Phase 24.1 / DEBT-034: live mode + no qualifying technique → block.

        Returns True iff:

        * ``config.mode == "live"`` (paper mode is unaffected), AND
        * No applicable technique for ``symbol`` has at least
          ``min_closed_trades_for_live_promotion`` closed trades.

        When True, the caller short-circuits and returns no proposal.
        Without this guard, real money could go to whichever cold-start
        technique sorts first alphabetically, since their composite
        scores collapse to ``confidence × no_history_score_factor`` and
        ``_select_best_technique`` falls back to lex-first by name on a
        tie.
        """
        if self.config.mode != "live":
            return False
        threshold = self.config.min_closed_trades_for_live_promotion
        if threshold <= 0:
            return False
        population = (
            strategies if strategies is not None else list(self.strategies.values())
        )
        applicable = [
            s for s in population if not s.info.symbols or symbol in s.info.symbols
        ]
        if not applicable:
            return False  # No-applicable-technique path is handled by callers.
        # Build a per-technique trade-count snapshot up-front so the
        # activity event payload can show operators *why* the bot is
        # idle (which techniques fell short and by how much). The
        # iteration is short (one record per applicable technique) so
        # the loop fuses cleanly with the threshold short-circuit
        # below.
        per_technique: dict[str, int] = {}
        max_trades = 0
        for strategy in applicable:
            perf = self.performance_tracker.get_performance(
                strategy.name, strategy.version
            )
            per_technique[strategy.name] = perf.total_trades
            if perf.total_trades > max_trades:
                max_trades = perf.total_trades
            if perf.total_trades >= threshold:
                return False
        logger.info(
            "live cold-start guard: no applicable technique on %s has "
            ">= %d closed trades; skipping proposal "
            "(min_closed_trades_for_live_promotion)",
            symbol,
            threshold,
        )
        # Phase 24.2 / DEBT-034 follow-up: emit a structured activity
        # event so the dashboard surfaces the deliberate idle state.
        # ``logger.info`` alone is invisible to operators reading the
        # dashboard timeline; the activity event closes that gap.
        if self.activity_log is not None:
            self.activity_log.append(
                ActivityEventType.COLD_START_BLOCKED,
                (
                    f"Cold-start guard: no applicable technique on "
                    f"{symbol} has >= {threshold} closed trades"
                ),
                details={
                    "symbol": symbol,
                    "reason": "cold_start_below_min_closed_trades",
                    "min_closed_trades_for_live_promotion": threshold,
                    "max_trades_observed": max_trades,
                    "per_technique_trades": per_technique,
                },
            )
        return True

    def _select_all_techniques(
        self,
        symbol: str,
        strategies: list[BaseStrategy] | None = None,
    ) -> list[tuple[BaseStrategy, TechniquePerformance | None]]:
        """Phase 10.6: every applicable technique for ``symbol``.

        Filters strategies the same way as ``_select_best_technique``
        (symbol whitelist or no whitelist), but returns the full
        applicable population instead of picking one. Each entry
        carries a ``perf`` record (or ``None`` for cold-start
        techniques with zero closed trades) so the caller can compute
        composite scores via ``_score`` exactly as the legacy path
        does.

        Order is lex by strategy name — deterministic for tests; the
        actual ranking happens after analysis on the composite score.
        """
        population = (
            strategies if strategies is not None else list(self.strategies.values())
        )
        applicable = sorted(
            (s for s in population if not s.info.symbols or symbol in s.info.symbols),
            key=lambda s: s.name,
        )

        results: list[tuple[BaseStrategy, TechniquePerformance | None]] = []
        for strategy in applicable:
            perf = self.performance_tracker.get_performance(
                strategy.name, strategy.version
            )
            # Treat zero-history records as None so ``_score`` takes
            # the cold-start branch — consistent with
            # ``_select_best_technique``.
            results.append((strategy, perf if perf.total_trades > 0 else None))
        return results

    def _score(
        self,
        analysis: AnalysisResult,
        perf: TechniquePerformance | None,
    ) -> ProposalScore:
        """Build a ``ProposalScore`` from an analysis + perf record.

        Score formula::

            sample_factor = min(1, sample_size / min_trades_for_full_score)
            edge_factor   = max(0, expected_value)              # in % units
            composite     = confidence × edge_factor × sample_factor   if perf
                          = confidence × no_history_score_factor       if not perf

        Confidence is clamped defensively to [0, 1] in case a
        strategy returns out-of-spec.
        """
        confidence = max(0.0, min(1.0, analysis.confidence))

        if perf is None or perf.total_trades == 0:
            return ProposalScore(
                confidence=confidence,
                win_rate=0.0,
                sample_size=0,
                expected_value=0.0,
                sample_factor=0.0,
                edge_factor=0.0,
                composite=confidence * self.config.no_history_score_factor,
            )

        sample_factor = min(
            1.0, perf.total_trades / self.config.min_trades_for_full_score
        )
        edge_factor = max(0.0, perf.avg_pnl_percent)
        composite = confidence * edge_factor * sample_factor
        return ProposalScore(
            confidence=confidence,
            win_rate=perf.win_rate,
            sample_size=perf.total_trades,
            expected_value=perf.avg_pnl_percent,
            sample_factor=sample_factor,
            edge_factor=edge_factor,
            composite=composite,
        )


__all__ = [
    "Proposal",
    "ProposalEngine",
    "ProposalEngineConfig",
    "ProposalEngineError",
    "ProposalScore",
]
