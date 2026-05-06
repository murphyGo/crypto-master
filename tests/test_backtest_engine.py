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
    async def test_insufficient_warmup_yields_zero_trades(self, tmp_path: Path) -> None:
        """If OHLCV shorter than warmup, no analysis calls → no trades."""
        bt = make_backtester(tmp_path, warmup_candles=10)
        strategy = ControllableStrategy(default=long_analysis())
        candles = make_flat_candles(5)
        result = await bt.run(strategy, candles, "BTC/USDT")
        assert result.total_trades == 0
        assert strategy.calls == []

    @pytest.mark.asyncio
    async def test_strategy_minimum_candles_raises_effective_warmup(
        self, tmp_path: Path
    ) -> None:
        """Strategy-owned warmup can raise the engine's default floor."""
        bt = make_backtester(tmp_path, warmup_candles=2)
        strategy = ControllableStrategy(
            info=TechniqueInfo(
                name="warmup_test",
                version="1.0.0",
                description="strategy with declared warmup",
                technique_type="code",
                min_warmup_candles=4,
            )
        )
        candles = make_flat_candles(6)

        await bt.run(strategy, candles, "BTC/USDT")

        assert bt.effective_warmup_candles(strategy) == 4
        assert strategy.calls == [3, 4, 5]

    @pytest.mark.asyncio
    async def test_all_neutral_yields_zero_trades(self, tmp_path: Path) -> None:
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
    async def test_sl_wins_when_both_in_same_candle(self, tmp_path: Path) -> None:
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
    async def test_open_trade_closes_on_last_candle(self, tmp_path: Path) -> None:
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
    async def test_slippage_applied_to_entry(self, tmp_path: Path) -> None:
        """Long entry fills higher than the candle close by slippage_bps."""
        bt = make_backtester(tmp_path, slippage_bps=10)  # 0.1%
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        trade = result.trades[0]
        # candle close is 50000, slippage 10 bps = +50
        assert trade.entry_price == Decimal("50050")

    @pytest.mark.asyncio
    async def test_slippage_applied_to_exit(self, tmp_path: Path) -> None:
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
    async def test_final_balance_matches_initial_plus_pnl(self, tmp_path: Path) -> None:
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
        assert result.final_balance == result.initial_balance + result.total_pnl

    @pytest.mark.asyncio
    async def test_win_rate_for_mixed_results(self, tmp_path: Path) -> None:
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
    async def test_profile_filters_low_confidence(self, tmp_path: Path) -> None:
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
        strategy = ControllableStrategy(signals={2: long_analysis(confidence=0.5)})
        result = await bt.run(strategy, candles, "BTC/USDT", profile=profile)
        assert result.total_trades == 0
        assert result.profile_name == "strict"

    @pytest.mark.asyncio
    async def test_profile_accepted_trade_recorded(self, tmp_path: Path) -> None:
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
        strategy = ControllableStrategy(signals={2: long_analysis(confidence=0.9)})
        result = await bt.run(strategy, candles, "BTC/USDT", profile=profile)
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
    async def test_load_missing_returns_none(self, tmp_path: Path) -> None:
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

    @pytest.mark.asyncio
    async def test_save_result_crash_leaves_no_half_written_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 26.1 / DEBT-045: a mid-write crash leaves no half-written ``result.json``.

        Mirrors the Phase 22.1 site tests: monkeypatch
        ``atomic_write_text`` to raise, then assert that no truncated
        ``result.json`` is sitting in the run directory for downstream
        readers to trip over.
        """
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")

        def boom(path: Path, text: str, **kwargs: object) -> None:
            raise OSError("simulated mid-write crash")

        monkeypatch.setattr("src.backtest.engine.atomic_write_text", boom)

        with pytest.raises(OSError, match="simulated mid-write crash"):
            bt.save_result(result)

        # Fresh-run case: no prior file, no half-written file. The run
        # directory was created (mkdir is upstream of the write) but
        # ``result.json`` itself must not exist.
        run_dir = (tmp_path / "backtest") / result.run_id
        assert run_dir.exists()
        assert not (run_dir / "result.json").exists()

    @pytest.mark.asyncio
    async def test_save_result_crash_preserves_prior_result(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 26.1 / DEBT-045: a mid-write crash preserves a prior ``result.json``.

        Re-saving the same ``run_id`` (rare in practice, but the
        durability contract is "either fully old or fully new") must
        leave the original payload readable byte-for-byte.
        """
        bt = make_backtester(tmp_path)
        candles = make_flat_candles(5)
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")
        path = bt.save_result(result)
        original_bytes = path.read_bytes()

        def boom(p: Path, text: str, **kwargs: object) -> None:
            raise OSError("simulated mid-write crash")

        monkeypatch.setattr("src.backtest.engine.atomic_write_text", boom)

        with pytest.raises(OSError, match="simulated mid-write crash"):
            bt.save_result(result)

        # The original payload is preserved byte-for-byte.
        assert path.read_bytes() == original_bytes
        loaded = bt.load_result(result.run_id)
        assert loaded is not None
        assert loaded.run_id == result.run_id


# =============================================================================
# Per-bar circuit breaker (Phase 17.2 / DEBT-019)
# =============================================================================


class TestPerBarCircuitBreaker:
    """The backtester must abort cleanly when a per-bar invocation
    either times out or accumulates ``max_parse_failures`` consecutive
    failures. Closes the 9-hour-hang failure mode where a structurally
    broken ``prompt``-type technique looped forever producing
    unparseable output."""

    @pytest.mark.asyncio
    async def test_consecutive_parse_failures_trip_breaker(
        self, tmp_path: Path
    ) -> None:
        """``ClaudeParseError`` raised on every bar trips
        ``BacktestAbortedError(reason="consecutive_parse_failures")``
        after exactly ``max_parse_failures`` consecutive failures."""
        from src.ai.exceptions import ClaudeParseError
        from src.backtest.engine import BacktestAbortedError

        class AlwaysParseError(BaseStrategy):
            def __init__(self) -> None:
                super().__init__(
                    info=TechniqueInfo(
                        name="always_parse_error",
                        version="1.0.0",
                        description="raises ClaudeParseError every bar",
                        technique_type="prompt",
                    )
                )
                self.calls = 0

            async def analyze(
                self,
                ohlcv: list[OHLCV],
                symbol: str,
                timeframe: str = "1h",
            ) -> AnalysisResult:
                self.calls += 1
                raise ClaudeParseError("no parseable JSON in response")

        # Override the breaker config explicitly so the test pins the
        # contract regardless of the global default.
        bt = Backtester(
            config=BacktestConfig(
                warmup_candles=2,
                fee_rate=Decimal("0"),
                slippage_bps=0,
                max_parse_failures=3,
                per_bar_timeout=60.0,
            ),
            data_dir=tmp_path / "backtest",
        )
        strategy = AlwaysParseError()
        candles = make_flat_candles(20)

        with pytest.raises(BacktestAbortedError) as excinfo:
            await bt.run(strategy, candles, "BTC/USDT")
        assert excinfo.value.reason == "consecutive_parse_failures"
        # First analysis call lands on candle index 1 (warmup_candles=2
        # means we need len(prefix) >= 2, so i=1 is the first bar that
        # actually invokes analyze). 3 consecutive failures trip on
        # candle index 3 (1, 2, 3).
        assert excinfo.value.candle_index == 3
        assert strategy.calls == 3

    @pytest.mark.asyncio
    async def test_per_bar_timeout_trips_breaker(self, tmp_path: Path) -> None:
        """A strategy that blocks past ``per_bar_timeout`` aborts with
        ``BacktestAbortedError(reason="per_bar_timeout")`` on the
        first slow bar — no consecutive-failure accumulation needed."""
        import asyncio

        from src.backtest.engine import BacktestAbortedError

        class TooSlow(BaseStrategy):
            def __init__(self) -> None:
                super().__init__(
                    info=TechniqueInfo(
                        name="too_slow",
                        version="1.0.0",
                        description="sleeps past per-bar timeout",
                        technique_type="prompt",
                    )
                )
                self.calls = 0

            async def analyze(
                self,
                ohlcv: list[OHLCV],
                symbol: str,
                timeframe: str = "1h",
            ) -> AnalysisResult:
                self.calls += 1
                # Block much longer than the per_bar_timeout below.
                await asyncio.sleep(5.0)
                return long_analysis()

        bt = Backtester(
            config=BacktestConfig(
                warmup_candles=2,
                fee_rate=Decimal("0"),
                slippage_bps=0,
                max_parse_failures=5,
                # Tight enough to fire well before the 5s sleep.
                per_bar_timeout=1.0,
            ),
            data_dir=tmp_path / "backtest",
        )
        strategy = TooSlow()
        candles = make_flat_candles(20)

        with pytest.raises(BacktestAbortedError) as excinfo:
            await bt.run(strategy, candles, "BTC/USDT")
        assert excinfo.value.reason == "per_bar_timeout"
        # First analyze call is candle index 1 with warmup_candles=2.
        assert excinfo.value.candle_index == 1
        assert strategy.calls == 1

    @pytest.mark.asyncio
    async def test_intermittent_failures_do_not_trip(self, tmp_path: Path) -> None:
        """4 failures then a success must reset the consecutive counter.

        The cumulative-rate breaker has a 50-failure floor, so this
        small intermittent sample still completes normally.
        """
        from src.ai.exceptions import ClaudeParseError

        class FlakyThenStable(BaseStrategy):
            def __init__(self) -> None:
                super().__init__(
                    info=TechniqueInfo(
                        name="flaky_then_stable",
                        version="1.0.0",
                        description="fails 4 then succeeds neutral",
                        technique_type="prompt",
                    )
                )
                self.calls = 0

            async def analyze(
                self,
                ohlcv: list[OHLCV],
                symbol: str,
                timeframe: str = "1h",
            ) -> AnalysisResult:
                self.calls += 1
                if self.calls <= 4:
                    raise ClaudeParseError("transient")
                # Stay neutral so no trades open and we exercise the
                # full candle range.
                return neutral_analysis()

        bt = Backtester(
            config=BacktestConfig(
                warmup_candles=2,
                fee_rate=Decimal("0"),
                slippage_bps=0,
                # 4 failures < 5; counter resets on the 5th call.
                max_parse_failures=5,
                per_bar_timeout=60.0,
            ),
            data_dir=tmp_path / "backtest",
        )
        strategy = FlakyThenStable()
        candles = make_flat_candles(20)

        # Must complete normally, no exception raised.
        result = await bt.run(strategy, candles, "BTC/USDT")
        assert isinstance(result, BacktestResult)
        assert result.total_trades == 0  # neutral signals only
        # 4 errors then 19 - 4 = 15 successful neutral calls = 19 calls
        # over the 19 post-warmup bars (indices 1..19 inclusive).
        assert strategy.calls == 19

    @pytest.mark.asyncio
    async def test_cumulative_parse_failure_rate_trips_breaker(
        self, tmp_path: Path
    ) -> None:
        """Alternating failure/success avoids the consecutive breaker
        but must abort once cumulative failures exceed the rate floor."""
        from src.ai.exceptions import ClaudeParseError
        from src.backtest.engine import BacktestAbortedError

        class AlternatingParseError(BaseStrategy):
            def __init__(self) -> None:
                super().__init__(
                    info=TechniqueInfo(
                        name="alternating_parse_error",
                        version="1.0.0",
                        description="fails every other bar",
                        technique_type="prompt",
                    )
                )
                self.calls = 0

            async def analyze(
                self,
                ohlcv: list[OHLCV],
                symbol: str,
                timeframe: str = "1h",
            ) -> AnalysisResult:
                self.calls += 1
                if self.calls % 2 == 1:
                    raise ClaudeParseError("intermittent parse failure")
                return neutral_analysis()

        bt = Backtester(
            config=BacktestConfig(
                warmup_candles=2,
                fee_rate=Decimal("0"),
                slippage_bps=0,
                max_parse_failures=1000,
                min_cumulative_parse_failures=50,
                max_cumulative_parse_failure_rate=0.5,
                per_bar_timeout=60.0,
            ),
            data_dir=tmp_path / "backtest",
        )
        strategy = AlternatingParseError()
        candles = make_flat_candles(130)

        with pytest.raises(BacktestAbortedError) as excinfo:
            await bt.run(strategy, candles, "BTC/USDT")

        assert excinfo.value.reason == "cumulative_parse_failure_rate"
        assert excinfo.value.candle_index == 101
        assert strategy.calls == 101


# =============================================================================
# DEBT-024 / Phase 20.1: PnL convention alignment
# =============================================================================


class TestPnLConventionAlignment:
    """Backtester and PaperTrader must compute identical realised PnL.

    Pre-Phase-20.1 the backtester multiplied PnL by ``leverage`` a
    second time at close, while PaperTrader's in-memory P&L
    calculation did not — so for a levered trade the two engines'
    P&L computations diverged by a factor of ``leverage``. These
    tests pin the post-fix invariant: with the same (entry, exit,
    qty, side, leverage) inputs and zero fees / slippage, the
    backtester ``BacktestTrade.pnl``, the canonical helper
    ``pnl_for_trade``, and the persisted ``TradeHistory.pnl`` (via
    ``TradeHistoryTracker.close_trade``) all agree exactly.
    Leverage is set to 10 so any accidental re-introduction of the
    second multiplication is loud (10x divergence).

    Phase 20.1 extension: the persistence-layer site
    (``TradeHistory.calculate_pnl`` in
    ``src/strategy/performance.py``) was the third instance of
    DEBT-024 and is now also fixed. The third test below pins the
    backtester ↔ persisted-paper-trader equality by direct numeric
    comparison (no spy / mock.patch), which would have failed before
    the fix.
    """

    @pytest.mark.asyncio
    async def test_backtester_and_paper_trader_match_long(self, tmp_path: Path) -> None:
        from datetime import datetime as _dt

        from src.backtest.engine import _OpenTrade
        from src.models import Position
        from src.utils.trading_math import pnl_for_trade

        entry = Decimal("100")
        exit_price = Decimal("110")
        qty = Decimal("2")
        leverage = 10  # loud multiplier — any double-apply == 10x diff

        # Backtester side: drive _close_trade directly with a
        # synthetic _OpenTrade so the test does not depend on the
        # walk-forward loop. Zero fees / zero slippage so the gross
        # price-move PnL == BacktestTrade.pnl == balance_delta.
        bt = make_backtester(
            tmp_path,
            slippage_bps=0,
            fee_rate=Decimal("0"),
            leverage=leverage,
        )
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=entry,
            quantity=qty,
            leverage=leverage,
            stop_loss=Decimal("90"),
            take_profit=Decimal("120"),
        )
        open_trade = _OpenTrade(
            position=position,
            entry_time=_dt(2026, 1, 1, 0, 0, 0),
            actual_entry_price=entry,
            entry_fee=Decimal("0"),
        )
        bt_trade, bt_balance_delta = bt._close_trade(
            open_trade=open_trade,
            exit_time=_dt(2026, 1, 1, 1, 0, 0),
            target_exit_price=exit_price,
            reason="take_profit",
            skip_slippage=True,
        )

        # Canonical helper output (paper.py now computes its
        # in-memory ``pnl`` via this same call). Expected:
        # (110 - 100) * 2 = 20. Pre-fix the backtester would have
        # produced 20 * 10 = 200.
        helper_pnl = pnl_for_trade(
            entry=entry,
            exit=exit_price,
            qty=qty,
            side="long",
        )
        expected = Decimal("20")
        assert helper_pnl == expected
        assert bt_trade.pnl == expected, (
            f"Backtester PnL {bt_trade.pnl} != expected {expected}; "
            "leverage may be double-applied (DEBT-024)."
        )
        assert bt_balance_delta == expected
        assert bt_trade.pnl == helper_pnl, (
            "Backtester and canonical helper disagree; "
            "convention has drifted (DEBT-024)."
        )

    @pytest.mark.asyncio
    async def test_backtester_and_paper_trader_match_short(
        self, tmp_path: Path
    ) -> None:
        from datetime import datetime as _dt

        from src.backtest.engine import _OpenTrade
        from src.models import Position
        from src.utils.trading_math import pnl_for_trade

        entry = Decimal("100")
        exit_price = Decimal("90")
        qty = Decimal("2")
        leverage = 10

        bt = make_backtester(
            tmp_path,
            slippage_bps=0,
            fee_rate=Decimal("0"),
            leverage=leverage,
        )
        position = Position(
            symbol="BTC/USDT",
            side="short",
            entry_price=entry,
            quantity=qty,
            leverage=leverage,
            stop_loss=Decimal("110"),
            take_profit=Decimal("80"),
        )
        open_trade = _OpenTrade(
            position=position,
            entry_time=_dt(2026, 1, 1, 0, 0, 0),
            actual_entry_price=entry,
            entry_fee=Decimal("0"),
        )
        bt_trade, _ = bt._close_trade(
            open_trade=open_trade,
            exit_time=_dt(2026, 1, 1, 1, 0, 0),
            target_exit_price=exit_price,
            reason="take_profit",
            skip_slippage=True,
        )

        helper_pnl = pnl_for_trade(
            entry=entry,
            exit=exit_price,
            qty=qty,
            side="short",
        )
        # Expected gross PnL: (100 - 90) * 2 = 20.
        expected = Decimal("20")
        assert helper_pnl == expected
        assert bt_trade.pnl == expected
        assert bt_trade.pnl == helper_pnl

    @pytest.mark.asyncio
    async def test_backtester_and_persisted_paper_trade_match_long(
        self, tmp_path: Path
    ) -> None:
        """Backtester and persisted-paper-trader PnL agree numerically.

        Opens identical (entry, exit, qty, leverage=10) positions in
        the backtester and the paper trader, closes both at the same
        exit price with zero fees, and asserts that the backtester's
        ``BacktestTrade.pnl`` equals the persisted
        ``TradeHistory.pnl`` from ``TradeHistoryTracker.close_trade``.

        Pre-Phase-20.1 (extended) this would have failed by a factor
        of 10: the persistence layer multiplied PnL by ``leverage``
        again inside ``TradeHistory.calculate_pnl``. The leverage=10
        choice means any regression blows up loudly (10× divergence).
        """
        from datetime import datetime as _dt

        from src.backtest.engine import _OpenTrade
        from src.models import Position
        from src.trading.paper import ZERO_FEE_CONFIG, FeeConfig, PaperTrader
        from src.utils.trading_math import pnl_for_trade

        entry = Decimal("100")
        exit_price = Decimal("110")
        qty = Decimal("2")
        leverage = 10

        # Backtester side
        bt = make_backtester(
            tmp_path / "bt",
            slippage_bps=0,
            fee_rate=Decimal("0"),
            leverage=leverage,
        )
        bt_position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=entry,
            quantity=qty,
            leverage=leverage,
            stop_loss=Decimal("90"),
            take_profit=Decimal("120"),
        )
        open_trade = _OpenTrade(
            position=bt_position,
            entry_time=_dt(2026, 1, 1, 0, 0, 0),
            actual_entry_price=entry,
            entry_fee=Decimal("0"),
        )
        bt_trade, _ = bt._close_trade(
            open_trade=open_trade,
            exit_time=_dt(2026, 1, 1, 1, 0, 0),
            target_exit_price=exit_price,
            reason="take_profit",
            skip_slippage=True,
        )

        # Paper trader side — exercise the full persistence path so
        # we are comparing what actually gets written to disk via
        # TradeHistoryTracker.close_trade, not just an in-memory
        # value.
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path / "paper",
            fee_config=ZERO_FEE_CONFIG,
        )
        paper_position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=entry,
            quantity=qty,
            leverage=leverage,
            stop_loss=Decimal("90"),
            take_profit=Decimal("120"),
        )
        opened = await trader.open_position(paper_position)
        persisted = await trader.close_position(opened.id, exit_price)
        assert persisted is not None

        # Canonical: (110 - 100) * 2 = 20. Pre-fix the backtester
        # would have produced 200 (10× double-apply); pre-extension
        # the persisted record would also have produced 200.
        helper_pnl = pnl_for_trade(
            entry=entry,
            exit=exit_price,
            qty=qty,
            side="long",
        )
        expected = Decimal("20")
        assert helper_pnl == expected
        assert bt_trade.pnl == expected
        assert persisted.pnl == expected, (
            f"Persisted paper PnL {persisted.pnl} != expected "
            f"{expected}; persistence layer may be double-applying "
            "leverage (DEBT-024 / Phase 20.1 extension)."
        )
        assert bt_trade.pnl == persisted.pnl, (
            "Backtester and persisted paper-trade PnL disagree; "
            "convention has drifted (DEBT-024)."
        )

        # Confirm we did not introduce a stray FeeConfig dependency.
        assert isinstance(trader.fee_config, FeeConfig)

    @pytest.mark.asyncio
    async def test_backtester_and_persisted_paper_trade_match_short(
        self, tmp_path: Path
    ) -> None:
        """Short-side counterpart of the persisted-equality test."""
        from datetime import datetime as _dt

        from src.backtest.engine import _OpenTrade
        from src.models import Position
        from src.trading.paper import ZERO_FEE_CONFIG, PaperTrader
        from src.utils.trading_math import pnl_for_trade

        entry = Decimal("100")
        exit_price = Decimal("90")
        qty = Decimal("2")
        leverage = 10

        bt = make_backtester(
            tmp_path / "bt",
            slippage_bps=0,
            fee_rate=Decimal("0"),
            leverage=leverage,
        )
        bt_position = Position(
            symbol="BTC/USDT",
            side="short",
            entry_price=entry,
            quantity=qty,
            leverage=leverage,
            stop_loss=Decimal("110"),
            take_profit=Decimal("80"),
        )
        open_trade = _OpenTrade(
            position=bt_position,
            entry_time=_dt(2026, 1, 1, 0, 0, 0),
            actual_entry_price=entry,
            entry_fee=Decimal("0"),
        )
        bt_trade, _ = bt._close_trade(
            open_trade=open_trade,
            exit_time=_dt(2026, 1, 1, 1, 0, 0),
            target_exit_price=exit_price,
            reason="take_profit",
            skip_slippage=True,
        )

        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path / "paper",
            fee_config=ZERO_FEE_CONFIG,
        )
        paper_position = Position(
            symbol="BTC/USDT",
            side="short",
            entry_price=entry,
            quantity=qty,
            leverage=leverage,
            stop_loss=Decimal("110"),
            take_profit=Decimal("80"),
        )
        opened = await trader.open_position(paper_position)
        persisted = await trader.close_position(opened.id, exit_price)
        assert persisted is not None

        helper_pnl = pnl_for_trade(
            entry=entry,
            exit=exit_price,
            qty=qty,
            side="short",
        )
        expected = Decimal("20")  # (100 - 90) * 2
        assert helper_pnl == expected
        assert bt_trade.pnl == expected
        assert persisted.pnl == expected
        assert bt_trade.pnl == persisted.pnl


# =============================================================================
# Phase 26.4 / DEBT-047: backtester liquidation parity
# =============================================================================


class TestBacktesterLiquidationParity:
    """The backtester must mirror PaperTrader's Phase 22.2 liquidation
    visibility: an under-water close emits a structural marker on the
    affected ``BacktestTrade`` and rolls up to ``BacktestResult.
    liquidated``. PnL math is unchanged — the marker is purely
    observational so operators can distinguish "would have been
    liquidated" from "deep drawdown but recovered".
    """

    @pytest.mark.asyncio
    async def test_liquidating_trade_marks_trade_and_result(
        self, tmp_path: Path
    ) -> None:
        """A risk-sized SL hit on a max-risk position with adversarial
        slippage + fees pushes the balance below zero. Fires
        ``liquidated=True`` on the trade and on the result summary.

        Sizing geometry (DEBT-024 / Phase 20.1 helper formula):
            risk_amt = 100 * 1.0 = 100
            risk_per_unit = |50000 - 45000| = 5000
            qty = 100 / 5000 = 0.02
        Entry at the candle close 50000 + 20 bps long slippage = 50100,
        entry_fee 50100 * 0.02 * 0.001 = 1.002 → balance ≈ 98.998 with
        the trade open. SL hit at 45000 with 20 bps long-exit slippage
        = 44910, raw_pnl = (44910 - 50100) * 0.02 = -103.8, exit_fee
        ≈ 0.898 → balance ≈ -5.7. The risk-sized cap (-100) is
        breached purely by the friction terms — exactly the asymmetry
        with PaperTrader's Phase 22.2 LIQUIDATED branch we're closing.
        """
        bt = Backtester(
            config=BacktestConfig(
                initial_balance=Decimal("100"),
                fee_rate=Decimal("0.001"),
                slippage_bps=20,
                warmup_candles=2,
                leverage=10,
                risk_percent=100.0,
                max_position_size_percent=100.0,
                min_risk_reward_ratio=1.0,
            ),
            data_dir=tmp_path / "backtest",
        )
        candles = make_flat_candles(5)
        # SL-breaking candle at index 3.
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("44000"),  # crosses SL 45000
            close=Decimal("44500"),
        )
        strategy = ControllableStrategy(
            signals={2: long_analysis(entry="50000", stop="45000", take="60000")}
        )
        result = await bt.run(strategy, candles, "BTC/USDT")

        assert result.total_trades == 1
        trade = result.trades[0]
        assert trade.close_reason == "stop_loss"
        # Balance after the close is < 0 (literal liquidation, default
        # threshold = Decimal("0")).
        assert result.final_balance < Decimal("0")
        assert trade.liquidated is True
        assert result.liquidated is True
        # PnL math unchanged: the trade still records the full loss.
        assert trade.pnl < 0
        # Equity curve is truncated at the liquidating trade's exit so
        # downstream MDD / Sharpe don't compute against post-
        # liquidation phantom bars.
        assert result.equity_curve  # not empty
        assert result.equity_curve[-1].timestamp == trade.exit_time

    @pytest.mark.asyncio
    async def test_solvent_run_leaves_no_marker(self, tmp_path: Path) -> None:
        """A profitable / mild-loss run never crosses the threshold,
        so no trade nor the result is marked. Regression guard against
        the marker firing on the no-leverage / shallow-drawdown path."""
        bt = make_backtester(
            tmp_path,
            initial_balance=Decimal("10000"),
            leverage=1,
            risk_percent=1.0,
        )
        candles = make_flat_candles(5)
        # Make the SL-bearing candle move favourably (TP hit).
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("51500"),
            low=Decimal("49900"),
            close=Decimal("51200"),
        )
        strategy = ControllableStrategy(signals={2: long_analysis()})
        result = await bt.run(strategy, candles, "BTC/USDT")

        assert result.total_trades == 1
        assert result.trades[0].pnl > 0
        assert result.trades[0].liquidated is False
        assert result.liquidated is False
        # Default behaviour preserved: equity curve length matches
        # candle count when no liquidation fires.
        assert len(result.equity_curve) == len(candles)

    @pytest.mark.asyncio
    async def test_positive_threshold_catches_earlier(self, tmp_path: Path) -> None:
        """A 10% maintenance-margin floor (1000 against 10000 initial)
        catches a drawdown that a literal-zero default would miss.
        Pins the configurability of ``liquidation_threshold``."""
        # Same geometry as the first test, but scaled up so the loss
        # lands the balance well above 0 yet below 1000.
        bt = Backtester(
            config=BacktestConfig(
                initial_balance=Decimal("10000"),
                fee_rate=Decimal("0"),
                slippage_bps=0,
                warmup_candles=2,
                leverage=10,
                risk_percent=95.0,
                max_position_size_percent=100.0,
                min_risk_reward_ratio=1.0,
                liquidation_threshold=Decimal("1000"),
            ),
            data_dir=tmp_path / "backtest",
        )
        # Sizing: risk_amt = 10000 * 0.95 = 9500. risk_per_unit = 5000.
        # qty = 9500 / 5000 = 1.9 → notional 95000, margin 9500 ≤ 10000.
        # SL hit at 45000 with no slippage / fees → raw_pnl = -9500 →
        # final_balance = 500. Between 0 and 1000, so the literal-zero
        # default would NOT fire but a 1000 maintenance-margin floor
        # does.
        candles = make_flat_candles(5)
        candles[3] = make_candle(
            timestamp=candles[3].timestamp,
            open_price=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("44000"),
            close=Decimal("44500"),
        )
        strategy = ControllableStrategy(
            signals={2: long_analysis(entry="50000", stop="45000", take="60000")}
        )
        result = await bt.run(strategy, candles, "BTC/USDT")

        assert result.total_trades == 1
        # Final balance is positive but under the 1000 threshold.
        assert Decimal("0") < result.final_balance <= Decimal("1000")
        # Threshold > 0 still fires the marker.
        assert result.trades[0].liquidated is True
        assert result.liquidated is True

    @pytest.mark.asyncio
    async def test_default_threshold_is_zero(self, tmp_path: Path) -> None:
        """Default ``BacktestConfig.liquidation_threshold`` is the
        literal-liquidation floor (``Decimal("0")``). Pins the
        decision-point default agreed with the lead."""
        config = BacktestConfig()
        assert config.liquidation_threshold == Decimal("0")
