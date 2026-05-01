"""Backtest the bundled baseline strategies and write reference numbers.

Phase 10.3 operator script, Phase 25.2 snapshot-pinned. Runs each
baseline strategy through :class:`Backtester` and
:class:`PerformanceAnalyzer`, and persists three artefacts per
baseline under ``data/backtest/baselines/<technique_name>/``:

* ``result.json``  — full :class:`BacktestResult` (NFR-006).
* ``analysis.md``  — human-readable performance report.
* ``summary.json`` — flat row consumed by :func:`update_baselines_doc`
  to refresh the reference-numbers table in ``docs/baselines.md``.

Idempotent: re-running the script overwrites the previous artefacts
cleanly. The script does not commit or push; the operator reviews
the diff and commits manually.

**Phase 25.2 snapshot-pinned mode.** The default, recommended,
reproducible path is ``--snapshot``: OHLCV reads route through
:class:`src.backtest.snapshot.SnapshotExchange` instead of
mainnet, so two operators on different days produce byte-identical
baseline numbers. The live-fetch path stays available behind
``--refresh-snapshot`` (operator-gated; the only path that touches
mainnet) for the rare case where the snapshot needs refreshing.

Usage::

    # Reproducible run from the committed snapshot dataset.
    python -m scripts.backtest_baselines --snapshot

    # Refresh the snapshot from live Binance (operator-gated).
    python -m scripts.backtest_baselines --refresh-snapshot

    # Tighten the active-baseline freshness window (default 30 days).
    python -m scripts.backtest_baselines --snapshot \\
        --max-snapshot-age-days 14

    # Skip the docs update (just re-run the backtests):
    python -m scripts.backtest_baselines --snapshot --no-update-doc

The smoke test in ``tests/test_scripts_backtest_baselines.py``
exercises every path against synthetic OHLCV without hitting the
network.

Related Requirements:
- FR-025: Backtesting Execution (consumed; Phase 25 extends with
  snapshot-pinned reproducibility)
- NFR-006: Backtesting Result Storage
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from src.backtest.analyzer import PerformanceAnalyzer, PerformanceMetrics
from src.backtest.engine import Backtester, BacktestResult
from src.backtest.snapshot import (
    Snapshot,
    SnapshotExchange,
    SnapshotMetadata,
    baseline_directory,
    is_snapshot_fresh,
    save_snapshot,
)
from src.config import BinanceConfig, get_settings
from src.exchange.binance import BinanceExchange
from src.logger import get_logger
from src.models import OHLCV
from src.strategy.base import BaseStrategy
from src.strategy.loader import load_strategy
from src.utils.time import now_utc

logger = get_logger("crypto_master.scripts.backtest_baselines")

# Project layout. Constants kept module-level so tests can monkeypatch
# them onto a ``tmp_path`` without re-importing.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGIES_DIR = PROJECT_ROOT / "strategies"
DEFAULT_BASELINE_DIR = PROJECT_ROOT / "data" / "backtest" / "baselines"
DEFAULT_BASELINES_DOC = PROJECT_ROOT / "docs" / "baselines.md"
# Phase 25.2: snapshot-pinned dataset root. ``SnapshotExchange``
# resolves the conventional ``baselines/<SYMBOL>__<timeframe>/``
# layout underneath this root.
DEFAULT_SNAPSHOT_ROOT = PROJECT_ROOT / "data" / "backtest" / "snapshots"
# Per quant carry-over from 25.1: the operator path runs against a
# tighter 30-day window than the absolute 90-day stale ceiling
# defined in ``src.backtest.snapshot.DEFAULT_MAX_AGE_DAYS``. 30 days
# is the active-use limit for promotion-gate baselines; 90 is the
# absolute ceiling beyond which the snapshot is unambiguously stale.
DEFAULT_MAX_SNAPSHOT_AGE_DAYS = 30

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
#
# Phase 25.2 reconciliation note. The 25 plan referred to "4 baselines"
# (matching docs/baselines.md's narrative count) while the script ships
# 5. Decision: KEEP ``rsi_universal``. It's a deliberate fallback
# variant (Phase 9.4; see strategies/rsi.py module docstring) that
# represents the "universal-cadence" RSI run alongside the explicit-
# cadence ``rsi_4h`` and ``rsi_15m`` siblings. Dropping it would
# silently lose the universal baseline's edge history. Phase 25.3 will
# update the docs/baselines.md table to enumerate all five rows.
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
    # Phase 24.1 / DEBT-030: per-bar equity curve.
    for point in data.get("equity_curve", []):
        point["timestamp"] = point["timestamp"].isoformat()
        point["equity"] = str(point["equity"])
    return data


def build_summary(
    spec: BaselineSpec,
    metrics: PerformanceMetrics,
    *,
    result: BacktestResult | None = None,
    fetched_at: datetime | None = None,
) -> dict:
    """Build the flat ``summary.json`` row for the docs table.

    Sharpe is reported as ``None`` (rendered as "n/a") when the run
    produced fewer than two trades — mirroring
    :class:`PerformanceAnalyzer`'s contract.

    DEBT-048 (Phase 26.2): the docs table widened to 9 columns; the
    summary now also carries ``total_pnl`` (from the
    :class:`BacktestResult` when available) and ``fetched_at`` (from
    the snapshot metadata when running with ``--snapshot``). Both are
    optional — callers that don't have them pass ``None`` and the
    table cell renders the ``_AWAITING_OPERATOR_FIRST_RUN_`` token.
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
        "total_pnl": str(result.total_pnl) if result is not None else None,
        "fetched_at": fetched_at.isoformat() if fetched_at is not None else None,
    }


def write_baseline_artifacts(
    spec: BaselineSpec,
    result: BacktestResult,
    metrics: PerformanceMetrics,
    output_root: Path,
    *,
    fetched_at: datetime | None = None,
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
        json.dumps(
            build_summary(spec, metrics, result=result, fetched_at=fetched_at),
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info(
        "Baseline %s: trades=%d win_rate=%.2f%% sharpe=%s mdd=%.2f%% return=%.2f%%",
        spec.technique_name,
        metrics.total_trades,
        metrics.win_rate * 100,
        f"{metrics.sharpe_ratio:.3f}" if metrics.sharpe_ratio is not None else "n/a",
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
    fetched_at: datetime | None = None,
) -> dict:
    """Run a single baseline end-to-end and persist its artefacts.

    Args:
        spec: The baseline to run.
        exchange: A connected :class:`BinanceExchange`.
        output_root: Root dir for per-baseline output.
        strategies_dir: Where the strategy file lives.
        fetched_at: Snapshot ``fetched_at`` ISO timestamp (DEBT-048,
            Phase 26.2). Threaded through to the docs table when
            running off ``--snapshot``; ``None`` when running off
            live Binance.

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
    write_baseline_artifacts(spec, result, metrics, output_root, fetched_at=fetched_at)
    return build_summary(spec, metrics, result=result, fetched_at=fetched_at)


# ---------------------------------------------------------------------------
# Markdown table rendering
# ---------------------------------------------------------------------------


# Region of docs/baselines.md that gets re-rendered. The header line
# (``| Strategy | Symbol | ...``) and the separator row are matched
# verbatim; everything between the separator and the next blank line
# is replaced with rows assembled from per-baseline ``summary.json``s.
#
# DEBT-048 (Phase 26.2): widened from 6 to 9 columns — added
# ``Trades``, ``Total PnL (USDT)``, ``Snapshot fetched_at``; renamed
# ``Period`` → ``Timeframe``. Placeholder token swapped from ``_TBD_``
# to the more semantic ``_AWAITING_OPERATOR_FIRST_RUN_``.
PLACEHOLDER_TOKEN = "_AWAITING_OPERATOR_FIRST_RUN_"

_TABLE_HEADER = (
    "| Strategy | Symbol | Timeframe | Trades | Win Rate | Sharpe | "
    "MDD | Total PnL (USDT) | Snapshot fetched_at |\n"
    "|----------|--------|-----------|--------|----------|--------|"
    "-----|------------------|---------------------|\n"
)
_TABLE_PATTERN = re.compile(
    r"(\| Strategy \| Symbol \| Timeframe \| Trades \| Win Rate \| Sharpe \| "
    r"MDD \| Total PnL \(USDT\) \| Snapshot fetched_at \|\n"
    r"\|[\-\| ]+\|\n)"
    r"(?:\|[^\n]*\n)+",
    re.MULTILINE,
)


def _format_metric(value: float | None, suffix: str = "") -> str:
    """Render a metric for the docs table, falling back to ``n/a``."""
    if value is None:
        return "n/a"
    return f"{value:.2f}{suffix}"


def render_table(summaries: list[dict]) -> str:
    """Render the reference-numbers Markdown table from summary rows.

    Rows preserve the order of ``summaries``. The caller is expected to
    pass them in the canonical baseline order (matches :data:`BASELINES`).

    DEBT-048 (Phase 26.2): each summary row may carry ``total_pnl`` and
    ``fetched_at`` (snapshot ISO-8601 timestamp). When either is absent
    or ``None`` the cell renders as the placeholder token to signal
    the operator first run still needs to land for that field.
    """
    lines = [_TABLE_HEADER.rstrip("\n")]
    for s in summaries:
        win_rate_pct = s["win_rate"] * 100 if s.get("win_rate") is not None else None
        total_pnl = s.get("total_pnl")
        if total_pnl is None:
            total_pnl_cell = PLACEHOLDER_TOKEN
        else:
            total_pnl_cell = f"{float(total_pnl):.2f}"
        fetched_at = s.get("fetched_at") or PLACEHOLDER_TOKEN
        trades = s.get("total_trades")
        trades_cell = str(trades) if trades is not None else PLACEHOLDER_TOKEN
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{s['technique_name']}`",
                    s["symbol"],
                    s["period_label"],
                    trades_cell,
                    _format_metric(win_rate_pct, "%"),
                    _format_metric(s.get("sharpe_ratio")),
                    _format_metric(s.get("max_drawdown_percent"), "%"),
                    total_pnl_cell,
                    fetched_at,
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


def _build_snapshot_exchange(
    snapshot_root: Path,
    max_snapshot_age_days: int,
    *,
    now: datetime | None = None,
) -> SnapshotExchange:
    """Load every BASELINES snapshot off disk and freshness-check.

    Phase 25.2 read path. Loads one snapshot per (symbol, timeframe)
    pair declared in :data:`BASELINES` and refuses to proceed if any
    of them was fetched more than ``max_snapshot_age_days`` ago — the
    operator must explicitly opt in to refreshing via
    ``--refresh-snapshot`` rather than silently consuming stale data.

    Args:
        snapshot_root: Snapshot dataset root (typically
            ``data/backtest/snapshots``); the conventional
            ``baselines/<SYMBOL>__<timeframe>/`` layout from
            :func:`baseline_directory` is resolved underneath.
        max_snapshot_age_days: Active-use freshness window (default
            30 per quant). Tighter than the 90-day absolute ceiling
            in :data:`src.backtest.snapshot.DEFAULT_MAX_AGE_DAYS`.
        now: Override the wall clock for tests.

    Returns:
        Loaded :class:`SnapshotExchange` ready for injection.

    Raises:
        RuntimeError: If any required snapshot is older than
            ``max_snapshot_age_days``. The message names the offending
            (symbol, timeframe) and the snapshot's ``fetched_at`` so
            the operator can spot the mis-aged file directly.
    """
    pairs = sorted({(spec.symbol, spec.timeframe) for spec in BASELINES})
    exchange = SnapshotExchange.from_directory(snapshot_root, pairs)

    # Freshness check. Use the script's tighter active-use window
    # (default 30) rather than the snapshot module's 90-day default.
    for (symbol, timeframe), metadata in exchange.loaded_metadata().items():
        if not is_snapshot_fresh(
            metadata,
            max_age_days=max_snapshot_age_days,
            now=now,
        ):
            raise RuntimeError(
                f"snapshot for ({symbol}, {timeframe}) is older than "
                f"{max_snapshot_age_days} days "
                f"(fetched_at={metadata.fetched_at.isoformat()}); "
                "re-run with --refresh-snapshot to fetch a fresh one."
            )
    return exchange


async def refresh_snapshots(
    *,
    snapshot_root: Path = DEFAULT_SNAPSHOT_ROOT,
    exchange: BinanceExchange | None = None,
) -> list[Path]:
    """Fetch fresh OHLCV from live Binance and overwrite the snapshots.

    Phase 25.2 operator-gated refresh path. This is the ONLY path
    that touches Binance mainnet; the rest of the script consumes
    the persisted snapshots. Each unique (symbol, timeframe) pair in
    :data:`BASELINES` is fetched (paginated past the 1500-bar cap if
    needed), wrapped in a :class:`Snapshot` with a fresh
    :class:`SnapshotMetadata` sidecar (``fetched_at=now_utc()``,
    ``fetcher_version="phase-25.2"``), and written via
    :func:`save_snapshot` to ``baseline_directory(snapshot_root, ...)``.

    Args:
        snapshot_root: Snapshot dataset root.
        exchange: Pre-built exchange (mainly for tests). When ``None``,
            a fresh :class:`BinanceExchange` is constructed against
            mainnet and disconnected on completion.

    Returns:
        List of snapshot directories written, one per refreshed
        (symbol, timeframe) pair.
    """
    # Per-pair candle count: the ``BASELINES`` list may contain
    # multiple specs for the same (symbol, timeframe) pair; fetch
    # the longest window so every spec is covered by one snapshot.
    per_pair_candles: dict[tuple[str, str], int] = {}
    for spec in BASELINES:
        key = (spec.symbol, spec.timeframe)
        per_pair_candles[key] = max(per_pair_candles.get(key, 0), spec.candles)

    owns_exchange = exchange is None
    if exchange is None:
        # Same construction as the legacy live path: mainnet, no keys
        # (public OHLCV endpoint).
        exchange = BinanceExchange(
            BinanceConfig(api_key="", api_secret=""), testnet=False
        )
        await exchange.connect()

    written: list[Path] = []
    try:
        for (symbol, timeframe), candles in per_pair_candles.items():
            logger.warning(
                "FETCHING FROM LIVE BINANCE: %s %s (%d candles)",
                symbol,
                timeframe,
                candles,
            )
            ohlcv = await fetch_ohlcv_window(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                total_candles=candles,
            )
            if not ohlcv:
                raise RuntimeError(
                    f"refresh: no OHLCV returned for {symbol} {timeframe}"
                )
            metadata = SnapshotMetadata(
                symbol=symbol,
                timeframe=timeframe,
                source="binance",
                fetched_at=now_utc(),
                candle_count=len(ohlcv),
                first_timestamp=ohlcv[0].timestamp,
                last_timestamp=ohlcv[-1].timestamp,
                fetcher_version="phase-25.2",
            )
            snapshot = Snapshot(metadata=metadata, ohlcv=ohlcv)
            target = baseline_directory(snapshot_root, symbol, timeframe)
            save_snapshot(snapshot, target)
            written.append(target)
            logger.info(
                "Wrote snapshot %s (%d rows, first=%s, last=%s)",
                target,
                len(ohlcv),
                ohlcv[0].timestamp.isoformat(),
                ohlcv[-1].timestamp.isoformat(),
            )
    finally:
        if owns_exchange:
            await exchange.disconnect()

    return written


async def run_all(
    *,
    output_root: Path = DEFAULT_BASELINE_DIR,
    update_doc: bool = True,
    doc_path: Path = DEFAULT_BASELINES_DOC,
    exchange: BinanceExchange | SnapshotExchange | None = None,
    strategies_dir: Path = STRATEGIES_DIR,
    snapshot_root: Path | None = None,
    max_snapshot_age_days: int = DEFAULT_MAX_SNAPSHOT_AGE_DAYS,
) -> list[dict]:
    """Run every baseline and (optionally) update the docs table.

    Args:
        output_root: Where to write per-baseline artefacts.
        update_doc: If True, rewrite the table in ``doc_path``.
        doc_path: Path to the baselines doc.
        exchange: Pre-built exchange (mainly for tests). When ``None``
            and ``snapshot_root`` is set, the script loads a
            :class:`SnapshotExchange` from disk; when both are
            ``None``, a fresh :class:`BinanceExchange` is constructed
            and connected against Binance mainnet (public endpoints
            only). Direct exchange injection wins over ``snapshot_root``.
        strategies_dir: Where the baseline strategy files live.
        snapshot_root: Phase 25.2 snapshot root. When set (and
            ``exchange`` is None), OHLCV reads route through a
            :class:`SnapshotExchange` loaded from this directory
            instead of live Binance.
        max_snapshot_age_days: Active-use freshness window (default
            :data:`DEFAULT_MAX_SNAPSHOT_AGE_DAYS`).

    Returns:
        Ordered summary dicts (one per baseline, in :data:`BASELINES`
        order).
    """
    output_root.mkdir(parents=True, exist_ok=True)

    owns_exchange = exchange is None
    if exchange is None:
        if snapshot_root is not None:
            # Phase 25.2 reproducible path: load the snapshot dataset.
            exchange = _build_snapshot_exchange(snapshot_root, max_snapshot_age_days)
            await exchange.connect()
        else:
            # Legacy live path. Public OHLCV endpoint — no keys needed.
            # Mainnet (testnet=False) because Binance testnet historical
            # data is sparse / synthetic.
            exchange = BinanceExchange(
                BinanceConfig(api_key="", api_secret=""), testnet=False
            )
            await exchange.connect()

    # DEBT-048 (Phase 26.2): when running off the snapshot dataset,
    # surface ``SnapshotMetadata.fetched_at`` for each (symbol,
    # timeframe) so the docs table records *when* the figures were
    # pinned. Live runs leave it None — the operator runbook is the
    # only path that produces meaningful timestamps anyway.
    metadata_by_pair: dict[tuple[str, str], datetime] = {}
    if isinstance(exchange, SnapshotExchange):
        metadata_by_pair = {
            pair: meta.fetched_at for pair, meta in exchange.loaded_metadata().items()
        }

    summaries: list[dict] = []
    try:
        for spec in BASELINES:
            summary = await run_baseline(
                spec=spec,
                exchange=exchange,  # type: ignore[arg-type]
                output_root=output_root,
                strategies_dir=strategies_dir,
                fetched_at=metadata_by_pair.get((spec.symbol, spec.timeframe)),
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
    """CLI entry point. Returns a process exit code.

    Phase 25.2 added three flags:

    * ``--snapshot [path]`` — read OHLCV from the snapshot dataset
      under ``path`` (default :data:`DEFAULT_SNAPSHOT_ROOT`). The
      reproducible path: same snapshot in, same baseline numbers out.
    * ``--refresh-snapshot`` — fetch fresh OHLCV from live Binance
      and overwrite the snapshot dataset. Operator-gated: this is the
      ONLY flag that touches mainnet. Mutually exclusive with
      ``--snapshot``.
    * ``--max-snapshot-age-days`` — active-use freshness window
      (default :data:`DEFAULT_MAX_SNAPSHOT_AGE_DAYS`, currently 30).
      A snapshot older than this fails the run loud unless
      ``--refresh-snapshot`` was passed. Tighter than the absolute
      90-day stale ceiling enforced inside ``snapshot.py``.
    """
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
        help="Where per-baseline artefacts go " "(default: data/backtest/baselines).",
    )
    # Phase 25.2 flags. ``--snapshot`` and ``--refresh-snapshot`` are
    # mutually exclusive: one consumes the snapshot dataset, the other
    # rebuilds it.
    snapshot_group = parser.add_mutually_exclusive_group()
    snapshot_group.add_argument(
        "--snapshot",
        type=Path,
        nargs="?",
        const=DEFAULT_SNAPSHOT_ROOT,
        default=None,
        help=(
            "Read OHLCV from the snapshot dataset rooted at this path "
            "(default: data/backtest/snapshots). Reproducible mode: "
            "same snapshot → same baseline numbers."
        ),
    )
    snapshot_group.add_argument(
        "--refresh-snapshot",
        action="store_true",
        help=(
            "Fetch fresh OHLCV from live Binance and overwrite the "
            "snapshot dataset. Operator-gated: this is the only path "
            "that touches mainnet. Skips the baseline run."
        ),
    )
    # Default reads from settings so ``ENGINE_BASELINE_MAX_SNAPSHOT_AGE_DAYS``
    # in ``.env`` overrides the 30-day quant default without an
    # explicit CLI flag.
    parser.add_argument(
        "--max-snapshot-age-days",
        type=int,
        default=get_settings().engine_baseline_max_snapshot_age_days,
        help=(
            f"Active-use freshness window in days (default: "
            f"{DEFAULT_MAX_SNAPSHOT_AGE_DAYS}, env-overridable via "
            "ENGINE_BASELINE_MAX_SNAPSHOT_AGE_DAYS). A snapshot older "
            "than this fails loud unless --refresh-snapshot is set."
        ),
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=DEFAULT_SNAPSHOT_ROOT,
        help=(
            "Snapshot dataset root for --refresh-snapshot writes "
            "(default: data/backtest/snapshots)."
        ),
    )
    args = parser.parse_args(argv)

    # Bring the script's logs to the operator's terminal. The library
    # logger defaults to WARNING for non-root namespaces.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.refresh_snapshot:
        # Operator-gated live path. Loud warning so the operator
        # knows mainnet is being hit; refresh exits without running
        # the baselines (a follow-up ``--snapshot`` invocation
        # consumes the freshly-written dataset).
        print("WARNING: --refresh-snapshot fetches OHLCV from LIVE " "Binance mainnet.")
        written = asyncio.run(refresh_snapshots(snapshot_root=args.snapshot_root))
        print(f"Refreshed {len(written)} snapshots:")
        for path in written:
            print(f"  {path}")
        return 0

    summaries = asyncio.run(
        run_all(
            output_root=args.output_dir,
            update_doc=not args.no_update_doc,
            snapshot_root=args.snapshot,
            max_snapshot_age_days=args.max_snapshot_age_days,
        )
    )
    print(f"Ran {len(summaries)} baselines:")
    for s in summaries:
        wr = s["win_rate"] * 100 if s["win_rate"] is not None else 0.0
        sharpe = f"{s['sharpe_ratio']:.3f}" if s["sharpe_ratio"] is not None else "n/a"
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
