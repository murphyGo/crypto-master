"""Backtest the bundled baseline strategies and write reference numbers.

Phase 10.3 operator script. Pulls historical OHLCV from Binance's
public klines endpoint (no API keys needed — public market data),
runs each baseline strategy through :class:`Backtester` and
:class:`PerformanceAnalyzer`, and persists three artefacts per
baseline under ``data/backtest/baselines/<technique_name>/``:

* ``result.json``  — full :class:`BacktestResult` (NFR-006).
* ``analysis.md``  — human-readable performance report.
* ``summary.json`` — flat row consumed by :func:`update_baselines_doc`
  to refresh the reference-numbers table in ``docs/baselines.md``.

Idempotent: re-running the script overwrites the previous artefacts
cleanly. The script does not commit or push; the operator reviews
the diff and commits manually.

Usage::

    # From the project root, with the venv active:
    python -m scripts.backtest_baselines

    # Skip the docs update (just re-run the backtests):
    python -m scripts.backtest_baselines --no-update-doc

The script makes real network calls to Binance's public klines API.
There is no automated CI invocation — that's why this lives in
``scripts/`` rather than ``src/``. The smoke test in
``tests/test_scripts_backtest_baselines.py`` mocks the exchange and
verifies the artefact layout without hitting the network.

Related Requirements:
- FR-025: Backtesting Execution (consumed)
- NFR-006: Backtesting Result Storage
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.backtest.analyzer import PerformanceAnalyzer, PerformanceMetrics
from src.backtest.engine import Backtester, BacktestResult
from src.config import BinanceConfig
from src.exchange.binance import BinanceExchange
from src.logger import get_logger
from src.models import OHLCV
from src.strategy.base import BaseStrategy
from src.strategy.loader import load_strategy

logger = get_logger("crypto_master.scripts.backtest_baselines")

# Project layout. Constants kept module-level so tests can monkeypatch
# them onto a ``tmp_path`` without re-importing.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGIES_DIR = PROJECT_ROOT / "strategies"
DEFAULT_BASELINE_DIR = PROJECT_ROOT / "data" / "backtest" / "baselines"
DEFAULT_BASELINES_DOC = PROJECT_ROOT / "docs" / "baselines.md"

# Binance public API caps a single ``fetch_ohlcv`` call at 1500 bars,
# so longer windows (3mo × 1h ≈ 2160 bars; 1mo × 15m ≈ 2880 bars) need
# to be paginated. We walk back from "now" page-by-page.
BINANCE_MAX_LIMIT = 1500

# Candle duration in milliseconds, by timeframe label. Used to compute
# the ``since`` cursor when paginating.
TIMEFRAME_MS: dict[str, int] = {
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
}


@dataclass(frozen=True)
class BaselineSpec:
    """Declarative description of one baseline backtest run.

    Attributes:
        technique_name: Logical baseline name; matches the strategy's
            ``TECHNIQUE_INFO["name"]`` and the row label in
            ``docs/baselines.md``.
        strategy_file: Filename of the strategy under ``strategies/``.
        symbol: Trading pair to fetch OHLCV for.
        timeframe: Candle timeframe.
        candles: Total candle count to fetch (drives the lookback window).
        period_label: Human-readable period for the baselines doc table
            (e.g. ``"3mo 1h"``).
    """

    technique_name: str
    strategy_file: str
    symbol: str
    timeframe: Literal["15m", "1h", "4h"]
    candles: int
    period_label: str


# Five baselines mirroring docs/baselines.md. Periods follow the
# Phase 10.3 spec: 3 months for swing baselines, 1 month for the 15m
# scalp variant. Exact candle counts approximate calendar months
# (30 days = 720 hours = 2880 fifteen-minute candles).
BASELINES: tuple[BaselineSpec, ...] = (
    BaselineSpec(
        technique_name="rsi_universal",
        strategy_file="rsi.py",
        symbol="BTC/USDT",
        timeframe="1h",
        candles=24 * 90,  # 90 days × 24 = 2160
        period_label="3mo 1h",
    ),
    BaselineSpec(
        technique_name="rsi_4h",
        strategy_file="rsi_4h.py",
        symbol="BTC/USDT",
        timeframe="4h",
        candles=6 * 90,  # 90 days × 6 = 540
        period_label="3mo 4h",
    ),
    BaselineSpec(
        technique_name="rsi_15m",
        strategy_file="rsi_15m.py",
        symbol="BTC/USDT",
        timeframe="15m",
        candles=96 * 30,  # 30 days × 96 = 2880
        period_label="1mo 15m",
    ),
    BaselineSpec(
        technique_name="bollinger_band_reversion",
        strategy_file="bollinger_bands.py",
        symbol="BTC/USDT",
        timeframe="1h",
        candles=24 * 90,
        period_label="3mo 1h",
    ),
    BaselineSpec(
        technique_name="ma_crossover",
        strategy_file="ma_crossover.py",
        symbol="BTC/USDT",
        timeframe="1h",
        candles=24 * 90,
        period_label="3mo 1h",
    ),
)


# ---------------------------------------------------------------------------
# Public API (also used by the smoke test)
# ---------------------------------------------------------------------------


async def fetch_ohlcv_window(
    exchange: BinanceExchange,
    symbol: str,
    timeframe: Literal["15m", "1h", "4h"],
    total_candles: int,
) -> list[OHLCV]:
    """Fetch ``total_candles`` of OHLCV, paginating past Binance's 1500-bar cap.

    For windows longer than the per-call cap we page backwards using
    ``BinanceExchange.get_ohlcv(..., since=...)``: fetch the most
    recent page first, then repeatedly request the page that ends just
    before that one's earliest timestamp. The returned list is
    chronologically ascending and de-duplicated by timestamp.

    Args:
        exchange: A connected :class:`BinanceExchange`.
        symbol: Trading pair (e.g. ``"BTC/USDT"``).
        timeframe: Candle timeframe label.
        total_candles: Approximate number of bars wanted. The actual
            length may be slightly less if the exchange returns fewer
            bars than requested for a page.

    Returns:
        List of :class:`OHLCV`, ascending by timestamp.
    """
    if total_candles <= BINANCE_MAX_LIMIT:
        return await exchange.get_ohlcv(
            symbol=symbol, timeframe=timeframe, limit=total_candles
        )

    candle_ms = TIMEFRAME_MS[timeframe]

    # Page back from "now": fetch the most-recent page first, then
    # repeatedly request the page that ends just before that one's
    # earliest timestamp.
    pages: list[list[OHLCV]] = []
    recent = await exchange.get_ohlcv(
        symbol=symbol, timeframe=timeframe, limit=BINANCE_MAX_LIMIT
    )
    if not recent:
        return []
    pages.append(recent)
    earliest_ts = int(recent[0].timestamp.timestamp() * 1000)
    fetched = len(recent)

    while fetched < total_candles:
        page_size = min(BINANCE_MAX_LIMIT, total_candles - fetched)
        # Request the window ending just before the earliest bar we
        # already have. ccxt's ``since`` is inclusive on the start.
        since = earliest_ts - candle_ms * page_size
        page = await exchange.get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=page_size,
            since=since,
        )
        if not page:
            break
        pages.append(page)
        new_earliest = int(page[0].timestamp.timestamp() * 1000)
        if new_earliest >= earliest_ts:
            # No older data available; bail to avoid an infinite loop.
            break
        earliest_ts = new_earliest
        fetched += len(page)

    # Flatten + dedupe (pages may overlap by a candle at the boundary).
    seen: set[int] = set()
    flat: list[OHLCV] = []
    for page in pages:
        for candle in page:
            ts = int(candle.timestamp.timestamp() * 1000)
            if ts in seen:
                continue
            seen.add(ts)
            flat.append(candle)
    flat.sort(key=lambda c: c.timestamp)
    return flat


def serialize_result(result: BacktestResult) -> dict:
    """Serialize a :class:`BacktestResult` for ``result.json``.

    Mirrors :meth:`Backtester._result_to_dict`'s contract — we don't
    call that protected helper directly to avoid the coupling, but the
    output shape is the same so downstream consumers can ``BacktestResult(**data)``.
    """
    data = result.model_dump()
    for key in ("start_time", "end_time"):
        data[key] = data[key].isoformat()
    for key in ("initial_balance", "final_balance", "total_pnl", "total_fees"):
        data[key] = str(data[key])
    for trade in data["trades"]:
        trade["entry_time"] = trade["entry_time"].isoformat()
        trade["exit_time"] = trade["exit_time"].isoformat()
        for k in (
            "entry_price",
            "exit_price",
            "quantity",
            "stop_loss",
            "take_profit",
            "entry_fee",
            "exit_fee",
            "pnl",
        ):
            if trade.get(k) is not None:
                trade[k] = str(trade[k])
    return data


def build_summary(
    spec: BaselineSpec,
    metrics: PerformanceMetrics,
) -> dict:
    """Build the flat ``summary.json`` row for the docs table.

    Sharpe is reported as ``None`` (rendered as "n/a") when the run
    produced fewer than two trades — mirroring
    :class:`PerformanceAnalyzer`'s contract.
    """
    return {
        "technique_name": spec.technique_name,
        "symbol": spec.symbol,
        "period_label": spec.period_label,
        "win_rate": metrics.win_rate,
        "total_return_percent": metrics.return_percent,
        "sharpe_ratio": metrics.sharpe_ratio,
        "max_drawdown_percent": metrics.max_drawdown_percent,
        "total_trades": metrics.total_trades,
    }


def write_baseline_artifacts(
    spec: BaselineSpec,
    result: BacktestResult,
    metrics: PerformanceMetrics,
    output_root: Path,
) -> Path:
    """Persist ``result.json`` + ``analysis.md`` + ``summary.json``.

    Args:
        spec: The baseline that was just run.
        result: The full backtest result.
        metrics: Pre-computed performance metrics.
        output_root: Root dir for baselines (typically
            ``data/backtest/baselines``).

    Returns:
        The per-baseline directory (``output_root / spec.technique_name``).
    """
    baseline_dir = output_root / spec.technique_name
    baseline_dir.mkdir(parents=True, exist_ok=True)

    (baseline_dir / "result.json").write_text(
        json.dumps(serialize_result(result), indent=2),
        encoding="utf-8",
    )

    analyzer = PerformanceAnalyzer()
    (baseline_dir / "analysis.md").write_text(
        analyzer.generate_report(result, metrics=metrics),
        encoding="utf-8",
    )

    (baseline_dir / "summary.json").write_text(
        json.dumps(build_summary(spec, metrics), indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Baseline %s: trades=%d win_rate=%.2f%% sharpe=%s mdd=%.2f%% return=%.2f%%",
        spec.technique_name,
        metrics.total_trades,
        metrics.win_rate * 100,
        f"{metrics.sharpe_ratio:.3f}"
        if metrics.sharpe_ratio is not None
        else "n/a",
        metrics.max_drawdown_percent,
        metrics.return_percent,
    )
    return baseline_dir


async def run_baseline(
    spec: BaselineSpec,
    exchange: BinanceExchange,
    output_root: Path,
    *,
    strategies_dir: Path = STRATEGIES_DIR,
) -> dict:
    """Run a single baseline end-to-end and persist its artefacts.

    Args:
        spec: The baseline to run.
        exchange: A connected :class:`BinanceExchange`.
        output_root: Root dir for per-baseline output.
        strategies_dir: Where the strategy file lives.

    Returns:
        The summary dict (same content as ``summary.json``).
    """
    strategy_path = strategies_dir / spec.strategy_file
    strategy: BaseStrategy = load_strategy(strategy_path)
    logger.info(
        "Backtesting %s (%s × %s, %d candles)",
        spec.technique_name,
        spec.symbol,
        spec.timeframe,
        spec.candles,
    )

    ohlcv = await fetch_ohlcv_window(
        exchange=exchange,
        symbol=spec.symbol,
        timeframe=spec.timeframe,
        total_candles=spec.candles,
    )
    if not ohlcv:
        raise RuntimeError(
            f"No OHLCV returned for {spec.symbol} {spec.timeframe}; "
            "cannot run baseline."
        )

    backtester = Backtester()
    result = await backtester.run_for_strategy(
        strategy=strategy,
        ohlcv=ohlcv,
        symbol=spec.symbol,
        timeframe=spec.timeframe,
        profile=None,
    )
    metrics = PerformanceAnalyzer().analyze(result)
    write_baseline_artifacts(spec, result, metrics, output_root)
    return build_summary(spec, metrics)


# ---------------------------------------------------------------------------
# Markdown table rendering
# ---------------------------------------------------------------------------


# Region of docs/baselines.md that gets re-rendered. The header line
# (``| Strategy | Symbol | ...``) and the separator row are matched
# verbatim; everything between the separator and the next blank line
# is replaced with rows assembled from per-baseline ``summary.json``s.
_TABLE_HEADER = (
    "| Strategy | Symbol | Period | Win Rate | Sharpe | MDD |\n"
    "|----------|--------|--------|----------|--------|-----|\n"
)
_TABLE_PATTERN = re.compile(
    r"(\| Strategy \| Symbol \| Period \| Win Rate \| Sharpe \| MDD \|\n"
    r"\|[\-\| ]+\|\n)"
    r"(?:\|[^\n]*\n)+",
    re.MULTILINE,
)


def _format_metric(value: float | None, suffix: str = "") -> str:
    """Render a metric for the docs table, falling back to ``_TBD_``."""
    if value is None:
        return "n/a"
    return f"{value:.2f}{suffix}"


def render_table(summaries: list[dict]) -> str:
    """Render the reference-numbers Markdown table from summary rows.

    Rows preserve the order of ``summaries``. The caller is expected to
    pass them in the canonical baseline order (matches :data:`BASELINES`).
    """
    lines = [_TABLE_HEADER.rstrip("\n")]
    for s in summaries:
        win_rate_pct = (
            s["win_rate"] * 100 if s.get("win_rate") is not None else None
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{s['technique_name']}`",
                    s["symbol"],
                    s["period_label"],
                    _format_metric(win_rate_pct, "%"),
                    _format_metric(s.get("sharpe_ratio")),
                    _format_metric(s.get("max_drawdown_percent"), "%"),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def update_baselines_doc(
    summaries: list[dict],
    doc_path: Path = DEFAULT_BASELINES_DOC,
) -> str:
    """Rewrite the reference-numbers table in ``docs/baselines.md``.

    Reads the file, splices the freshly-rendered table over the old
    rows, and writes the result back. Returns the new file content
    (also useful for the smoke test).

    Args:
        summaries: Ordered list of baseline summary dicts (one per row).
        doc_path: Path to the baselines doc.

    Returns:
        The full new contents of ``doc_path``.

    Raises:
        RuntimeError: If the table region can't be found in the doc.
    """
    text = doc_path.read_text(encoding="utf-8")
    table = render_table(summaries)
    new_text, count = _TABLE_PATTERN.subn(table, text, count=1)
    if count == 0:
        raise RuntimeError(
            f"Could not locate the reference-numbers table in {doc_path}; "
            "check the header row matches the expected format."
        )
    doc_path.write_text(new_text, encoding="utf-8")
    return new_text


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


async def run_all(
    *,
    output_root: Path = DEFAULT_BASELINE_DIR,
    update_doc: bool = True,
    doc_path: Path = DEFAULT_BASELINES_DOC,
    exchange: BinanceExchange | None = None,
    strategies_dir: Path = STRATEGIES_DIR,
) -> list[dict]:
    """Run every baseline and (optionally) update the docs table.

    Args:
        output_root: Where to write per-baseline artefacts.
        update_doc: If True, rewrite the table in ``doc_path``.
        doc_path: Path to the baselines doc.
        exchange: Pre-built exchange (mainly for tests). When ``None``,
            a fresh :class:`BinanceExchange` is constructed and
            connected against Binance mainnet (public endpoints only).
        strategies_dir: Where the baseline strategy files live.

    Returns:
        Ordered summary dicts (one per baseline, in :data:`BASELINES`
        order).
    """
    output_root.mkdir(parents=True, exist_ok=True)

    owns_exchange = exchange is None
    if exchange is None:
        # Public OHLCV endpoint — no keys needed. Mainnet (testnet=False)
        # because Binance testnet historical data is sparse / synthetic.
        exchange = BinanceExchange(
            BinanceConfig(api_key="", api_secret=""), testnet=False
        )
        await exchange.connect()

    summaries: list[dict] = []
    try:
        for spec in BASELINES:
            summary = await run_baseline(
                spec=spec,
                exchange=exchange,
                output_root=output_root,
                strategies_dir=strategies_dir,
            )
            summaries.append(summary)
    finally:
        if owns_exchange:
            await exchange.disconnect()

    if update_doc:
        update_baselines_doc(summaries, doc_path=doc_path)
        logger.info("Updated reference-numbers table in %s", doc_path)

    return summaries


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        description="Backtest the bundled baseline strategies."
    )
    parser.add_argument(
        "--no-update-doc",
        action="store_true",
        help="Skip rewriting the table in docs/baselines.md.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_BASELINE_DIR,
        help="Where per-baseline artefacts go "
        "(default: data/backtest/baselines).",
    )
    args = parser.parse_args(argv)

    # Bring the script's logs to the operator's terminal. The library
    # logger defaults to WARNING for non-root namespaces.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    summaries = asyncio.run(
        run_all(
            output_root=args.output_dir,
            update_doc=not args.no_update_doc,
        )
    )
    print(f"Ran {len(summaries)} baselines:")
    for s in summaries:
        wr = s["win_rate"] * 100 if s["win_rate"] is not None else 0.0
        sharpe = (
            f"{s['sharpe_ratio']:.3f}"
            if s["sharpe_ratio"] is not None
            else "n/a"
        )
        print(
            f"  {s['technique_name']:<28} "
            f"trades={s['total_trades']:>4}  "
            f"wr={wr:>6.2f}%  "
            f"sharpe={sharpe:>7}  "
            f"mdd={s['max_drawdown_percent']:>6.2f}%  "
            f"ret={s['total_return_percent']:>+7.2f}%"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
