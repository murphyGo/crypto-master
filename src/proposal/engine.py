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

from src.exchange.base import BaseExchange, ExchangeError
from src.logger import get_logger
from src.models import AnalysisResult
from src.strategy.base import BaseStrategy, StrategyError
from src.strategy.performance import PerformanceTracker, TechniquePerformance
from src.trading.strategy import TradingStrategy, TradingValidationError

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


class Proposal(BaseModel):
    """A trade idea ready for the user-interaction layer.

    Attributes:
        proposal_id: UUID generated at construction.
        created_at: When the proposal was built.
        symbol: Trading pair, e.g. ``"BTC/USDT"``.
        timeframe: Candle timeframe used for the analysis.
        technique_name / technique_version: Which technique fired.
        profile_name: Trading profile applied, if any.
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
    created_at: datetime = Field(default_factory=datetime.now)
    symbol: str
    timeframe: str
    technique_name: str
    technique_version: str
    profile_name: str | None = None
    signal: Literal["long", "short"]
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
        """
        self.exchange = exchange
        self.strategies = strategies
        self.performance_tracker = performance_tracker or PerformanceTracker()
        self.trading_strategy = trading_strategy or TradingStrategy()
        self.config = config or ProposalEngineConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def propose_bitcoin(
        self,
        symbol: str = "BTC/USDT",
        balance: Decimal | None = None,
        timeframe: str | None = None,
    ) -> Proposal | None:
        """FR-011: best-technique proposal for a single symbol.

        Returns ``None`` when the chosen technique produced a neutral
        signal, when no technique exists for the symbol, or when the
        resulting trade fails sizing/validation. Exchange errors
        propagate — single-symbol intent means the caller should hear
        about them.
        """
        return await self._propose_for_symbol(
            symbol=symbol,
            timeframe=timeframe or self.config.timeframe,
            balance=balance or self.config.default_balance,
        )

    async def propose_altcoins(
        self,
        symbols: list[str],
        balance: Decimal | None = None,
        timeframe: str | None = None,
        top_k: int = 3,
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

        proposals: list[Proposal] = []
        for symbol in symbols:
            try:
                proposal = await self._propose_for_symbol(
                    symbol=symbol, timeframe=tf, balance=bal
                )
            except ExchangeError as e:
                logger.warning(f"Exchange error scanning {symbol}: {e}; skipping")
                continue
            except StrategyError as e:
                logger.warning(f"Strategy error on {symbol}: {e}; skipping")
                continue
            if proposal is not None:
                proposals.append(proposal)

        proposals.sort(key=lambda p: p.score.composite, reverse=True)
        return proposals[:top_k]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _propose_for_symbol(
        self,
        symbol: str,
        timeframe: str,
        balance: Decimal,
    ) -> Proposal | None:
        """Build a proposal for one symbol, or return None if unfit.

        Exchange errors propagate; strategy errors and validation
        errors return None (logged) so this method is safe to call
        from the multi-symbol scanner with try/except per symbol.
        """
        selection = self._select_best_technique(symbol)
        if selection is None:
            logger.info(f"No applicable technique for {symbol}; skipping proposal")
            return None
        strategy, perf = selection

        # Exchange call propagates — let propose_altcoins decide how to
        # handle per-symbol failures.
        ohlcv = await self.exchange.get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,  # type: ignore[arg-type]
            limit=self.config.ohlcv_limit,
        )

        try:
            analysis = await strategy.analyze(ohlcv, symbol, timeframe)
        except StrategyError as e:
            logger.warning(f"Strategy {strategy.name} failed on {symbol}: {e}")
            return None

        if analysis.signal == "neutral":
            logger.info(f"{strategy.name} returned neutral on {symbol}; " "no proposal")
            return None

        try:
            position = self.trading_strategy.create_position(
                analysis=analysis,
                symbol=symbol,
                balance=balance,
                leverage=self.config.leverage,
                risk_percent=self.config.risk_percent,
            )
        except TradingValidationError as e:
            logger.info(f"Position rejected for {symbol} via {strategy.name}: {e}")
            return None

        rr = analysis.risk_reward_ratio or 0.0
        score = self._score(analysis, perf)

        return Proposal(
            symbol=symbol,
            timeframe=timeframe,
            technique_name=strategy.name,
            technique_version=strategy.version,
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

    def _select_best_technique(
        self,
        symbol: str,
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
        applicable = [
            s
            for s in self.strategies.values()
            if not s.info.symbols or symbol in s.info.symbols
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
