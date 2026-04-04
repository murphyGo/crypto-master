"""Tests for the data models module."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models import (
    AnalysisResult,
    Balance,
    OHLCV,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
    Ticker,
    Trade,
)


class TestOrderStatus:
    """Tests for OrderStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Test that all expected statuses are defined."""
        assert OrderStatus.PENDING == "pending"
        assert OrderStatus.OPEN == "open"
        assert OrderStatus.FILLED == "filled"
        assert OrderStatus.PARTIALLY_FILLED == "partially_filled"
        assert OrderStatus.CANCELLED == "cancelled"
        assert OrderStatus.REJECTED == "rejected"

    def test_is_json_serializable(self) -> None:
        """Test that OrderStatus is JSON serializable."""
        status = OrderStatus.FILLED
        assert str(status.value) == "filled"


class TestOHLCV:
    """Tests for OHLCV model."""

    def test_create_ohlcv(self) -> None:
        """Test creating an OHLCV instance."""
        now = datetime.now()
        ohlcv = OHLCV(
            timestamp=now,
            open=Decimal("100.5"),
            high=Decimal("105.0"),
            low=Decimal("99.0"),
            close=Decimal("103.0"),
            volume=Decimal("1000000"),
        )
        assert ohlcv.timestamp == now
        assert ohlcv.open == Decimal("100.5")
        assert ohlcv.close == Decimal("103.0")

    def test_ohlcv_is_immutable(self) -> None:
        """Test that OHLCV instances are immutable (frozen)."""
        ohlcv = OHLCV(
            timestamp=datetime.now(),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("103"),
            volume=Decimal("1000"),
        )
        with pytest.raises(ValidationError):
            ohlcv.close = Decimal("200")

    def test_ohlcv_serialization(self) -> None:
        """Test OHLCV serializes to dict correctly."""
        now = datetime.now()
        ohlcv = OHLCV(
            timestamp=now,
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("103"),
            volume=Decimal("1000"),
        )
        data = ohlcv.model_dump()
        assert data["open"] == Decimal("100")
        assert data["timestamp"] == now


class TestTicker:
    """Tests for Ticker model."""

    def test_create_ticker(self) -> None:
        """Test creating a Ticker instance."""
        now = datetime.now()
        ticker = Ticker(symbol="BTC/USDT", price=Decimal("50000"), timestamp=now)
        assert ticker.symbol == "BTC/USDT"
        assert ticker.price == Decimal("50000")


class TestBalance:
    """Tests for Balance model."""

    def test_create_balance(self) -> None:
        """Test creating a Balance instance."""
        balance = Balance(
            currency="USDT",
            free=Decimal("1000"),
            locked=Decimal("500"),
            total=Decimal("1500"),
        )
        assert balance.currency == "USDT"
        assert balance.free == Decimal("1000")
        assert balance.total == Decimal("1500")

    def test_balance_defaults(self) -> None:
        """Test Balance has sensible defaults."""
        balance = Balance(currency="BTC")
        assert balance.free == Decimal("0")
        assert balance.locked == Decimal("0")


class TestOrderRequest:
    """Tests for OrderRequest model."""

    def test_create_market_order(self) -> None:
        """Test creating a market order request."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            type="market",
            quantity=Decimal("0.1"),
        )
        assert order.type == "market"
        assert order.price is None

    def test_create_limit_order(self) -> None:
        """Test creating a limit order request."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="sell",
            type="limit",
            quantity=Decimal("0.1"),
            price=Decimal("55000"),
        )
        assert order.type == "limit"
        assert order.price == Decimal("55000")

    def test_limit_order_requires_price(self) -> None:
        """Test that limit orders must have a price."""
        with pytest.raises(ValidationError):
            OrderRequest(
                symbol="BTC/USDT",
                side="buy",
                type="limit",
                quantity=Decimal("0.1"),
                # price is missing
            )

    def test_quantity_must_be_positive(self) -> None:
        """Test that quantity must be positive."""
        with pytest.raises(ValidationError):
            OrderRequest(
                symbol="BTC/USDT",
                side="buy",
                type="market",
                quantity=Decimal("0"),
            )

    def test_side_validation(self) -> None:
        """Test that side must be buy or sell."""
        with pytest.raises(ValidationError):
            OrderRequest(
                symbol="BTC/USDT",
                side="invalid",  # type: ignore
                type="market",
                quantity=Decimal("1"),
            )


class TestOrder:
    """Tests for Order model."""

    def test_create_order(self) -> None:
        """Test creating an Order instance."""
        now = datetime.now()
        order = Order(
            id="123",
            symbol="BTC/USDT",
            side="buy",
            type="limit",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            status=OrderStatus.OPEN,
            created_at=now,
        )
        assert order.id == "123"
        assert order.status == OrderStatus.OPEN

    def test_remaining_quantity(self) -> None:
        """Test remaining_quantity calculation."""
        order = Order(
            id="123",
            symbol="BTC/USDT",
            side="buy",
            type="market",
            quantity=Decimal("1.0"),
            filled_quantity=Decimal("0.3"),
            status=OrderStatus.PARTIALLY_FILLED,
            created_at=datetime.now(),
        )
        assert order.remaining_quantity == Decimal("0.7")

    def test_is_complete_for_filled(self) -> None:
        """Test is_complete returns True for filled orders."""
        order = Order(
            id="123",
            symbol="BTC/USDT",
            side="buy",
            type="market",
            quantity=Decimal("1.0"),
            filled_quantity=Decimal("1.0"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )
        assert order.is_complete is True

    def test_is_complete_for_cancelled(self) -> None:
        """Test is_complete returns True for cancelled orders."""
        order = Order(
            id="123",
            symbol="BTC/USDT",
            side="buy",
            type="market",
            quantity=Decimal("1.0"),
            status=OrderStatus.CANCELLED,
            created_at=datetime.now(),
        )
        assert order.is_complete is True

    def test_is_complete_for_open(self) -> None:
        """Test is_complete returns False for open orders."""
        order = Order(
            id="123",
            symbol="BTC/USDT",
            side="buy",
            type="market",
            quantity=Decimal("1.0"),
            status=OrderStatus.OPEN,
            created_at=datetime.now(),
        )
        assert order.is_complete is False


class TestPosition:
    """Tests for Position model."""

    def test_create_position(self) -> None:
        """Test creating a Position instance."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        assert position.symbol == "BTC/USDT"
        assert position.leverage == 10

    def test_position_defaults(self) -> None:
        """Test Position has sensible defaults."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
        )
        assert position.leverage == 1
        assert position.stop_loss is None
        assert position.take_profit is None

    def test_notional_value(self) -> None:
        """Test notional_value calculation."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
        )
        assert position.notional_value == Decimal("5000")

    def test_margin_required(self) -> None:
        """Test margin_required calculation."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
        )
        assert position.margin_required == Decimal("500")

    def test_calculate_pnl_long_profit(self) -> None:
        """Test PnL calculation for profitable long position."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
        )
        pnl = position.calculate_pnl(Decimal("55000"))
        assert pnl == Decimal("500")  # (55000 - 50000) * 0.1

    def test_calculate_pnl_long_loss(self) -> None:
        """Test PnL calculation for losing long position."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
        )
        pnl = position.calculate_pnl(Decimal("45000"))
        assert pnl == Decimal("-500")

    def test_calculate_pnl_short_profit(self) -> None:
        """Test PnL calculation for profitable short position."""
        position = Position(
            symbol="BTC/USDT",
            side="short",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
        )
        pnl = position.calculate_pnl(Decimal("45000"))
        assert pnl == Decimal("500")

    def test_leverage_constraints(self) -> None:
        """Test leverage must be between 1 and 125."""
        with pytest.raises(ValidationError):
            Position(
                symbol="BTC/USDT",
                side="long",
                entry_price=Decimal("50000"),
                quantity=Decimal("0.1"),
                leverage=0,
            )

        with pytest.raises(ValidationError):
            Position(
                symbol="BTC/USDT",
                side="long",
                entry_price=Decimal("50000"),
                quantity=Decimal("0.1"),
                leverage=126,
            )


class TestAnalysisResult:
    """Tests for AnalysisResult model."""

    def test_create_analysis_result(self) -> None:
        """Test creating an AnalysisResult instance."""
        result = AnalysisResult(
            signal="long",
            confidence=0.85,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("55000"),
            reasoning="Bullish pattern detected",
        )
        assert result.signal == "long"
        assert result.confidence == 0.85

    def test_confidence_must_be_0_to_1(self) -> None:
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            AnalysisResult(
                signal="long",
                confidence=1.5,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                reasoning="Test",
            )

        with pytest.raises(ValidationError):
            AnalysisResult(
                signal="long",
                confidence=-0.1,
                entry_price=Decimal("50000"),
                stop_loss=Decimal("48000"),
                take_profit=Decimal("55000"),
                reasoning="Test",
            )

    def test_risk_reward_ratio(self) -> None:
        """Test risk_reward_ratio calculation."""
        result = AnalysisResult(
            signal="long",
            confidence=0.8,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),  # Risk: 2000
            take_profit=Decimal("56000"),  # Reward: 6000
            reasoning="Test",
        )
        assert result.risk_reward_ratio == 3.0  # 6000 / 2000

    def test_risk_reward_ratio_with_zero_risk(self) -> None:
        """Test risk_reward_ratio returns None with zero risk."""
        result = AnalysisResult(
            signal="long",
            confidence=0.8,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("50000"),  # Same as entry
            take_profit=Decimal("55000"),
            reasoning="Test",
        )
        assert result.risk_reward_ratio is None

    def test_timestamp_defaults_to_now(self) -> None:
        """Test that timestamp defaults to current time."""
        before = datetime.now()
        result = AnalysisResult(
            signal="neutral",
            confidence=0.5,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("48000"),
            take_profit=Decimal("52000"),
            reasoning="Test",
        )
        after = datetime.now()
        assert before <= result.timestamp <= after


class TestTrade:
    """Tests for Trade model."""

    def test_create_trade(self) -> None:
        """Test creating a Trade instance."""
        entry_time = datetime.now() - timedelta(hours=2)
        exit_time = datetime.now()
        trade = Trade(
            id="trade_001",
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            exit_price=Decimal("52000"),
            quantity=Decimal("0.1"),
            leverage=10,
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=Decimal("200"),
            pnl_percentage=4.0,
            fees=Decimal("1.0"),
        )
        assert trade.id == "trade_001"
        assert trade.pnl == Decimal("200")

    def test_is_profitable(self) -> None:
        """Test is_profitable property."""
        profitable_trade = Trade(
            id="1",
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            exit_price=Decimal("52000"),
            quantity=Decimal("0.1"),
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            pnl=Decimal("200"),
            pnl_percentage=4.0,
        )
        assert profitable_trade.is_profitable is True

        losing_trade = Trade(
            id="2",
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            exit_price=Decimal("48000"),
            quantity=Decimal("0.1"),
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            pnl=Decimal("-200"),
            pnl_percentage=-4.0,
        )
        assert losing_trade.is_profitable is False

    def test_duration(self) -> None:
        """Test duration calculation in hours."""
        entry_time = datetime.now() - timedelta(hours=3, minutes=30)
        exit_time = datetime.now()
        trade = Trade(
            id="1",
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            exit_price=Decimal("52000"),
            quantity=Decimal("0.1"),
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=Decimal("200"),
            pnl_percentage=4.0,
        )
        assert trade.duration == pytest.approx(3.5, rel=0.01)


class TestDecimalPrecision:
    """Tests for Decimal precision handling."""

    def test_decimal_precision_preserved(self) -> None:
        """Test that Decimal precision is preserved."""
        ohlcv = OHLCV(
            timestamp=datetime.now(),
            open=Decimal("100.12345678"),
            high=Decimal("105.00000001"),
            low=Decimal("99.99999999"),
            close=Decimal("103.50000000"),
            volume=Decimal("1000000.123"),
        )
        assert ohlcv.open == Decimal("100.12345678")
        assert ohlcv.high == Decimal("105.00000001")

    def test_decimal_from_string(self) -> None:
        """Test creating Decimal from string maintains precision."""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000.12345678"),
            quantity=Decimal("0.00001234"),
        )
        assert str(position.entry_price) == "50000.12345678"
        assert str(position.quantity) == "0.00001234"
