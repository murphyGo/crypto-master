"""Tests for strategy performance tracking.

Tests PerformanceRecord, TechniquePerformance, PerformanceTracker,
TradeHistory, and TradeHistoryTracker.
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
    TradeHistory,
    TradeHistoryTracker,
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


class TestPerformanceRecordEnhanced:
    """Tests for PerformanceRecord enhanced fields (NFR-007)."""

    def test_create_record_with_trade_fields(self) -> None:
        """Test creating record with trade execution details."""
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
            quantity=Decimal("0.1"),
            leverage=10,
            fees=Decimal("5.50"),
            actual_entry_price=Decimal("50010"),
            mode="paper",
        )

        assert record.quantity == Decimal("0.1")
        assert record.leverage == 10
        assert record.fees == Decimal("5.50")
        assert record.actual_entry_price == Decimal("50010")
        assert record.mode == "paper"

    def test_default_trade_fields(self) -> None:
        """Test default values for trade execution fields."""
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

        assert record.quantity is None
        assert record.leverage == 1
        assert record.fees == Decimal("0")
        assert record.actual_entry_price is None
        assert record.actual_exit_price is None
        assert record.mode == "backtest"
        assert record.trade_id is None

    def test_trade_id_link(self) -> None:
        """Test record can be linked to trade ID."""
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
            trade_id="abc-123-def",
        )

        assert record.trade_id == "abc-123-def"

    def test_record_serialization_with_trade_fields(
        self, tracker: PerformanceTracker, tmp_path: Path
    ) -> None:
        """Test enhanced fields are serialized correctly."""
        record = PerformanceRecord(
            technique_name="test_enhanced",
            technique_version="1.0.0",
            symbol="BTC/USDT",
            timeframe="1h",
            signal="long",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.8,
            quantity=Decimal("0.5"),
            leverage=5,
            fees=Decimal("10.25"),
            mode="live",
        )

        tracker.save_record(record)

        records_path = tmp_path / "test_enhanced" / "records.json"
        with open(records_path) as f:
            data = json.load(f)

        assert data[0]["quantity"] == "0.5"
        assert data[0]["leverage"] == 5
        assert data[0]["fees"] == "10.25"
        assert data[0]["mode"] == "live"


class TestTradeHistory:
    """Tests for TradeHistory model."""

    def test_create_trade_history(self) -> None:
        """Test creating a TradeHistory record."""
        trade = TradeHistory(
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
        )

        assert trade.id is not None
        assert trade.symbol == "BTC/USDT"
        assert trade.side == "long"
        assert trade.mode == "paper"
        assert trade.status == "open"
        assert trade.leverage == 1
        assert trade.fees == Decimal("0")

    def test_trade_id_is_unique(self) -> None:
        """Test each trade gets a unique ID."""
        trade1 = TradeHistory(
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
        )
        trade2 = TradeHistory(
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
        )

        assert trade1.id != trade2.id

    def test_decimal_conversion(self) -> None:
        """Test numeric values are converted to Decimal."""
        trade = TradeHistory(
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_price=50000,  # int
            entry_quantity="0.1",  # string
            fees=5.5,  # float
        )

        assert isinstance(trade.entry_price, Decimal)
        assert isinstance(trade.entry_quantity, Decimal)
        assert isinstance(trade.fees, Decimal)

    def test_calculate_pnl_long_win(self) -> None:
        """Test P&L calculation for winning long trade."""
        trade = TradeHistory(
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            exit_price=Decimal("52000"),
            exit_quantity=Decimal("0.1"),
            leverage=10,
            fees=Decimal("10"),
        )

        pnl, pnl_pct = trade.calculate_pnl()

        assert pnl is not None
        # (52000 - 50000) * 0.1 * 10 - 10 = 2000 * 0.1 * 10 - 10 = 2000 - 10 = 1990
        assert pnl == Decimal("1990")
        # (2000/50000) * 100 * 10 = 0.04 * 100 * 10 = 40%
        assert abs(pnl_pct - 40.0) < 0.01

    def test_calculate_pnl_short_win(self) -> None:
        """Test P&L calculation for winning short trade."""
        trade = TradeHistory(
            symbol="BTC/USDT",
            side="short",
            mode="paper",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            exit_price=Decimal("48000"),
            exit_quantity=Decimal("0.1"),
            leverage=5,
            fees=Decimal("5"),
        )

        pnl, pnl_pct = trade.calculate_pnl()

        assert pnl is not None
        # (50000 - 48000) * 0.1 * 5 - 5 = 2000 * 0.1 * 5 - 5 = 1000 - 5 = 995
        assert pnl == Decimal("995")
        # (2000/50000) * 100 * 5 = 0.04 * 100 * 5 = 20%
        assert abs(pnl_pct - 20.0) < 0.01

    def test_calculate_pnl_long_loss(self) -> None:
        """Test P&L calculation for losing long trade."""
        trade = TradeHistory(
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            exit_price=Decimal("49000"),
            exit_quantity=Decimal("0.1"),
            leverage=10,
            fees=Decimal("10"),
        )

        pnl, pnl_pct = trade.calculate_pnl()

        assert pnl is not None
        # (49000 - 50000) * 0.1 * 10 - 10 = -1000 * 0.1 * 10 - 10 = -1000 - 10 = -1010
        assert pnl == Decimal("-1010")
        assert pnl_pct < 0

    def test_calculate_pnl_open_trade(self) -> None:
        """Test P&L returns None for open trade."""
        trade = TradeHistory(
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
        )

        pnl, pnl_pct = trade.calculate_pnl()
        assert pnl is None
        assert pnl_pct is None

    def test_link_to_performance_record(self) -> None:
        """Test trade can be linked to performance record."""
        trade = TradeHistory(
            symbol="BTC/USDT",
            side="long",
            mode="paper",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            performance_record_id="perf-123",
        )

        assert trade.performance_record_id == "perf-123"


@pytest.fixture
def trade_tracker(tmp_path: Path) -> TradeHistoryTracker:
    """Create a TradeHistoryTracker with temporary directory."""
    return TradeHistoryTracker(data_dir=tmp_path)


class TestTradeHistoryTracker:
    """Tests for TradeHistoryTracker class."""

    def test_init_default_dir(self) -> None:
        """Test tracker initializes with default directory."""
        tracker = TradeHistoryTracker()
        assert "trades" in str(tracker.data_dir)

    def test_init_custom_dir(self, tmp_path: Path) -> None:
        """Test tracker initializes with custom directory."""
        tracker = TradeHistoryTracker(data_dir=tmp_path)
        assert tracker.data_dir == tmp_path

    def test_open_trade(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test opening a new trade."""
        trade = trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
            leverage=10,
        )

        assert trade.id is not None
        assert trade.symbol == "BTC/USDT"
        assert trade.side == "long"
        assert trade.mode == "paper"
        assert trade.leverage == 10
        assert trade.status == "open"

    def test_close_trade(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test closing an open trade."""
        trade = trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        closed = trade_tracker.close_trade(
            trade.id,
            exit_price=Decimal("52000"),
            close_reason="take_profit",
            fees=Decimal("5"),
        )

        assert closed is not None
        assert closed.status == "closed"
        assert closed.exit_price == Decimal("52000")
        assert closed.close_reason == "take_profit"
        assert closed.pnl is not None
        assert closed.pnl_percent is not None

    def test_close_trade_not_found(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test closing non-existent trade."""
        result = trade_tracker.close_trade(
            "nonexistent-id",
            exit_price=Decimal("50000"),
        )
        assert result is None

    def test_close_already_closed_trade(
        self, trade_tracker: TradeHistoryTracker
    ) -> None:
        """Test closing already closed trade fails."""
        trade = trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        trade_tracker.close_trade(trade.id, exit_price=Decimal("51000"))
        result = trade_tracker.close_trade(trade.id, exit_price=Decimal("52000"))

        assert result is None

    def test_cancel_trade(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test cancelling an open trade."""
        trade = trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        cancelled = trade_tracker.cancel_trade(trade.id)

        assert cancelled is not None
        assert cancelled.status == "cancelled"

    def test_load_trades_by_mode(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test loading trades filtered by mode."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )
        trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="short",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1.0"),
            mode="live",
        )

        paper_trades = trade_tracker.load_trades(mode="paper")
        live_trades = trade_tracker.load_trades(mode="live")

        assert len(paper_trades) == 1
        assert paper_trades[0].symbol == "BTC/USDT"
        assert len(live_trades) == 1
        assert live_trades[0].symbol == "ETH/USDT"

    def test_load_trades_by_symbol(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test loading trades filtered by symbol."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )
        trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="short",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1.0"),
            mode="paper",
        )

        btc_trades = trade_tracker.load_trades(symbol="BTC/USDT")

        assert len(btc_trades) == 1
        assert btc_trades[0].symbol == "BTC/USDT"

    def test_get_open_trades(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test getting open trades."""
        trade1 = trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )
        trade2 = trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="short",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1.0"),
            mode="paper",
        )

        # Close one trade
        trade_tracker.close_trade(trade1.id, exit_price=Decimal("51000"))

        open_trades = trade_tracker.get_open_trades(mode="paper")

        assert len(open_trades) == 1
        assert open_trades[0].id == trade2.id

    def test_get_trade_by_id(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test getting trade by ID."""
        trade = trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        found = trade_tracker.get_trade(trade.id)

        assert found is not None
        assert found.id == trade.id
        assert found.symbol == "BTC/USDT"

    def test_get_trade_not_found(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test getting non-existent trade."""
        found = trade_tracker.get_trade("nonexistent-id")
        assert found is None

    def test_get_trades_by_date_range(
        self, trade_tracker: TradeHistoryTracker
    ) -> None:
        """Test filtering trades by date range."""
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        trades = trade_tracker.get_trades_by_date_range(
            yesterday, now + timedelta(hours=1), mode="paper"
        )

        assert len(trades) == 1

    def test_link_to_performance(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test linking trade to performance record."""
        trade = trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        linked = trade_tracker.link_to_performance(trade.id, "perf-record-123")

        assert linked is not None
        assert linked.performance_record_id == "perf-record-123"

        # Verify persisted
        found = trade_tracker.get_trade(trade.id)
        assert found.performance_record_id == "perf-record-123"

    def test_get_trades_by_performance_record(
        self, trade_tracker: TradeHistoryTracker
    ) -> None:
        """Test getting trades linked to performance record."""
        trade1 = trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
            performance_record_id="perf-123",
        )
        trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="short",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1.0"),
            mode="paper",
            performance_record_id="perf-456",
        )

        trades = trade_tracker.get_trades_by_performance_record("perf-123")

        assert len(trades) == 1
        assert trades[0].id == trade1.id

    def test_delete_trades(self, trade_tracker: TradeHistoryTracker) -> None:
        """Test deleting trades for a mode."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        assert trade_tracker.delete_trades("paper") is True
        assert trade_tracker.load_trades(mode="paper") == []

    def test_delete_trades_not_found(
        self, trade_tracker: TradeHistoryTracker
    ) -> None:
        """Test deleting non-existent mode."""
        assert trade_tracker.delete_trades("nonexistent") is False


class TestTradeHistoryStorage:
    """Tests for trade history data storage (JSON files)."""

    def test_trades_file_created(
        self, trade_tracker: TradeHistoryTracker, tmp_path: Path
    ) -> None:
        """Test trades file is created on save."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        trades_path = tmp_path / "paper" / "trades.json"
        assert trades_path.exists()

    def test_trades_json_format(
        self, trade_tracker: TradeHistoryTracker, tmp_path: Path
    ) -> None:
        """Test trades file is valid JSON."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        trades_path = tmp_path / "paper" / "trades.json"
        with open(trades_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["symbol"] == "BTC/USDT"
        assert data[0]["side"] == "long"
        assert data[0]["status"] == "open"

    def test_decimal_serialization(
        self, trade_tracker: TradeHistoryTracker, tmp_path: Path
    ) -> None:
        """Test Decimal values are serialized as strings."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000.50"),
            entry_quantity=Decimal("0.12345"),
            mode="paper",
        )

        trades_path = tmp_path / "paper" / "trades.json"
        with open(trades_path) as f:
            data = json.load(f)

        assert isinstance(data[0]["entry_price"], str)
        assert data[0]["entry_price"] == "50000.50"
        assert data[0]["entry_quantity"] == "0.12345"

    def test_datetime_serialization(
        self, trade_tracker: TradeHistoryTracker, tmp_path: Path
    ) -> None:
        """Test datetime values are serialized as ISO format."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )

        trades_path = tmp_path / "paper" / "trades.json"
        with open(trades_path) as f:
            data = json.load(f)

        assert isinstance(data[0]["entry_time"], str)
        # Should be parseable
        datetime.fromisoformat(data[0]["entry_time"])

    def test_mode_separation(
        self, trade_tracker: TradeHistoryTracker, tmp_path: Path
    ) -> None:
        """Test trades are separated by mode (NFR-008)."""
        trade_tracker.open_trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            entry_quantity=Decimal("0.1"),
            mode="paper",
        )
        trade_tracker.open_trade(
            symbol="ETH/USDT",
            side="short",
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1.0"),
            mode="live",
        )
        trade_tracker.open_trade(
            symbol="SOL/USDT",
            side="long",
            entry_price=Decimal("100"),
            entry_quantity=Decimal("5.0"),
            mode="backtest",
        )

        paper_path = tmp_path / "paper" / "trades.json"
        live_path = tmp_path / "live" / "trades.json"
        backtest_path = tmp_path / "backtest" / "trades.json"

        assert paper_path.exists()
        assert live_path.exists()
        assert backtest_path.exists()

        with open(paper_path) as f:
            paper_data = json.load(f)
        with open(live_path) as f:
            live_data = json.load(f)
        with open(backtest_path) as f:
            backtest_data = json.load(f)

        assert len(paper_data) == 1
        assert paper_data[0]["symbol"] == "BTC/USDT"
        assert len(live_data) == 1
        assert live_data[0]["symbol"] == "ETH/USDT"
        assert len(backtest_data) == 1
        assert backtest_data[0]["symbol"] == "SOL/USDT"
