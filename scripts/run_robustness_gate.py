"""Re-validate today's modified strategies with ``RobustnessGate``.

Operator script. Today's commits modified seven strategies; the
original 12-day Fly paper run flagged most of them as failing the
regime sub-gate by construction (mean-reversion in a sustained rally).
This script re-runs :class:`src.backtest.validator.RobustnessGate`
against the post-fix strategies on BTC/USDT and prints per-gate
verdicts so the lead can confirm the fixes land.

Strategies covered:

* ``bollinger_band_reversion`` v1.1.0 (1h)
* ``rsi_universal`` v1.1.0 (1h)
* ``rsi_4h`` v1.1.0 (4h)
* ``rsi_15m`` v1.1.0 (15m)
* ``vwap_mean_reversion`` v1.1.1 (15m)
* ``session_vwap_pullback`` v1.1.0 (15m)
* ``vcp_breakout`` v1.1.0 (4h)

Modeled on :mod:`scripts.backtest_baselines`: same explicit snapshot vs live
posture and the same ``fetch_ohlcv_window`` paginator. Promotion runs default
to pinned Snapshot v2 and never fall through to live data. The only write path
is the explicit ``--refresh-snapshot`` command, which publishes immutable v2
generations and exits before evaluating strategies.

Usage::

    # Default: pinned snapshot, else loud failure without live fallback.
    python -m scripts.run_robustness_gate

    # Force live fetch from mainnet (public endpoints, read-only).
    python -m scripts.run_robustness_gate --live

    # Trim runtime: only fetch the last 60 days of OHLCV.
    python -m scripts.run_robustness_gate --live --window-days 60

    # One strategy only (fast iteration).
    python -m scripts.run_robustness_gate --live --strategy rsi_universal

    # Explicitly refresh Snapshot v2 from public Binance endpoints and exit.
    python -m scripts.run_robustness_gate --refresh-snapshot

Related Requirements:
- FR-026: Automated Feedback Loop (this is the re-validation surface)
- FR-027: Technique Adoption (only robust strategies promoted)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from scripts.backtest_baselines import fetch_ohlcv_window
from src.backtest.snapshot import baseline_directory
from src.backtest.snapshot_replay import SnapshotReplaySource
from src.backtest.snapshot_v2 import (
    SnapshotSeriesMetadata,
    SnapshotV2,
    SnapshotV2Metadata,
    save_snapshot_v2,
)
from src.backtest.validator import (
    GateStatus,
    RobustnessGate,
    RobustnessReport,
)
from src.config import BinanceConfig
from src.exchange.binance import BinanceExchange
from src.logger import get_logger
from src.strategy.base import BaseStrategy
from src.strategy.loader import load_strategy
from src.utils.time import now_utc

logger = get_logger("crypto_master.scripts.run_robustness_gate")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGIES_DIR = PROJECT_ROOT / "strategies"
DEFAULT_SNAPSHOT_ROOT = PROJECT_ROOT / "data" / "backtest" / "snapshots"

# Default OHLCV window per timeframe (calendar days). Sized so the
# robustness gate has enough data for its 5-window walk-forward without
# blowing runtime. ``--window-days`` overrides for all timeframes.
DEFAULT_WINDOW_DAYS = 90

# Bars-per-day per timeframe for window-days → candle-count conversion.
TIMEFRAME_BARS_PER_DAY: dict[str, int] = {
    "15m": 96,
    "1h": 24,
    "4h": 6,
}


# ---------------------------------------------------------------------------
# Strategy specs — what to validate, on what cadence, with what knobs
# ---------------------------------------------------------------------------


# Subset of :class:`BinanceExchange` the script touches.
# Typed as ``Any`` rather than a Protocol because BinanceExchange's
# ``get_ohlcv`` accepts a ``Literal["1m", "5m", "15m", "1h", "4h",
# "1d", "1w"]`` for ``timeframe`` while a Protocol matching the
# script's str-typed call signature is incompatible (callable
# parameter types are contravariant). The runtime ``Any`` is fine —
# tests inject a fake duck-typed instance and the contract is
# explicit in :func:`evaluate_strategy`.
_OHLCVExchange = Any


@dataclass(frozen=True)
class StrategySpec:
    """Declarative description of one strategy to re-validate.

    Attributes:
        name: Logical strategy name (matches ``TECHNIQUE_INFO["name"]``).
        strategy_file: Filename under ``strategies/``.
        timeframe: Primary candle timeframe to validate against.
        param_grid: Sensitivity-gate parameter grid. Empty dict => the
            sensitivity gate skips per ``RobustnessGate``'s contract.
        factory_kwargs: Names of constructor kwargs accepted by the
            strategy class (used to build the sensitivity factory).
            Empty when no factory is wired.
    """

    name: str
    strategy_file: str
    timeframe: Literal["15m", "1h", "4h"]
    param_grid: dict[str, list[Any]] = field(default_factory=dict)
    factory_kwargs: tuple[str, ...] = ()


# Hardcoded list — re-validate exactly today's modified strategies.
# Per the lead's spec: BTC/USDT only (the only pair with enough
# history; multi-symbol multiplies runtime by N).
STRATEGY_SPECS: tuple[StrategySpec, ...] = (
    StrategySpec(
        name="bollinger_band_reversion",
        strategy_file="bollinger_bands.py",
        timeframe="1h",
        # BollingerBandReversionStrategy.__init__ accepts period + std_dev.
        param_grid={"period": [15, 20, 25], "std_dev": [1.8, 2.0, 2.2]},
        factory_kwargs=("period", "std_dev"),
    ),
    StrategySpec(
        name="rsi_universal",
        strategy_file="rsi.py",
        timeframe="1h",
        param_grid={"period": [10, 14, 21], "oversold": [25, 30, 35]},
        factory_kwargs=("period", "oversold"),
    ),
    StrategySpec(
        name="rsi_4h",
        strategy_file="rsi_4h.py",
        timeframe="4h",
        param_grid={"period": [10, 14, 21], "oversold": [25, 30, 35]},
        factory_kwargs=("period", "oversold"),
    ),
    StrategySpec(
        name="rsi_15m",
        strategy_file="rsi_15m.py",
        timeframe="15m",
        param_grid={"period": [10, 14, 21], "oversold": [25, 30, 35]},
        factory_kwargs=("period", "oversold"),
    ),
    StrategySpec(
        name="vwap_mean_reversion",
        strategy_file="vwap_mean_reversion.py",
        timeframe="15m",
        # Knobs are module-level constants, not __init__ kwargs — the
        # sensitivity gate skips per ``RobustnessGate``'s contract when
        # ``param_grid`` is empty.
        param_grid={},
    ),
    StrategySpec(
        name="session_vwap_pullback",
        strategy_file="session_vwap_pullback.py",
        timeframe="15m",
        param_grid={},
    ),
    StrategySpec(
        name="vcp_breakout",
        strategy_file="vcp_breakout.py",
        timeframe="4h",
        param_grid={},
    ),
    StrategySpec(
        name="raschke_holy_grail",
        strategy_file="raschke_holy_grail.py",
        timeframe="1h",
        # Knobs (ADX_THRESHOLD, EMA_PERIOD, ...) are module-level
        # constants, not __init__ kwargs — sensitivity gate skips.
        param_grid={},
    ),
    StrategySpec(
        name="ma_crossover",
        strategy_file="ma_crossover.py",
        timeframe="1h",
        # MovingAverageCrossoverStrategy.__init__ accepts short/long period.
        param_grid={"short_period": [8, 10, 12], "long_period": [20, 25, 30]},
        factory_kwargs=("short_period", "long_period"),
    ),
)

SYMBOL = "BTC/USDT"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def candle_count_for(timeframe: str, window_days: int) -> int:
    """Convert a calendar-day window to a candle count for ``timeframe``."""
    bars = TIMEFRAME_BARS_PER_DAY.get(timeframe)
    if bars is None:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}")
    return bars * window_days


def build_strategy_factory(
    spec: StrategySpec,
    strategies_dir: Path,
) -> Any:
    """Build a sensitivity-gate factory closure for ``spec``.

    Returns ``None`` when the spec declares no ``factory_kwargs``, which
    in turn causes ``RobustnessGate`` to SKIP the sensitivity gate per
    its contract. Loading the strategy class once outside the closure
    keeps each variant build cheap.
    """
    if not spec.factory_kwargs:
        return None

    # We need the class object (not an instance) so each sensitivity
    # combo gets its own ``period``/``std_dev`` etc. Re-using the
    # already-loaded ``BaseStrategy`` instance would mean the gate sees
    # the same parameters every iteration.
    strategy_path = strategies_dir / spec.strategy_file

    # Late import to avoid a top-level loader.load_technique_info_from_py
    # dependency on the strategies dir being importable in test setup.
    from src.strategy.loader import load_technique_info_from_py

    info, strategy_class = load_technique_info_from_py(strategy_path)

    def _factory(**kwargs: Any) -> BaseStrategy:
        # Drop unexpected kwargs so a typo in ``param_grid`` surfaces as
        # a TypeError from the constructor instead of being silently
        # swallowed.
        return strategy_class(info=info, **kwargs)

    return _factory


async def evaluate_strategy(
    spec: StrategySpec,
    exchange: _OHLCVExchange,
    *,
    symbol: str = SYMBOL,
    window_days: int = DEFAULT_WINDOW_DAYS,
    strategies_dir: Path = STRATEGIES_DIR,
) -> RobustnessReport:
    """Run :class:`RobustnessGate` end-to-end against one strategy spec.

    Args:
        spec: Strategy descriptor.
        exchange: Connected exchange-like object (real or fake).
        symbol: Trading pair to fetch OHLCV for.
        window_days: Calendar-day OHLCV window.
        strategies_dir: Where to load strategy files from.

    Returns:
        The full ``RobustnessReport`` for downstream rendering.
    """
    strategy_path = strategies_dir / spec.strategy_file
    strategy = load_strategy(strategy_path)

    candles = candle_count_for(spec.timeframe, window_days)
    logger.info(
        "Fetching %d %s candles for %s (%s)",
        candles,
        spec.timeframe,
        spec.name,
        symbol,
    )
    ohlcv = await fetch_ohlcv_window(
        exchange=exchange,  # type: ignore[arg-type]
        symbol=symbol,
        timeframe=spec.timeframe,
        total_candles=candles,
    )
    if not ohlcv:
        raise RuntimeError(
            f"No OHLCV returned for {symbol} {spec.timeframe}; "
            f"cannot run robustness gate for {spec.name}."
        )

    factory = build_strategy_factory(spec, strategies_dir)

    gate = RobustnessGate()
    return await gate.evaluate(
        strategy=strategy,
        ohlcv=ohlcv,
        symbol=symbol,
        timeframe=spec.timeframe,
        strategy_factory=factory,
        param_grid=spec.param_grid or None,
    )


async def evaluate_snapshot_strategy(
    spec: StrategySpec,
    replay: SnapshotReplaySource,
    *,
    strategies_dir: Path = STRATEGIES_DIR,
    seed: int = 0,
) -> RobustnessReport:
    """Run one promotion-relevant gate from a pinned snapshot source."""

    strategy = load_strategy(strategies_dir / spec.strategy_file)
    factory = build_strategy_factory(spec, strategies_dir)
    return await RobustnessGate().evaluate_snapshot(
        strategy,
        replay,
        strategy_factory=factory,
        param_grid=spec.param_grid or None,
        seed=seed,
    )


async def refresh_snapshots_v2(
    *,
    snapshot_root: Path = DEFAULT_SNAPSHOT_ROOT,
    exchange: _OHLCVExchange | None = None,
    only_strategy: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    symbol: str = SYMBOL,
) -> list[tuple[Path, str]]:
    """Explicitly collect normalized OHLCV/Funding/OI into Snapshot v2."""

    specs = _select_specs(only_strategy)
    per_pair_candles: dict[tuple[str, Literal["15m", "1h", "4h"]], int] = {}
    for spec in specs:
        key = (symbol, spec.timeframe)
        per_pair_candles[key] = max(
            per_pair_candles.get(key, 0),
            candle_count_for(spec.timeframe, window_days),
        )

    owns_exchange = exchange is None
    if exchange is None:
        exchange = BinanceExchange(
            BinanceConfig(api_key="", api_secret=""), testnet=False
        )
        await exchange.connect()

    written: list[tuple[Path, str]] = []
    try:
        for (pair_symbol, timeframe), candle_count in per_pair_candles.items():
            candles = await fetch_ohlcv_window(
                exchange=exchange,
                symbol=pair_symbol,
                timeframe=timeframe,
                total_candles=candle_count,
            )
            if not candles:
                raise RuntimeError(
                    f"refresh: no OHLCV returned for {pair_symbol} {timeframe}"
                )
            requested_since = candles[0].timestamp
            requested_until = candles[-1].timestamp
            since_ms = int(requested_since.timestamp() * 1000)
            until_ms = int(requested_until.timestamp() * 1000)
            funding_limit = max(1, (until_ms - since_ms) // (8 * 60 * 60 * 1000) + 2)
            oi_limit = max(1, (until_ms - since_ms) // (60 * 60 * 1000) + 2)
            funding = await exchange.get_funding_rate_history(
                pair_symbol,
                since_ms,
                limit=funding_limit,
                until=until_ms,
            )
            open_interest = await exchange.get_open_interest_history(
                pair_symbol,
                timeframe="1h",
                since=since_ms,
                limit=oi_limit,
                until=until_ms,
            )
            fetched_at = now_utc()
            snapshot = SnapshotV2(
                metadata=SnapshotV2Metadata(
                    source="binance",
                    symbol=pair_symbol,
                    timeframe=timeframe,
                    created_at=fetched_at,
                    ohlcv=_series_metadata(
                        fetched_at=fetched_at,
                        requested_since=requested_since,
                        requested_until=requested_until,
                        points=tuple(candles),
                        granularity=timeframe,
                    ),
                    funding=_series_metadata(
                        fetched_at=fetched_at,
                        requested_since=requested_since,
                        requested_until=requested_until,
                        points=tuple(funding),
                        granularity="8h",
                    ),
                    open_interest=SnapshotSeriesMetadata(
                        fetched_at=fetched_at,
                        requested_since=open_interest.requested_since,
                        requested_until=open_interest.requested_until,
                        actual_since=open_interest.actual_since,
                        actual_until=open_interest.actual_until,
                        granularity="1h",
                        point_count=len(open_interest.points),
                        truncated_at_venue_retention=(
                            open_interest.truncated_at_venue_retention
                        ),
                    ),
                ),
                ohlcv=tuple(candles),
                funding=tuple(funding),
                open_interest=open_interest,
            )
            target = baseline_directory(snapshot_root, pair_symbol, timeframe)
            generation_id = save_snapshot_v2(snapshot, target)
            written.append((target, generation_id))
    finally:
        if owns_exchange:
            await exchange.disconnect()
    return written


def _series_metadata(
    *,
    fetched_at: datetime,
    requested_since: datetime,
    requested_until: datetime,
    points: tuple[Any, ...],
    granularity: str,
) -> SnapshotSeriesMetadata:
    return SnapshotSeriesMetadata(
        fetched_at=fetched_at,
        requested_since=requested_since,
        requested_until=requested_until,
        actual_since=None if not points else points[0].timestamp,
        actual_until=None if not points else points[-1].timestamp,
        granularity=granularity,
        point_count=len(points),
    )


def _select_specs(only_strategy: str | None) -> tuple[StrategySpec, ...]:
    if only_strategy is None:
        return STRATEGY_SPECS
    specs = tuple(spec for spec in STRATEGY_SPECS if spec.name == only_strategy)
    if not specs:
        known = ", ".join(spec.name for spec in STRATEGY_SPECS)
        raise ValueError(f"Unknown strategy {only_strategy!r}. Known: {known}")
    return specs


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_strategy_section(spec: StrategySpec, report: RobustnessReport) -> str:
    """Render one strategy's verdict block as markdown."""
    overall = _overall_label(report)
    lines = [
        f"### `{spec.name}` ({spec.timeframe}) — overall: **{overall}**",
        "",
        (
            f"Baseline: trades={report.baseline_trades}, "
            f"sharpe={_fmt_sharpe(report.baseline_sharpe)}"
        ),
        "",
    ]
    if report.replay_identity is not None:
        lines.extend(
            [
                (
                    "Replay: "
                    f"schema=v{report.replay_identity.schema_version}, "
                    f"generation={report.replay_identity.generation_id or 'legacy-v1'}, "
                    f"digest={report.configuration_digest or 'n/a'}, seed={report.seed}"
                ),
                (
                    "Context coverage: "
                    f"ignored_prefix={report.context_ignored_prefix_bars}, "
                    f"eligible={report.context_eligible_bars}, "
                    f"unmet={report.context_unmet_bars}"
                ),
                "",
            ]
        )
    for gate in report.gates:
        status_label = gate.status.value.upper()
        lines.append(f"- **{gate.name}**: {status_label} — {gate.reason}")
    lines.append("")
    return "\n".join(lines)


def render_summary(reports: list[tuple[StrategySpec, RobustnessReport]]) -> str:
    """Render the per-strategy verdict summary table."""
    pass_count = sum(1 for _, r in reports if r.overall_passed)
    insufficient_count = sum(
        1 for _, report in reports if _overall_label(report) == "INSUFFICIENT_DATA"
    )
    lines = [
        "## Summary",
        "",
        f"Strategies evaluated: {len(reports)}  |  Passed: {pass_count}  |  "
        f"Failed: {len(reports) - pass_count - insufficient_count}  |  "
        f"Insufficient: {insufficient_count}",
        "",
        "| Strategy | TF | Overall | OOS | Walk-fwd | Regime | Sensitivity |",
        "|----------|----|---------|-----|----------|--------|-------------|",
    ]
    for spec, report in reports:
        gate_status = {g.name: g.status for g in report.gates}
        overall = _overall_label(report)
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{spec.name}`",
                    spec.timeframe,
                    overall,
                    _label(gate_status.get("oos")),
                    _label(gate_status.get("walk_forward")),
                    _label(gate_status.get("regime")),
                    _label(gate_status.get("sensitivity")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def render_report(
    reports: list[tuple[StrategySpec, RobustnessReport]],
    *,
    mode: str | None = None,
) -> str:
    """Render the full markdown report."""
    blocks = [
        "# Robustness gate verdicts",
        "",
        f"Symbol: `{SYMBOL}`  |  Strategies: {len(reports)}",
        f"Mode: `{mode}`" if mode is not None else "",
        "",
    ]
    for spec, report in reports:
        blocks.append(render_strategy_section(spec, report))
    blocks.append(render_summary(reports))
    return "\n".join(blocks)


def _fmt_sharpe(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "n/a"


def _label(status: GateStatus | None) -> str:
    if status is None:
        return "—"
    return status.value.upper()


def _overall_label(report: RobustnessReport) -> str:
    if any(gate.status is GateStatus.INSUFFICIENT_DATA for gate in report.gates):
        return "INSUFFICIENT_DATA"
    return "PASSED" if report.overall_passed else "FAILED"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_all(
    *,
    exchange: _OHLCVExchange | None = None,
    only_strategy: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    strategies_dir: Path = STRATEGIES_DIR,
    symbol: str = SYMBOL,
) -> list[tuple[StrategySpec, RobustnessReport]]:
    """Evaluate every configured strategy.

    Args:
        exchange: Pre-built exchange (mainly for tests). When ``None``,
            constructs a public-only :class:`BinanceExchange` against
            mainnet (``testnet=False``) and disconnects on completion.
        only_strategy: When set, restrict the run to this single
            ``StrategySpec.name``. Raises ``ValueError`` if the name
            is unknown so a typo doesn't silently no-op.
        window_days: Calendar-day OHLCV window for every strategy.
        strategies_dir: Where to load strategy files from.
        symbol: Trading pair (BTC/USDT canonical).

    Returns:
        List of ``(spec, report)`` pairs in input order.
    """
    specs = _select_specs(only_strategy)

    owns_exchange = exchange is None
    active_exchange: _OHLCVExchange
    if exchange is None:
        # Public OHLCV endpoint — no keys needed. Mainnet (testnet=False)
        # because Binance testnet historical data is sparse / synthetic.
        active_exchange = BinanceExchange(
            BinanceConfig(api_key="", api_secret=""), testnet=False
        )
        await active_exchange.connect()
    else:
        active_exchange = exchange

    reports: list[tuple[StrategySpec, RobustnessReport]] = []
    try:
        for spec in specs:
            try:
                report = await evaluate_strategy(
                    spec,
                    active_exchange,
                    symbol=symbol,
                    window_days=window_days,
                    strategies_dir=strategies_dir,
                )
            except Exception as exc:  # noqa: BLE001 — surface in report
                # Don't kill the whole run on a single strategy failure;
                # operators want every verdict so they know which fixes
                # landed and which didn't.
                logger.exception("Robustness gate raised for %s", spec.name)
                report = _failed_placeholder_report(exc)
            reports.append((spec, report))
    finally:
        if owns_exchange:
            await active_exchange.disconnect()

    return reports


async def run_all_snapshot(
    *,
    snapshot_root: Path = DEFAULT_SNAPSHOT_ROOT,
    only_strategy: str | None = None,
    generation_ids: dict[str, str] | None = None,
    strategies_dir: Path = STRATEGIES_DIR,
    symbol: str = SYMBOL,
    seed: int = 0,
) -> list[tuple[StrategySpec, RobustnessReport]]:
    """Evaluate configured strategies from pinned snapshots only."""

    reports: list[tuple[StrategySpec, RobustnessReport]] = []
    for spec in _select_specs(only_strategy):
        try:
            replay = SnapshotReplaySource.from_directory(
                baseline_directory(snapshot_root, symbol, spec.timeframe),
                generation_id=(
                    None if generation_ids is None else generation_ids.get(spec.name)
                ),
            )
            report = await evaluate_snapshot_strategy(
                spec,
                replay,
                strategies_dir=strategies_dir,
                seed=seed,
            )
        except Exception as exc:  # noqa: BLE001 - keep every operator verdict
            logger.exception("Snapshot robustness gate raised for %s", spec.name)
            report = _failed_placeholder_report(exc)
        reports.append((spec, report))
    return reports


def parse_generation_ids(values: list[str] | None) -> dict[str, str]:
    """Parse repeatable `STRATEGY=GENERATION_ID` CLI selections."""

    parsed: dict[str, str] = {}
    for raw in values or []:
        name, separator, generation_id = raw.partition("=")
        if (
            not separator
            or not name
            or len(generation_id) != 64
            or any(char not in "0123456789abcdef" for char in generation_id)
        ):
            raise ValueError("--generation-id must use STRATEGY=64-lowercase-hex")
        if name not in {spec.name for spec in STRATEGY_SPECS}:
            raise ValueError(f"Unknown generation-id strategy {name!r}")
        if name in parsed:
            raise ValueError(f"Duplicate generation-id strategy {name!r}")
        parsed[name] = generation_id
    return parsed


def _failed_placeholder_report(exc: Exception) -> RobustnessReport:
    """Wrap an unexpected exception without serializing its raw message.

    The caller logs the full exception for local diagnosis. Promotion reports
    retain only the exception class so paths, URL query strings, credentials,
    and raw venue payloads cannot cross the report boundary.
    """
    from src.backtest.validator import GateResult

    error_type = type(exc).__name__
    return RobustnessReport(
        overall_passed=False,
        gates=[
            GateResult(
                name="runner",
                status=GateStatus.FAILED,
                reason=f"runner raised {error_type}; inspect local logs",
                details={"error_type": error_type},
            )
        ],
        summary=f"Runner failed with {error_type}; inspect local logs.",
        baseline_sharpe=None,
        baseline_trades=0,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code.

    Exit code is 0 even when a strategy fails — the operator wants to
    see the markdown report, not chase a non-zero exit. Errors that
    prevent the run from completing (e.g. exchange connection refused)
    surface as Python tracebacks.
    """
    parser = argparse.ArgumentParser(
        description=("Re-validate today's modified strategies with RobustnessGate.")
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--live",
        action="store_true",
        help=(
            "Exploratory only: fetch OHLCV from live Binance mainnet. "
            "This mode is not snapshot-pinned promotion evidence."
        ),
    )
    mode_group.add_argument(
        "--snapshot",
        type=Path,
        nargs="?",
        const=DEFAULT_SNAPSHOT_ROOT,
        default=None,
        help=(
            "Run promotion gates from Snapshot v2 (default root: "
            "data/backtest/snapshots). This is the default mode."
        ),
    )
    mode_group.add_argument(
        "--refresh-snapshot",
        type=Path,
        nargs="?",
        const=DEFAULT_SNAPSHOT_ROOT,
        default=None,
        help=(
            "Explicitly fetch public Binance OHLCV/Funding/OI, publish "
            "Snapshot v2 generations, print ids, and exit."
        ),
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        help=(
            "Restrict the run to a single strategy by name "
            "(e.g. rsi_universal). Default: all seven."
        ),
    )
    parser.add_argument(
        "--generation-id",
        action="append",
        default=None,
        metavar="STRATEGY=HEX",
        help=(
            "Pin an exact 64-hex snapshot generation for one strategy. "
            "Repeat for multiple strategies. Snapshot mode only."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic promotion-report seed (default: 0).",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help=(
            "Calendar-day OHLCV window per strategy "
            f"(default: {DEFAULT_WINDOW_DAYS})."
        ),
    )
    args = parser.parse_args(argv)

    # Bring the script's logs to the operator's terminal. Same convention
    # as ``backtest_baselines.main``.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    generation_ids = parse_generation_ids(args.generation_id)
    if (args.live or args.refresh_snapshot is not None) and generation_ids:
        raise ValueError("--generation-id is available only in snapshot mode")

    if args.refresh_snapshot is not None:
        print(
            "WARNING: --refresh-snapshot fetches public OHLCV/Funding/OI "
            "from LIVE Binance mainnet."
        )
        written = asyncio.run(
            refresh_snapshots_v2(
                snapshot_root=args.refresh_snapshot,
                only_strategy=args.strategy,
                window_days=args.window_days,
            )
        )
        print(f"Refreshed {len(written)} Snapshot v2 generations:")
        for path, generation_id in written:
            print(f"  {path}: {generation_id}")
        return 0

    if args.live:
        reports = asyncio.run(
            run_all(
                only_strategy=args.strategy,
                window_days=args.window_days,
            )
        )
        print(render_report(reports, mode="live-exploratory-unpinned"))
        return 0

    snapshot_root = args.snapshot or DEFAULT_SNAPSHOT_ROOT
    if not snapshot_root.exists():
        print(
            f"Snapshot root does not exist: {snapshot_root}. "
            "Run --refresh-snapshot explicitly; no live fallback was attempted."
        )
        return 1
    reports = asyncio.run(
        run_all_snapshot(
            snapshot_root=snapshot_root,
            only_strategy=args.strategy,
            generation_ids=generation_ids,
            seed=args.seed,
        )
    )
    print(render_report(reports, mode="snapshot-pinned"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
