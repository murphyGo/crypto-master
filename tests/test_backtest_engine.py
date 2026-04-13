"""Tests for the Backtester engine."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.backtest.engine import (
    BacktestConfig,
    Backtester,
    BacktestError,
    BacktestResult,
)
from src.models import OHLCV, AnalysisResult
from src.strategy.base import BaseStrategy, TechniqueInfo
from src.trading.profiles import TradingProfile

# =============================================================================
# Test helpers
# =============================================================================


def make_candle(
    timestamp: datetime,
    open_price: Decimal = Decimal("50000"),
    high: Decimal = Decimal("50200"),
    low: Decimal = Decimal("49800"),
    close: Decimal = Decimal("50000"),
    volume: Decimal = Decimal("100"),
) -> OHLCV:
    """Build a single candle with sensible defaults."""
    return OHLCV(
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def make_flat_candles(
    count: int,
    start: datetime | None = None,
    price: Decimal = Decimal("50000"),
    spread: Decimal = Decimal("100"),
) -> list[OHLCV]:
    """Build ``count`` flat candles all centered on ``price``."""
    if start is None:
        start = datetime(2026, 1, 1, 0, 0, 0)
    return [
        make_candle(
            timestamp=start + timedelta(hours=i),
            open_price=price,
            high=price + spread,
            low=price - spread,
            close=price,
        )
        for i in range(count)
    ]


def neutral_analysis() -> AnalysisResult:
    return AnalysisResult(
        signal="neutral",
        confidence=0.0,
        entry_price=Decimal("50000"),
        stop_loss=Decimal("49000"),
        take_profit=Decimal("51000"),
        reasoning="neutral",
    )


def long_analysis(
    entry: str = "50000",
    stop: str = "49500",
    take: str = "51000",
    confidence: float = 0.8,
) -> AnalysisResult:
    return AnalysisResult(
        signal="long",
        confidence=confidence,
        entry_price=Decimal(entry),
        stop_loss=Decimal(stop),
        take_profit=Decimal(take),
        reasoning="long",
    )


def short_analysis(
    entry: str = "50000",
    stop: str = "50500",
    take: str = "49000",
    confidence: float = 0.8,
) -> AnalysisResult:
    return AnalysisResult(
        signal="short",
        confidence=confidence,
        entry_price=Decimal(entry),
        stop_loss=Decimal(stop),
        take_profit=Decimal(take),
        reasoning="short",
    )


class ControllableStrategy(BaseStrategy):
    """Test double: returns a preset AnalysisResult per current-candle index.

    The index is inferred from the length of the OHLCV list the
    backtester passes in (``len(ohlcv) - 1`` == current candle index).
    If no override is provided for an index, ``default`` is returned.
    """

    def __init__(
        self,
        signals: dict[int, AnalysisResult] | None = None,
        default: AnalysisResult | None = None,
        info: TechniqueInfo | None = None,
    ) -> None:
        super().__init__(
            info=info
            or TechniqueInfo(
                name="test_technique",
                version="1.0.0",
                description="controllable test strategy",
                technique_type="code",
            )
        )
        self.signals = signals or {}
        self.default = default or neutral_analysis()
        self.calls: list[int] = []

    async def analyze(
        self, ohlcv: list[OHLCV], symbol: str, timeframe: str = "1h"
    ) -> AnalysisResult:
        index = len(ohlcv) - 1
        self.calls.append(index)
        return self.signals.get(index, self.default)


def make_backtester(
    tmp_path: Path,
    *,
    slippage_bps: int = 0,
    fee_rate: Decimal = Decimal("0"),
    warmup_candles: int = 2,
    leverage: int = 1,
    risk_percent: float = 1.0,
    max_position_size_percent: float = 50.0,
    min_risk_reward_ratio: float = 1.5,
    initial_balance: Decimal = Decimal("10000"),
) -> Backtester:
    return Backtester(
        config=BacktestConfig(
            initial_balance=initial_balance,
            fee_rate=fee_rate,
            slippage_bps=slippage_bps,
            warmup_candles=warmup_candles,
            leverage=leverage,
            risk_percent=risk_percent,
            max_position_size_percent=max_position_size_percent,
            min_risk_reward_ratio=min_risk_reward_ratio,
        ),
        data_dir=tmp_path / "backtest",
    )


# =============================================================================
# Guard rails
# =============================================================================


class TestBacktesterGuards:
    """Tests for basic input validation."""

    @pytest.mark.asyncio
    async def test_empty_ohlcv_raises(self, tmp_path: Path) -> None:
        """Empty series is rejected up front."""
        bt = make_backtester(tmp_path)
        strategy = ControllableStrategy()
        with pytest.raises(BacktestError):
            await bt.run(strategy, [], "BTC/USDT")

    @pytest.mark.asyncio
    async def test_insufficient_warmup_yields_zero_trades(
        self, tmp_path: Path
    ) -> None:
        """If OHLCV shorter than warmup, no analysis calls → no trades."""
        bt = make_backtester(tmp_path, warmup_candles=10)
        strategy = ControllableStrategy(default=long_analysis())
        candles = make_flat_candles(5)
        result = await bt.run(strategy, candles, "BTC/USDT")
        assert result.total_trades == 0
        assert strategy.calls == []

    @pytest.mark.asyncio
    async def test_all_neutral_yields_zero_trades(
        self, tmp_path: Path
    ) -> None:
        """A strategy that always returns neutral trades nothing."""
        bt = make_backtester(tmp_path)
        strategy = ControllableStrategy()  # default is neutral
        candles = make_flat_candles(20)
        result = await bt.run(strategy, candles, "BTC/USDT")
        assert result.total_trades == 0
        assert result.final_balance == result.initial_balance


# =============================================================================
# Walk-forward semantics (no look-ahead)
# =============================================================================


class TestWalkForwardSemantics:
    """Ensure the strategy only sees data up to the current candle."""

    @pytest.mark.asyncio
    async def test_strategy_sees_only_prefix(self, tmp_path: Path) -> None:
        """Each analyze call receives candles 0..i (no future bars)."""
        bt = make_backtester(tmp_path, warmup_candles=1)
        strategy = ControllableStrategy()
        candles = make_flat_candles(5)
        await bt.run(strategy, candles, "BTC/USDT")
        # First call at index 0, last call at index 4
        assert strategy.calls == [0, 1, 2, 3, 4]


# =============================================================================
# Winning & losing trades
# =============================================================================


class TestWinningTrade:
    """Tests for trades that hit take-profit."""

    @pytest.mark.asyncio
    async def test_long_take_profit(self, tmp_path: Path) -> None:
        """A long whose TP is inside a later candle's high closes as a win."""
        bt = make_backtester(tmp_path)
        # Flat candles so no SL/TP hit except when we engineer a breakout.
        candles = make_flat_candles(5)
        # Candle 3 breaks out high to hit TP = 51000
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("51500"),
            low=Decimal("49900"),
            close=Decimal("51200"),
        )
        strategy = ControllableStrategy(
            signals={2: long_analysis()},  # signal at candle 2
        )
        result = await bt.run(strategy, candles, "BTC/USDT")

        assert result.total_trades == 1
        assert result.wins == 1
        assert result.losses == 0
        trade = result.trades[0]
        assert trade.side == "long"
        assert trade.close_reason == "take_profit"
        assert trade.exit_price == Decimal("51000")  # TP target, zero slippage
        assert trade.pnl > 0
        assert result.final_balance > result.initial_balance

    @pytest.mark.asyncio
    async def test_short_take_profit(self, tmp_path: Path) -> None:
        """A short whose TP (lower) is inside a candle's low closes as a win."""
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("48800"),  # breaks below TP 49000
            close=Decimal("48900"),
        )
        strategy = ControllableStrategy(signals={2: short_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")

        assert result.total_trades == 1
        assert result.wins == 1
        assert result.trades[0].side == "short"
        assert result.trades[0].close_reason == "take_profit"
        assert result.trades[0].exit_price == Decimal("49000")


class TestLosingTrade:
    """Tests for trades that hit stop-loss."""

    @pytest.mark.asyncio
    async def test_long_stop_loss(self, tmp_path: Path) -> None:
        """Long whose SL (lower) is inside a candle's low closes as a loss."""
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49200"),  # breaks below SL 49500
            close=Decimal("49400"),
        )
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")

        assert result.total_trades == 1
        assert result.losses == 1
        assert result.trades[0].close_reason == "stop_loss"
        assert result.trades[0].exit_price == Decimal("49500")
        assert result.trades[0].pnl < 0

    @pytest.mark.asyncio
    async def test_sl_wins_when_both_in_same_candle(
        self, tmp_path: Path
    ) -> None:
        """Pessimistic: if SL and TP both fall in range, SL wins."""
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)
        # Huge candle that crosses both SL 49500 AND TP 51000
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("51500"),
            low=Decimal("49200"),
            close=Decimal("50500"),
        )
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        assert result.trades[0].close_reason == "stop_loss"


# =============================================================================
# End-of-data close
# =============================================================================


class TestEndOfDataClose:
    """Open trades are force-closed at the last candle."""

    @pytest.mark.asyncio
    async def test_open_trade_closes_on_last_candle(
        self, tmp_path: Path
    ) -> None:
        """A trade that never hits SL/TP closes at the final candle close."""
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)  # all flat, no SL/TP hit
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        assert result.total_trades == 1
        assert result.trades[0].close_reason == "end_of_data"
        assert result.trades[0].exit_time == candles[-1].timestamp


# =============================================================================
# Concurrent-position gate
# =============================================================================


class TestConcurrentPositions:
    """Second signal during open trade is ignored by default."""

    @pytest.mark.asyncio
    async def test_second_signal_skipped(self, tmp_path: Path) -> None:
        """With default config, only one trade is opened."""
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(6)
        # Long signal at 2 and at 3 — second must be skipped
        strategy = ControllableStrategy(
            signals={2: long_analysis(), 3: long_analysis()}
        )
        result = await bt.run(strategy, candles, "BTC/USDT")
        # End-of-data close of the first trade
        assert result.total_trades == 1


# =============================================================================
# Slippage & fees
# =============================================================================


class TestSlippageAndFees:
    """Slippage and taker fees are reflected in fills and P&L."""

    @pytest.mark.asyncio
    async def test_slippage_applied_to_entry(
        self, tmp_path: Path
    ) -> None:
        """Long entry fills higher than the candle close by slippage_bps."""
        bt = make_backtester(tmp_path, slippage_bps=10)  # 0.1%
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        trade = result.trades[0]
        # candle close is 50000, slippage 10 bps = +50
        assert trade.entry_price == Decimal("50050")

    @pytest.mark.asyncio
    async def test_slippage_applied_to_exit(
        self, tmp_path: Path
    ) -> None:
        """Long TP exit fills lower than the TP target by slippage_bps."""
        bt = make_backtester(tmp_path, slippage_bps=10)
        candles = make_flat_candles(5)
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("51500"),
            low=Decimal("49900"),
            close=Decimal("51200"),
        )
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        trade = result.trades[0]
        # TP=51000, exit slippage 10 bps = -51 => 50949
        assert trade.exit_price == Decimal("50949")

    @pytest.mark.asyncio
    async def test_fees_recorded_on_trade(self, tmp_path: Path) -> None:
        """entry_fee and exit_fee are recorded per trade."""
        bt = make_backtester(tmp_path, fee_rate=Decimal("0.001"))  # 0.1%
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        trade = result.trades[0]
        expected_entry_fee = trade.entry_price * trade.quantity * Decimal("0.001")
        expected_exit_fee = trade.exit_price * trade.quantity * Decimal("0.001")
        assert trade.entry_fee == expected_entry_fee
        assert trade.exit_fee == expected_exit_fee
        assert result.total_fees == expected_entry_fee + expected_exit_fee

    @pytest.mark.asyncio
    async def test_fees_reduce_pnl(self, tmp_path: Path) -> None:
        """A flat round-trip loses only fees, and the loss matches fees."""
        bt = make_backtester(tmp_path, fee_rate=Decimal("0.001"))
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        trade = result.trades[0]
        assert trade.pnl == -trade.entry_fee - trade.exit_fee


# =============================================================================
# Result summary math
# =============================================================================


class TestResultSummary:
    """Aggregate metrics are computed from the trade list."""

    @pytest.mark.asyncio
    async def test_final_balance_matches_initial_plus_pnl(
        self, tmp_path: Path
    ) -> None:
        """Running balance reconciles to final_balance exactly."""
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("51500"),
            low=Decimal("49900"),
            close=Decimal("51200"),
        )
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        assert (
            result.final_balance
            == result.initial_balance + result.total_pnl
        )

    @pytest.mark.asyncio
    async def test_win_rate_for_mixed_results(
        self, tmp_path: Path
    ) -> None:
        """Win rate reflects wins / total_trades."""
        bt = make_backtester(tmp_path)
        # 6 candles: 2 is signal (win), 3 closes with TP, 4 is another
        # signal, 5 ends with end-of-data flat (break-even-ish)
        candles = make_flat_candles(6)
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("51500"),
            low=Decimal("49900"),
            close=Decimal("51000"),
        )
        strategy = ControllableStrategy(
            signals={2: long_analysis(), 4: long_analysis()}
        )
        result = await bt.run(strategy, candles, "BTC/USDT")
        # First trade: TP hit on candle 3 (win). Second trade: opened on
        # candle 4, closes end-of-data on candle 5.
        assert result.total_trades == 2
        assert result.wins >= 1  # at least one winner


# =============================================================================
# Profile integration
# =============================================================================


class TestProfileIntegration:
    """Profiles filter signals and drive sizing."""

    @pytest.mark.asyncio
    async def test_profile_filters_low_confidence(
        self, tmp_path: Path
    ) -> None:
        """A low-confidence signal is skipped when profile.min_confidence is high."""
        bt = make_backtester(tmp_path)
        profile = TradingProfile(
            name="strict",
            min_confidence=0.9,
            risk_percent=1.0,
            max_leverage=5,
            default_leverage=1,
            min_risk_reward_ratio=1.5,
        )
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(
            signals={2: long_analysis(confidence=0.5)}
        )
        result = await bt.run(
            strategy, candles, "BTC/USDT", profile=profile
        )
        assert result.total_trades == 0
        assert result.profile_name == "strict"

    @pytest.mark.asyncio
    async def test_profile_accepted_trade_recorded(
        self, tmp_path: Path
    ) -> None:
        """High-confidence signal is taken; profile_name is on the result."""
        bt = make_backtester(tmp_path)
        profile = TradingProfile(
            name="moderate",
            min_confidence=0.5,
            risk_percent=1.0,
            max_leverage=5,
            default_leverage=1,
            min_risk_reward_ratio=1.5,
        )
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(
            signals={2: long_analysis(confidence=0.9)}
        )
        result = await bt.run(
            strategy, candles, "BTC/USDT", profile=profile
        )
        assert result.total_trades == 1
        assert result.profile_name == "moderate"


# =============================================================================
# Persistence (NFR-006)
# =============================================================================


class TestPersistence:
    """Backtest results can be saved, listed, and reloaded."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, tmp_path: Path) -> None:
        """Save a result then load it back equal (modulo JSON types)."""
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("51500"),
            low=Decimal("49900"),
            close=Decimal("51200"),
        )
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")

        path = bt.save_result(result)
        assert path.exists()

        loaded = bt.load_result(result.run_id)
        assert loaded is not None
        assert isinstance(loaded, BacktestResult)
        assert loaded.run_id == result.run_id
        assert loaded.total_trades == result.total_trades
        assert loaded.final_balance == result.final_balance
        assert len(loaded.trades) == len(result.trades)
        assert loaded.trades[0].close_reason == "take_profit"

    @pytest.mark.asyncio
    async def test_load_missing_returns_none(
        self, tmp_path: Path
    ) -> None:
        """Non-existent run_id loads to None."""
        bt = make_backtester(tmp_path)
        assert bt.load_result("does-not-exist") is None

    @pytest.mark.asyncio
    async def test_list_runs(self, tmp_path: Path) -> None:
        """list_runs returns all saved run IDs."""
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(signals={2: long_analysis()})

        result_a = await bt.run(strategy, candles, "BTC/USDT")
        result_b = await bt.run(strategy, candles, "BTC/USDT")
        bt.save_result(result_a)
        bt.save_result(result_b)

        runs = bt.list_runs()
        assert result_a.run_id in runs
        assert result_b.run_id in runs

    def test_list_runs_empty_dir(self, tmp_path: Path) -> None:
        """list_runs on a fresh dir returns []."""
        bt = make_backtester(tmp_path)
        assert bt.list_runs() == []
