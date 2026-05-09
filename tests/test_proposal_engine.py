"""Tests for the ProposalEngine (Phase 6.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
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
    technique_type: str = "prompt",
    prompt_trigger: str = "none",
) -> TechniqueInfo:
    return TechniqueInfo(
        name=name,
        version=version,
        description=f"{name} description",
        technique_type=technique_type,  # type: ignore[arg-type]
        symbols=symbols if symbols is not None else ["BTC/USDT"],
        prompt_trigger=prompt_trigger,  # type: ignore[arg-type]
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


def make_flat_ohlcv(n: int = 30, price: str = "50000") -> list[OHLCV]:
    """Build candles without sweep, OB, or FVG trigger patterns."""
    start = datetime(2026, 1, 1)
    base = Decimal(price)
    return [
        OHLCV(
            timestamp=start + timedelta(hours=i),
            open=base,
            high=base + Decimal("100"),
            low=base - Decimal("100"),
            close=base,
            volume=Decimal("100"),
        )
        for i in range(n)
    ]


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
    analysis: AnalysisResult | Exception | None = None,
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
    activity_log: object | None = None,
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
        activity_log=activity_log,  # type: ignore[arg-type]
    )
    return engine, exchange


# =============================================================================
# propose_bitcoin happy-path / rejection paths
# =============================================================================


async def test_fetch_and_validate_ohlcv_uses_cache_for_single_timeframe() -> None:
    strategy = make_strategy(info=make_info("tech_a", symbols=["BTC/USDT"]))
    engine, exchange = make_engine()
    cache: dict[tuple[str, str], list[OHLCV]] = {}

    first = await engine._fetch_and_validate_ohlcv(
        strategy=strategy,
        symbol="BTC/USDT",
        timeframe="1h",
        ohlcv_cache=cache,
    )
    second = await engine._fetch_and_validate_ohlcv(
        strategy=strategy,
        symbol="BTC/USDT",
        timeframe="1h",
        ohlcv_cache=cache,
    )

    assert first is not None
    assert second is not None
    assert first[0] == "1h"
    assert first[1] == second[1]
    assert first[2] is None
    assert first[3] == first[1][-1].close
    exchange.get_ohlcv.assert_awaited_once()


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


async def test_propose_bitcoin_uses_per_call_leverage_override() -> None:
    strategy = make_strategy(
        info=make_info("tech_a", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine, _ = make_engine(strategies={"tech_a": strategy})

    proposal = await engine.propose_bitcoin(
        symbol="BTC/USDT",
        balance=Decimal("10000"),
        leverage=2,
    )

    assert proposal is not None
    assert proposal.leverage == 2


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


# =============================================================================
# Multi-timeframe dispatch (Phase 9.1)
# =============================================================================


async def test_propose_single_timeframe_makes_one_fetch() -> None:
    """Regression: existing single-TF strategies still hit the exchange once."""
    strategy = make_strategy(
        info=make_info("tech_a", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    perf = make_perf("tech_a", total_trades=20, avg_pnl_percent=2.0)
    engine, exchange = make_engine(
        strategies={"tech_a": strategy},
        perf_records={"tech_a": perf},
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    assert exchange.get_ohlcv.await_count == 1
    # No multi-TF kwargs were threaded through.
    call_kwargs = strategy.analyze.await_args.kwargs
    assert call_kwargs.get("ohlcv_by_timeframe") is None
    assert call_kwargs.get("current_price") is None


async def test_propose_multi_timeframe_fetches_each_declared_tf() -> None:
    """A ``requires_multi_timeframe=True`` strategy fetches every TF in order.

    Mirrors the chasulang setup: the strategy declares 4h/1h/15m/5m and
    the engine pre-fetches all four before invoking ``analyze``.
    """
    info = TechniqueInfo(
        name="multi_tech",
        version="1.0.0",
        description="multi-tf",
        technique_type="prompt",
        symbols=["BTC/USDT"],
        timeframes=["4h", "1h", "15m", "5m"],
        requires_multi_timeframe=True,
    )
    strategy = make_strategy(info=info, analysis=make_analysis(signal="long"))
    engine, exchange = make_engine(
        strategies={"multi_tech": strategy},
        perf_records={"multi_tech": make_perf("multi_tech", total_trades=20)},
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    assert exchange.get_ohlcv.await_count == 4
    fetched_tfs = [c.kwargs["timeframe"] for c in exchange.get_ohlcv.await_args_list]
    assert fetched_tfs == ["4h", "1h", "15m", "5m"]


async def test_propose_multi_timeframe_passes_dict_and_current_price() -> None:
    """The engine forwards the per-TF dict + last-close current_price.

    Verifies the contract `PromptStrategy.format_prompt` relies on:
    ``ohlcv_by_timeframe`` keyed by each declared TF, and
    ``current_price`` derived from the primary (last-listed) TF's
    final candle close.
    """
    info = TechniqueInfo(
        name="multi_tech",
        version="1.0.0",
        description="multi-tf",
        technique_type="prompt",
        symbols=["BTC/USDT"],
        timeframes=["4h", "15m"],
        requires_multi_timeframe=True,
    )
    strategy = make_strategy(info=info, analysis=make_analysis(signal="long"))

    exchange = AsyncMock(spec=BaseExchange)
    candles_4h = make_ohlcv(n=30, base_price=49_000)
    candles_15m = make_ohlcv(n=30, base_price=50_000)

    def fake_get_ohlcv(**kwargs: object) -> list[OHLCV]:
        return candles_4h if kwargs.get("timeframe") == "4h" else candles_15m

    exchange.get_ohlcv.side_effect = fake_get_ohlcv
    tracker = MagicMock(spec=PerformanceTracker)
    tracker.get_performance.return_value = make_perf(
        "multi_tech", total_trades=20, avg_pnl_percent=2.0
    )
    engine = ProposalEngine(
        exchange=exchange,
        strategies={"multi_tech": strategy},
        performance_tracker=tracker,
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    # Primary TF is the last entry in info.timeframes.
    assert proposal.timeframe == "15m"

    call_args = strategy.analyze.await_args
    # First positional arg is the primary-TF candle list.
    assert call_args.args[0] is candles_15m
    assert call_args.args[1] == "BTC/USDT"
    assert call_args.args[2] == "15m"
    # Per-TF dict carries every declared TF.
    dict_arg = call_args.kwargs["ohlcv_by_timeframe"]
    assert set(dict_arg.keys()) == {"4h", "15m"}
    assert dict_arg["4h"] is candles_4h
    assert dict_arg["15m"] is candles_15m
    # current_price = primary TF's last close.
    assert call_args.kwargs["current_price"] == candles_15m[-1].close


async def test_propose_multi_timeframe_skips_when_primary_empty() -> None:
    """If the primary-TF fetch returns no candles, return None gracefully."""
    info = TechniqueInfo(
        name="multi_tech",
        version="1.0.0",
        description="multi-tf",
        technique_type="prompt",
        symbols=["BTC/USDT"],
        timeframes=["4h", "15m"],
        requires_multi_timeframe=True,
    )
    strategy = make_strategy(info=info, analysis=make_analysis(signal="long"))

    exchange = AsyncMock(spec=BaseExchange)

    def fake_get_ohlcv(**kwargs: object) -> list[OHLCV]:
        return [] if kwargs.get("timeframe") == "15m" else make_ohlcv()

    exchange.get_ohlcv.side_effect = fake_get_ohlcv
    tracker = MagicMock(spec=PerformanceTracker)
    tracker.get_performance.return_value = make_perf("multi_tech", total_trades=20)
    engine = ProposalEngine(
        exchange=exchange,
        strategies={"multi_tech": strategy},
        performance_tracker=tracker,
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is None
    # ``analyze`` was never reached.
    strategy.analyze.assert_not_awaited()


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


# =============================================================================
# Phase 12.3: LLM_TIMEOUT activity event
# =============================================================================


async def test_engine_logs_llm_timeout_event(tmp_path: Path) -> None:
    """ClaudeTimeoutError on a strategy emits an LLM_TIMEOUT activity event."""
    from src.ai.exceptions import ClaudeTimeoutError
    from src.runtime.activity_log import ActivityEventType, ActivityLog

    activity = ActivityLog(path=tmp_path / "activity.jsonl")

    strategy = make_strategy(
        info=make_info("slow_tech", symbols=["BTC/USDT"]),
        analysis=ClaudeTimeoutError("timeout", timeout_seconds=180.0),
    )
    engine, _ = make_engine(
        strategies={"slow_tech": strategy},
        activity_log=activity,
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    # Neutral fallback — timeout should not crash the cycle.
    assert proposal is None

    # Exactly one LLM_TIMEOUT event recorded with diagnostic details.
    events = activity.filter(event_type=ActivityEventType.LLM_TIMEOUT)
    assert len(events) == 1
    event = events[0]
    assert event.details["strategy_name"] == "slow_tech"
    assert event.details["symbol"] == "BTC/USDT"
    assert event.details["timeout_seconds"] == 180.0


async def test_engine_llm_timeout_event_carries_attempt_metadata(
    tmp_path: Path,
) -> None:
    """Phase 14.1: ``LLM_TIMEOUT`` payload exposes retry-path metadata.

    Operators triaging "is the retry actually firing?" need to see
    ``attempt_number`` (1 = no retry, 2+ = retry path) and
    ``final_timeout_seconds`` (the timeout the *final* attempt gave up
    at) without grepping subprocess WARN lines. The original
    ``timeout_seconds`` key is preserved for back-compat with existing
    dashboard readers.
    """
    from src.ai.exceptions import ClaudeTimeoutError
    from src.runtime.activity_log import ActivityEventType, ActivityLog

    activity = ActivityLog(path=tmp_path / "activity.jsonl")

    strategy = make_strategy(
        info=make_info("chasulang_ict_smc", symbols=["BTC/USDT"]),
        analysis=ClaudeTimeoutError(
            "timed out", timeout_seconds=360.0, attempt_number=2
        ),
    )
    engine, _ = make_engine(
        strategies={"chasulang_ict_smc": strategy},
        activity_log=activity,
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")
    assert proposal is None

    events = activity.filter(event_type=ActivityEventType.LLM_TIMEOUT)
    assert len(events) == 1
    details = events[0].details
    # Phase 14.1 additions — attempt_number == 2 means the retry path
    # fired and *both* attempts timed out (the final, longer-leash
    # attempt being the one that surfaced the error).
    assert details["attempt_number"] == 2
    assert details["final_timeout_seconds"] == 360.0
    # Back-compat: the legacy ``timeout_seconds`` key is still emitted
    # so existing log readers / dashboards keep working.
    assert details["timeout_seconds"] == 360.0


async def test_engine_does_not_log_llm_timeout_for_other_strategy_errors(
    tmp_path: Path,
) -> None:
    """Non-timeout StrategyError must NOT emit LLM_TIMEOUT (false-positive guard)."""
    from src.runtime.activity_log import ActivityEventType, ActivityLog

    activity = ActivityLog(path=tmp_path / "activity.jsonl")

    strategy = make_strategy(
        analysis=StrategyExecutionError("blew up", strategy_name="tech_a"),
    )
    engine, _ = make_engine(
        strategies={"tech_a": strategy},
        activity_log=activity,
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is None
    events = activity.filter(event_type=ActivityEventType.LLM_TIMEOUT)
    assert len(events) == 0


async def test_engine_no_activity_log_means_no_crash_on_timeout() -> None:
    """When activity_log is None, timeouts still fall back cleanly to None."""
    from src.ai.exceptions import ClaudeTimeoutError

    strategy = make_strategy(
        analysis=ClaudeTimeoutError("timeout", timeout_seconds=120.0),
    )
    engine, _ = make_engine(strategies={"tech_a": strategy})  # activity_log=None

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is None


# =============================================================================
# Phase 24.1 / DEBT-034: live cold-start guard
# =============================================================================


async def test_live_mode_blocks_cold_start_proposal(tmp_path: Path) -> None:
    """Phase 24.1 / DEBT-034: live mode + every technique below the
    closed-trades threshold → no proposal.

    Without the guard, real money would go to whichever technique
    sorts first alphabetically since cold-start composites collapse to
    ``confidence × no_history_score_factor``. The guard returns ``None``
    so a fresh deployment cannot fire a live trade until at least one
    technique has accumulated enough history to be promotable.

    Phase 24.2 / DEBT-034 follow-up: assert the
    :data:`ActivityEventType.COLD_START_BLOCKED` event lands so the
    dashboard surfaces the deliberate idle state to operators.
    """
    from src.runtime.activity_log import ActivityEventType, ActivityLog

    a = make_strategy(
        info=make_info("alpha", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    b = make_strategy(
        info=make_info("beta", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    activity_log = ActivityLog(path=tmp_path / "activity.jsonl")
    engine, _ = make_engine(
        strategies={"alpha": a, "beta": b},
        # No perf records → both techniques have total_trades=0.
        config=ProposalEngineConfig(
            mode="live",
            min_closed_trades_for_live_promotion=5,
        ),
        activity_log=activity_log,
    )

    proposal = await engine.propose_bitcoin()

    assert proposal is None

    # Phase 24.2 / DEBT-034 follow-up: the dashboard-facing event must
    # land with the canonical reason string + per-technique trade
    # snapshot so operators can see *which* techniques fell short.
    events = activity_log.tail(50)
    cold_events = [
        e for e in events if e.event_type == ActivityEventType.COLD_START_BLOCKED.value
    ]
    assert len(cold_events) == 1
    event = cold_events[0]
    assert event.details["symbol"] == "BTC/USDT"
    assert event.details["reason"] == "cold_start_below_min_closed_trades"
    assert event.details["min_closed_trades_for_live_promotion"] == 5
    assert event.details["max_trades_observed"] == 0
    assert event.details["per_technique_trades"] == {"alpha": 0, "beta": 0}


async def test_paper_mode_allows_cold_start_proposal() -> None:
    """Phase 24.1 / DEBT-034: paper mode is unaffected by the guard.

    The guard only fires in live mode — paper mode continues to bootstrap
    technique performance from cold-start since there's no real-money
    exposure.
    """
    a = make_strategy(
        info=make_info("alpha", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    engine, _ = make_engine(
        strategies={"alpha": a},
        # Paper mode is the default — we set it explicitly to make the
        # contract obvious to readers.
        config=ProposalEngineConfig(
            mode="paper",
            min_closed_trades_for_live_promotion=5,
        ),
    )

    proposal = await engine.propose_bitcoin()

    assert proposal is not None
    assert proposal.technique_name == "alpha"
    assert proposal.score.sample_size == 0  # Cold start


async def test_live_mode_allows_proposal_when_one_technique_has_enough_trades() -> None:
    """Phase 24.1 / DEBT-034: the guard releases as soon as ANY
    applicable technique meets the threshold.

    The single technique with sufficient closed trades is the live
    candidate; cold-start techniques in the same population still
    aren't picked (their composites are below the qualifying
    technique's), but the guard itself is no longer a hard block.
    """
    qualified = make_strategy(
        info=make_info("alpha", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    cold = make_strategy(
        info=make_info("beta", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    engine, _ = make_engine(
        strategies={"alpha": qualified, "beta": cold},
        perf_records={
            "alpha": make_perf("alpha", total_trades=10, avg_pnl_percent=2.0),
            # beta has no record → cold start.
        },
        config=ProposalEngineConfig(
            mode="live",
            min_closed_trades_for_live_promotion=5,
            multi_technique_per_symbol=False,  # Use legacy single-best path
        ),
    )

    proposal = await engine.propose_bitcoin()

    assert proposal is not None
    assert proposal.technique_name == "alpha"


async def test_live_mode_blocks_when_only_cold_start_techniques_present() -> None:
    """Phase 24.1 / DEBT-034: multi-technique scan path also blocks.

    The guard is enforced before either ``_select_best_technique``
    (legacy path) or ``_select_all_techniques`` (Phase 10.6 multi-
    technique path) runs, so both code paths return None / empty in
    live mode when no technique qualifies.
    """
    a = make_strategy(
        info=make_info("alpha", symbols=["BTC/USDT"]),
        analysis=make_analysis(),
    )
    engine, _ = make_engine(
        strategies={"alpha": a},
        perf_records={
            "alpha": make_perf("alpha", total_trades=2, avg_pnl_percent=2.0),
        },
        config=ProposalEngineConfig(
            mode="live",
            min_closed_trades_for_live_promotion=5,
            multi_technique_per_symbol=True,  # Phase 10.6 default
        ),
    )

    # Single-symbol entry point.
    bitcoin = await engine.propose_bitcoin()
    assert bitcoin is None

    # Multi-symbol scan entry point: the guard fires per-symbol.
    altcoins = await engine.propose_altcoins(symbols=["BTC/USDT"], top_k=3)
    assert altcoins == []


async def test_prompt_strategy_cooldown_skips_repeated_symbol_runs() -> None:
    """Prompt strategies should not spend Claude tokens every cycle when
    a runtime cooldown is configured.
    """
    strategy = make_strategy(
        info=make_info("prompt_a", symbols=["BTC/USDT"], technique_type="prompt"),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine, exchange = make_engine(
        strategies={"prompt_a": strategy},
        config=ProposalEngineConfig(prompt_strategy_min_interval_seconds=3600),
    )

    first = await engine.propose_bitcoin()
    second = await engine.propose_bitcoin()

    assert first is not None
    assert second is None
    assert strategy.analyze.await_count == 1
    assert exchange.get_ohlcv.await_count == 1


async def test_prompt_strategy_cooldown_is_per_symbol() -> None:
    strategy = make_strategy(
        info=make_info("prompt_a", symbols=[], technique_type="prompt"),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine, _ = make_engine(
        strategies={"prompt_a": strategy},
        config=ProposalEngineConfig(prompt_strategy_min_interval_seconds=3600),
    )

    proposals = await engine.propose_altcoins(
        symbols=["ETH/USDT", "SOL/USDT"],
        top_k=2,
    )

    assert len(proposals) == 2
    assert strategy.analyze.await_count == 2


async def test_prompt_strategy_cooldown_does_not_apply_to_code_strategies() -> None:
    strategy = make_strategy(
        info=make_info("code_a", symbols=["BTC/USDT"], technique_type="code"),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine, _ = make_engine(
        strategies={"code_a": strategy},
        config=ProposalEngineConfig(prompt_strategy_min_interval_seconds=3600),
    )

    first = await engine.propose_bitcoin()
    second = await engine.propose_bitcoin()

    assert first is not None
    assert second is not None
    assert strategy.analyze.await_count == 2


async def test_prompt_trigger_blocks_claude_when_market_condition_absent() -> None:
    strategy = make_strategy(
        info=make_info(
            "chasulang_like",
            symbols=["BTC/USDT"],
            technique_type="prompt",
            prompt_trigger="ict_smc_context",
        ),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine, exchange = make_engine(
        strategies={"chasulang_like": strategy},
        ohlcv=make_flat_ohlcv(),
    )

    proposal = await engine.propose_bitcoin()

    assert proposal is None
    assert exchange.get_ohlcv.await_count == 1
    assert strategy.analyze.await_count == 0


async def test_prompt_trigger_allows_claude_after_liquidity_sweep() -> None:
    candles = make_flat_ohlcv()
    prior_low = min(c.low for c in candles[:-1])
    latest = candles[-1].model_copy(
        update={
            "low": prior_low - Decimal("100"),
            "close": prior_low + Decimal("50"),
        }
    )
    candles[-1] = latest
    strategy = make_strategy(
        info=make_info(
            "chasulang_like",
            symbols=["BTC/USDT"],
            technique_type="prompt",
            prompt_trigger="ict_smc_context",
        ),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine, _ = make_engine(
        strategies={"chasulang_like": strategy},
        ohlcv=candles,
    )

    proposal = await engine.propose_bitcoin()

    assert proposal is not None
    assert strategy.analyze.await_count == 1


async def test_prompt_trigger_skip_does_not_start_cooldown() -> None:
    quiet = make_flat_ohlcv()
    sweep = make_flat_ohlcv()
    prior_high = max(c.high for c in sweep[:-1])
    sweep[-1] = sweep[-1].model_copy(
        update={
            "high": prior_high + Decimal("100"),
            "close": prior_high - Decimal("50"),
        }
    )
    strategy = make_strategy(
        info=make_info(
            "chasulang_like",
            symbols=["BTC/USDT"],
            technique_type="prompt",
            prompt_trigger="ict_smc_context",
        ),
        analysis=make_analysis(
            signal="short",
            confidence=0.8,
            entry="50000",
            sl="50500",
            tp="48500",
        ),
    )
    engine, exchange = make_engine(
        strategies={"chasulang_like": strategy},
        config=ProposalEngineConfig(prompt_strategy_min_interval_seconds=3600),
    )

    exchange.get_ohlcv.return_value = quiet
    first = await engine.propose_bitcoin()
    exchange.get_ohlcv.return_value = sweep
    second = await engine.propose_bitcoin()

    assert first is None
    assert second is not None
    assert strategy.analyze.await_count == 1


async def test_ict_prompt_trigger_allows_claude_near_swing_extreme() -> None:
    candles = make_flat_ohlcv()
    candles[-1] = candles[-1].model_copy(update={"close": Decimal("50090")})
    strategy = make_strategy(
        info=make_info(
            "chasulang_like",
            symbols=["BTC/USDT"],
            technique_type="prompt",
            prompt_trigger="ict_smc_context",
        ),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine, _ = make_engine(
        strategies={"chasulang_like": strategy},
        ohlcv=candles,
    )

    proposal = await engine.propose_bitcoin()

    assert proposal is not None
    assert strategy.analyze.await_count == 1


async def test_trend_prompt_trigger_allows_claude_after_directional_move() -> None:
    candles = make_flat_ohlcv()
    for i, candle in enumerate(candles):
        price = Decimal("50000") + Decimal(i * 100)
        candles[i] = candle.model_copy(
            update={
                "open": price,
                "high": price + Decimal("100"),
                "low": price - Decimal("100"),
                "close": price,
            }
        )
    strategy = make_strategy(
        info=make_info(
            "simple_trend_like",
            symbols=["BTC/USDT"],
            technique_type="prompt",
            prompt_trigger="trend_context",
        ),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine, _ = make_engine(
        strategies={"simple_trend_like": strategy},
        ohlcv=candles,
    )

    proposal = await engine.propose_bitcoin()

    assert proposal is not None
    assert strategy.analyze.await_count == 1
