"""Performance tracking for analysis techniques.

Tracks trade outcomes and calculates aggregate metrics like win rate
and profit rate for each analysis technique.

Related Requirements:
- FR-004: Analysis Technique Storage/Management
- FR-005: Analysis Technique Performance Tracking
- NFR-006: Backtesting Result Storage (JSON format)
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

    model_config = {"use_enum_values": True}

    @field_validator("entry_price", "stop_loss", "take_profit", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: str | int | float | Decimal) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("exit_price", mode="before")
    @classmethod
    def convert_exit_to_decimal(
        cls, v: str | int | float | Decimal | None
    ) -> Decimal | None:
        """Convert exit price to Decimal if present."""
        if v is None:
            return None
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
        for key in ["entry_price", "stop_loss", "take_profit", "exit_price"]:
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
