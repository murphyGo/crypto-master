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

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.config import get_settings
from src.logger import get_logger
from src.models import OHLCV, Position
from src.strategy.base import BaseStrategy, StrategyError
from src.trading.profiles import TradingProfile, create_strategy_from_profile
from src.trading.strategy import (
    TradingStrategy,
    TradingStrategyConfig,
    TradingValidationError,
)

logger = get_logger("crypto_master.backtest.engine")


class BacktestError(Exception):
    """Base exception for backtest errors."""

    pass


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
        pnl: Net P&L after fees and leverage.
        close_reason: "take_profit", "stop_loss", or "end_of_data".
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


@dataclass
class _OpenTrade:
    """Internal bookkeeping for a currently-open simulated trade."""

    position: Position
    entry_time: datetime
    actual_entry_price: Decimal
    entry_fee: Decimal


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

        # First analysis call happens once we have enough history.
        # Walk candle-by-candle; the strategy only sees up to index i.
        for i, current_candle in enumerate(ohlcv):
            # 1. Apply intra-candle SL/TP checks to any open trade.
            if open_trade is not None:
                exit_hit = self._check_intra_candle_exit(
                    open_trade, current_candle
                )
                if exit_hit is not None:
                    target_exit_price, reason = exit_hit
                    trade, pnl_delta = self._close_trade(
                        open_trade=open_trade,
                        exit_time=current_candle.timestamp,
                        target_exit_price=target_exit_price,
                        reason=reason,
                    )
                    trades.append(trade)
                    balance += pnl_delta
                    open_trade = None

            # 2. Not enough history yet? skip analysis.
            if i + 1 < self.config.warmup_candles:
                continue

            # 3. Concurrent positions gate.
            if (
                open_trade is not None
                and not self.config.allow_concurrent_positions
            ):
                continue

            # 4. Run the technique on candles 0..i (inclusive).
            try:
                analysis = await strategy.analyze(
                    ohlcv[: i + 1], symbol, timeframe
                )
            except StrategyError as e:
                logger.debug(
                    f"Strategy raised on candle {i}: {e}; skipping"
                )
                continue

            if analysis.signal == "neutral":
                continue

            # 5. Profile filter (confidence, neutral rejection).
            if profile is not None and not profile.accepts_signal(analysis):
                continue

            # 6. Build the position; skip on any validation failure.
            try:
                position = trading_strategy.create_position(
                    analysis=analysis,
                    symbol=symbol,
                    balance=balance,
                    leverage=leverage,
                    risk_percent=risk_percent,
                )
            except TradingValidationError as e:
                logger.debug(
                    f"Position rejected on candle {i}: {e}; skipping"
                )
                continue

            # 7. Simulate fill at current candle close with slippage.
            actual_entry = self._apply_slippage(
                base_price=current_candle.close,
                side=position.side,
                is_entry=True,
            )
            entry_fee = (
                actual_entry * position.quantity * self.config.fee_rate
            )
            if entry_fee > balance:
                logger.debug(
                    f"Insufficient balance for entry fee on candle {i}"
                )
                continue

            balance -= entry_fee
            open_trade = _OpenTrade(
                position=position,
                entry_time=current_candle.timestamp,
                actual_entry_price=actual_entry,
                entry_fee=entry_fee,
            )

        # End of data: force-close any lingering position at the last close.
        if open_trade is not None:
            last_candle = ohlcv[-1]
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
                skip_slippage=True,  # already applied above
            )
            trades.append(trade)
            balance += pnl_delta
            open_trade = None

        return self._build_result(
            strategy=strategy,
            ohlcv=ohlcv,
            symbol=symbol,
            timeframe=timeframe,
            profile=profile,
            trades=trades,
            final_balance=balance,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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

    def _resolve_sizing(
        self, profile: TradingProfile | None
    ) -> tuple[float, int]:
        """Pick risk_percent and leverage for the run."""
        if profile is not None:
            return profile.risk_percent, profile.default_leverage
        return self.config.risk_percent, self.config.leverage

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
            leveraged P&L minus the exit fee (the entry fee was
            already deducted when the trade opened).
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

        # Leveraged raw P&L
        if position.side == "long":
            raw_pnl = (
                (actual_exit - open_trade.actual_entry_price)
                * position.quantity
                * Decimal(position.leverage)
            )
        else:
            raw_pnl = (
                (open_trade.actual_entry_price - actual_exit)
                * position.quantity
                * Decimal(position.leverage)
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
        wins = sum(1 for t in trades if t.pnl > 0)
        losses = sum(1 for t in trades if t.pnl < 0)
        breakevens = sum(1 for t in trades if t.pnl == 0)
        total_pnl = sum((t.pnl for t in trades), Decimal("0"))
        total_fees = sum(
            (t.entry_fee + t.exit_fee for t in trades), Decimal("0")
        )
        total = len(trades)
        win_rate = (wins / total) if total else 0.0
        initial = self.config.initial_balance
        return_pct = (
            float((final_balance - initial) / initial * 100) if initial > 0 else 0.0
        )

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
            total_trades=total,
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            total_pnl=total_pnl,
            total_fees=total_fees,
            win_rate=win_rate,
            return_percent=return_pct,
            trades=trades,
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
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

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
        """Convert a ``BacktestResult`` to a JSON-serializable dict."""
        data = result.model_dump()
        # datetimes
        for key in ("start_time", "end_time"):
            data[key] = data[key].isoformat()
        # decimals
        for key in (
            "initial_balance",
            "final_balance",
            "total_pnl",
            "total_fees",
        ):
            data[key] = str(data[key])
        # trades
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
        return data
