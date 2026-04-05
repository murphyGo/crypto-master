"""Performance tracking for analysis techniques.

Tracks trade outcomes and calculates aggregate metrics like win rate
and profit rate for each analysis technique. Also provides trade history
tracking for complete trade lifecycle management.

Related Requirements:
- FR-004: Analysis Technique Storage/Management
- FR-005: Analysis Technique Performance Tracking
- NFR-006: Backtesting Result Storage (JSON format)
- NFR-007: Trading History Storage
- NFR-008: Asset/PnL History (mode separation)
"""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.config import get_settings
from src.logger import get_logger
from src.models import AnalysisResult
from src.strategy.base import TechniqueInfo

logger = get_logger("crypto_master.strategy.performance")

# Default performance data directory
DEFAULT_PERFORMANCE_DIR = Path("data/performance")


class TradeOutcome(str, Enum):
    """Outcome of a trade based on analysis."""

    WIN = "win"  # Hit take profit
    LOSS = "loss"  # Hit stop loss
    BREAKEVEN = "breakeven"  # Exited at entry price
    PENDING = "pending"  # Trade not yet closed


class PerformanceRecord(BaseModel):
    """Single analysis/trade performance record.

    Stores the analysis result and its eventual trade outcome
    for performance tracking purposes.

    Attributes:
        id: Unique record identifier (UUID).
        technique_name: Name of the analysis technique.
        technique_version: Version of the technique used.
        symbol: Trading pair symbol (e.g., "BTC/USDT").
        timeframe: Candle timeframe (e.g., "1h", "4h").
        signal: Trading signal from analysis.
        entry_price: Suggested entry price.
        stop_loss: Stop loss price.
        take_profit: Take profit price.
        confidence: Confidence score (0.0-1.0).
        analysis_timestamp: When the analysis was performed.
        outcome: Trade outcome (win/loss/breakeven/pending).
        exit_price: Actual exit price if trade closed.
        exit_timestamp: When the trade was closed.
        pnl_percent: Profit/loss as percentage of entry.
        quantity: Position size (if trade executed).
        leverage: Leverage multiplier used.
        fees: Trading fees incurred.
        actual_entry_price: Actual fill price (may differ from signal).
        actual_exit_price: Actual exit fill price.
        mode: Trading mode (backtest/paper/live).
        trade_id: Link to TradeHistory record if executed.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    technique_name: str
    technique_version: str
    symbol: str
    timeframe: str
    signal: Literal["long", "short", "neutral"]
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    confidence: float = Field(ge=0.0, le=1.0)
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    outcome: TradeOutcome = TradeOutcome.PENDING
    exit_price: Decimal | None = None
    exit_timestamp: datetime | None = None
    pnl_percent: float | None = None
    # Trade execution details (added for NFR-007)
    quantity: Decimal | None = None
    leverage: int = 1
    fees: Decimal = Field(default=Decimal("0"))
    actual_entry_price: Decimal | None = None
    actual_exit_price: Decimal | None = None
    mode: Literal["backtest", "paper", "live"] = "backtest"
    trade_id: str | None = None

    model_config = {"use_enum_values": True}

    @field_validator("entry_price", "stop_loss", "take_profit", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: str | int | float | Decimal) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("exit_price", "quantity", "actual_entry_price", "actual_exit_price", mode="before")
    @classmethod
    def convert_optional_to_decimal(
        cls, v: str | int | float | Decimal | None
    ) -> Decimal | None:
        """Convert optional numeric values to Decimal if present."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("fees", mode="before")
    @classmethod
    def convert_fees_to_decimal(cls, v: str | int | float | Decimal) -> Decimal:
        """Convert fees to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def calculate_pnl(self) -> float | None:
        """Calculate P&L percentage based on outcome.

        Returns:
            P&L as percentage of entry price, or None if pending.
        """
        if self.outcome == TradeOutcome.PENDING or self.exit_price is None:
            return None

        if self.signal == "neutral":
            return 0.0

        entry = float(self.entry_price)
        exit_p = float(self.exit_price)

        if self.signal == "long":
            return ((exit_p - entry) / entry) * 100
        else:  # short
            return ((entry - exit_p) / entry) * 100


class TechniquePerformance(BaseModel):
    """Aggregated performance metrics for a technique.

    Calculates and stores summary statistics across all trades
    for a specific technique.

    Attributes:
        technique_name: Name of the analysis technique.
        technique_version: Version of the technique.
        total_trades: Total number of trades recorded.
        wins: Number of winning trades.
        losses: Number of losing trades.
        breakevens: Number of breakeven trades.
        pending: Number of pending trades.
        win_rate: Win rate as decimal (wins / closed trades).
        avg_pnl_percent: Average P&L percentage per trade.
        total_pnl_percent: Cumulative P&L percentage.
        best_trade_pnl: Best single trade P&L percentage.
        worst_trade_pnl: Worst single trade P&L percentage.
        last_updated: Timestamp of last update.
    """

    technique_name: str
    technique_version: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    pending: int = 0
    win_rate: float = 0.0
    avg_pnl_percent: float = 0.0
    total_pnl_percent: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_records(
        cls,
        technique_name: str,
        technique_version: str,
        records: list[PerformanceRecord],
    ) -> "TechniquePerformance":
        """Calculate performance metrics from a list of records.

        Args:
            technique_name: Name of the technique.
            technique_version: Version of the technique.
            records: List of performance records.

        Returns:
            TechniquePerformance with calculated metrics.
        """
        if not records:
            return cls(
                technique_name=technique_name,
                technique_version=technique_version,
            )

        wins = sum(1 for r in records if r.outcome == TradeOutcome.WIN)
        losses = sum(1 for r in records if r.outcome == TradeOutcome.LOSS)
        breakevens = sum(1 for r in records if r.outcome == TradeOutcome.BREAKEVEN)
        pending = sum(1 for r in records if r.outcome == TradeOutcome.PENDING)

        closed_trades = wins + losses + breakevens
        win_rate = wins / closed_trades if closed_trades > 0 else 0.0

        # Calculate P&L stats from closed trades
        pnl_values = [r.pnl_percent for r in records if r.pnl_percent is not None]
        total_pnl = sum(pnl_values) if pnl_values else 0.0
        avg_pnl = total_pnl / len(pnl_values) if pnl_values else 0.0
        best_pnl = max(pnl_values) if pnl_values else 0.0
        worst_pnl = min(pnl_values) if pnl_values else 0.0

        return cls(
            technique_name=technique_name,
            technique_version=technique_version,
            total_trades=len(records),
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            pending=pending,
            win_rate=win_rate,
            avg_pnl_percent=avg_pnl,
            total_pnl_percent=total_pnl,
            best_trade_pnl=best_pnl,
            worst_trade_pnl=worst_pnl,
            last_updated=datetime.now(),
        )


class PerformanceTracker:
    """Tracks and manages performance records for analysis techniques.

    Provides methods to record analysis results, update outcomes,
    and query aggregated performance metrics.

    Related Requirements:
    - FR-005: Analysis Technique Performance Tracking

    Attributes:
        data_dir: Directory for storing performance data.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize PerformanceTracker.

        Args:
            data_dir: Directory for storing performance data.
                     Defaults to data/performance/.
        """
        if data_dir is None:
            settings = get_settings()
            self.data_dir = settings.data_dir / "performance"
        else:
            self.data_dir = data_dir

    def _get_technique_dir(self, technique_name: str) -> Path:
        """Get the directory for a technique's performance data.

        Args:
            technique_name: Name of the technique.

        Returns:
            Path to the technique's performance directory.
        """
        return self.data_dir / technique_name

    def _get_records_path(self, technique_name: str) -> Path:
        """Get the path to the records file for a technique.

        Args:
            technique_name: Name of the technique.

        Returns:
            Path to the records JSON file.
        """
        return self._get_technique_dir(technique_name) / "records.json"

    def _get_summary_path(self, technique_name: str) -> Path:
        """Get the path to the summary file for a technique.

        Args:
            technique_name: Name of the technique.

        Returns:
            Path to the summary JSON file.
        """
        return self._get_technique_dir(technique_name) / "summary.json"

    def record_analysis(
        self,
        technique: TechniqueInfo,
        result: AnalysisResult,
        symbol: str,
        timeframe: str,
    ) -> PerformanceRecord:
        """Record a new analysis result.

        Creates a PerformanceRecord from the analysis and saves it.

        Args:
            technique: The technique that produced the analysis.
            result: The analysis result.
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.

        Returns:
            The created PerformanceRecord.
        """
        record = PerformanceRecord(
            technique_name=technique.name,
            technique_version=technique.version,
            symbol=symbol,
            timeframe=timeframe,
            signal=result.signal,
            entry_price=result.entry_price,
            stop_loss=result.stop_loss,
            take_profit=result.take_profit,
            confidence=result.confidence,
            analysis_timestamp=result.timestamp,
        )

        self.save_record(record)
        logger.info(
            f"Recorded analysis: {technique.name} v{technique.version} "
            f"on {symbol} ({timeframe}) - signal: {result.signal}"
        )
        return record

    def update_outcome(
        self,
        record_id: str,
        outcome: TradeOutcome,
        exit_price: Decimal,
        technique_name: str,
    ) -> PerformanceRecord | None:
        """Update the outcome of a pending trade.

        Args:
            record_id: ID of the record to update.
            outcome: The trade outcome.
            exit_price: The exit price.
            technique_name: Name of the technique (for loading records).

        Returns:
            Updated PerformanceRecord, or None if not found.
        """
        records = self.load_records(technique_name)
        updated_record = None

        for i, record in enumerate(records):
            if record.id == record_id:
                record.outcome = outcome
                record.exit_price = exit_price
                record.exit_timestamp = datetime.now()
                record.pnl_percent = record.calculate_pnl()
                records[i] = record
                updated_record = record
                break

        if updated_record:
            self._save_records(technique_name, records)
            self._update_summary(technique_name, records)
            logger.info(
                f"Updated outcome for record {record_id}: "
                f"{outcome.value}, P&L: {updated_record.pnl_percent:.2f}%"
            )

        return updated_record

    def save_record(self, record: PerformanceRecord) -> None:
        """Save a performance record to storage.

        Appends the record to the technique's records file.

        Args:
            record: The record to save.
        """
        records = self.load_records(record.technique_name)
        records.append(record)
        self._save_records(record.technique_name, records)
        self._update_summary(record.technique_name, records)

    def _save_records(
        self, technique_name: str, records: list[PerformanceRecord]
    ) -> None:
        """Save all records for a technique.

        Args:
            technique_name: Name of the technique.
            records: List of records to save.
        """
        technique_dir = self._get_technique_dir(technique_name)
        technique_dir.mkdir(parents=True, exist_ok=True)

        records_path = self._get_records_path(technique_name)
        data = [self._record_to_dict(r) for r in records]

        with open(records_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _record_to_dict(self, record: PerformanceRecord) -> dict:
        """Convert a PerformanceRecord to a JSON-serializable dict.

        Args:
            record: The record to convert.

        Returns:
            Dictionary representation of the record.
        """
        data = record.model_dump()
        # Convert Decimals to strings for JSON
        decimal_fields = [
            "entry_price", "stop_loss", "take_profit", "exit_price",
            "quantity", "fees", "actual_entry_price", "actual_exit_price"
        ]
        for key in decimal_fields:
            if data[key] is not None:
                data[key] = str(data[key])
        # Convert datetime to ISO format
        for key in ["analysis_timestamp", "exit_timestamp"]:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data

    def _update_summary(
        self, technique_name: str, records: list[PerformanceRecord]
    ) -> None:
        """Update the summary file for a technique.

        Args:
            technique_name: Name of the technique.
            records: All records for the technique.
        """
        if not records:
            return

        # Get version from latest record
        version = records[-1].technique_version
        performance = TechniquePerformance.from_records(
            technique_name, version, records
        )

        summary_path = self._get_summary_path(technique_name)
        data = performance.model_dump()
        data["last_updated"] = data["last_updated"].isoformat()

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_records(
        self,
        technique_name: str,
        version: str | None = None,
    ) -> list[PerformanceRecord]:
        """Load performance records for a technique.

        Args:
            technique_name: Name of the technique.
            version: Optional version filter.

        Returns:
            List of PerformanceRecords.
        """
        records_path = self._get_records_path(technique_name)

        if not records_path.exists():
            return []

        try:
            with open(records_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load records from {records_path}: {e}")
            return []

        records = [PerformanceRecord(**item) for item in data]

        if version:
            records = [r for r in records if r.technique_version == version]

        return records

    def get_performance(
        self,
        technique_name: str,
        version: str | None = None,
    ) -> TechniquePerformance:
        """Get aggregated performance metrics for a technique.

        Args:
            technique_name: Name of the technique.
            version: Optional version filter.

        Returns:
            TechniquePerformance with aggregated metrics.
        """
        records = self.load_records(technique_name, version)
        technique_version = version or (records[-1].technique_version if records else "")
        return TechniquePerformance.from_records(
            technique_name, technique_version, records
        )

    def recalculate_performance(self, technique_name: str) -> TechniquePerformance:
        """Recalculate and update performance metrics.

        Forces a recalculation of all metrics from records.

        Args:
            technique_name: Name of the technique.

        Returns:
            Updated TechniquePerformance.
        """
        records = self.load_records(technique_name)
        if records:
            self._update_summary(technique_name, records)
        return self.get_performance(technique_name)

    def get_records_by_symbol(
        self,
        technique_name: str,
        symbol: str,
    ) -> list[PerformanceRecord]:
        """Get records filtered by symbol.

        Args:
            technique_name: Name of the technique.
            symbol: Trading pair symbol to filter by.

        Returns:
            List of matching PerformanceRecords.
        """
        records = self.load_records(technique_name)
        return [r for r in records if r.symbol == symbol]

    def get_records_by_timeframe(
        self,
        technique_name: str,
        timeframe: str,
    ) -> list[PerformanceRecord]:
        """Get records filtered by timeframe.

        Args:
            technique_name: Name of the technique.
            timeframe: Timeframe to filter by.

        Returns:
            List of matching PerformanceRecords.
        """
        records = self.load_records(technique_name)
        return [r for r in records if r.timeframe == timeframe]

    def get_records_by_date_range(
        self,
        technique_name: str,
        start: datetime,
        end: datetime,
    ) -> list[PerformanceRecord]:
        """Get records within a date range.

        Args:
            technique_name: Name of the technique.
            start: Start of date range (inclusive).
            end: End of date range (inclusive).

        Returns:
            List of matching PerformanceRecords.
        """
        records = self.load_records(technique_name)
        return [r for r in records if start <= r.analysis_timestamp <= end]

    def list_techniques(self) -> list[str]:
        """List all techniques with performance data.

        Returns:
            List of technique names.
        """
        if not self.data_dir.exists():
            return []

        return [
            d.name
            for d in self.data_dir.iterdir()
            if d.is_dir() and (d / "records.json").exists()
        ]

    def delete_records(self, technique_name: str) -> bool:
        """Delete all records for a technique.

        Args:
            technique_name: Name of the technique.

        Returns:
            True if deleted, False if not found.
        """
        technique_dir = self._get_technique_dir(technique_name)

        if not technique_dir.exists():
            return False

        import shutil

        shutil.rmtree(technique_dir)
        logger.info(f"Deleted performance data for technique: {technique_name}")
        return True


# Default trades data directory
DEFAULT_TRADES_DIR = Path("data/trades")


class TradeHistory(BaseModel):
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
        pnl: Absolute profit/loss amount.
        pnl_percent: Profit/loss as percentage.
        status: Trade status (open/closed/cancelled).
        close_reason: Reason for closing (take_profit/stop_loss/manual).
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    performance_record_id: str | None = None
    symbol: str
    side: Literal["long", "short"]
    mode: Literal["backtest", "paper", "live"]

    # Entry details
    entry_price: Decimal
    entry_quantity: Decimal
    entry_time: datetime = Field(default_factory=datetime.now)
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

    # Status
    status: Literal["open", "closed", "cancelled"] = "open"
    close_reason: str | None = None  # "take_profit", "stop_loss", "manual"

    model_config = {"use_enum_values": True}

    @field_validator("entry_price", "entry_quantity", mode="before")
    @classmethod
    def convert_entry_to_decimal(cls, v: str | int | float | Decimal) -> Decimal:
        """Convert entry values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator(
        "exit_price", "exit_quantity", "pnl", mode="before"
    )
    @classmethod
    def convert_exit_fields_to_decimal(
        cls, v: str | int | float | Decimal | None
    ) -> Decimal | None:
        """Convert optional exit fields to Decimal."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("fees", mode="before")
    @classmethod
    def convert_trade_fees_to_decimal(cls, v: str | int | float | Decimal) -> Decimal:
        """Convert fees to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def calculate_pnl(self) -> tuple[Decimal | None, float | None]:
        """Calculate P&L based on entry and exit.

        Returns:
            Tuple of (absolute P&L, percentage P&L), or (None, None) if not closed.
        """
        if self.exit_price is None or self.exit_quantity is None:
            return None, None

        entry = self.entry_price
        exit_p = self.exit_price
        qty = self.exit_quantity

        if self.side == "long":
            pnl = (exit_p - entry) * qty * self.leverage - self.fees
            pnl_pct = float((exit_p - entry) / entry) * 100 * self.leverage
        else:  # short
            pnl = (entry - exit_p) * qty * self.leverage - self.fees
            pnl_pct = float((entry - exit_p) / entry) * 100 * self.leverage

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

    def __init__(self, data_dir: Path | None = None) -> None:
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

    def _get_trades_path(self, mode: str) -> Path:
        """Get the path to the trades file for a mode.

        Args:
            mode: Trading mode (backtest/paper/live).

        Returns:
            Path to the trades JSON file.
        """
        mode_dir = self.data_dir / mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        return mode_dir / "trades.json"

    def open_trade(
        self,
        symbol: str,
        side: Literal["long", "short"],
        entry_price: Decimal,
        entry_quantity: Decimal,
        mode: Literal["backtest", "paper", "live"],
        leverage: int = 1,
        entry_order_id: str | None = None,
        performance_record_id: str | None = None,
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
            entry_order_id=entry_order_id,
            performance_record_id=performance_record_id,
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
        trade.exit_time = datetime.now()
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
            f"Closed trade {trade_id}: {close_reason}, "
            f"P&L={pnl} ({pnl_pct:.2f}%)"
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
        trade.exit_time = datetime.now()

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

        with open(trades_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

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
            "entry_price", "entry_quantity", "exit_price",
            "exit_quantity", "fees", "pnl"
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
            with open(trades_path, encoding="utf-8") as f:
                data = json.load(f)
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
            t for t in all_trades
            if t.performance_record_id == performance_record_id
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
