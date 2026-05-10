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

Modeled on :mod:`scripts.backtest_baselines`: same snapshot vs live
switches, same ``fetch_ohlcv_window`` paginator. Output is markdown
to stdout — pipe to a file if the operator wants persistence; this
script never writes anywhere itself.

Usage::

    # Default: snapshot if available, else loud failure (use --live).
    python -m scripts.run_robustness_gate

    # Force live fetch from mainnet (public endpoints, read-only).
    python -m scripts.run_robustness_gate --live

    # Trim runtime: only fetch the last 60 days of OHLCV.
    python -m scripts.run_robustness_gate --live --window-days 60

    # One strategy only (fast iteration).
    python -m scripts.run_robustness_gate --live --strategy rsi_universal

Related Requirements:
- FR-026: Automated Feedback Loop (this is the re-validation surface)
- FR-027: Technique Adoption (only robust strategies promoted)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from scripts.backtest_baselines import fetch_ohlcv_window
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

logger = get_logger("crypto_master.scripts.run_robustness_gate")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGIES_DIR = PROJECT_ROOT / "strategies"

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


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_strategy_section(spec: StrategySpec, report: RobustnessReport) -> str:
    """Render one strategy's verdict block as markdown."""
    overall = "PASSED" if report.overall_passed else "FAILED"
    lines = [
        f"### `{spec.name}` ({spec.timeframe}) — overall: **{overall}**",
        "",
        (
            f"Baseline: trades={report.baseline_trades}, "
            f"sharpe={_fmt_sharpe(report.baseline_sharpe)}"
        ),
        "",
    ]
    for gate in report.gates:
        status_label = gate.status.value.upper()
        lines.append(f"- **{gate.name}**: {status_label} — {gate.reason}")
    lines.append("")
    return "\n".join(lines)


def render_summary(reports: list[tuple[StrategySpec, RobustnessReport]]) -> str:
    """Render the per-strategy verdict summary table."""
    pass_count = sum(1 for _, r in reports if r.overall_passed)
    lines = [
        "## Summary",
        "",
        f"Strategies evaluated: {len(reports)}  |  Passed: {pass_count}  |  "
        f"Failed: {len(reports) - pass_count}",
        "",
        "| Strategy | TF | Overall | OOS | Walk-fwd | Regime | Sensitivity |",
        "|----------|----|---------|-----|----------|--------|-------------|",
    ]
    for spec, report in reports:
        gate_status = {g.name: g.status for g in report.gates}
        overall = "PASSED" if report.overall_passed else "FAILED"
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


def render_report(reports: list[tuple[StrategySpec, RobustnessReport]]) -> str:
    """Render the full markdown report."""
    blocks = [
        "# Robustness gate verdicts",
        "",
        f"Symbol: `{SYMBOL}`  |  Strategies: {len(reports)}",
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
    if only_strategy is not None:
        specs = tuple(s for s in STRATEGY_SPECS if s.name == only_strategy)
        if not specs:
            known = ", ".join(s.name for s in STRATEGY_SPECS)
            raise ValueError(f"Unknown strategy {only_strategy!r}. Known: {known}")
    else:
        specs = STRATEGY_SPECS

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


def _failed_placeholder_report(exc: Exception) -> RobustnessReport:
    """Wrap an unexpected exception in a single-gate FAILED report."""
    from src.backtest.validator import GateResult

    return RobustnessReport(
        overall_passed=False,
        gates=[
            GateResult(
                name="runner",
                status=GateStatus.FAILED,
                reason=f"runner raised {type(exc).__name__}: {exc}",
            )
        ],
        summary=f"Runner failed: {exc}",
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
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Fetch OHLCV from live Binance mainnet (public endpoint, "
            "read-only). Required while the snapshot dataset is empty."
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

    if not args.live:
        # Snapshot mode is intentionally not wired — there is no
        # snapshot dataset on this machine, and silently consuming a
        # stale one would defeat the point of re-validation. Surface
        # the requirement loudly.
        print(
            "Snapshot mode is not yet wired for this script; pass --live "
            "to fetch OHLCV from Binance mainnet (public endpoint)."
        )
        return 1

    reports = asyncio.run(
        run_all(
            only_strategy=args.strategy,
            window_days=args.window_days,
        )
    )
    print(render_report(reports))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
