"""Tests for strategy correlation governor input models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.backtest.engine import BacktestResult, BacktestTrade
from src.runtime.correlation_governor import (
    CorrelationExposureSource,
    CorrelationGateConfig,
    CorrelationInputSet,
    CorrelationWarningPolicy,
    CorrelationWarningType,
    compute_duplicate_exposure_warnings,
    evaluate_correlation_gate,
)
from src.strategy.performance import TradeHistory


def make_backtest_trade(
    trade_id: str = "bt-1",
    *,
    symbol: str = "BTC/USDT",
    sub_account_id: str = "alpha",
    technique_name: str = "breakout",
) -> BacktestTrade:
    opened = datetime(2026, 5, 7, tzinfo=timezone.utc)
    return BacktestTrade(
        trade_id=trade_id,
        symbol=symbol,
        side="long",
        entry_time=opened,
        exit_time=opened + timedelta(hours=1),
        entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        quantity=Decimal("0.2"),
        leverage=1,
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        entry_fee=Decimal("0.01"),
        exit_fee=Decimal("0.01"),
        pnl=Decimal("1.98"),
        close_reason="take_profit",
        sub_account_id=sub_account_id,
        technique_name=technique_name,
    )


def make_backtest_result(trades: list[BacktestTrade]) -> BacktestResult:
    opened = datetime(2026, 5, 7, tzinfo=timezone.utc)
    return BacktestResult(
        run_id="run-1",
        technique_name="fallback_strategy",
        technique_version="1.0.0",
        symbol="BTC/USDT",
        timeframe="1h",
        start_time=opened,
        end_time=opened + timedelta(hours=2),
        initial_balance=Decimal("10000"),
        final_balance=Decimal("10001.98"),
        total_trades=len(trades),
        wins=len(trades),
        losses=0,
        breakevens=0,
        total_pnl=sum((trade.pnl for trade in trades), Decimal("0")),
        total_fees=Decimal("0.02"),
        win_rate=1.0 if trades else 0.0,
        return_percent=0.0198,
        trades=trades,
    )


def make_runtime_trade(
    trade_id: str = "rt-1",
    *,
    symbol: str = "ETH/USDT",
    sub_account_id: str = "beta",
    performance_record_id: str | None = "perf-1",
) -> TradeHistory:
    opened = datetime(2026, 5, 7, tzinfo=timezone.utc)
    return TradeHistory(
        id=trade_id,
        performance_record_id=performance_record_id,
        sub_account_id=sub_account_id,
        symbol=symbol,
        side="short",
        mode="paper",
        entry_price=Decimal("200"),
        entry_quantity=Decimal("0.5"),
        entry_time=opened,
        exit_price=Decimal("180"),
        exit_quantity=Decimal("0.5"),
        exit_time=opened + timedelta(hours=1),
        leverage=2,
        fees=Decimal("0.02"),
        pnl=Decimal("9.98"),
        pnl_percent=10.0,
        status="closed",
        close_reason="take_profit",
    )


def test_correlation_inputs_from_backtest_results() -> None:
    trade = make_backtest_trade()
    inputs = CorrelationInputSet.from_backtest_results([make_backtest_result([trade])])

    exposure = inputs.exposures[0]
    assert exposure.source == CorrelationExposureSource.BACKTEST
    assert exposure.exposure_id == "bt-1"
    assert exposure.strategy_id == "breakout"
    assert exposure.sub_account_id == "alpha"
    assert exposure.symbol == "BTC/USDT"
    assert exposure.notional == Decimal("20.0")
    assert exposure.pnl == Decimal("1.98")


def test_correlation_inputs_from_runtime_trade_history() -> None:
    trade = make_runtime_trade()
    inputs = CorrelationInputSet.from_trade_history(
        [trade],
        strategy_lookup={"perf-1": "mean_reversion"},
    )

    exposure = inputs.exposures[0]
    assert exposure.source == CorrelationExposureSource.RUNTIME
    assert exposure.exposure_id == "rt-1"
    assert exposure.strategy_id == "mean_reversion"
    assert exposure.side == "short"
    assert exposure.notional == Decimal("100.0")
    assert exposure.closed_at is not None


def test_correlation_inputs_support_open_runtime_trades() -> None:
    trade = make_runtime_trade(performance_record_id=None)
    trade = trade.model_copy(update={"exit_time": None, "status": "open", "pnl": None})

    inputs = CorrelationInputSet.from_trade_history([trade])

    exposure = inputs.exposures[0]
    assert exposure.strategy_id == "unknown"
    assert exposure.closed_at is None
    assert exposure.pnl is None


def test_correlation_input_filters_by_sub_account_and_symbol() -> None:
    btc = make_backtest_trade("bt-1", symbol="BTC/USDT", sub_account_id="alpha")
    eth = make_backtest_trade("bt-2", symbol="ETH/USDT", sub_account_id="beta")
    inputs = CorrelationInputSet.from_backtest_results(
        [make_backtest_result([btc, eth])]
    )

    assert [e.exposure_id for e in inputs.for_sub_account("alpha")] == ["bt-1"]
    assert [e.exposure_id for e in inputs.for_symbol("ETH/USDT")] == ["bt-2"]


def test_correlation_input_allows_empty_exposure_set() -> None:
    inputs = CorrelationInputSet.from_backtest_results([make_backtest_result([])])

    assert inputs.exposures == []


def test_duplicate_exposure_warns_on_same_symbol_side_across_sub_accounts() -> None:
    alpha = make_backtest_trade("a", symbol="BTC/USDT", sub_account_id="alpha")
    beta = make_backtest_trade("b", symbol="BTC/USDT", sub_account_id="beta")
    inputs = CorrelationInputSet.from_backtest_results(
        [make_backtest_result([alpha, beta])]
    )

    warnings = compute_duplicate_exposure_warnings(inputs)

    symbol_warning = next(
        warning
        for warning in warnings
        if warning.warning_type == CorrelationWarningType.DUPLICATE_SYMBOL_SIDE
    )
    assert symbol_warning.symbol == "BTC/USDT"
    assert symbol_warning.side == "long"
    assert symbol_warning.sub_account_ids == ["alpha", "beta"]
    assert symbol_warning.exposure_ids == ["a", "b"]
    assert symbol_warning.total_notional == Decimal("40.0")


def test_duplicate_exposure_warns_on_same_strategy_symbol_side() -> None:
    alpha = make_backtest_trade(
        "a",
        symbol="ETH/USDT",
        sub_account_id="alpha",
        technique_name="breakout",
    )
    beta = make_backtest_trade(
        "b",
        symbol="ETH/USDT",
        sub_account_id="beta",
        technique_name="breakout",
    )
    inputs = CorrelationInputSet.from_backtest_results(
        [make_backtest_result([alpha, beta])]
    )

    warnings = compute_duplicate_exposure_warnings(inputs)

    strategy_warning = next(
        warning
        for warning in warnings
        if warning.warning_type == CorrelationWarningType.DUPLICATE_STRATEGY_SYMBOL_SIDE
    )
    assert strategy_warning.strategy_id == "breakout"
    assert strategy_warning.symbol == "ETH/USDT"
    assert "breakout repeats ETH/USDT long" in strategy_warning.message


def test_duplicate_exposure_policy_can_allow_multiple_sub_accounts() -> None:
    alpha = make_backtest_trade("a", symbol="BTC/USDT", sub_account_id="alpha")
    beta = make_backtest_trade("b", symbol="BTC/USDT", sub_account_id="beta")
    inputs = CorrelationInputSet.from_backtest_results(
        [make_backtest_result([alpha, beta])]
    )

    warnings = compute_duplicate_exposure_warnings(
        inputs,
        policy=CorrelationWarningPolicy(
            max_sub_accounts_per_symbol_side=2,
            max_sub_accounts_per_strategy_symbol_side=2,
        ),
    )

    assert warnings == []


def test_duplicate_exposure_ignores_repeated_same_sub_account() -> None:
    first = make_backtest_trade("a", symbol="BTC/USDT", sub_account_id="alpha")
    second = make_backtest_trade("b", symbol="BTC/USDT", sub_account_id="alpha")
    inputs = CorrelationInputSet.from_backtest_results(
        [make_backtest_result([first, second])]
    )

    assert compute_duplicate_exposure_warnings(inputs) == []


def test_correlation_input_open_only_filters_closed_exposures() -> None:
    open_trade = make_runtime_trade("open")
    open_trade = open_trade.model_copy(update={"exit_time": None, "status": "open"})
    closed_trade = make_runtime_trade("closed")
    inputs = CorrelationInputSet.from_trade_history([open_trade, closed_trade])

    open_inputs = inputs.open_only()

    assert [exposure.exposure_id for exposure in open_inputs.exposures] == ["open"]


def test_correlation_gate_allows_non_duplicate_candidate() -> None:
    existing = CorrelationInputSet()
    candidate = CorrelationInputSet.from_backtest_results(
        [
            make_backtest_result(
                [make_backtest_trade("b", symbol="ETH/USDT", sub_account_id="beta")]
            )
        ]
    ).exposures[0]

    decision = evaluate_correlation_gate(
        existing,
        candidate,
        config=CorrelationGateConfig(enabled=True),
    )

    assert decision.allowed is True
    assert decision.warnings == []
    assert decision.reason == "no correlated duplicate exposure detected"


def test_correlation_gate_disabled_allows_with_advisory_warnings() -> None:
    existing = CorrelationInputSet.from_backtest_results(
        [make_backtest_result([make_backtest_trade("a", symbol="BTC/USDT")])]
    )
    candidate = CorrelationInputSet.from_backtest_results(
        [
            make_backtest_result(
                [make_backtest_trade("b", symbol="BTC/USDT", sub_account_id="beta")]
            )
        ]
    ).exposures[0]

    decision = evaluate_correlation_gate(existing, candidate)

    assert decision.allowed is True
    assert decision.reason == "correlation gate disabled; advisory warnings only"
    assert len(decision.warnings) == 2


def test_correlation_gate_enabled_rejects_duplicate_candidate() -> None:
    existing = CorrelationInputSet.from_backtest_results(
        [make_backtest_result([make_backtest_trade("a", symbol="BTC/USDT")])]
    )
    candidate = CorrelationInputSet.from_backtest_results(
        [
            make_backtest_result(
                [make_backtest_trade("b", symbol="BTC/USDT", sub_account_id="beta")]
            )
        ]
    ).exposures[0]

    decision = evaluate_correlation_gate(
        existing,
        candidate,
        config=CorrelationGateConfig(enabled=True),
    )

    assert decision.allowed is False
    assert decision.reason == "correlation gate rejected excessive duplicate exposure"
    assert {warning.warning_type for warning in decision.warnings} == {
        CorrelationWarningType.DUPLICATE_SYMBOL_SIDE,
        CorrelationWarningType.DUPLICATE_STRATEGY_SYMBOL_SIDE,
    }


def test_correlation_gate_respects_relaxed_warning_policy() -> None:
    existing = CorrelationInputSet.from_backtest_results(
        [make_backtest_result([make_backtest_trade("a", symbol="BTC/USDT")])]
    )
    candidate = CorrelationInputSet.from_backtest_results(
        [
            make_backtest_result(
                [make_backtest_trade("b", symbol="BTC/USDT", sub_account_id="beta")]
            )
        ]
    ).exposures[0]

    decision = evaluate_correlation_gate(
        existing,
        candidate,
        config=CorrelationGateConfig(
            enabled=True,
            warning_policy=CorrelationWarningPolicy(
                max_sub_accounts_per_symbol_side=2,
                max_sub_accounts_per_strategy_symbol_side=2,
            ),
        ),
    )

    assert decision.allowed is True
    assert decision.warnings == []
