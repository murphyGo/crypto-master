"""Tests for shared backtest metric helpers."""

from decimal import Decimal

import pytest

from src.backtest.metrics import (
    count_trade_outcomes,
    max_drawdown_from_equity_values,
    return_percent,
    sharpe_from_returns,
    sharpe_from_trade_pnls,
)


def test_count_trade_outcomes_and_rates() -> None:
    counts = count_trade_outcomes(
        [Decimal("10"), Decimal("-2"), Decimal("0"), Decimal("3")]
    )

    assert counts.wins == 2
    assert counts.losses == 1
    assert counts.breakevens == 1
    assert counts.total == 4
    assert counts.win_rate == 0.5
    assert counts.loss_rate == 0.25


def test_count_trade_outcomes_empty_rates_are_zero() -> None:
    counts = count_trade_outcomes([])

    assert counts.total == 0
    assert counts.win_rate == 0.0
    assert counts.loss_rate == 0.0


def test_return_percent_handles_non_positive_initial() -> None:
    assert return_percent(Decimal("100"), Decimal("125")) == 25.0
    assert return_percent(Decimal("0"), Decimal("125")) == 0.0


def test_max_drawdown_from_equity_values_tracks_peak_to_trough() -> None:
    max_dd, max_dd_pct = max_drawdown_from_equity_values(
        [Decimal("110"), Decimal("105"), Decimal("120"), Decimal("90")],
        Decimal("100"),
    )

    assert max_dd == Decimal("30")
    assert max_dd_pct == 25.0


def test_sharpe_from_returns_matches_trade_pnl_normalization() -> None:
    returns = [0.01, 0.02, -0.01]
    direct = sharpe_from_returns(returns)
    from_pnl = sharpe_from_trade_pnls(
        [Decimal("100"), Decimal("200"), Decimal("-100")],
        Decimal("10000"),
    )

    assert direct is not None
    assert from_pnl == pytest.approx(direct)


def test_sharpe_returns_none_for_zero_variance() -> None:
    assert sharpe_from_returns([0.01, 0.01]) is None
    assert sharpe_from_trade_pnls([Decimal("1")], Decimal("100")) is None
