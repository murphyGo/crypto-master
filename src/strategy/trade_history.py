"""Trade lifecycle history tracking.

Tracks complete trade lifecycle records (entry, exit, financial outcomes)
with mode-separated storage under ``data/trades``. Split out of
``src.strategy.performance`` (CAH-08 / STRAT-F1) so the technique-performance
aggregate (``data/performance``) and the trade-history aggregate
(``data/trades``) live in independent modules. This is a behaviour-preserving
relocation — every symbol is re-exported from ``src.strategy`` and from
``src.strategy.performance`` so existing import paths keep working.

Related Requirements:
- NFR-007: Trading History Storage
- NFR-008: Asset/PnL History (mode separation)
"""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.config import get_settings
from src.logger import get_logger
from src.strategy.performance import DEFAULT_SUB_ACCOUNT_ID
from src.utils.io import atomic_write_text, read_text
from src.utils.pydantic_mixins import DecimalFieldsMixin, UtcTimestampMixin
from src.utils.time import ensure_utc, now_utc
from src.utils.trading_math import pnl_for_trade
from src.utils.trading_types import TradeSide

logger = get_logger("crypto_master.strategy.trade_history")

# Default trades data directory
DEFAULT_TRADES_DIR = Path("data/trades")


class TradeHistory(DecimalFieldsMixin, UtcTimestampMixin, BaseModel):
    """Complete trade lifecycle record.

    Stores full details of a trade execution including entry, exit,
    and financial outcomes. Linked to PerformanceRecord for analysis
    technique performance tracking.

    Related Requirements:
    - NFR-007: Trading History Storage
    - NFR-008: Asset/PnL History (mode separation)

    Attributes:
        id: Unique trade identifier (UUID).
        performance_record_id: Link to PerformanceRecord if from analysis.
        symbol: Trading pair symbol (e.g., "BTC/USDT").
        side: Trade direction (long/short).
        mode: Trading mode (backtest/paper/live).
        entry_price: Entry fill price.
        entry_quantity: Entry position size.
        entry_time: Time of entry execution.
        entry_order_id: Exchange order ID for entry.
        exit_price: Exit fill price (if closed).
        exit_quantity: Exit position size (if closed).
        exit_time: Time of exit execution.
        exit_order_id: Exchange order ID for exit.
        leverage: Leverage multiplier used.
        fees: Total trading fees incurred.
        pnl: Absolute profit/loss amount, net of fees. Computed via
            :func:`src.utils.trading_math.pnl_for_trade` against the
            already-levered ``entry_quantity``; ``leverage`` is *not*
            re-multiplied at PnL time (DEBT-024 / Phase 20.1).
        pnl_percent: Profit/loss as percentage of entry notional —
            i.e. the unleveraged price-move return. Leverage does
            not scale a price move and is not multiplied in here
            either (DEBT-024 / Phase 20.1).
        status: Trade status (open/closed/cancelled).
        close_reason: Reason for closing (take_profit/stop_loss/manual).
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    performance_record_id: str | None = None
    sub_account_id: str = DEFAULT_SUB_ACCOUNT_ID
    symbol: str
    side: TradeSide
    mode: Literal["backtest", "paper", "live"]

    # Entry details
    entry_price: Decimal
    entry_quantity: Decimal
    entry_time: datetime = Field(default_factory=now_utc)
    entry_order_id: str | None = None

    # Exit details
    exit_price: Decimal | None = None
    exit_quantity: Decimal | None = None
    exit_time: datetime | None = None
    exit_order_id: str | None = None

    # Financial details
    leverage: int = 1
    fees: Decimal = Field(default=Decimal("0"))
    pnl: Decimal | None = None
    pnl_percent: float | None = None

    # Risk bounds captured when a runtime-managed position is opened.
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None

    # Status
    status: Literal["open", "closed", "cancelled"] = "open"
    close_reason: str | None = None  # "take_profit", "stop_loss", "manual"

    model_config = {"use_enum_values": True}

    def calculate_pnl(self) -> tuple[Decimal | None, float | None]:
        """Calculate P&L based on entry and exit.

        Routes through :func:`src.utils.trading_math.pnl_for_trade` so
        the persistence layer obeys the same single-source convention
        as the backtester / portfolio / paper-trader sites (DEBT-024 /
        Phase 20.1). Per that convention, ``leverage`` is *not*
        applied a second time at PnL time: ``calculate_position_size``
        sizes ``quantity = risk_amount / risk_per_unit`` independently
        of leverage, so the price-move PnL ``(Δp) * qty`` is already
        the correct levered figure.

        ``pnl_pct`` is the unleveraged return on notional —
        ``(pnl / (entry * qty)) * 100`` — i.e. the percentage move on
        price. Leverage does not scale a price move and therefore is
        not multiplied in here either.

        Returns:
            Tuple of (absolute P&L net of fees, percentage P&L on
            price-move), or (None, None) if not closed.
        """
        if self.exit_price is None or self.exit_quantity is None:
            return None, None

        entry = self.entry_price
        exit_p = self.exit_price
        qty = self.exit_quantity

        gross_pnl = pnl_for_trade(
            entry=entry,
            exit=exit_p,
            qty=qty,
            side=self.side,
        )
        pnl = gross_pnl - self.fees

        notional = entry * qty
        if notional == 0:
            pnl_pct = 0.0
        else:
            pnl_pct = float(gross_pnl / notional) * 100

        return pnl, pnl_pct


class TradeHistoryTracker:
    """Tracks and manages trade history records.

    Provides methods to open, close, and query trades with
    separate storage for each trading mode.

    Related Requirements:
    - NFR-007: Trading History Storage
    - NFR-008: Asset/PnL History (mode separation)

    Attributes:
        data_dir: Directory for storing trade data.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        sub_account_id: str = DEFAULT_SUB_ACCOUNT_ID,
    ) -> None:
        """Initialize TradeHistoryTracker.

        Args:
            data_dir: Directory for storing trade data.
                     Defaults to data/trades/.
        """
        if data_dir is None:
            settings = get_settings()
            self.data_dir = settings.data_dir / "trades"
        else:
            self.data_dir = data_dir
        self.sub_account_id = sub_account_id

    def _get_trades_path(self, mode: str) -> Path:
        """Get the path to the trades file for a mode.

        Args:
            mode: Trading mode (backtest/paper/live).

        Returns:
            Path to the trades JSON file.
        """
        mode_dir = self.data_dir / mode / self.sub_account_id
        mode_dir.mkdir(parents=True, exist_ok=True)
        return mode_dir / "trades.json"

    def open_trade(
        self,
        symbol: str,
        side: TradeSide,
        entry_price: Decimal,
        entry_quantity: Decimal,
        mode: Literal["backtest", "paper", "live"],
        leverage: int = 1,
        entry_order_id: str | None = None,
        performance_record_id: str | None = None,
        sub_account_id: str | None = None,
        fees: Decimal = Decimal("0"),
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
    ) -> TradeHistory:
        """Open a new trade.

        Args:
            symbol: Trading pair symbol.
            side: Trade direction.
            entry_price: Entry fill price.
            entry_quantity: Position size.
            mode: Trading mode.
            leverage: Leverage multiplier.
            entry_order_id: Exchange order ID.
            performance_record_id: Link to PerformanceRecord.

        Returns:
            The created TradeHistory record.
        """
        trade = TradeHistory(
            symbol=symbol,
            side=side,
            mode=mode,
            entry_price=entry_price,
            entry_quantity=entry_quantity,
            leverage=leverage,
            fees=fees,
            entry_order_id=entry_order_id,
            performance_record_id=performance_record_id,
            sub_account_id=sub_account_id or self.sub_account_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status="open",
        )

        self.save_trade(trade)
        logger.info(
            f"Opened {mode} trade: {side} {symbol} at {entry_price}, "
            f"qty={entry_quantity}, leverage={leverage}x"
        )
        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: Decimal,
        exit_quantity: Decimal | None = None,
        close_reason: str = "manual",
        exit_order_id: str | None = None,
        fees: Decimal = Decimal("0"),
    ) -> TradeHistory | None:
        """Close an open trade.

        Args:
            trade_id: ID of the trade to close.
            exit_price: Exit fill price.
            exit_quantity: Exit quantity (defaults to entry quantity).
            close_reason: Reason for closing.
            exit_order_id: Exchange order ID.
            fees: Trading fees.

        Returns:
            Updated TradeHistory, or None if not found.
        """
        trade = self.get_trade(trade_id)
        if trade is None:
            logger.warning(f"Trade not found: {trade_id}")
            return None

        if trade.status != "open":
            logger.warning(f"Trade {trade_id} is not open (status: {trade.status})")
            return None

        trade.exit_price = exit_price
        trade.exit_quantity = exit_quantity or trade.entry_quantity
        trade.exit_time = now_utc()
        trade.exit_order_id = exit_order_id
        trade.fees = trade.fees + fees
        trade.close_reason = close_reason
        trade.status = "closed"

        # Calculate P&L
        pnl, pnl_pct = trade.calculate_pnl()
        trade.pnl = pnl
        trade.pnl_percent = pnl_pct

        self._update_trade(trade)
        logger.info(
            f"Closed trade {trade_id}: {close_reason}, " f"P&L={pnl} ({pnl_pct:.2f}%)"
        )
        return trade

    def cancel_trade(self, trade_id: str) -> TradeHistory | None:
        """Cancel an open trade.

        Args:
            trade_id: ID of the trade to cancel.

        Returns:
            Updated TradeHistory, or None if not found.
        """
        trade = self.get_trade(trade_id)
        if trade is None:
            logger.warning(f"Trade not found: {trade_id}")
            return None

        if trade.status != "open":
            logger.warning(f"Trade {trade_id} is not open (status: {trade.status})")
            return None

        trade.status = "cancelled"
        trade.exit_time = now_utc()

        self._update_trade(trade)
        logger.info(f"Cancelled trade {trade_id}")
        return trade

    def save_trade(self, trade: TradeHistory) -> None:
        """Save a new trade to storage.

        Args:
            trade: The trade to save.
        """
        trades = self.load_trades(trade.mode)
        trades.append(trade)
        self._save_trades(trade.mode, trades)

    def _update_trade(self, trade: TradeHistory) -> None:
        """Update an existing trade in storage.

        Args:
            trade: The trade to update.
        """
        trades = self.load_trades(trade.mode)
        for i, t in enumerate(trades):
            if t.id == trade.id:
                trades[i] = trade
                break
        self._save_trades(trade.mode, trades)

    def _save_trades(self, mode: str, trades: list[TradeHistory]) -> None:
        """Save all trades for a mode.

        Args:
            mode: Trading mode.
            trades: List of trades to save.
        """
        trades_path = self._get_trades_path(mode)
        data = [self._trade_to_dict(t) for t in trades]

        # DEBT-028 (Phase 22.1): atomic write so the trade ledger is
        # never observable in a half-written state. The load-all →
        # mutate → save-all shape here is exactly the surface
        # DEBT-028 names.
        atomic_write_text(
            trades_path,
            json.dumps(data, indent=2, default=str),
        )

    def _trade_to_dict(self, trade: TradeHistory) -> dict:
        """Convert a TradeHistory to a JSON-serializable dict.

        Args:
            trade: The trade to convert.

        Returns:
            Dictionary representation of the trade.
        """
        data = trade.model_dump()
        # Convert Decimals to strings for JSON
        decimal_fields = [
            "entry_price",
            "entry_quantity",
            "exit_price",
            "exit_quantity",
            "fees",
            "pnl",
            "stop_loss",
            "take_profit",
        ]
        for key in decimal_fields:
            if data[key] is not None:
                data[key] = str(data[key])
        # Convert datetime to ISO format
        for key in ["entry_time", "exit_time"]:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data

    def load_trades(
        self,
        mode: str | None = None,
        symbol: str | None = None,
    ) -> list[TradeHistory]:
        """Load trades from storage.

        Args:
            mode: Trading mode to load (loads all if None).
            symbol: Optional symbol filter.

        Returns:
            List of TradeHistory records.
        """
        if mode:
            trades = self._load_trades_for_mode(mode)
        else:
            trades = []
            for m in ["backtest", "paper", "live"]:
                trades.extend(self._load_trades_for_mode(m))

        if symbol:
            trades = [t for t in trades if t.symbol == symbol]

        return trades

    def _load_trades_for_mode(self, mode: str) -> list[TradeHistory]:
        """Load trades for a specific mode.

        Args:
            mode: Trading mode.

        Returns:
            List of TradeHistory records.
        """
        trades_path = self._get_trades_path(mode)

        if not trades_path.exists():
            return []

        try:
            # CAH-14: route the read through ``utils/io`` so all FS access
            # in this module goes through one seam (writes already use
            # ``atomic_write_text``). Same error semantics as the prior
            # raw ``open(...)``.
            data = json.loads(read_text(trades_path))
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load trades from {trades_path}: {e}")
            return []

        return [TradeHistory(**item) for item in data]

    def get_trade(self, trade_id: str) -> TradeHistory | None:
        """Get a trade by ID.

        Args:
            trade_id: The trade ID.

        Returns:
            TradeHistory or None if not found.
        """
        for mode in ["backtest", "paper", "live"]:
            trades = self.load_trades(mode)
            for trade in trades:
                if trade.id == trade_id:
                    return trade
        return None

    def get_open_trades(
        self,
        mode: str | None = None,
        symbol: str | None = None,
    ) -> list[TradeHistory]:
        """Get all open trades.

        Args:
            mode: Optional mode filter.
            symbol: Optional symbol filter.

        Returns:
            List of open TradeHistory records.
        """
        trades = self.load_trades(mode, symbol)
        return [t for t in trades if t.status == "open"]

    def get_trades_by_date_range(
        self,
        start: datetime,
        end: datetime,
        mode: str | None = None,
    ) -> list[TradeHistory]:
        """Get trades within a date range.

        Args:
            start: Start of date range (inclusive).
            end: End of date range (inclusive).
            mode: Optional mode filter.

        Returns:
            List of matching TradeHistory records.
        """
        trades = self.load_trades(mode)
        # DEBT-025 (Phase 21.2): trades on disk are now UTC-aware
        # (validator coerces); tolerate naive callers by treating
        # naive ``start`` / ``end`` as UTC.
        if start.tzinfo is None:
            start = ensure_utc(start)
        if end.tzinfo is None:
            end = ensure_utc(end)
        return [t for t in trades if start <= t.entry_time <= end]

    def link_to_performance(
        self,
        trade_id: str,
        performance_record_id: str,
    ) -> TradeHistory | None:
        """Link a trade to a performance record.

        Args:
            trade_id: ID of the trade.
            performance_record_id: ID of the PerformanceRecord.

        Returns:
            Updated TradeHistory, or None if not found.
        """
        trade = self.get_trade(trade_id)
        if trade is None:
            return None

        trade.performance_record_id = performance_record_id
        self._update_trade(trade)
        logger.info(
            f"Linked trade {trade_id} to performance record {performance_record_id}"
        )
        return trade

    def get_trades_by_performance_record(
        self,
        performance_record_id: str,
    ) -> list[TradeHistory]:
        """Get trades linked to a performance record.

        Args:
            performance_record_id: ID of the PerformanceRecord.

        Returns:
            List of linked TradeHistory records.
        """
        all_trades = self.load_trades()
        return [
            t for t in all_trades if t.performance_record_id == performance_record_id
        ]

    def delete_trades(self, mode: str) -> bool:
        """Delete all trades for a mode.

        Args:
            mode: Trading mode.

        Returns:
            True if deleted, False if not found.
        """
        mode_dir = self.data_dir / mode

        if not mode_dir.exists():
            return False

        import shutil

        shutil.rmtree(mode_dir)
        logger.info(f"Deleted trade history for mode: {mode}")
        return True


__all__ = [
    "DEFAULT_TRADES_DIR",
    "TradeHistory",
    "TradeHistoryTracker",
]
