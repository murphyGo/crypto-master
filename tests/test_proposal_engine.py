"""Tests for the ProposalEngine (Phase 6.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exchange.base import BaseExchange, ExchangeAPIError
from src.models import OHLCV, AnalysisResult
from src.proposal.engine import (
    Proposal,
    ProposalEngine,
    ProposalEngineConfig,
    ProposalEngineError,
)
from src.strategy.base import BaseStrategy, StrategyExecutionError, TechniqueInfo
from src.strategy.performance import PerformanceTracker, TechniquePerformance

# =============================================================================
# Helpers
# =============================================================================


def make_info(
    name: str = "tech_a",
    symbols: list[str] | None = None,
    version: str = "1.0.0",
) -> TechniqueInfo:
    return TechniqueInfo(
        name=name,
        version=version,
        description=f"{name} description",
        technique_type="prompt",
        symbols=symbols if symbols is not None else ["BTC/USDT"],
    )


def make_ohlcv(n: int = 30, base_price: float = 50_000) -> list[OHLCV]:
    """Build a simple ascending OHLCV series."""
    start = datetime(2026, 1, 1)
    out: list[OHLCV] = []
    for i in range(n):
        price = Decimal(str(base_price + i * 10))
        out.append(
            OHLCV(
                timestamp=start + timedelta(hours=i),
                open=price,
                high=price + Decimal("100"),
                low=price - Decimal("100"),
                close=price + Decimal("50"),
                volume=Decimal("100"),
            )
        )
    return out


def make_analysis(
    signal: str = "long",
    confidence: float = 0.8,
    entry: str = "50000",
    sl: str = "49500",
    tp: str = "51500",
    reasoning: str = "test",
) -> AnalysisResult:
    return AnalysisResult(
        signal=signal,  # type: ignore[arg-type]
        confidence=confidence,
        entry_price=Decimal(entry),
        stop_loss=Decimal(sl),
        take_profit=Decimal(tp),
        reasoning=reasoning,
    )


def make_strategy(
    info: TechniqueInfo | None = None,
    analysis: AnalysisResult | StrategyExecutionError | None = None,
) -> BaseStrategy:
    """Build a mock BaseStrategy that returns ``analysis`` from analyze()."""
    info = info or make_info()
    strategy = MagicMock(spec=BaseStrategy)
    strategy.name = info.name
    strategy.version = info.version
    strategy.info = info

    if isinstance(analysis, Exception):
        strategy.analyze = AsyncMock(side_effect=analysis)
    else:
        strategy.analyze = AsyncMock(return_value=analysis or make_analysis())
    return strategy


def make_perf(
    name: str,
    version: str = "1.0.0",
    total_trades: int = 0,
    win_rate: float = 0.0,
    avg_pnl_percent: float = 0.0,
) -> TechniquePerformance:
    return TechniquePerformance(
        technique_name=name,
        technique_version=version,
        total_trades=total_trades,
        win_rate=win_rate,
        avg_pnl_percent=avg_pnl_percent,
    )


def make_engine(
    *,
    strategies: dict[str, BaseStrategy] | None = None,
    perf_records: dict[str, TechniquePerformance] | None = None,
    ohlcv: list[OHLCV] | Exception | None = None,
    config: ProposalEngineConfig | None = None,
) -> tuple[ProposalEngine, AsyncMock]:
    """Build a ProposalEngine with mocked exchange and tracker."""
    exchange = AsyncMock(spec=BaseExchange)
    if isinstance(ohlcv, Exception):
        exchange.get_ohlcv.side_effect = ohlcv
    else:
        exchange.get_ohlcv.return_value = ohlcv if ohlcv is not None else make_ohlcv()

    tracker = MagicMock(spec=PerformanceTracker)
    perf_records = perf_records or {}

    def _get_perf(name: str, version: str | None = None) -> TechniquePerformance:
        return perf_records.get(name, make_perf(name, version or "1.0.0"))

    tracker.get_performance.side_effect = _get_perf

    engine = ProposalEngine(
        exchange=exchange,
        strategies=strategies or {},
        performance_tracker=tracker,
        config=config or ProposalEngineConfig(),
    )
    return engine, exchange


# =============================================================================
# propose_bitcoin happy-path / rejection paths
# =============================================================================


async def test_propose_bitcoin_returns_full_proposal() -> None:
    strategy = make_strategy(
        info=make_info("tech_a", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    perf = make_perf("tech_a", total_trades=30, win_rate=0.6, avg_pnl_percent=2.0)
    engine, exchange = make_engine(
        strategies={"tech_a": strategy},
        perf_records={"tech_a": perf},
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT", balance=Decimal("10000"))

    assert proposal is not None
    assert isinstance(proposal, Proposal)
    assert proposal.symbol == "BTC/USDT"
    assert proposal.signal == "long"
    assert proposal.technique_name == "tech_a"
    assert proposal.technique_version == "1.0.0"
    assert proposal.entry_price == Decimal("50000")
    assert proposal.stop_loss == Decimal("49500")
    assert proposal.take_profit == Decimal("51500")
    assert proposal.quantity > 0
    assert proposal.leverage == 1
    assert proposal.risk_reward_ratio == pytest.approx(3.0, rel=1e-6)
    # Score should reflect the perf record we passed in.
    assert proposal.score.sample_size == 30
    assert proposal.score.expected_value == 2.0
    assert proposal.score.sample_factor == 1.0
    assert proposal.score.composite > 0

    # Exchange was hit once with our config.
    exchange.get_ohlcv.assert_awaited_once()
    args = exchange.get_ohlcv.await_args
    assert args.kwargs["symbol"] == "BTC/USDT"


async def test_propose_bitcoin_returns_none_for_neutral_signal() -> None:
    strategy = make_strategy(analysis=make_analysis(signal="neutral"))
    engine, _ = make_engine(strategies={"tech_a": strategy})

    proposal = await engine.propose_bitcoin()

    assert proposal is None


async def test_propose_bitcoin_returns_none_when_no_strategies() -> None:
    engine, _ = make_engine(strategies={})

    proposal = await engine.propose_bitcoin()

    assert proposal is None


async def test_propose_bitcoin_returns_none_when_no_strategy_supports_symbol() -> None:
    strategy = make_strategy(
        info=make_info("eth_only", symbols=["ETH/USDT"]),
    )
    engine, _ = make_engine(strategies={"eth_only": strategy})

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is None


async def test_propose_bitcoin_propagates_exchange_error() -> None:
    strategy = make_strategy()
    engine, _ = make_engine(
        strategies={"tech_a": strategy},
        ohlcv=ExchangeAPIError("rate limited"),
    )

    with pytest.raises(ExchangeAPIError):
        await engine.propose_bitcoin()


async def test_propose_bitcoin_skips_when_strategy_raises() -> None:
    strategy = make_strategy(
        analysis=StrategyExecutionError("blew up", strategy_name="tech_a")
    )
    engine, _ = make_engine(strategies={"tech_a": strategy})

    proposal = await engine.propose_bitcoin()

    assert proposal is None


async def test_propose_bitcoin_skips_when_rr_below_floor() -> None:
    """TradingStrategy default min R/R is 1.5; a 1:1 should reject."""
    strategy = make_strategy(
        analysis=make_analysis(entry="50000", sl="49500", tp="50500")  # RR = 1.0
    )
    engine, _ = make_engine(strategies={"tech_a": strategy})

    proposal = await engine.propose_bitcoin()

    assert proposal is None


# =============================================================================
# propose_altcoins ranking + resilience
# =============================================================================


async def test_propose_altcoins_ranks_and_returns_top_k() -> None:
    """Two symbols, two techniques — the higher-EV technique wins."""
    strong = make_strategy(
        info=make_info("strong", symbols=["ETH/USDT", "SOL/USDT"], version="1.0.0"),
        analysis=make_analysis(confidence=0.9),
    )
    weak = make_strategy(
        info=make_info("weak", symbols=["ETH/USDT", "SOL/USDT"], version="1.0.0"),
        analysis=make_analysis(confidence=0.4),
    )
    engine, _ = make_engine(
        strategies={"strong": strong, "weak": weak},
        perf_records={
            "strong": make_perf("strong", total_trades=30, avg_pnl_percent=3.0),
            "weak": make_perf("weak", total_trades=30, avg_pnl_percent=0.5),
        },
    )

    proposals = await engine.propose_altcoins(symbols=["ETH/USDT", "SOL/USDT"], top_k=2)

    assert len(proposals) == 2
    # Ranking is by composite, descending.
    assert proposals[0].score.composite >= proposals[1].score.composite
    # The "strong" technique should be picked for both symbols.
    assert all(p.technique_name == "strong" for p in proposals)


async def test_propose_altcoins_top_k_truncates() -> None:
    strategy = make_strategy(
        info=make_info("tech_a", symbols=["ETH/USDT", "SOL/USDT", "ADA/USDT"]),
        analysis=make_analysis(confidence=0.7),
    )
    engine, _ = make_engine(
        strategies={"tech_a": strategy},
        perf_records={
            "tech_a": make_perf("tech_a", total_trades=30, avg_pnl_percent=1.0)
        },
    )

    proposals = await engine.propose_altcoins(
        symbols=["ETH/USDT", "SOL/USDT", "ADA/USDT"], top_k=2
    )

    assert len(proposals) == 2


async def test_propose_altcoins_skips_failing_symbol() -> None:
    """An exchange error on one symbol should not abort the scan."""
    strategy = make_strategy(
        info=make_info("tech_a", symbols=["ETH/USDT", "SOL/USDT"]),
    )
    exchange = AsyncMock(spec=BaseExchange)

    def fake_get_ohlcv(**kwargs: object) -> list[OHLCV]:
        if kwargs.get("symbol") == "ETH/USDT":
            raise ExchangeAPIError("eth dead")
        return make_ohlcv()

    exchange.get_ohlcv.side_effect = fake_get_ohlcv

    tracker = MagicMock(spec=PerformanceTracker)
    tracker.get_performance.return_value = make_perf(
        "tech_a", total_trades=10, avg_pnl_percent=1.0
    )

    engine = ProposalEngine(
        exchange=exchange,
        strategies={"tech_a": strategy},
        performance_tracker=tracker,
    )

    proposals = await engine.propose_altcoins(symbols=["ETH/USDT", "SOL/USDT"], top_k=3)

    # ETH was skipped; SOL produced a proposal.
    assert len(proposals) == 1
    assert proposals[0].symbol == "SOL/USDT"


async def test_propose_altcoins_skips_neutral_signals() -> None:
    neutral_strat = make_strategy(
        info=make_info("tech_a", symbols=["ETH/USDT", "SOL/USDT"]),
        analysis=make_analysis(signal="neutral"),
    )
    engine, _ = make_engine(strategies={"tech_a": neutral_strat})

    proposals = await engine.propose_altcoins(symbols=["ETH/USDT", "SOL/USDT"])

    assert proposals == []


async def test_propose_altcoins_invalid_top_k_raises() -> None:
    engine, _ = make_engine()
    with pytest.raises(ProposalEngineError, match="top_k"):
        await engine.propose_altcoins(symbols=["ETH/USDT"], top_k=0)


# =============================================================================
# Best-technique selection
# =============================================================================


async def test_select_best_technique_picks_highest_ev() -> None:
    high = make_strategy(
        info=make_info("high_ev", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    low = make_strategy(
        info=make_info("low_ev", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    engine, _ = make_engine(
        strategies={"high_ev": high, "low_ev": low},
        perf_records={
            "high_ev": make_perf("high_ev", total_trades=20, avg_pnl_percent=3.0),
            "low_ev": make_perf("low_ev", total_trades=20, avg_pnl_percent=0.2),
        },
    )

    proposal = await engine.propose_bitcoin()

    assert proposal is not None
    assert proposal.technique_name == "high_ev"


async def test_select_best_technique_falls_back_when_no_history() -> None:
    a = make_strategy(
        info=make_info("alpha", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    b = make_strategy(
        info=make_info("beta", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    engine, _ = make_engine(
        strategies={"alpha": a, "beta": b},
        # No perf records at all → every technique returns total_trades=0.
    )

    proposal = await engine.propose_bitcoin()

    # Cold start: lex-first wins, score is confidence × no_history_factor.
    assert proposal is not None
    assert proposal.technique_name == "alpha"
    assert proposal.score.sample_size == 0
    assert proposal.score.composite == pytest.approx(0.8 * 0.5)


async def test_select_best_technique_filters_by_symbol() -> None:
    btc_strat = make_strategy(
        info=make_info("btc_only", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    eth_strat = make_strategy(
        info=make_info("eth_only", symbols=["ETH/USDT"]),
        analysis=make_analysis(),
    )
    engine, _ = make_engine(
        strategies={"btc_only": btc_strat, "eth_only": eth_strat},
        perf_records={
            "btc_only": make_perf("btc_only", total_trades=10, avg_pnl_percent=1.0),
            "eth_only": make_perf("eth_only", total_trades=100, avg_pnl_percent=10.0),
        },
    )

    # eth_only has bigger history but doesn't list BTC/USDT.
    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    assert proposal.technique_name == "btc_only"


# =============================================================================
# Score formula
# =============================================================================


def test_score_low_sample_is_discounted() -> None:
    engine, _ = make_engine(config=ProposalEngineConfig(min_trades_for_full_score=20))
    perf_low = make_perf("a", total_trades=2, avg_pnl_percent=2.0)
    perf_full = make_perf("a", total_trades=20, avg_pnl_percent=2.0)

    score_low = engine._score(make_analysis(confidence=0.8), perf_low)
    score_full = engine._score(make_analysis(confidence=0.8), perf_full)

    assert score_low.sample_factor == pytest.approx(0.1)
    assert score_full.sample_factor == 1.0
    assert score_full.composite > score_low.composite


def test_score_no_history_uses_confidence_floor() -> None:
    engine, _ = make_engine(config=ProposalEngineConfig(no_history_score_factor=0.5))

    score = engine._score(make_analysis(confidence=0.8), perf=None)

    assert score.sample_size == 0
    assert score.edge_factor == 0.0
    assert score.composite == pytest.approx(0.4)


def test_score_negative_ev_zero_edge() -> None:
    engine, _ = make_engine()
    losing = make_perf("a", total_trades=20, avg_pnl_percent=-1.5)

    score = engine._score(make_analysis(confidence=0.9), losing)

    assert score.edge_factor == 0.0
    assert score.composite == 0.0


def test_score_clamps_confidence_above_one() -> None:
    """A misbehaving strategy returning confidence > 1 should not blow up."""
    engine, _ = make_engine()
    # AnalysisResult validates confidence <= 1, so we construct a
    # MagicMock-shaped "result" that bypasses validation.
    analysis = MagicMock()
    analysis.confidence = 1.5
    perf = make_perf("a", total_trades=20, avg_pnl_percent=2.0)

    score = engine._score(analysis, perf)

    assert score.confidence == 1.0
