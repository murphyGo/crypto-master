"""Tests for Phase 10.6 multi-technique per-symbol scan.

These cover the trading-correctness invariants surfaced by the
quant-trader-expert review:

* every public entry point must return at most one proposal per
  symbol (long+long and long+short conflict cases);
* neutral signals are filtered out before per-symbol dedup;
* cold-start techniques don't crowd out proven techniques (existing
  scoring semantic preserved);
* ``propose_altcoins`` order of operations is dedup-by-symbol then
  top-K (FR-012 diversification);
* the single-applicable-technique smoke path still works;
* ``multi_technique_per_symbol=False`` reproduces pre-10.6 behaviour
  (legacy back-compat smoke).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.exchange.base import BaseExchange
from src.proposal.engine import ProposalEngine, ProposalEngineConfig
from src.strategy.performance import PerformanceTracker, TechniquePerformance
from tests.test_proposal_engine import (
    make_analysis,
    make_info,
    make_ohlcv,
    make_perf,
    make_strategy,
)

# =============================================================================
# Helpers
# =============================================================================


def _engine(
    strategies: dict[str, object],
    perf_records: dict[str, TechniquePerformance] | None = None,
    *,
    multi_technique_per_symbol: bool = True,
) -> ProposalEngine:
    """Build an engine with default-on multi-technique config.

    Mirrors ``test_proposal_engine.make_engine`` but exposes the new
    ``multi_technique_per_symbol`` flag and skips returning the
    exchange — these tests don't introspect get_ohlcv calls.
    """
    exchange = AsyncMock(spec=BaseExchange)
    exchange.get_ohlcv.return_value = make_ohlcv()

    tracker = MagicMock(spec=PerformanceTracker)
    perf_records = perf_records or {}

    def _get_perf(name: str, version: str | None = None) -> TechniquePerformance:
        return perf_records.get(name, make_perf(name, version or "1.0.0"))

    tracker.get_performance.side_effect = _get_perf

    return ProposalEngine(
        exchange=exchange,
        strategies=strategies,  # type: ignore[arg-type]
        performance_tracker=tracker,
        config=ProposalEngineConfig(
            multi_technique_per_symbol=multi_technique_per_symbol
        ),
    )


# =============================================================================
# Multi-technique dedup — long + long
# =============================================================================


async def test_long_plus_long_keeps_highest_composite() -> None:
    """Two long techniques on the same symbol → highest composite wins."""
    high = make_strategy(
        info=make_info("high_ev", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.9),
    )
    low = make_strategy(
        info=make_info("low_ev", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.4),
    )
    engine = _engine(
        {"high_ev": high, "low_ev": low},
        {
            "high_ev": make_perf("high_ev", total_trades=20, avg_pnl_percent=3.0),
            "low_ev": make_perf("low_ev", total_trades=20, avg_pnl_percent=0.5),
        },
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    assert proposal.technique_name == "high_ev"
    # Both techniques ran (analyze called once each).
    assert high.analyze.await_count == 1
    assert low.analyze.await_count == 1


# =============================================================================
# Multi-technique dedup — long + short conflict
# =============================================================================


async def test_long_plus_short_conflict_keeps_highest_composite() -> None:
    """Opposing signals on the same symbol must NOT both pass through.

    Without per-symbol dedup the runtime engine would open a synthetic
    hedge at 2× ``risk_percent`` — the highest-composite candidate
    must win regardless of side.
    """
    bull = make_strategy(
        info=make_info("bull", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.5),
    )
    bear = make_strategy(
        info=make_info("bear", symbols=["BTC/USDT"]),
        analysis=make_analysis(
            signal="short", confidence=0.95, entry="50000", sl="50500", tp="48500"
        ),
    )
    engine = _engine(
        {"bull": bull, "bear": bear},
        {
            "bull": make_perf("bull", total_trades=20, avg_pnl_percent=1.0),
            "bear": make_perf("bear", total_trades=20, avg_pnl_percent=2.0),
        },
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    # ``bear`` has confidence 0.95 × edge 2.0 vs bull's 0.5 × 1.0
    assert proposal.technique_name == "bear"
    assert proposal.signal == "short"


# =============================================================================
# Neutral techniques are filtered before dedup
# =============================================================================


async def test_neutral_technique_is_filtered_out_before_dedup() -> None:
    """A neutral signal never becomes a candidate; the live one wins."""
    quiet = make_strategy(
        info=make_info("quiet", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="neutral"),
    )
    live = make_strategy(
        info=make_info("live", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.7),
    )
    engine = _engine(
        {"quiet": quiet, "live": live},
        {
            "quiet": make_perf("quiet", total_trades=50, avg_pnl_percent=10.0),
            "live": make_perf("live", total_trades=20, avg_pnl_percent=1.0),
        },
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    assert proposal.technique_name == "live"


# =============================================================================
# Cold-start techniques don't crowd out proven techniques
# =============================================================================


async def test_cold_start_does_not_crowd_out_proven_technique() -> None:
    """A no-history technique scores ``confidence × 0.5``; a proven one
    with edge × full sample beats it."""
    cold = make_strategy(
        info=make_info("cold", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=1.0),  # composite ~0.5
    )
    proven = make_strategy(
        info=make_info("proven", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.6),  # composite 0.6×2.0×1
    )
    engine = _engine(
        {"cold": cold, "proven": proven},
        # ``cold`` has no record → tracker default is 0 trades
        {"proven": make_perf("proven", total_trades=20, avg_pnl_percent=2.0)},
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    assert proposal.technique_name == "proven"
    assert proposal.score.composite > 0.5  # well above cold-start floor


# =============================================================================
# Top-K across the cross-symbol set after per-symbol dedup
# =============================================================================


async def test_top_k_after_per_symbol_dedup() -> None:
    """Three symbols × two techniques → 3 candidates after dedup; top-K
    selects across symbols, never doubling up on one pair."""
    big_winner = make_strategy(
        info=make_info(
            "big_winner",
            symbols=["ETH/USDT", "SOL/USDT", "ADA/USDT"],
        ),
        analysis=make_analysis(signal="long", confidence=0.9),
    )
    small_winner = make_strategy(
        info=make_info(
            "small_winner",
            symbols=["ETH/USDT", "SOL/USDT", "ADA/USDT"],
        ),
        analysis=make_analysis(signal="long", confidence=0.3),
    )
    engine = _engine(
        {"big_winner": big_winner, "small_winner": small_winner},
        {
            "big_winner": make_perf(
                "big_winner", total_trades=20, avg_pnl_percent=3.0
            ),
            "small_winner": make_perf(
                "small_winner", total_trades=20, avg_pnl_percent=1.0
            ),
        },
    )

    proposals = await engine.propose_altcoins(
        symbols=["ETH/USDT", "SOL/USDT", "ADA/USDT"], top_k=2
    )

    # Top-2 of 3 deduped symbols, every survivor is the big_winner.
    assert len(proposals) == 2
    symbols = {p.symbol for p in proposals}
    assert len(symbols) == 2  # diversified across symbols, not doubled-up
    assert all(p.technique_name == "big_winner" for p in proposals)


# =============================================================================
# Single-applicable-technique back-compat smoke
# =============================================================================


async def test_single_applicable_technique_still_works() -> None:
    """With only one applicable technique, multi-tech path is a no-op."""
    only = make_strategy(
        info=make_info("only", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine = _engine(
        {"only": only},
        {"only": make_perf("only", total_trades=20, avg_pnl_percent=2.0)},
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    assert proposal.technique_name == "only"


# =============================================================================
# Legacy opt-out path: identical to pre-10.6 behaviour
# =============================================================================


async def test_legacy_opt_out_uses_select_best_technique_unchanged() -> None:
    """``multi_technique_per_symbol=False`` must reproduce the legacy
    single-best-technique selection: only the best-EV technique runs;
    the others are never analysed."""
    high = make_strategy(
        info=make_info("high_ev", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    low = make_strategy(
        info=make_info("low_ev", symbols=["BTC/USDT"]),
        analysis=make_analysis(signal="long", confidence=0.8),
    )
    engine = _engine(
        {"high_ev": high, "low_ev": low},
        {
            "high_ev": make_perf("high_ev", total_trades=20, avg_pnl_percent=3.0),
            "low_ev": make_perf("low_ev", total_trades=20, avg_pnl_percent=0.2),
        },
        multi_technique_per_symbol=False,
    )

    proposal = await engine.propose_bitcoin(symbol="BTC/USDT")

    assert proposal is not None
    assert proposal.technique_name == "high_ev"
    # Pre-10.6 behaviour: only the chosen technique was analysed.
    assert high.analyze.await_count == 1
    assert low.analyze.await_count == 0
