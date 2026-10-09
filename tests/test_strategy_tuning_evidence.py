"""Window selection and account-capital units for DEBT-085."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.dashboard.pages.strategies import (
    build_strategy_tuning_rows,
    load_tuning_capital,
    record_strategy_tuning_observations,
)
from src.strategy.performance import PerformanceRecord, TradeOutcome
from src.strategy.tuning import StrategyOverride, StrategyTuningPolicy, ThresholdSpec
from src.strategy.tuning_evidence import evidence_from_records
from src.strategy.tuning_observations import StrategyTuningObservationStore
from src.strategy.tuning_recommender import recommend_action


def trade(i=0, pnl=1.0, **updates):
    row = PerformanceRecord(
        id=str(i),
        technique_name="test",
        technique_version="1",
        symbol="BTC/USDT",
        timeframe="1h",
        signal="long",
        entry_price=Decimal("100"),
        stop_loss=Decimal("90"),
        take_profit=Decimal("120"),
        confidence=0.8,
        quantity=Decimal("10"),
        pnl_percent=pnl,
        outcome=TradeOutcome.BREAKEVEN,
        exit_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
    )
    return row.model_copy(update=updates)


def evidence(rows, **updates):
    args = {
        "window_closed_trades": 30,
        "initial_balance": Decimal("10000"),
        "fail_closed_rate": 0,
    }
    args.update(updates)
    return evidence_from_records(rows, **args)


def test_last_thirty_excludes_old_losses_open_and_synthetic():
    rows = [trade(i, -100) for i in range(10)] + [
        trade(i, 2 if i % 2 == 0 else -1) for i in range(10, 40)
    ]
    rows += [
        trade(99, -999, synthetic=True),
        trade(100, -999, outcome=TradeOutcome.PENDING),
    ]
    actual = evidence(list(reversed(rows)))
    assert actual.closed_trades == 30
    assert actual.closed_pnl_pct == pytest.approx(1.5)
    assert actual.profit_factor == pytest.approx(2)
    assert actual.win_rate == 0.5
    assert actual.economic_complete


def test_amount_weighted_pf_actual_entry_fees_and_peak_drawdown():
    # First +1000 net, then -500 net on unequal actual notionals.
    rows = [
        trade(
            0, 11, actual_entry_price=Decimal("1000"), fees=Decimal("100"), leverage=100
        ),
        trade(1, -50),
    ]
    actual = evidence(list(reversed(rows)))
    assert actual.closed_pnl_pct == 5
    assert actual.profit_factor == 2
    assert actual.max_drawdown_pct == pytest.approx(500 / 11000 * 100)
    assert evidence(rows, initial_balance=Decimal("20000")).closed_pnl_pct == 2.5


@pytest.mark.parametrize(
    "updates",
    [
        {"initial_balance": None},
        {"initial_balance": Decimal("0")},
        {"initial_balance": Decimal("NaN")},
    ],
)
def test_invalid_capital_disables_economic_advice_but_preserves_failure_pause(updates):
    actual = evidence([trade()], **updates)
    assert not actual.economic_complete
    assert recommend_action(actual, ThresholdSpec()) is None
    assert (
        recommend_action(
            evidence([trade()], fail_closed_rate=1, **updates), ThresholdSpec()
        )
        == "pause"
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"quantity": None},
        {"pnl_percent": None},
        {"exit_timestamp": None},
        {"symbol": "BTC/USDC"},
    ],
)
def test_unknown_window_evidence_is_not_silently_discarded(updates):
    actual = evidence([trade(0, -5, **updates), trade(1, 10)])
    assert not actual.economic_complete
    assert actual.coverage_note
    assert actual.profit_factor is None
    assert recommend_action(actual, ThresholdSpec()) is None


def test_unknown_amount_outside_selected_window_does_not_contaminate_window():
    actual = evidence([trade(0, quantity=None), trade(1, 1)], window_closed_trades=1)
    assert actual.economic_complete
    assert actual.closed_pnl_pct == 0.1


def test_account_loss_pause_boundary():
    rows = [trade(i, 0) for i in range(14)] + [trade(14, -50)]
    assert evidence(rows).closed_pnl_pct == -5
    assert recommend_action(evidence(rows), ThresholdSpec()) == "pause"
    assert (
        recommend_action(
            evidence(rows, initial_balance=Decimal("10001")), ThresholdSpec()
        )
        != "pause"
    )


def test_ui_and_observation_share_per_strategy_window_and_basis(tmp_path):
    tracker = MagicMock()
    tracker.sub_account_id = "lab"
    tracker.load_records.return_value = [trade(i, -50) for i in range(31)] + [
        trade(31, 2),
        trade(32, -1),
    ]
    strategy = SimpleNamespace(name="test", version="1")
    policy = StrategyTuningPolicy(
        strategy_overrides={
            "test": StrategyOverride(thresholds=ThresholdSpec(window_closed_trades=2))
        }
    )
    args = {"initial_balance": Decimal("20000")}
    rows = build_strategy_tuning_rows({"test": strategy}, policy, tracker, **args)
    assert "window=2" in rows[0].evidence_summary
    assert "closed=2" in rows[0].evidence_summary
    store = StrategyTuningObservationStore(state_dir=tmp_path)
    observed = record_strategy_tuning_observations(
        {"test": strategy}, policy, tracker, store, **args
    )[0]
    assert observed.evidence.capital_base == 20000
    assert observed.evidence.closed_pnl_pct == 0.05
    assert observed.evidence.window_closed_trades == 2
    persisted = store.list_observations()[0]
    assert persisted.evidence == observed.evidence
    tracker.get_performance.assert_not_called()


def test_config_resolves_only_matching_account_capital_without_trader(tmp_path):
    config = tmp_path / "accounts.yaml"
    config.write_text(
        "sub_accounts:\n  - id: lab\n    name: Lab\n    mode: paper\n    capital_policy:\n      initial_balance: {USDC: 23000}\n      quote_currency: USDC\n"
    )
    assert load_tuning_capital("lab", config) == (Decimal("23000"), "USDC")
    assert load_tuning_capital("missing", config) == (None, "USDT")
    config.write_text("bad: [")
    assert load_tuning_capital("lab", config) == (None, "USDT")


def test_legacy_observation_does_not_claim_validated_economic_basis():
    from src.strategy.tuning_observations import StrategyTuningEvidenceSnapshot

    old = StrategyTuningEvidenceSnapshot.model_validate(
        {
            "closed_trades": 30,
            "win_rate": 0.5,
            "profit_factor": 2,
            "closed_pnl_pct": 8,
            "max_drawdown_pct": 2,
            "fail_closed_rate": 0,
        }
    )
    assert not old.economic_complete
    assert "legacy" in old.coverage_note


def test_legacy_aggregate_cannot_drive_account_based_recommendation():
    from src.strategy.performance import TechniquePerformance
    from src.strategy.tuning_recommender import evidence_from_performance

    perf = TechniquePerformance(
        technique_name="test",
        technique_version="1",
        wins=30,
        losses=30,
        net_win_rate=0.5,
        net_win_pct=200,
        net_loss_pct=100,
        net_total_pnl_percent=100,
    )
    old = evidence_from_performance(perf, fail_closed_rate=0)
    assert not old.economic_complete
    assert recommend_action(old, ThresholdSpec()) is None
