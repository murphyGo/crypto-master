"""Auto-generate and gate Top-N catalog techniques from the priority matrix.

Operator script that turns picks from
``docs/research/strategies/00-priority-matrix.md`` into experimental
strategy candidates, runs them through the full feedback loop
(generate → backtest → robustness gate), and prints a summary so the
operator can decide which candidates to ``approve()`` for paper
trading.

The script does NOT auto-promote: every passing candidate stops at
``AWAITING_APPROVAL`` per CON-003. The operator reviews each one in
the dashboard or via ``FeedbackLoop.approve()`` before it joins the
active strategy pool.

Pipeline per pick::

    StrategyImprover.generate_idea(context=<description>)
        → strategies/experimental/{slug}_{ts}.md
    FeedbackLoop._run_cycle()
        → Backtester (baseline)
        → RobustnessGate (OOS / Walk-Forward / Regime / Sensitivity)
        → CandidateRecord{status: AWAITING_APPROVAL | DISCARDED | ERRORED}

Default picks are the top OHLCV-only entries from the matrix's
"first-wave automation" section, since the current
``BaseExchange`` only exposes OHLCV/ticker — funding/OI/on-chain
techniques need data wiring that lives in a later phase.

Usage::

    python -m scripts.auto_research_candidates             # top 5 picks
    python -m scripts.auto_research_candidates --picks 9   # all OHLCV picks
    python -m scripts.auto_research_candidates --dry-run   # generate only

Network: makes real Binance public-API calls for OHLCV and real
``claude -p`` calls for technique generation. Both are mocked in
``tests/test_scripts_auto_research_candidates.py``.

Related Requirements:
- FR-023: New Technique Idea Generation
- FR-026: Automated Feedback Loop
- FR-034: Robustness Validation Gate
- CON-003: User Approval Required

Known follow-ups (not blocking 17.1):
- ``run_async`` constructs its own ``FeedbackLoop`` / ``BinanceExchange``
  instead of taking caller-built ones from ``main`` — currently fine
  because ``main`` is the only caller, but if a future test wants to
  inject mocks at the ``main`` layer the wiring will need a tweak.
- ``loop.propose_new`` is invoked without a ``param_grid``, so the
  sensitivity gate skips. Runs through 17.1 will report sensitivity
  as SKIPPED rather than PASSED — a gap operators should know about
  until the API for declaring a per-pick parameter grid is designed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from scripts.backtest_baselines import fetch_ohlcv_window
from src.ai.improver import StrategyImprover
from src.backtest.analyzer import PerformanceAnalyzer
from src.backtest.engine import BacktestConfig, Backtester
from src.backtest.validator import RobustnessGate
from src.config import BinanceConfig
from src.exchange.binance import BinanceExchange
from src.feedback.audit import AuditLog
from src.feedback.loop import CandidateRecord, FeedbackLoop, LoopStatus
from src.logger import get_logger
from src.models import OHLCV

logger = get_logger("crypto_master.scripts.auto_research")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "data" / "research_runs"


def _default_candles_for(timeframe: Literal["15m", "1h", "4h"]) -> int:
    """Default candle window per timeframe, sized to span at least one
    bull→bear transition.

    The robustness gate's regime check uses a 200-bar SMA + ±2% band to
    classify bull / bear / sideways and requires at least one
    evaluable regime to verdict. With shorter windows BTC sits entirely
    on one side of the SMA and the gate verdicts on a single regime —
    technically a PASS but proves nothing about regime independence.
    Operators reading "regime PASSED" deserve a window that actually
    contains both regimes.

    Floors:

    * ``4h`` → ~2 years (4380 bars). Catches the full crypto cycle.
    * ``1h`` → ~1 year  (8760 bars). One bull/bear transition.
    * ``15m`` → ~6 months (17520 bars). Comparable coverage at the
      cost of more pagination.

    ``fetch_ohlcv_window`` paginates past Binance's per-call 1500-bar
    cap, so larger windows are a wallclock cost, not a hard cap.
    """
    return {
        "4h": 4380,
        "1h": 8760,
        "15m": 17520,
    }[timeframe]


@dataclass(frozen=True)
class Pick:
    """One catalog pick to validate.

    Attributes:
        slug: Short identifier used in logs / output files.
        context: Steering text passed to ``StrategyImprover.generate_idea``.
            Should name the technique and key parameters so Claude
            doesn't drift to something unrelated.
        timeframe: Preferred backtest timeframe.
        candles: How many bars to fetch (drives lookback length).
            ``0`` (the default) routes through :func:`_default_candles_for`
            so the regime gate sees both bull and bear conditions.
            Tests can pass an explicit smaller value to keep runtimes
            tight.
    """

    slug: str
    context: str
    timeframe: Literal["15m", "1h", "4h"]
    candles: int = 0

    def __post_init__(self) -> None:
        # Frozen dataclasses can't reassign normally; use object.__setattr__.
        if self.candles == 0:
            object.__setattr__(self, "candles", _default_candles_for(self.timeframe))


# Top OHLCV-only picks from docs/research/strategies/00-priority-matrix.md
# §3 Top 30 Picks. Crypto-native picks (funding/OI/on-chain) are
# omitted until the data layer expands — see deployment plan.
TOP_PICKS: list[Pick] = [
    Pick(
        slug="donchian_system2",
        context=(
            "Implement Donchian Channel breakout — Turtle System 2 "
            "(55-bar entry, 20-bar exit). Long when close breaks above "
            "55-bar high; exit when close breaks below 20-bar low. "
            "ATR(20)-based position sizing and stop-loss at 2×ATR. "
            "Reference: docs/research/strategies/03-breakout-range.md "
            "Donchian System 2."
        ),
        timeframe="4h",
    ),
    Pick(
        slug="supertrend",
        context=(
            "Implement Supertrend (ATR period 10, multiplier 3) trend-"
            "following on BTC/USDT 1h. Long when close > Supertrend "
            "line and trend just flipped to up; exit on flip down. "
            "Combine with EMA200 trend filter to avoid sideways chop. "
            "Reference: docs/research/strategies/05-trend-indicators.md "
            "Supertrend."
        ),
        timeframe="1h",
    ),
    Pick(
        slug="connors_rsi2",
        context=(
            "Implement Connors RSI(2) short-term mean reversion "
            "(daily): long when RSI(2) < 10 AND close > SMA(200); exit "
            "when close > SMA(5). Tight stop at recent swing low. "
            "Reference: docs/research/strategies/04-mean-reversion.md "
            "Connors RSI(2)."
        ),
        timeframe="4h",
    ),
    Pick(
        slug="zscore_mean_reversion",
        context=(
            "Implement Z-score mean reversion: compute rolling mean and "
            "stdev of close over 50 bars. Long when z < -2 AND ADX(14) "
            "< 20 (range regime); exit when z crosses back to 0. SL at "
            "z = -3. Reference: docs/research/strategies/04-mean-"
            "reversion.md Z-score / Standard Deviation Mean Reversion."
        ),
        timeframe="1h",
    ),
    Pick(
        slug="larry_williams_volatility",
        context=(
            "Implement Larry Williams Volatility Breakout (K=0.5): "
            "trigger price = today's open + K × previous day's range "
            "(high-low). Long when intraday close crosses above "
            "trigger; exit at session close or fixed stop. "
            "Reference: docs/research/strategies/03-breakout-range.md "
            "Volatility Breakout (Larry Williams)."
        ),
        timeframe="1h",
    ),
    Pick(
        slug="ttm_squeeze",
        context=(
            "Implement TTM Squeeze breakout: detect when Bollinger "
            "Bands (20, 2σ) are inside Keltner Channels (20, 1.5×ATR) "
            "for ≥6 bars (squeeze ON), then long on the bar where "
            "squeeze releases AND momentum histogram is positive. SL "
            "at 1.5×ATR below entry. Reference: docs/research/"
            "strategies/03-breakout-range.md TTM Squeeze."
        ),
        timeframe="1h",
    ),
    Pick(
        slug="bb_pct_b_rsi_combo",
        context=(
            "Implement Bollinger %B + RSI mean reversion combo: long "
            "when %B < 0.05 (touching lower band) AND RSI(14) < 30 "
            "AND price > EMA200 (uptrend filter). Exit on %B > 0.5 "
            "(mid-band) or RSI > 50. SL below the lower band. "
            "Reference: docs/research/strategies/04-mean-reversion.md "
            "Bollinger %B + RSI Combo."
        ),
        timeframe="1h",
    ),
    Pick(
        slug="golden_cross",
        context=(
            "Implement Golden Cross / Death Cross trend filter: long "
            "on SMA(50) crossing above SMA(200) (daily); flat/short on "
            "the inverse cross. Single position, no leverage. "
            "Reference: docs/research/strategies/05-trend-indicators.md "
            "Moving Average Crossover."
        ),
        timeframe="4h",
    ),
    Pick(
        slug="nr7_breakout",
        context=(
            "Implement NR7 (Narrowest Range in 7) breakout: identify "
            "bars whose range is the smallest of the last 7. Long when "
            "next bar closes above the NR7's high; SL below the NR7's "
            "low. Add ATR-based volatility regime filter to avoid "
            "low-volatility traps. Reference: docs/research/strategies/"
            "03-breakout-range.md NR7 Breakout."
        ),
        timeframe="1h",
    ),
]


@dataclass
class PickResult:
    """Outcome of one pick's full pipeline run.

    ``decision_reason`` and ``robustness_summary`` are both surfaced in
    the operator summary so a DISCARDED candidate's *why* is visible
    without opening the JSON snapshot — e.g. "Discarded: gate FAILED on
    regime" plus the report's regime-level detail (which regimes were
    evaluable, average expectancy, etc).
    """

    slug: str
    context_preview: str
    status: str  # LoopStatus value
    candidate_id: str | None
    technique_name: str | None
    saved_path: str | None
    robustness_passed: bool | None
    failed_gates: list[str]
    decision_reason: str
    robustness_summary: str | None = None
    error: str | None = None

    @classmethod
    def from_record(
        cls, slug: str, context: str, record: CandidateRecord
    ) -> PickResult:
        return cls(
            slug=slug,
            context_preview=context[:80] + ("…" if len(context) > 80 else ""),
            status=record.status,
            candidate_id=record.candidate_id,
            technique_name=record.technique_name,
            saved_path=str(record.source_path),
            robustness_passed=record.robustness_passed,
            failed_gates=list(record.failed_gates),
            decision_reason=record.decision_reason,
            robustness_summary=record.robustness_summary,
        )

    @classmethod
    def errored(cls, slug: str, context: str, error: Exception) -> PickResult:
        return cls(
            slug=slug,
            context_preview=context[:80] + ("…" if len(context) > 80 else ""),
            status=LoopStatus.ERRORED.value,
            candidate_id=None,
            technique_name=None,
            saved_path=None,
            robustness_passed=None,
            failed_gates=[],
            decision_reason="",
            robustness_summary=None,
            error=f"{type(error).__name__}: {error}",
        )


def build_loop() -> FeedbackLoop:
    """Wire the four building blocks into a FeedbackLoop instance."""
    improver = StrategyImprover()  # default catalog_path picks up the matrix
    backtester = Backtester(BacktestConfig())
    analyzer = PerformanceAnalyzer()
    gate = RobustnessGate(backtester=backtester)
    audit_log = AuditLog()
    return FeedbackLoop(
        improver=improver,
        backtester=backtester,
        analyzer=analyzer,
        gate=gate,
        audit_log=audit_log,
    )


async def fetch_for_picks(
    exchange: BinanceExchange,
    symbol: str,
    picks: list[Pick],
) -> dict[str, list[OHLCV]]:
    """Fetch and cache OHLCV per (symbol, timeframe) used by the picks."""
    cache: dict[str, list[OHLCV]] = {}
    for pick in picks:
        if pick.timeframe in cache:
            continue
        logger.info(
            f"Fetching {pick.candles} {pick.timeframe} bars of {symbol} "
            f"from Binance public API…"
        )
        bars = await fetch_ohlcv_window(
            exchange=exchange,
            symbol=symbol,
            timeframe=pick.timeframe,
            total_candles=pick.candles,
        )
        cache[pick.timeframe] = bars
        logger.info(f"  → {len(bars)} bars fetched")
    return cache


async def run_picks(
    picks: list[Pick],
    symbol: str,
    *,
    dry_run: bool = False,
    loop: FeedbackLoop | None = None,
    exchange: BinanceExchange | None = None,
) -> list[PickResult]:
    """Generate, backtest, and gate each pick.

    Args:
        picks: Catalog picks to validate.
        symbol: Market symbol (e.g. ``"BTC/USDT"``).
        dry_run: If True, only call ``improver.generate_idea`` and skip
            the backtest + gate. Useful for verifying Claude returns
            valid technique files without spending compute on the gate.
            Dry-run files are routed under
            ``<experimental_dir>/dry_runs/`` so they don't mix with
            real, gated candidates the operator might approve later.
        loop: Optional pre-built loop (tests inject mocks here).
        exchange: Optional pre-built exchange (tests inject mocks here).
    """
    loop = loop or build_loop()
    owns_exchange = exchange is None
    exchange = exchange or BinanceExchange(BinanceConfig())
    if owns_exchange:
        await exchange.connect()

    if dry_run:
        # Route dry-run output to a subdir so an operator running
        # `--dry-run` and then a real pass doesn't end up with a mix of
        # ungated and gated files in `strategies/experimental/`.
        # Re-pointing the improver is safe: nothing else in run_picks
        # writes to its experimental_dir.
        loop.improver.experimental_dir = loop.improver.experimental_dir / "dry_runs"

    try:
        cache = await fetch_for_picks(exchange, symbol, picks)
        results: list[PickResult] = []

        for pick in picks:
            ohlcv = cache[pick.timeframe]
            logger.info(f"=== Running pick: {pick.slug} ===")
            try:
                if dry_run:
                    generated = await loop.improver.generate_idea(
                        context=pick.context, save=True
                    )
                    logger.info(
                        f"  dry-run: generated technique '{generated.name}' at "
                        f"{generated.saved_path} — skipping backtest/gate"
                    )
                    results.append(
                        PickResult(
                            slug=pick.slug,
                            context_preview=pick.context[:80] + "…",
                            status="generated_only",
                            candidate_id=None,
                            technique_name=generated.name,
                            saved_path=str(generated.saved_path),
                            robustness_passed=None,
                            failed_gates=[],
                            decision_reason="dry-run",
                        )
                    )
                    continue

                record = await loop.propose_new(
                    context=pick.context,
                    ohlcv=ohlcv,
                    symbol=symbol,
                    timeframe=pick.timeframe,
                )
                results.append(PickResult.from_record(pick.slug, pick.context, record))
                logger.info(
                    f"  status={record.status} "
                    f"passed={record.robustness_passed} "
                    f"reason={record.decision_reason}"
                )
            except Exception as e:  # noqa: BLE001
                logger.exception(f"Pick {pick.slug} errored: {e}")
                results.append(PickResult.errored(pick.slug, pick.context, e))

        return results
    finally:
        if owns_exchange:
            await exchange.disconnect()


def render_summary(results: list[PickResult]) -> str:
    """Format the run summary as a markdown table.

    A primary row carries the headline columns (slug / status / passed /
    failed-gate names / technique). Each row is followed by an indented
    continuation line carrying the human-readable ``decision_reason``
    and the gate's full ``robustness_summary`` (which surfaces e.g.
    "regime PASSED on 1 evaluable regime" vs. "PASSED on 3"). This way
    operators can spot WHY a pick was DISCARDED without opening the
    JSON snapshot, while still keeping the table itself narrow.
    """
    if not results:
        return "(no picks ran)"

    rows = [
        "| slug | status | passed | failed gates | technique |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        passed = (
            "✓" if r.robustness_passed else "✗" if r.robustness_passed is False else "—"
        )
        failed = ", ".join(r.failed_gates) if r.failed_gates else "—"
        tech = r.technique_name or "—"
        rows.append(f"| {r.slug} | {r.status} | {passed} | {failed} | {tech} |")

        # Indented continuation: decision reason + gate-level summary.
        # Both can be empty for a freshly-generated candidate that
        # never reached the gate; print them only when present.
        detail_bits: list[str] = []
        if r.decision_reason:
            detail_bits.append(f"reason: {r.decision_reason}")
        if r.robustness_summary:
            detail_bits.append(f"gate: {r.robustness_summary}")
        if r.error:
            detail_bits.append(f"error: {r.error}")
        if detail_bits:
            rows.append("    " + " | ".join(detail_bits))
    return "\n".join(rows)


def write_run_artifacts(
    results: list[PickResult], results_dir: Path | None = None
) -> Path:
    """Persist a JSON snapshot of this run for post-hoc review."""
    target_dir = results_dir or DEFAULT_RESULTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = target_dir / f"run_{ts}.json"
    payload = {
        "timestamp": ts,
        "results": [r.__dict__ for r in results],
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


async def run_async(
    picks: list[Pick], symbol: str, *, dry_run: bool, results_dir: Path | None
) -> int:
    results = await run_picks(picks, symbol, dry_run=dry_run)
    summary = render_summary(results)
    print("\n=== Auto-research summary ===\n")
    print(summary)
    artifact = write_run_artifacts(results, results_dir=results_dir)
    print(f"\nFull results: {artifact}")

    awaiting = sum(1 for r in results if r.status == LoopStatus.AWAITING_APPROVAL.value)
    print(
        f"\n{awaiting}/{len(results)} candidates passed the gate and are "
        "AWAITING_APPROVAL. Review in the dashboard or call "
        "FeedbackLoop.approve() to promote."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--picks",
        type=int,
        default=5,
        help=f"How many top picks to run (max {len(TOP_PICKS)}, default 5)",
    )
    parser.add_argument(
        "--symbol", default="BTC/USDT", help="Market symbol (default BTC/USDT)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate techniques only; skip backtest + robustness gate",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Where to write the run snapshot (default data/research_runs)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    n = max(1, min(args.picks, len(TOP_PICKS)))
    picks = TOP_PICKS[:n]
    logger.info(f"Running {n} picks against {args.symbol} (dry_run={args.dry_run})")
    return asyncio.run(
        run_async(
            picks, args.symbol, dry_run=args.dry_run, results_dir=args.results_dir
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
