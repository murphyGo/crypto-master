"""Tests for strategy performance tracking.

Tests PerformanceRecord, TechniquePerformance, and PerformanceTracker.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.models import AnalysisResult
from src.strategy.base import TechniqueInfo
from src.strategy.performance import (
    PerformanceRecord,
    PerformanceTracker,
    TechniquePerformance,
    TradeOutcome,
)


@pytest.fixture
def sample_technique_info() -> TechniqueInfo:
    """Create a sample TechniqueInfo for testing."""
    return TechniqueInfo(
        name="test_strategy",
        version="1.0.0",
        description="Test strategy for unit tests",
        technique_type="code",
    )


@pytest.fixture
def sample_analysis_result() -> AnalysisResult:
    """Create a sample AnalysisResult for testing."""
    return AnalysisResult(
        signal="long",
        confidence=0.85,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),
        take_profit=Decimal("52000"),
        reasoning="Test analysis",
    )


@pytest.fixture
def sample_performance_record() -> PerformanceRecord:
    """Create a sample PerformanceRecord for testing."""
    return PerformanceRecord(
        technique_name="test_strategy",
        technique_version="1.0.0",
        symbol="BTC/USDT",
        timeframe="4h",
        signal="long",
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),
        take_profit=Decimal("52000"),
        confidence=0.85,
    )


@pytest.fixture
def tracker(tmp_path: Path) -> PerformanceTracker:
    """Create a PerformanceTracker with temporary directory."""
    return PerformanceTracker(data_dir=tmp_path)


class TestTradeOutcome:
    """Tests for TradeOutcome enum."""

    def test_trade_outcome_values(self) -> None:
        """Test TradeOutcome has expected values."""
        assert TradeOutcome.WIN.value == "win"
        assert TradeOutcome.LOSS.value == "loss"
        assert TradeOutcome.BREAKEVEN.value == "breakeven"
        assert TradeOutcome.PENDING.value == "pending"

    def test_trade_outcome_is_string(self) -> None:
        """Test TradeOutcome values are strings."""
        assert isinstance(TradeOutcome.WIN.value, str)


class TestPerformanceRecord:
    """Tests for PerformanceRecord model."""

    def test_create_record_with_defaults(self) -> None:
        """Test creating record with default values."""
        record = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
        )

        assert record.id is not None
        assert record.outcome == TradeOutcome.PENDING
        assert record.exit_price is None
        assert record.pnl_percent is None

    def test_record_id_is_unique(self) -> None:
        """Test each record gets a unique ID."""
        record1 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
        )
        record2 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
        )

        assert record1.id != record2.id

    def test_decimal_conversion(self) -> None:
        """Test numeric values are converted to Decimal."""
        record = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=50000,  # int
            stop_loss="49000",  # string
            take_profit=52000.0,  # float
            confidence=0.8,
        )

        assert isinstance(record.entry_price, Decimal)
        assert isinstance(record.stop_loss, Decimal)
        assert isinstance(record.take_profit, Decimal)

    def test_confidence_validation(self) -> None:
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            PerformanceRecord(
                technique_name="test",
                technique_version="1.0.0",
                symbol="BTC/USDT",
                timeframe="1h",
                signal="long",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49000"),
                take_profit=Decimal("52000"),
                confidence=1.5,  # Invalid
            )

    def test_calculate_pnl_long_win(self) -> None:
        """Test P&L calculation for winning long trade."""
        record = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
            outcome=TradeOutcome.WIN,
            exit_price=Decimal("52000"),
        )

        pnl = record.calculate_pnl()
        assert pnl is not None
        assert abs(pnl - 4.0) < 0.01  # 4% profit

    def test_calculate_pnl_long_loss(self) -> None:
        """Test P&L calculation for losing long trade."""
        record = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
            outcome=TradeOutcome.LOSS,
            exit_price=Decimal("49000"),
        )

        pnl = record.calculate_pnl()
        assert pnl is not None
        assert abs(pnl - (-2.0)) < 0.01  # -2% loss

    def test_calculate_pnl_short_win(self) -> None:
        """Test P&L calculation for winning short trade."""
        record = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="short",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
            confidence=0.8,
            outcome=TradeOutcome.WIN,
            exit_price=Decimal("48000"),
        )

        pnl = record.calculate_pnl()
        assert pnl is not None
        assert abs(pnl - 4.0) < 0.01  # 4% profit

    def test_calculate_pnl_pending(self) -> None:
        """Test P&L returns None for pending trade."""
        record = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
        )

        assert record.calculate_pnl() is None

    def test_calculate_pnl_neutral(self) -> None:
        """Test P&L returns 0 for neutral signal."""
        record = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="neutral",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.5,
            outcome=TradeOutcome.BREAKEVEN,
            exit_price=Decimal("50000"),
        )

        assert record.calculate_pnl() == 0.0


class TestTechniquePerformance:
    """Tests for TechniquePerformance model."""

    def test_create_empty_performance(self) -> None:
        """Test creating performance with default values."""
        perf = TechniquePerformance(
            technique_name="test",
            technique_version="1.0.0",
        )

        assert perf.total_trades == 0
        assert perf.win_rate == 0.0
        assert perf.avg_pnl_percent == 0.0

    def test_from_records_empty(self) -> None:
        """Test from_records with empty list."""
        perf = TechniquePerformance.from_records("test", "1.0.0", [])

        assert perf.total_trades == 0
        assert perf.wins == 0
        assert perf.losses == 0

    def test_from_records_with_trades(self) -> None:
        """Test from_records calculates metrics correctly."""
        records = [
            PerformanceRecord(
                technique_name="test",
                technique_version="1.0.0",
                symbol="BTC/USDT",
                timeframe="1h",
                signal="long",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49000"),
                take_profit=Decimal("52000"),
                confidence=0.8,
                outcome=TradeOutcome.WIN,
                exit_price=Decimal("52000"),
                pnl_percent=4.0,
            ),
            PerformanceRecord(
                technique_name="test",
                technique_version="1.0.0",
                symbol="BTC/USDT",
                timeframe="1h",
                signal="long",
                entry_price=Decimal("51000"),
                stop_loss=Decimal("50000"),
                take_profit=Decimal("53000"),
                confidence=0.7,
                outcome=TradeOutcome.LOSS,
                exit_price=Decimal("50000"),
                pnl_percent=-2.0,
            ),
            PerformanceRecord(
                technique_name="test",
                technique_version="1.0.0",
                symbol="BTC/USDT",
                timeframe="1h",
                signal="long",
                entry_price=Decimal("52000"),
                stop_loss=Decimal("51000"),
                take_profit=Decimal("54000"),
                confidence=0.8,
                outcome=TradeOutcome.WIN,
                exit_price=Decimal("54000"),
                pnl_percent=3.85,
            ),
        ]

        perf = TechniquePerformance.from_records("test", "1.0.0", records)

        assert perf.total_trades == 3
        assert perf.wins == 2
        assert perf.losses == 1
        assert abs(perf.win_rate - 0.6667) < 0.01  # 2/3
        assert perf.best_trade_pnl == 4.0
        assert perf.worst_trade_pnl == -2.0

    def test_from_records_with_pending(self) -> None:
        """Test from_records counts pending correctly."""
        records = [
            PerformanceRecord(
                technique_name="test",
                technique_version="1.0.0",
                symbol="BTC/USDT",
                timeframe="1h",
                signal="long",
                entry_price=Decimal("50000"),
                stop_loss=Decimal("49000"),
                take_profit=Decimal("52000"),
                confidence=0.8,
                outcome=TradeOutcome.PENDING,
            ),
            PerformanceRecord(
                technique_name="test",
                technique_version="1.0.0",
                symbol="BTC/USDT",
                timeframe="1h",
                signal="long",
                entry_price=Decimal("51000"),
                stop_loss=Decimal("50000"),
                take_profit=Decimal("53000"),
                confidence=0.7,
                outcome=TradeOutcome.WIN,
                exit_price=Decimal("53000"),
                pnl_percent=3.9,
            ),
        ]

        perf = TechniquePerformance.from_records("test", "1.0.0", records)

        assert perf.total_trades == 2
        assert perf.pending == 1
        assert perf.wins == 1
        assert perf.win_rate == 1.0  # 1 win / 1 closed


class TestPerformanceTracker:
    """Tests for PerformanceTracker class."""

    def test_init_default_dir(self) -> None:
        """Test tracker initializes with default directory."""
        tracker = PerformanceTracker()
        assert "performance" in str(tracker.data_dir)

    def test_init_custom_dir(self, tmp_path: Path) -> None:
        """Test tracker initializes with custom directory."""
        tracker = PerformanceTracker(data_dir=tmp_path)
        assert tracker.data_dir == tmp_path

    def test_record_analysis(
        self,
        tracker: PerformanceTracker,
        sample_technique_info: TechniqueInfo,
        sample_analysis_result: AnalysisResult,
    ) -> None:
        """Test recording an analysis result."""
        record = tracker.record_analysis(
            sample_technique_info,
            sample_analysis_result,
            "BTC/USDT",
            "4h",
        )

        assert record.technique_name == "test_strategy"
        assert record.technique_version == "1.0.0"
        assert record.symbol == "BTC/USDT"
        assert record.signal == "long"
        assert record.outcome == TradeOutcome.PENDING

    def test_save_and_load_records(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
    ) -> None:
        """Test saving and loading records."""
        tracker.save_record(sample_performance_record)

        records = tracker.load_records("test_strategy")

        assert len(records) == 1
        assert records[0].technique_name == "test_strategy"
        assert records[0].signal == "long"

    def test_load_records_empty(self, tracker: PerformanceTracker) -> None:
        """Test loading records for non-existent technique."""
        records = tracker.load_records("nonexistent")
        assert records == []

    def test_load_records_filter_by_version(
        self, tracker: PerformanceTracker
    ) -> None:
        """Test filtering records by version."""
        record1 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
        )
        record2 = PerformanceRecord(
            technique_name="test",
            technique_version="2.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="short",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
            confidence=0.9,
        )

        tracker.save_record(record1)
        tracker.save_record(record2)

        records_v1 = tracker.load_records("test", version="1.0.0")
        records_v2 = tracker.load_records("test", version="2.0.0")

        assert len(records_v1) == 1
        assert records_v1[0].signal == "long"
        assert len(records_v2) == 1
        assert records_v2[0].signal == "short"

    def test_update_outcome(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
    ) -> None:
        """Test updating trade outcome."""
        tracker.save_record(sample_performance_record)
        record_id = sample_performance_record.id

        updated = tracker.update_outcome(
            record_id,
            TradeOutcome.WIN,
            Decimal("52000"),
            "test_strategy",
        )

        assert updated is not None
        assert updated.outcome == TradeOutcome.WIN
        assert updated.exit_price == Decimal("52000")
        assert updated.pnl_percent is not None

    def test_update_outcome_not_found(self, tracker: PerformanceTracker) -> None:
        """Test updating non-existent record."""
        result = tracker.update_outcome(
            "nonexistent-id",
            TradeOutcome.WIN,
            Decimal("50000"),
            "test_strategy",
        )
        assert result is None

    def test_get_performance(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
    ) -> None:
        """Test getting performance metrics."""
        sample_performance_record.outcome = TradeOutcome.WIN
        sample_performance_record.exit_price = Decimal("52000")
        sample_performance_record.pnl_percent = 4.0

        tracker.save_record(sample_performance_record)

        perf = tracker.get_performance("test_strategy")

        assert perf.total_trades == 1
        assert perf.wins == 1
        assert perf.win_rate == 1.0

    def test_get_records_by_symbol(self, tracker: PerformanceTracker) -> None:
        """Test filtering records by symbol."""
        record1 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
        )
        record2 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="ETH/USDT",
            timeframe="1h",
            signal="short",
            entry_price=Decimal("3000"),
            stop_loss=Decimal("3100"),
            take_profit=Decimal("2800"),
            confidence=0.7,
        )

        tracker.save_record(record1)
        tracker.save_record(record2)

        btc_records = tracker.get_records_by_symbol("test", "BTC/USDT")

        assert len(btc_records) == 1
        assert btc_records[0].symbol == "BTC/USDT"

    def test_get_records_by_timeframe(self, tracker: PerformanceTracker) -> None:
        """Test filtering records by timeframe."""
        record1 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
        )
        record2 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="4h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.7,
        )

        tracker.save_record(record1)
        tracker.save_record(record2)

        hourly_records = tracker.get_records_by_timeframe("test", "1h")

        assert len(hourly_records) == 1
        assert hourly_records[0].timeframe == "1h"

    def test_get_records_by_date_range(self, tracker: PerformanceTracker) -> None:
        """Test filtering records by date range."""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        record1 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
            analysis_timestamp=now,
        )
        record2 = PerformanceRecord(
            technique_name="test",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="short",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
            confidence=0.7,
            analysis_timestamp=last_week,
        )

        tracker.save_record(record1)
        tracker.save_record(record2)

        recent_records = tracker.get_records_by_date_range(
            "test", yesterday, now + timedelta(hours=1)
        )

        assert len(recent_records) == 1
        assert recent_records[0].signal == "long"

    def test_list_techniques(self, tracker: PerformanceTracker) -> None:
        """Test listing techniques with data."""
        record1 = PerformanceRecord(
            technique_name="strategy_a",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
        )
        record2 = PerformanceRecord(
            technique_name="strategy_b",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="short",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
            confidence=0.7,
        )

        tracker.save_record(record1)
        tracker.save_record(record2)

        techniques = tracker.list_techniques()

        assert "strategy_a" in techniques
        assert "strategy_b" in techniques

    def test_delete_records(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
    ) -> None:
        """Test deleting technique records."""
        tracker.save_record(sample_performance_record)

        assert tracker.delete_records("test_strategy") is True
        assert tracker.load_records("test_strategy") == []

    def test_delete_records_not_found(self, tracker: PerformanceTracker) -> None:
        """Test deleting non-existent technique."""
        assert tracker.delete_records("nonexistent") is False


class TestPerformanceStorage:
    """Tests for performance data storage (JSON files)."""

    def test_records_file_created(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
        tmp_path: Path,
    ) -> None:
        """Test records file is created on save."""
        tracker.save_record(sample_performance_record)

        records_path = tmp_path / "test_strategy" / "records.json"
        assert records_path.exists()

    def test_summary_file_created(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
        tmp_path: Path,
    ) -> None:
        """Test summary file is created on save."""
        tracker.save_record(sample_performance_record)

        summary_path = tmp_path / "test_strategy" / "summary.json"
        assert summary_path.exists()

    def test_records_json_format(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
        tmp_path: Path,
    ) -> None:
        """Test records file is valid JSON."""
        tracker.save_record(sample_performance_record)

        records_path = tmp_path / "test_strategy" / "records.json"
        with open(records_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["technique_name"] == "test_strategy"

    def test_summary_json_format(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
        tmp_path: Path,
    ) -> None:
        """Test summary file is valid JSON."""
        tracker.save_record(sample_performance_record)

        summary_path = tmp_path / "test_strategy" / "summary.json"
        with open(summary_path) as f:
            data = json.load(f)

        assert data["technique_name"] == "test_strategy"
        assert "win_rate" in data
        assert "total_trades" in data

    def test_decimal_serialization(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
        tmp_path: Path,
    ) -> None:
        """Test Decimal values are serialized as strings."""
        tracker.save_record(sample_performance_record)

        records_path = tmp_path / "test_strategy" / "records.json"
        with open(records_path) as f:
            data = json.load(f)

        # Decimals should be strings in JSON
        assert isinstance(data[0]["entry_price"], str)
        assert data[0]["entry_price"] == "50000"

    def test_datetime_serialization(
        self,
        tracker: PerformanceTracker,
        sample_performance_record: PerformanceRecord,
        tmp_path: Path,
    ) -> None:
        """Test datetime values are serialized as ISO format."""
        tracker.save_record(sample_performance_record)

        records_path = tmp_path / "test_strategy" / "records.json"
        with open(records_path) as f:
            data = json.load(f)

        # Datetime should be ISO format string
        assert isinstance(data[0]["analysis_timestamp"], str)
        # Should be parseable
        datetime.fromisoformat(data[0]["analysis_timestamp"])
