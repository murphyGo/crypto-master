"""Backtesting engine.

Runs an analysis technique against historical OHLCV data and
produces a structured ``BacktestResult``. The engine walks forward
candle by candle, calling the strategy only with data up to and
including the current bar so there is no look-ahead bias. Simulated
fills account for slippage and taker fees; stop-loss and take-profit
are checked against the next candle's intra-bar high/low range.

Related Requirements:
- FR-025: Backtesting Execution
- FR-006/7/8: Risk/Reward, Leverage, SL/TP
- NFR-006: Backtesting Result Storage (JSON)
- NFR-008: Mode-separated P&L history
"""

from __future__ import annotations

import asyncio
import bisect
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.ai.exceptions import ClaudeParseError
from src.backtest.metrics import count_trade_outcomes, return_percent
from src.config import get_settings
from src.logger import get_logger
from src.models import OHLCV, AnalysisResult, Position
from src.strategy.base import (
    BaseStrategy,
    StrategyDataInsufficient,
    StrategyError,
)
from src.trading.profiles import TradingProfile, create_strategy_from_profile
from src.trading.strategy import (
    TradingStrategy,
    TradingStrategyConfig,
    TradingValidationError,
)
from src.utils.io import atomic_write_text
from src.utils.trading_math import pnl_for_trade

logger = get_logger("crypto_master.backtest.engine")


class BacktestError(Exception):
    """Base exception for backtest errors."""

    pass


class BacktestAbortedError(Exception):
    """Raised when the per-bar circuit breaker fires.

    Phase 17.2 / DEBT-019 — `Backtester.run` and
    `Backtester._run_multi_timeframe` (the per-bar invocation sites)
    abort cleanly when either the per-bar `asyncio.wait_for` timeout
    fires or the strategy raises ``ClaudeParseError`` /
    ``StrategyError`` ``max_parse_failures`` times in a row. This stops
    the 9-hour-hang failure mode where a structurally broken
    `prompt`-type technique never returns parseable JSON: instead of
    looping forever, the engine raises this exception, the existing
    ``except Exception`` handler in
    ``FeedbackLoop._run_cycle`` catches it, and the candidate lands as
    ``LoopStatus.ERRORED`` with a ``decision_reason`` naming the abort
    reason and offending candle index.

    Attributes:
        reason: ``"per_bar_timeout"`` when ``asyncio.wait_for`` fires,
            ``"consecutive_parse_failures"`` when the consecutive
            failure counter saturates, or
            ``"cumulative_parse_failure_rate"`` when intermittent
            failures waste too much of the backtest window.
        candle_index: 0-indexed candle position at which the breaker
            tripped (the bar whose `analyze` call timed out, or the
            bar of the final consecutive failure).
    """

    def __init__(self, reason: str, candle_index: int) -> None:
        """Initialize BacktestAbortedError.

        Args:
            reason: Breaker reason, such as ``"per_bar_timeout"``,
                ``"consecutive_parse_failures"``, or
                ``"cumulative_parse_failure_rate"``.
            candle_index: The candle index where the breaker tripped.
        """
        super().__init__(f"Backtest aborted at candle {candle_index}: {reason}")
        self.reason = reason
        self.candle_index = candle_index


class BacktestConfig(BaseModel):
    """Configuration for a backtest run.

    Attributes:
        initial_balance: Starting account balance.
        quote_currency: Currency label for the balance (informational).
        fee_rate: Taker fee rate applied to entry and exit notionals.
        slippage_bps: Price slippage applied to fills, in basis points
            (1 bp = 0.01%). Entry slips against you; exit slips against
            you. 5 bps = 0.05% on each side.
        warmup_candles: Number of candles the strategy needs before
            the first analysis call. Matches the strategy's own
            minimum-bars requirement.
        leverage: Leverage applied to sizing and P&L.
        risk_percent: Percent of balance risked per trade.
        min_risk_reward_ratio: Minimum R/R accepted for a signal.
        max_position_size_percent: Cap on margin as % of balance.
        allow_concurrent_positions: If False (default), a new signal
            is skipped while another trade is still open.
        per_bar_timeout: Phase 17.2 / DEBT-019 circuit breaker —
            per-bar wall-clock ceiling on ``strategy.analyze(...)``.
            ``asyncio.wait_for`` wraps each invocation; when it fires,
            the engine raises ``BacktestAbortedError(reason=
            "per_bar_timeout")`` instead of waiting forever. Defaults
            mirror ``Settings.engine_backtest_per_bar_timeout`` (600s).
            DEBT-020: the 600s default = chasulang's per-call ceiling
            (``claude_timeout_seconds: 480`` from
            ``strategies/chasulang_ict_smc.md``, applied per
            ``analyze()`` call by ``src/strategy/loader.py``) plus
            120s headroom for parsing/validation/disk I/O. Lower
            bound 1.0; lowering this below the strategy's
            ``claude_timeout_seconds`` will trip the breaker on every
            bar.
        max_parse_failures: Phase 17.2 / DEBT-019 circuit breaker —
            number of *consecutive* per-bar failures
            (``ClaudeParseError`` / ``StrategyError`` /
            ``asyncio.TimeoutError``) tolerated before the engine
            raises ``BacktestAbortedError(reason=
            "consecutive_parse_failures")``. A single successful bar
            resets the counter, so transient blips don't trip the
            breaker. Defaults mirror
            ``Settings.engine_backtest_max_parse_failures`` (5).
        min_cumulative_parse_failures: Phase 27 / DEBT-022 circuit
            breaker — minimum number of cumulative parse/strategy
            failures before the failure-rate breaker can fire. Default
            50 so small early samples do not abort statistically noisy
            strategies.
        max_cumulative_parse_failure_rate: Phase 27 / DEBT-022 circuit
            breaker — maximum tolerated cumulative failure ratio after
            ``min_cumulative_parse_failures`` is exceeded. Default 0.5
            aborts when more than half of attempted analysis calls
            have failed.
        liquidation_threshold: Phase 26.4 / DEBT-047 — equity floor at
            which the backtester emits a ``liquidated`` marker on the
            trade and stops adding to the equity curve. Default 0 =
            literal liquidation (free balance ≤ 0). For
            maintenance-margin parity with real exchanges, set to a
            positive fraction of initial balance.
    """

    initial_balance: Decimal = Decimal("10000")
    quote_currency: str = "USDT"
    fee_rate: Decimal = Field(default=Decimal("0.0004"), ge=0)
    slippage_bps: int = Field(default=5, ge=0)
    warmup_candles: int = Field(default=20, ge=1)
    leverage: int = Field(default=1, ge=1, le=125)
    risk_percent: float = Field(default=1.0, gt=0, le=100)
    min_risk_reward_ratio: float = Field(default=1.5, gt=0)
    max_position_size_percent: float = Field(default=10.0, gt=0, le=100)
    allow_concurrent_positions: bool = False
    # Phase 17.2 / DEBT-019: per-bar circuit breaker. Defaults match
    # ``Settings.engine_backtest_per_bar_timeout`` /
    # ``engine_backtest_max_parse_failures`` so existing deployments
    # don't change behaviour without an explicit env setting.
    per_bar_timeout: float = Field(default=600.0, ge=1.0)
    max_parse_failures: int = Field(default=5, ge=1)
    min_cumulative_parse_failures: int = Field(default=50, ge=1)
    max_cumulative_parse_failure_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    # Phase 26.4 / DEBT-047: backtester liquidation parity with the
    # post-Phase-22.2 ``PaperTrader``. Default 0 = literal liquidation
    # (balance ≤ 0); operators wanting maintenance-margin parity can
    # set this to a positive fraction of ``initial_balance`` (e.g.
    # ``Decimal("1000")`` against a 10k starting balance approximates
    # a 10% maintenance-margin floor).
    liquidation_threshold: Decimal = Field(
        default=Decimal("0"),
        description=(
            "Equity floor at which the backtester emits a `liquidated` "
            "marker on the trade and stops adding to the equity curve. "
            "Default 0 = literal liquidation (free balance ≤ 0). For "
            "maintenance-margin parity with real exchanges, set to a "
            "positive fraction of initial balance — e.g. "
            "`Decimal('1000')` against `Decimal('10000')` initial = "
            "~10% maintenance-margin proxy. With proper risk-based "
            "sizing (`risk_percent ≤ 5%`), the literal-zero default "
            "rarely fires; a positive threshold is the operationally "
            "useful setting."
        ),
    )

    model_config = {"validate_assignment": True}


class BacktestTrade(BaseModel):
    """A single simulated trade produced by the backtester.

    Attributes:
        trade_id: Unique ID for this trade.
        symbol: Trading pair symbol.
        side: "long" or "short".
        entry_time: Candle timestamp at which the entry filled.
        exit_time: Candle timestamp at which the exit filled.
        entry_price: Actual fill price after slippage.
        exit_price: Actual exit fill price after slippage.
        quantity: Position size.
        leverage: Leverage used.
        stop_loss: Stop-loss price that was active.
        take_profit: Take-profit price that was active.
        entry_fee: Fee paid on entry.
        exit_fee: Fee paid on exit.
        pnl: Net P&L after fees. Computed via ``pnl_for_trade`` against
            the levered ``quantity``; leverage is not re-multiplied (see
            DEBT-024 / Phase 20.1).
        close_reason: "take_profit", "stop_loss", or "end_of_data".
        liquidated: Phase 26.4 / DEBT-047 — True if this trade's close
            pushed the simulated equity ``≤ BacktestConfig.
            liquidation_threshold``. Structural marker only; PnL math
            is unchanged. The backtester continues simulating after
            the liquidation point so existing analysis tools still
            see the full trade list, but this flag tells operators
            "this strategy would have been liquidated at trade N".
    """

    trade_id: str
    symbol: str
    side: Literal["long", "short"]
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    leverage: int
    stop_loss: Decimal | None
    take_profit: Decimal | None
    entry_fee: Decimal
    exit_fee: Decimal
    pnl: Decimal
    close_reason: Literal["take_profit", "stop_loss", "end_of_data"]
    liquidated: bool = False
    sub_account_id: str = "default"
    technique_name: str = "unknown"


class EquityPoint(BaseModel):
    """A single (timestamp, equity) sample on the per-bar equity curve.

    The equity curve is the bar-by-bar mark-to-market of the account
    balance: closed-trade P&L plus the unrealized P&L of any currently-
    open position evaluated against the current bar's close. It is the
    correct surface for intra-trade drawdown (DEBT-030 / Phase 24.1) —
    a closed-trade-only equity walk misses every drawdown that occurs
    while a trade is still open and recovers before exit.
    """

    timestamp: datetime
    equity: Decimal

    model_config = {"frozen": True}


class BacktestResult(BaseModel):
    """Summary of a complete backtest run.

    Attributes:
        run_id: Unique ID for the run.
        technique_name: Name of the analysis technique under test.
        technique_version: Version string of that technique.
        profile_name: Optional trading profile applied.
        symbol: Trading pair backtested.
        timeframe: Candle timeframe.
        start_time: Timestamp of first candle used.
        end_time: Timestamp of last candle used.
        initial_balance: Starting balance.
        final_balance: Balance at end of backtest.
        total_trades: Number of closed trades.
        wins: Closed trades with positive P&L.
        losses: Closed trades with negative P&L.
        breakevens: Closed trades with zero P&L.
        total_pnl: Sum of trade P&Ls.
        total_fees: Sum of entry+exit fees across all trades.
        win_rate: wins / total_trades (0 if none).
        return_percent: (final - initial) / initial * 100.
        trades: Ordered list of all trades.
        equity_curve: Per-bar mark-to-market equity samples. Populated
            by :meth:`Backtester.run` and ``run_multi_timeframe``; the
            analyzer consumes this for intra-trade-aware MDD / Sharpe
            (DEBT-030 / Phase 24.1). Empty list for back-compat with
            tests that build ``BacktestResult`` directly.
        liquidated: Phase 26.4 / DEBT-047 — True if any trade in the
            run hit the ``BacktestConfig.liquidation_threshold``
            (equivalent to ``any(t.liquidated for t in trades)``).
            Structural marker only; PnL math is unchanged.
            Downstream consumers (PerformanceAnalyzer, dashboard) can
            surface this so operators can distinguish "would have
            been liquidated" from "deep drawdown but recovered".
    """

    run_id: str
    technique_name: str
    technique_version: str
    profile_name: str | None = None
    symbol: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    initial_balance: Decimal
    final_balance: Decimal
    total_trades: int
    wins: int
    losses: int
    breakevens: int
    total_pnl: Decimal
    total_fees: Decimal
    win_rate: float
    return_percent: float
    trades: list[BacktestTrade] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    liquidated: bool = False


def serialize_backtest_result(result: BacktestResult) -> dict:
    """Convert a ``BacktestResult`` to a JSON-serializable dict."""
    data = result.model_dump()
    for key in ("start_time", "end_time"):
        data[key] = data[key].isoformat()
    for key in (
        "initial_balance",
        "final_balance",
        "total_pnl",
        "total_fees",
    ):
        data[key] = str(data[key])
    for trade in data["trades"]:
        trade["entry_time"] = trade["entry_time"].isoformat()
        trade["exit_time"] = trade["exit_time"].isoformat()
        for key in (
            "entry_price",
            "exit_price",
            "quantity",
            "stop_loss",
            "take_profit",
            "entry_fee",
            "exit_fee",
            "pnl",
        ):
            if trade.get(key) is not None:
                trade[key] = str(trade[key])
    for point in data.get("equity_curve", []):
        point["timestamp"] = point["timestamp"].isoformat()
        point["equity"] = str(point["equity"])
    return data


@dataclass
class _OpenTrade:
    """Internal bookkeeping for a currently-open simulated trade."""

    position: Position
    entry_time: datetime
    actual_entry_price: Decimal
    entry_fee: Decimal


def slice_multi_tf_by_index(
    primary_ohlcv: list[OHLCV],
    ohlcv_by_timeframe: dict[str, list[OHLCV]] | None,
    start: int,
    end: int,
) -> tuple[list[OHLCV], dict[str, list[OHLCV]] | None]:
    """Slice a primary candle stream by index, propagating to higher TFs.

    Used by the multi-TF backtester loop and by the robustness gates'
    chronological splits (OOS, walk-forward). Higher-TF series have
    different bar counts than the primary, so we cut them by the
    primary slice's timestamp range, not by index.

    Args:
        primary_ohlcv: Primary-TF candle list (driver of iteration).
        ohlcv_by_timeframe: Per-TF candle dict, or ``None`` for
            single-TF mode (the function then just slices the primary
            and returns ``None`` for the dict).
        start: Inclusive start index on the primary series.
        end: Exclusive end index on the primary series.

    Returns:
        A ``(primary_slice, multi_tf_slice_or_None)`` tuple. The
        higher-TF slices are inclusive on both ends (every candle
        whose timestamp is between the primary slice's first and last
        timestamp inclusive). When ``primary_slice`` is empty the dict
        slices are also empty.
    """
    primary_slice = primary_ohlcv[start:end]
    if ohlcv_by_timeframe is None:
        return primary_slice, None
    if not primary_slice:
        return primary_slice, {tf: [] for tf in ohlcv_by_timeframe}

    start_ts = primary_slice[0].timestamp
    end_ts = primary_slice[-1].timestamp
    sliced: dict[str, list[OHLCV]] = {}
    for tf, candles in ohlcv_by_timeframe.items():
        # Pre-extract timestamps once per TF; bisect needs a sorted
        # key sequence and OHLCV is not directly comparable.
        timestamps = [c.timestamp for c in candles]
        lo = bisect.bisect_left(timestamps, start_ts)
        hi = bisect.bisect_right(timestamps, end_ts)
        sliced[tf] = candles[lo:hi]
    return primary_slice, sliced


class Backtester:
    """Walk-forward backtester for analysis techniques.

    The backtester is stateless between runs — each call to
    :meth:`run` constructs fresh balance/trade state. Results are
    optionally persisted under ``data/backtest/{run_id}/result.json``.

    Usage::

        backtester = Backtester(config=BacktestConfig(initial_balance=Decimal("5000")))
        result = await backtester.run(
            strategy=my_strategy,
            ohlcv=historical_candles,
            symbol="BTC/USDT",
            timeframe="1h",
        )
        backtester.save_result(result)
    """

    def __init__(
        self,
        config: BacktestConfig | None = None,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize the backtester.

        Args:
            config: Backtest parameters. Defaults to a neutral config
                (zero-slippage config is not the default; see
                ``BacktestConfig`` fields).
            data_dir: Root directory for result storage. Defaults to
                ``data/backtest/`` relative to the configured data root.
        """
        self.config = config or BacktestConfig()
        if data_dir is None:
            settings = get_settings()
            self.data_dir = settings.data_dir / "backtest"
        else:
            self.data_dir = data_dir

    async def run(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        profile: TradingProfile | None = None,
    ) -> BacktestResult:
        """Execute a backtest.

        Args:
            strategy: The analysis technique to evaluate.
            ohlcv: Historical candles, chronologically ascending.
            symbol: Trading pair symbol.
            timeframe: Candle timeframe label (stored on the result).
            profile: Optional trading profile whose rules override the
                backtest config (risk_percent, leverage, R/R floor,
                confidence filter).

        Returns:
            A ``BacktestResult`` summarizing the run.

        Raises:
            BacktestError: If the OHLCV series is empty.
        """
        if not ohlcv:
            raise BacktestError("Cannot backtest with empty OHLCV data")

        trading_strategy = self._build_trading_strategy(profile)
        risk_percent, leverage = self._resolve_sizing(profile)

        balance = self.config.initial_balance
        trades: list[BacktestTrade] = []
        open_trade: _OpenTrade | None = None
        # Phase 17.2 / DEBT-019: consecutive-failure counter for the
        # per-bar circuit breaker. A single non-error bar resets it;
        # see _check_breaker / the extended try/except below.
        consecutive_failures = 0
        analyzed_bars = 0
        cumulative_failures = 0

        warmup_candles = self.effective_warmup_candles(strategy)

        # First analysis call happens once we have enough history.
        # Walk candle-by-candle; the strategy only sees up to index i.
        for i, current_candle in enumerate(ohlcv):
            # 1. Apply intra-candle SL/TP checks to any open trade.
            open_trade, balance = self._close_open_trade_if_exit_hit(
                open_trade=open_trade,
                current_candle=current_candle,
                balance=balance,
                trades=trades,
            )

            # 2. Not enough history yet? skip analysis.
            if i + 1 < warmup_candles:
                continue

            # 3. Concurrent positions gate.
            if open_trade is not None and not self.config.allow_concurrent_positions:
                continue

            # 4. Run the technique on candles 0..i (inclusive).
            # Phase 17.2 / DEBT-019: ``asyncio.wait_for`` enforces a
            # per-bar wall-clock ceiling; ``ClaudeParseError`` is
            # caught here too because it is NOT a ``StrategyError``
            # subclass. The consecutive-failure counter resets on any
            # successful invocation so transient blips don't trip the
            # breaker.
            try:
                analysis = await asyncio.wait_for(
                    strategy.analyze(ohlcv[: i + 1], symbol, timeframe),
                    timeout=self.config.per_bar_timeout,
                )
            except asyncio.TimeoutError as e:
                logger.warning(
                    f"Strategy.analyze exceeded per-bar timeout "
                    f"({self.config.per_bar_timeout}s) on candle {i}: "
                    f"{e}; aborting backtest"
                )
                raise BacktestAbortedError(
                    reason="per_bar_timeout", candle_index=i
                ) from e
            except StrategyDataInsufficient as e:
                # Warmup gate — "not enough data yet". Skip the bar
                # without incrementing the breaker counter (otherwise a
                # strategy whose internal warmup exceeds
                # ``BacktestConfig.warmup_candles`` would trip the
                # breaker immediately, which is a footgun, not a
                # circuit breaker). Only the dedicated subclass skips —
                # other ``StrategyValidationError`` paths (bad prompt
                # placeholder, banned imports, malformed metadata) fall
                # through to the breaker so a structurally broken
                # strategy cannot quietly trade for thousands of bars
                # and emerge with a 0-trade pass (CH-04).
                logger.debug(
                    f"Strategy warmup short on candle {i}: {e}; "
                    "skipping (does not count toward breaker)"
                )
                continue
            except (ClaudeParseError, StrategyError) as e:
                analyzed_bars += 1
                cumulative_failures += 1
                consecutive_failures += 1
                logger.debug(
                    f"Strategy raised on candle {i} "
                    f"({type(e).__name__}, "
                    f"streak={consecutive_failures}/"
                    f"{self.config.max_parse_failures}): {e}"
                )
                if consecutive_failures >= self.config.max_parse_failures:
                    logger.warning(
                        f"Strategy.analyze hit "
                        f"{self.config.max_parse_failures} consecutive "
                        f"parse/strategy failures by candle {i}; "
                        f"aborting backtest"
                    )
                    raise BacktestAbortedError(
                        reason="consecutive_parse_failures",
                        candle_index=i,
                    ) from e
                self._raise_if_cumulative_failure_rate_exceeded(
                    candle_index=i,
                    analyzed_bars=analyzed_bars,
                    cumulative_failures=cumulative_failures,
                    context="backtest",
                    source=e,
                )
                continue
            else:
                analyzed_bars += 1
                consecutive_failures = 0

            filled = self._open_trade_from_analysis(
                analysis=analysis,
                symbol=symbol,
                current_candle=current_candle,
                trading_strategy=trading_strategy,
                profile=profile,
                balance=balance,
                leverage=leverage,
                risk_percent=risk_percent,
                candle_index=i,
            )
            if filled is None:
                continue
            open_trade, balance = filled

        # End of data: force-close any lingering position at the last close.
        open_trade, balance = self._close_open_trade_at_end_of_data(
            open_trade=open_trade,
            last_candle=ohlcv[-1],
            balance=balance,
            trades=trades,
        )

        return self._build_result(
            strategy=strategy,
            ohlcv=ohlcv,
            symbol=symbol,
            timeframe=timeframe,
            profile=profile,
            trades=trades,
            final_balance=balance,
        )

    async def run_multi_timeframe(
        self,
        strategy: BaseStrategy,
        ohlcv_by_timeframe: dict[str, list[OHLCV]],
        symbol: str,
        primary_timeframe: str,
        profile: TradingProfile | None = None,
    ) -> BacktestResult:
        """Walk-forward backtest for multi-timeframe strategies.

        Drives off the primary TF, slicing higher TFs by timestamp at
        each step. The strategy is called with the primary slice as
        its main ``ohlcv`` argument plus the full ``ohlcv_by_timeframe``
        dict and ``current_price`` derived from the primary candle's
        close — the same contract ``ProposalEngine`` uses (Phase 9.1).

        Args:
            strategy: Multi-TF analysis technique under test.
            ohlcv_by_timeframe: ``{tf: [OHLCV]}`` mapping. Each list
                must be chronologically ascending. The primary TF's
                list drives iteration; higher TFs are sliced by
                timestamp at each step.
            symbol: Trading pair symbol.
            primary_timeframe: Key into ``ohlcv_by_timeframe`` whose
                series drives the iteration. By convention this is the
                smallest / highest-resolution TF (matches
                ``strategy.info.timeframes[-1]`` when the macro→micro
                ordering is followed).
            profile: Optional trading profile.

        Returns:
            ``BacktestResult`` with ``timeframe`` set to the primary TF.

        Raises:
            BacktestError: ``ohlcv_by_timeframe`` empty, primary key
                missing, or primary series empty.
        """
        if not ohlcv_by_timeframe:
            raise BacktestError("Cannot backtest with empty ohlcv_by_timeframe dict")
        if primary_timeframe not in ohlcv_by_timeframe:
            raise BacktestError(
                f"primary_timeframe {primary_timeframe!r} not in "
                f"ohlcv_by_timeframe (keys: "
                f"{sorted(ohlcv_by_timeframe.keys())})"
            )
        primary_ohlcv = ohlcv_by_timeframe[primary_timeframe]
        if not primary_ohlcv:
            raise BacktestError(
                f"Primary timeframe {primary_timeframe!r} has empty " "candle list"
            )

        trading_strategy = self._build_trading_strategy(profile)
        risk_percent, leverage = self._resolve_sizing(profile)

        # Pre-extract timestamps for non-primary TFs so the per-step
        # bisect is O(log n). Cursors monotonically advance with the
        # primary index, but we still use bisect_right for correctness
        # when timestamps don't align cleanly to higher-TF candle opens.
        higher_timeframes = [tf for tf in ohlcv_by_timeframe if tf != primary_timeframe]
        higher_timestamps: dict[str, list[datetime]] = {
            tf: [c.timestamp for c in ohlcv_by_timeframe[tf]]
            for tf in higher_timeframes
        }

        balance = self.config.initial_balance
        trades: list[BacktestTrade] = []
        open_trade: _OpenTrade | None = None
        # Phase 17.2 / DEBT-019: consecutive-failure counter for the
        # per-bar circuit breaker (mirrors single-TF run loop).
        consecutive_failures = 0
        analyzed_bars = 0
        cumulative_failures = 0
        warmup_candles = self.effective_warmup_candles(strategy)

        for i, current_candle in enumerate(primary_ohlcv):
            # 1. Apply intra-candle SL/TP checks to any open trade.
            open_trade, balance = self._close_open_trade_if_exit_hit(
                open_trade=open_trade,
                current_candle=current_candle,
                balance=balance,
                trades=trades,
            )

            # 2. Build the multi-TF slice through the current bar.
            primary_slice = primary_ohlcv[: i + 1]
            slice_dict: dict[str, list[OHLCV]] = {primary_timeframe: primary_slice}
            cur_ts = current_candle.timestamp
            for tf in higher_timeframes:
                hi = bisect.bisect_right(higher_timestamps[tf], cur_ts)
                slice_dict[tf] = ohlcv_by_timeframe[tf][:hi]

            # 3. Warmup gate — every TF must have enough history. ICT
            # / SMC-style top-down analysis is meaningless without a
            # full higher-TF context window.
            if any(len(slice_dict[tf]) < warmup_candles for tf in slice_dict):
                continue

            # 4. Concurrent positions gate.
            if open_trade is not None and not self.config.allow_concurrent_positions:
                continue

            # 5. Run the technique with the full multi-TF context.
            # Phase 17.2 / DEBT-019: per-bar circuit breaker — mirror
            # of the single-TF path. ``asyncio.wait_for`` caps the
            # per-bar wall clock; ``ClaudeParseError`` is caught
            # alongside ``StrategyError`` because it does NOT inherit
            # from it.
            try:
                analysis = await asyncio.wait_for(
                    strategy.analyze(
                        primary_slice,
                        symbol,
                        primary_timeframe,
                        ohlcv_by_timeframe=slice_dict,
                        current_price=current_candle.close,
                    ),
                    timeout=self.config.per_bar_timeout,
                )
            except asyncio.TimeoutError as e:
                logger.warning(
                    f"Strategy.analyze exceeded per-bar timeout "
                    f"({self.config.per_bar_timeout}s) on candle {i}: "
                    f"{e}; aborting multi-TF backtest"
                )
                raise BacktestAbortedError(
                    reason="per_bar_timeout", candle_index=i
                ) from e
            except StrategyDataInsufficient as e:
                # See single-TF path (CH-04): warmup-only is a skip.
                # Structural ``StrategyValidationError`` falls through
                # to the breaker.
                logger.debug(
                    f"Strategy warmup short on candle {i}: {e}; "
                    "skipping (does not count toward breaker)"
                )
                continue
            except (ClaudeParseError, StrategyError) as e:
                analyzed_bars += 1
                cumulative_failures += 1
                consecutive_failures += 1
                logger.debug(
                    f"Strategy raised on candle {i} "
                    f"({type(e).__name__}, "
                    f"streak={consecutive_failures}/"
                    f"{self.config.max_parse_failures}): {e}"
                )
                if consecutive_failures >= self.config.max_parse_failures:
                    logger.warning(
                        f"Strategy.analyze hit "
                        f"{self.config.max_parse_failures} consecutive "
                        f"parse/strategy failures by candle {i}; "
                        f"aborting multi-TF backtest"
                    )
                    raise BacktestAbortedError(
                        reason="consecutive_parse_failures",
                        candle_index=i,
                    ) from e
                self._raise_if_cumulative_failure_rate_exceeded(
                    candle_index=i,
                    analyzed_bars=analyzed_bars,
                    cumulative_failures=cumulative_failures,
                    context="multi-TF backtest",
                    source=e,
                )
                continue
            else:
                analyzed_bars += 1
                consecutive_failures = 0

            filled = self._open_trade_from_analysis(
                analysis=analysis,
                symbol=symbol,
                current_candle=current_candle,
                trading_strategy=trading_strategy,
                profile=profile,
                balance=balance,
                leverage=leverage,
                risk_percent=risk_percent,
                candle_index=i,
            )
            if filled is None:
                continue
            open_trade, balance = filled

        # End of data: force-close any lingering position.
        open_trade, balance = self._close_open_trade_at_end_of_data(
            open_trade=open_trade,
            last_candle=primary_ohlcv[-1],
            balance=balance,
            trades=trades,
        )

        return self._build_result(
            strategy=strategy,
            ohlcv=primary_ohlcv,
            symbol=symbol,
            timeframe=primary_timeframe,
            profile=profile,
            trades=trades,
            final_balance=balance,
        )

    async def run_for_strategy(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str = "1h",
        profile: TradingProfile | None = None,
        *,
        ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None,
    ) -> BacktestResult:
        """Dispatcher: picks single- or multi-TF run from strategy metadata.

        The robustness gate and feedback loop call this so they do not
        need to branch on ``strategy.info.requires_multi_timeframe``
        themselves. ``timeframe`` is interpreted as the primary TF in
        the multi-TF case.

        Raises:
            BacktestError: When the strategy declares multi-TF but no
                ``ohlcv_by_timeframe`` was supplied.
        """
        if strategy.info.requires_multi_timeframe:
            if ohlcv_by_timeframe is None:
                raise BacktestError(
                    f"Strategy {strategy.name} declares "
                    "requires_multi_timeframe=True but ohlcv_by_timeframe "
                    "was not provided"
                )
            return await self.run_multi_timeframe(
                strategy=strategy,
                ohlcv_by_timeframe=ohlcv_by_timeframe,
                symbol=symbol,
                primary_timeframe=timeframe,
                profile=profile,
            )
        return await self.run(strategy, ohlcv, symbol, timeframe, profile)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def effective_warmup_candles(self, strategy: BaseStrategy) -> int:
        """Warmup floor used for a strategy in this backtester.

        ``BacktestConfig.warmup_candles`` is the engine/operator
        default. ``strategy.minimum_candles`` is the strategy-owned
        contract. The effective floor is the maximum so the engine
        never calls a strategy before its declared minimum, while
        operators can still raise the global warmup for comparisons.
        """
        return max(self.config.warmup_candles, strategy.minimum_candles)

    def _build_trading_strategy(
        self, profile: TradingProfile | None
    ) -> TradingStrategy:
        """Build the TradingStrategy that validates & sizes trades."""
        if profile is not None:
            return create_strategy_from_profile(profile)
        return TradingStrategy(
            config=TradingStrategyConfig(
                min_risk_reward_ratio=self.config.min_risk_reward_ratio,
                default_risk_percent=self.config.risk_percent,
                default_leverage=self.config.leverage,
                max_leverage=self.config.leverage,
                max_position_size_percent=self.config.max_position_size_percent,
            )
        )

    def _resolve_sizing(self, profile: TradingProfile | None) -> tuple[float, int]:
        """Pick risk_percent and leverage for the run."""
        if profile is not None:
            return profile.risk_percent, profile.default_leverage
        return self.config.risk_percent, self.config.leverage

    def _raise_if_cumulative_failure_rate_exceeded(
        self,
        *,
        candle_index: int,
        analyzed_bars: int,
        cumulative_failures: int,
        context: str,
        source: Exception,
    ) -> None:
        """Abort when intermittent parse failures waste too many calls."""
        if cumulative_failures <= self.config.min_cumulative_parse_failures:
            return
        failure_rate = cumulative_failures / analyzed_bars
        if failure_rate <= self.config.max_cumulative_parse_failure_rate:
            return

        logger.warning(
            f"Strategy.analyze exceeded cumulative parse failure rate "
            f"({cumulative_failures}/{analyzed_bars}={failure_rate:.2%}, "
            f"threshold={self.config.max_cumulative_parse_failure_rate:.2%}) "
            f"by candle {candle_index}; aborting {context}"
        )
        raise BacktestAbortedError(
            reason="cumulative_parse_failure_rate",
            candle_index=candle_index,
        ) from source

    def _apply_slippage(
        self,
        base_price: Decimal,
        side: Literal["long", "short"],
        is_entry: bool,
    ) -> Decimal:
        """Adjust a reference price by the configured slippage.

        Slippage always works *against* the trader:
        - Long entries buy a bit higher; long exits sell a bit lower.
        - Short entries sell a bit lower; short exits buy a bit higher.
        """
        if self.config.slippage_bps == 0:
            return base_price
        bps = Decimal(self.config.slippage_bps) / Decimal(10000)
        if side == "long":
            multiplier = (Decimal(1) + bps) if is_entry else (Decimal(1) - bps)
        else:
            multiplier = (Decimal(1) - bps) if is_entry else (Decimal(1) + bps)
        return base_price * multiplier

    def _check_intra_candle_exit(
        self,
        open_trade: _OpenTrade,
        candle: OHLCV,
    ) -> tuple[Decimal, Literal["stop_loss", "take_profit"]] | None:
        """Check whether SL or TP was hit within a candle's range.

        Pessimistic assumption: if both SL and TP fall within the
        same candle's [low, high] range, SL wins (assume worst case).

        Returns:
            (target_exit_price, reason) tuple if an exit fires, else
            None. ``target_exit_price`` is the SL/TP price *before*
            slippage; the caller applies slippage.
        """
        position = open_trade.position
        sl = position.stop_loss
        tp = position.take_profit

        sl_hit = False
        tp_hit = False

        if position.side == "long":
            if sl is not None and candle.low <= sl:
                sl_hit = True
            if tp is not None and candle.high >= tp:
                tp_hit = True
        else:  # short
            if sl is not None and candle.high >= sl:
                sl_hit = True
            if tp is not None and candle.low <= tp:
                tp_hit = True

        if sl_hit:
            assert sl is not None
            return sl, "stop_loss"
        if tp_hit:
            assert tp is not None
            return tp, "take_profit"
        return None

    def _close_trade(
        self,
        open_trade: _OpenTrade,
        exit_time: datetime,
        target_exit_price: Decimal,
        reason: Literal["stop_loss", "take_profit", "end_of_data"],
        skip_slippage: bool = False,
    ) -> tuple[BacktestTrade, Decimal]:
        """Close an open trade and compute the balance delta.

        Args:
            open_trade: The trade being closed.
            exit_time: Candle timestamp at which the exit fires.
            target_exit_price: SL/TP price or end-of-data price before
                slippage is applied.
            reason: Why the trade is closing.
            skip_slippage: If True, ``target_exit_price`` is treated
                as the actual fill (caller already adjusted).

        Returns:
            A tuple of (BacktestTrade, balance_delta). ``balance_delta``
            is the amount to add to the running balance — it is the
            gross price-move P&L minus the exit fee (the entry fee was
            already deducted when the trade opened). Leverage is
            already baked into ``position.quantity`` so the helper
            does not multiply by it again (DEBT-024 / Phase 20.1).
        """
        position = open_trade.position

        if skip_slippage:
            actual_exit = target_exit_price
        else:
            actual_exit = self._apply_slippage(
                base_price=target_exit_price,
                side=position.side,
                is_entry=False,
            )

        # Gross price-move PnL. Leverage is intentionally NOT applied
        # here: ``position.quantity`` already reflects the levered
        # notional from ``calculate_position_size`` (DEBT-024 / Phase
        # 20.1 — single source of truth in ``src.utils.trading_math``).
        raw_pnl = pnl_for_trade(
            entry=open_trade.actual_entry_price,
            exit=actual_exit,
            qty=position.quantity,
            side=position.side,
        )

        exit_fee = actual_exit * position.quantity * self.config.fee_rate
        net_pnl = raw_pnl - open_trade.entry_fee - exit_fee

        trade = BacktestTrade(
            trade_id=f"bt-{uuid.uuid4().hex[:12]}",
            symbol=position.symbol,
            side=position.side,
            entry_time=open_trade.entry_time,
            exit_time=exit_time,
            entry_price=open_trade.actual_entry_price,
            exit_price=actual_exit,
            quantity=position.quantity,
            leverage=position.leverage,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            entry_fee=open_trade.entry_fee,
            exit_fee=exit_fee,
            pnl=net_pnl,
            close_reason=reason,
        )

        # Balance delta: caller already subtracted entry_fee at open.
        balance_delta = raw_pnl - exit_fee
        return trade, balance_delta

    def _close_open_trade_if_exit_hit(
        self,
        *,
        open_trade: _OpenTrade | None,
        current_candle: OHLCV,
        balance: Decimal,
        trades: list[BacktestTrade],
    ) -> tuple[_OpenTrade | None, Decimal]:
        """Close an open trade if the current candle hits SL/TP."""
        if open_trade is None:
            return None, balance
        exit_hit = self._check_intra_candle_exit(open_trade, current_candle)
        if exit_hit is None:
            return open_trade, balance

        target_exit_price, reason = exit_hit
        trade, pnl_delta = self._close_trade(
            open_trade=open_trade,
            exit_time=current_candle.timestamp,
            target_exit_price=target_exit_price,
            reason=reason,
        )
        updated_balance = balance + pnl_delta
        trade = self._mark_if_liquidated(trade, updated_balance)
        trades.append(trade)
        return None, updated_balance

    def _open_trade_from_position(
        self,
        *,
        position: Position,
        current_candle: OHLCV,
        balance: Decimal,
        candle_index: int,
    ) -> tuple[_OpenTrade, Decimal] | None:
        """Apply entry slippage/fee and create an open trade if affordable."""
        actual_entry = self._apply_slippage(
            base_price=current_candle.close,
            side=position.side,
            is_entry=True,
        )
        entry_fee = actual_entry * position.quantity * self.config.fee_rate
        if entry_fee > balance:
            logger.debug(f"Insufficient balance for entry fee on candle {candle_index}")
            return None
        return (
            _OpenTrade(
                position=position,
                entry_time=current_candle.timestamp,
                actual_entry_price=actual_entry,
                entry_fee=entry_fee,
            ),
            balance - entry_fee,
        )

    def _open_trade_from_analysis(
        self,
        *,
        analysis: AnalysisResult,
        symbol: str,
        current_candle: OHLCV,
        trading_strategy: TradingStrategy,
        profile: TradingProfile | None,
        balance: Decimal,
        leverage: int,
        risk_percent: float,
        candle_index: int,
    ) -> tuple[_OpenTrade, Decimal] | None:
        """Convert a non-neutral accepted analysis into a simulated open trade."""
        if analysis.signal == "neutral":
            return None
        if profile is not None and not profile.accepts_signal(analysis):
            return None

        try:
            position = trading_strategy.create_position(
                analysis=analysis,
                symbol=symbol,
                balance=balance,
                leverage=leverage,
                risk_percent=risk_percent,
            )
        except TradingValidationError as e:
            logger.debug(f"Position rejected on candle {candle_index}: {e}; skipping")
            return None

        return self._open_trade_from_position(
            position=position,
            current_candle=current_candle,
            balance=balance,
            candle_index=candle_index,
        )

    def _close_open_trade_at_end_of_data(
        self,
        *,
        open_trade: _OpenTrade | None,
        last_candle: OHLCV,
        balance: Decimal,
        trades: list[BacktestTrade],
    ) -> tuple[_OpenTrade | None, Decimal]:
        """Force-close any lingering open trade at the final candle close."""
        if open_trade is None:
            return None, balance
        final_exit = self._apply_slippage(
            base_price=last_candle.close,
            side=open_trade.position.side,
            is_entry=False,
        )
        trade, pnl_delta = self._close_trade(
            open_trade=open_trade,
            exit_time=last_candle.timestamp,
            target_exit_price=final_exit,
            reason="end_of_data",
            skip_slippage=True,
        )
        updated_balance = balance + pnl_delta
        trade = self._mark_if_liquidated(trade, updated_balance)
        trades.append(trade)
        return None, updated_balance

    def _mark_if_liquidated(
        self, trade: BacktestTrade, balance_after_close: Decimal
    ) -> BacktestTrade:
        """Return a copy of ``trade`` with ``liquidated=True`` if the
        post-close balance crossed the configured threshold.

        Phase 26.4 / DEBT-047 — backtester liquidation parity with the
        post-Phase-22.2 ``PaperTrader``. Structural marker only; we
        deliberately do *not* alter PnL or stop the simulation. Once
        the marker is set, ``BacktestResult.liquidated`` will roll up
        to True, the equity curve helper masks subsequent points, and
        downstream consumers (analyzer, dashboard) can surface the
        crossing without the rest of the run silently disappearing.

        Args:
            trade: The just-closed trade.
            balance_after_close: Balance state immediately after the
                trade's PnL was added to the running balance. The
                backtester does not (yet) hold concurrent positions on
                its sizing path, so balance == equity at this point.

        Returns:
            ``trade`` if balance is above the threshold, otherwise a
            copy with ``liquidated=True``.
        """
        if balance_after_close <= self.config.liquidation_threshold:
            return trade.model_copy(update={"liquidated": True})
        return trade

    @staticmethod
    def _build_equity_curve(
        ohlcv: list[OHLCV],
        trades: list[BacktestTrade],
        initial_balance: Decimal,
    ) -> list[EquityPoint]:
        """Reconstruct the per-bar mark-to-market equity curve.

        Phase 24.1 / DEBT-030. The closed-trade equity walk used by
        :meth:`PerformanceAnalyzer._max_drawdown` misses every drawdown
        that occurs *while a trade is open* and recovers (partially or
        fully) before the trade exits — a textbook intra-trade
        drawdown. This helper replays the closed trades over the candle
        stream and emits one ``EquityPoint`` per bar:

        * **Realised P&L** — sum of ``trade.pnl`` for every trade that
          has already exited as of this candle.
        * **Unrealised P&L** — for the (at most one) trade that is open
          at this candle, mark to ``candle.close`` via
          :func:`pnl_for_trade`. Fees are *not* deducted again on the
          unrealised leg; entry/exit fees are already baked into the
          closed trade's ``pnl`` once the trade exits, so the realised
          line picks them up the candle the trade closes.

        Equity at bar i = ``initial_balance + realised + unrealised``.
        Concurrent positions are not supported by the engine's current
        sizing path; if they ever land, this helper still produces a
        single best-effort sample per bar (sums every still-open trade's
        unrealised mark) and the analyzer's MDD remains conservative.
        """
        if not ohlcv:
            return []

        # Sort trades by entry / exit time once so we can scan linearly
        # through the candle series.
        ordered = sorted(trades, key=lambda t: (t.entry_time, t.exit_time))

        curve: list[EquityPoint] = []
        for candle in ohlcv:
            ts = candle.timestamp
            close = candle.close
            realised = Decimal("0")
            unrealised = Decimal("0")
            for trade in ordered:
                if trade.exit_time <= ts:
                    realised += trade.pnl
                elif trade.entry_time < ts:
                    # Trade is open at this bar — mark to close.
                    unrealised += pnl_for_trade(
                        entry=trade.entry_price,
                        exit=close,
                        qty=trade.quantity,
                        side=trade.side,
                    )
                # else: trade hasn't entered yet — contributes 0.
            equity = initial_balance + realised + unrealised
            curve.append(EquityPoint(timestamp=ts, equity=equity))
        return curve

    def _build_result(
        self,
        strategy: BaseStrategy,
        ohlcv: list[OHLCV],
        symbol: str,
        timeframe: str,
        profile: TradingProfile | None,
        trades: list[BacktestTrade],
        final_balance: Decimal,
    ) -> BacktestResult:
        """Build the final BacktestResult summary."""
        info = strategy.info
        outcomes = count_trade_outcomes(t.pnl for t in trades)
        total_pnl = sum((t.pnl for t in trades), Decimal("0"))
        total_fees = sum((t.entry_fee + t.exit_fee for t in trades), Decimal("0"))
        initial = self.config.initial_balance
        return_pct = return_percent(initial, final_balance)

        # Phase 24.1 / DEBT-030: per-bar mark-to-market equity curve so
        # the analyzer can compute intra-trade-aware MDD / Sharpe.
        equity_curve = self._build_equity_curve(ohlcv, trades, initial)

        # Phase 26.4 / DEBT-047: liquidation parity rollup. The
        # backtester continues simulating after the liquidation
        # crossing so existing analysis tools still see the full
        # trade list, but the equity curve is truncated at the first
        # liquidating trade's exit timestamp so MDD / Sharpe don't
        # compute against a post-liquidation phantom.
        liquidated = any(t.liquidated for t in trades)
        if liquidated:
            first_liq_exit = min(t.exit_time for t in trades if t.liquidated)
            equity_curve = [p for p in equity_curve if p.timestamp <= first_liq_exit]

        return BacktestResult(
            run_id=f"bt-{uuid.uuid4().hex[:12]}",
            technique_name=info.name,
            technique_version=info.version,
            profile_name=profile.name if profile else None,
            symbol=symbol,
            timeframe=timeframe,
            start_time=ohlcv[0].timestamp,
            end_time=ohlcv[-1].timestamp,
            initial_balance=initial,
            final_balance=final_balance,
            total_trades=outcomes.total,
            wins=outcomes.wins,
            losses=outcomes.losses,
            breakevens=outcomes.breakevens,
            total_pnl=total_pnl,
            total_fees=total_fees,
            win_rate=outcomes.win_rate,
            return_percent=return_pct,
            trades=trades,
            equity_curve=equity_curve,
            liquidated=liquidated,
        )

    # ------------------------------------------------------------------
    # Persistence (NFR-006)
    # ------------------------------------------------------------------

    def save_result(self, result: BacktestResult) -> Path:
        """Persist a ``BacktestResult`` to disk.

        Writes ``data/backtest/{run_id}/result.json``.

        Args:
            result: The result to save.

        Returns:
            Path to the written file.
        """
        run_dir = self.data_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "result.json"

        payload = self._result_to_dict(result)
        # Phase 26.1 / DEBT-045: route through ``atomic_write_text`` so
        # a crash during persistence leaves either the prior file (if
        # this is a re-save) or no file at all — never a half-written
        # ``result.json`` for downstream readers.
        atomic_write_text(path, json.dumps(payload, indent=2))

        logger.info(
            f"Saved backtest result {result.run_id} to {path} "
            f"(trades={result.total_trades}, return={result.return_percent:.2f}%)"
        )
        return path

    def load_result(self, run_id: str) -> BacktestResult | None:
        """Load a persisted ``BacktestResult`` by run_id.

        Args:
            run_id: The run identifier.

        Returns:
            The result if found, otherwise None.
        """
        path = self.data_dir / run_id / "result.json"
        if not path.exists():
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load backtest result {run_id}: {e}")
            return None

        return BacktestResult(**data)

    def list_runs(self) -> list[str]:
        """List all persisted run IDs in ``data_dir``.

        Returns:
            Sorted list of run IDs that contain a ``result.json``.
        """
        if not self.data_dir.exists():
            return []
        runs = [
            p.name
            for p in self.data_dir.iterdir()
            if p.is_dir() and (p / "result.json").exists()
        ]
        return sorted(runs)

    @staticmethod
    def _result_to_dict(result: BacktestResult) -> dict:
        return serialize_backtest_result(result)
