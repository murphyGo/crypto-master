"""Economic outcomes must not inherit the runtime's exit-reason labels."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.dashboard.pages.strategies import build_summary_dataframe
from src.strategy.performance import (
    PerformanceRecord,
    TechniquePerformance,
    TradeOutcome,
    net_return_for_record,
)
from src.strategy.tuning import StrategyAction, ThresholdSpec
from src.strategy.tuning_evidence import evidence_from_records
from src.strategy.tuning_recommender import evidence_from_performance, recommend_action


def record(pnl: float | None, **overrides: object) -> PerformanceRecord:
    values = {
        "technique_name": "test",
        "technique_version": "1",
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "signal": "long",
        "entry_price": Decimal("100"),
        "stop_loss": Decimal("90"),
        "take_profit": Decimal("120"),
        "confidence": 0.8,
        "quantity": Decimal("10"),
        "pnl_percent": pnl,
        "outcome": TradeOutcome.BREAKEVEN,
        "exit_timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return PerformanceRecord.model_validate(values)


def test_time_stop_signs_and_fee_flipped_tp_keep_exit_labels() -> None:
    rows = [
        record(2),
        record(-1),
        record(0),
        record(0.1, fees=Decimal("2"), outcome=TradeOutcome.WIN),
        record(99, synthetic=True),
        record(99, outcome=TradeOutcome.PENDING),
    ]
    perf = TechniquePerformance.from_records("test", "1", rows)
    assert (perf.net_wins, perf.net_losses, perf.net_breakevens) == (1, 2, 1)
    assert perf.net_win_rate == 0.25
    assert perf.net_unknown == 0
    assert (perf.wins, perf.losses, perf.breakevens, perf.pending) == (1, 0, 3, 1)
    assert perf.synthetic_count == 1


@pytest.mark.parametrize(
    "pnl, overrides, expected",
    [
        (
            0.5,
            {"actual_entry_price": Decimal("200"), "fees": Decimal("10")},
            Decimal("0"),
        ),
        (1.0, {"quantity": None}, Decimal("1")),
        (1.0, {"quantity": None, "fees": Decimal("1")}, None),
        (None, {}, None),
        (float("nan"), {}, None),
        (1.0, {"quantity": Decimal("0"), "fees": Decimal("1")}, None),
    ],
)
def test_actual_entry_and_legacy_unknowns(pnl, overrides, expected) -> None:
    assert net_return_for_record(record(pnl, **overrides)) == expected


def test_unknowns_are_visible_and_excluded_from_rate_denominator() -> None:
    perf = TechniquePerformance.from_records("test", "1", [record(1), record(None)])
    assert perf.net_win_rate == 1.0
    assert perf.net_unknown == 1
    unknown = TechniquePerformance.from_records("test", "1", [record(None)])
    assert unknown.net_win_rate is None
    legacy = TechniquePerformance.model_validate(
        {"technique_name": "test", "technique_version": "1", "win_rate": 1}
    )
    assert legacy.net_win_rate is None
    assert evidence_from_performance(legacy, fail_closed_rate=0).win_rate == 0


def test_time_stop_economic_win_rate_clears_keep_threshold() -> None:
    perf = TechniquePerformance.from_records(
        "test", "1", [record(2)] * 10 + [record(-1)] * 10
    )
    assert perf.win_rate == 0
    evidence = evidence_from_records(
        [record(2)] * 10 + [record(-1)] * 10,
        window_closed_trades=30,
        initial_balance=Decimal("10000"),
        fail_closed_rate=0,
    )
    assert evidence.win_rate == 0.5
    assert recommend_action(evidence, ThresholdSpec()) == StrategyAction.KEEP


def test_summary_separates_economic_and_exit_label_statistics() -> None:
    perf = TechniquePerformance.from_records(
        "test", "1", [record(2), record(-1), record(None)]
    )
    tracker = MagicMock()
    tracker.get_performance.return_value = perf
    info = SimpleNamespace(name="test", version="1", technique_type="code", symbols=[])
    strategy = SimpleNamespace(name="test", version="1", info=info)
    row = build_summary_dataframe({"test": strategy}, tracker).iloc[0]
    assert row["Win Rate %"] == 50
    assert row["Wins"] == 1
    assert row["Losses"] == 1
    assert row["Net Unknown"] == 1
    assert row["Exit-label Win Rate %"] == 0
