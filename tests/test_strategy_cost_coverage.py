"""Cost coverage stays honest across persisted trades, reports and observations."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.dashboard.pages.strategies import (
    build_strategy_tuning_rows,
    record_strategy_tuning_observations,
)
from src.strategy.cost_coverage import adverse_carry_sensitivity
from src.strategy.performance import PerformanceRecord, PerformanceTracker
from src.strategy.trade_history import TradeHistory
from src.strategy.tuning import StrategyTuningPolicy
from src.strategy.tuning_evidence import evidence_from_records
from src.strategy.tuning_observations import StrategyTuningObservationStore
from src.tools.report_strategy_costs import main, report_strategy_costs


def paired_trade(side="long", **trade_updates):
    entry = datetime(2026, 10, 1, tzinfo=timezone.utc)
    trade = TradeHistory(
        id="trade-1",
        sub_account_id="lab",
        symbol="BTC/USDT",
        side=side,
        mode="paper",
        entry_price=Decimal("100"),
        entry_quantity=Decimal("10"),
        entry_time=entry,
        exit_price=Decimal("110") if side == "long" else Decimal("90"),
        exit_time=entry + timedelta(hours=12),
        status="closed",
        fees=Decimal("2"),
        pnl=Decimal("98"),
        pnl_percent=10,
        leverage=5,
    ).model_copy(update=trade_updates)
    record = PerformanceRecord(
        id="record-1",
        trade_id=trade.id,
        sub_account_id="lab",
        technique_name="test",
        technique_version="1",
        symbol=trade.symbol,
        timeframe="1h",
        signal=side,
        mode="paper",
        # Proposal price/time differ deliberately: scenario must use the fill.
        entry_price=Decimal("80"),
        actual_entry_price=trade.entry_price,
        quantity=trade.entry_quantity,
        analysis_timestamp=entry - timedelta(hours=3),
        stop_loss=Decimal("90"),
        take_profit=Decimal("120"),
        confidence=0.8,
        outcome="win",
        exit_timestamp=trade.exit_time,
        pnl_percent=10,
        fees=trade.fees,
    )
    return trade, record


def scenario(records, trades, **kwargs):
    return adverse_carry_sensitivity(
        records,
        {t.id: t for t in trades},
        rate_per_interval=kwargs.get("rate", Decimal("0.0001")),
        interval_hours=kwargs.get("interval", Decimal("8")),
        quote_currency="USDT",
    )


@pytest.mark.parametrize("side", ["long", "short"])
def test_adverse_scenario_uses_executed_hold_notional_once(side):
    trade, record = paired_trade(side)
    before = trade.model_dump_json(), record.model_dump_json()
    result = scenario([record], [trade])
    assert result.complete
    assert result.scenario_cost_subtotal == Decimal("0.15")
    assert result.fee_net_pnl_subtotal == 98
    assert result.scenario_pnl == Decimal("97.85")
    assert result.funding_coverage == "unknown"
    assert "not actual funding" in result.scenario
    assert before == (trade.model_dump_json(), record.model_dump_json())


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"exit_time": None}, "missing_closed_trade_time"),
        (
            {"entry_time": datetime(2027, 1, 1, tzinfo=timezone.utc)},
            "exit_before_entry",
        ),
        ({"entry_quantity": Decimal("NaN")}, "unknown_trade_economics"),
        ({"entry_price": Decimal("Infinity")}, "unknown_trade_economics"),
        ({"pnl": None}, "unknown_trade_economics"),
        ({"sub_account_id": "other"}, "trade_identity_mismatch"),
        ({"mode": "live"}, "trade_identity_mismatch"),
    ],
)
def test_incomplete_inputs_do_not_become_complete_zero_cost(updates, reason):
    trade, record = paired_trade()
    result = scenario([record], [trade.model_copy(update=updates)])
    assert not result.complete
    assert result.scenario_pnl is None
    assert result.excluded_reasons == {reason: 1}


def test_missing_links_duplicate_links_and_wrong_currency_are_explicit():
    trade, record = paired_trade()
    assert scenario([record], []).excluded_reasons == {"missing_trade_link": 1}
    duplicate = record.model_copy(update={"id": "other-record"})
    result = scenario([record, duplicate], [trade])
    assert result.excluded_reasons == {"duplicate_trade_link": 2}
    assert result.included_trades == 0
    wrong_trade = trade.model_copy(update={"symbol": "BTC/USDC"})
    wrong_record = record.model_copy(update={"symbol": "BTC/USDC"})
    assert scenario([wrong_record], [wrong_trade]).excluded_reasons == {
        "quote_currency_mismatch": 1
    }
    other = record.model_copy(update={"id": "other", "sub_account_id": "other"})
    with pytest.raises(ValueError, match="one sub-account"):
        scenario([record, other], [trade])


def test_pending_synthetic_and_no_explicit_entry_time_never_fabricate_coverage():
    trade, record = paired_trade()
    rows = [
        record,
        record.model_copy(update={"synthetic": True}),
        record.model_copy(update={"outcome": "pending"}),
    ]
    result = scenario(rows, [trade])
    assert result.closed_real_records == result.included_trades == 1
    assert result.scenario_pnl == Decimal("97.85")
    raw = trade.model_dump(mode="json")
    del raw["entry_time"]
    legacy = TradeHistory.model_validate(raw)
    assert scenario([record], [legacy]).scenario_pnl is None
    assert not scenario([], []).complete


@pytest.mark.parametrize(
    ("rate", "interval"),
    [("NaN", "8"), ("Infinity", "8"), ("-0.01", "8"), ("0.01", "0"), ("0", "NaN")],
)
def test_invalid_scenario_assumptions_are_rejected(rate, interval):
    with pytest.raises(ValueError):
        scenario([], [], rate=Decimal(rate), interval=Decimal(interval))


def save_snapshot(tmp_path):
    trade, record = paired_trade()
    record_path = tmp_path / "performance/lab/test/records.json"
    trade_path = tmp_path / "trades/paper/lab/trades.json"
    for path, row in [(record_path, record), (trade_path, trade)]:
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps([row.model_dump(mode="json")]))
    return trade, record, (record_path, trade_path)


def test_fixed_snapshot_cli_reproduces_numbers_and_preserves_every_input(
    tmp_path, capsys
):
    _, _, paths = save_snapshot(tmp_path)
    before = {p: p.read_bytes() for p in paths}
    args = [
        "--snapshot",
        str(tmp_path),
        "--sub-account",
        "lab",
        "--strategy",
        "test",
        "--rate-per-interval",
        "0.0001",
        "--interval-hours",
        "8",
    ]
    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out) == first
    assert first["actual_funding_cost"] is None
    assert Decimal(first["scenario_pnl"]) == Decimal("97.85")
    assert first["scenario_complete"]
    for item in first["inputs"]:
        assert (
            item["sha256"]
            == hashlib.sha256(
                before[next(p for p in paths if str(p.resolve()) == item["path"])]
            ).hexdigest()
        )
    assert before == {p: p.read_bytes() for p in paths}


def test_report_rejects_duplicate_ledgers_and_malformed_snapshots(tmp_path):
    _, _, paths = save_snapshot(tmp_path)
    rows = json.loads(paths[1].read_text())
    paths[1].write_text(json.dumps(rows + rows))
    with pytest.raises(ValueError, match="duplicate"):
        report_strategy_costs(
            tmp_path,
            "lab",
            "test",
            rate_per_interval=Decimal(0),
            interval_hours=Decimal(8),
        )
    paths[0].write_text("{}")
    with pytest.raises(ValueError, match="array"):
        report_strategy_costs(
            tmp_path,
            "lab",
            "test",
            rate_per_interval=Decimal(0),
            interval_hours=Decimal(8),
        )


@pytest.mark.parametrize("flag", ["--rate-per-interval", "--interval-hours"])
def test_cli_invalid_decimal_is_a_usage_error(tmp_path, capsys, flag):
    args = [
        "--snapshot",
        str(tmp_path),
        "--sub-account",
        "lab",
        "--strategy",
        "test",
        "--rate-per-interval",
        "0.0001",
        "--interval-hours",
        "8",
    ]
    args[args.index(flag) + 1] = "nope"
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert "expected a decimal number" in capsys.readouterr().err


def test_persisted_history_to_ui_and_observation_retains_funding_unknown(tmp_path):
    _, record, _ = save_snapshot(tmp_path)
    tracker = PerformanceTracker(
        data_dir=tmp_path / "performance", sub_account_id="lab"
    )
    strategies = {"test": SimpleNamespace(name="test", version="1")}
    policy = StrategyTuningPolicy()
    rows = build_strategy_tuning_rows(
        strategies, policy, tracker, initial_balance=Decimal("10000")
    )
    assert "Fee-net; funding not measured" in rows[0].evidence_summary
    store = StrategyTuningObservationStore(state_dir=tmp_path / "observations")
    observation = record_strategy_tuning_observations(
        strategies, policy, tracker, store, initial_balance=Decimal("10000")
    )[0]
    loaded = store.load("lab", "test")
    assert loaded == observation
    assert loaded.evidence.economic_complete
    assert loaded.evidence.funding_coverage == "unknown"
    assert loaded.evidence.pnl_basis == "fee_net_excluding_funding"
    assert loaded.evidence.closed_pnl_pct == pytest.approx(0.98)
    raw = json.loads(store.path_for("lab", "test").read_text())
    raw["evidence"].pop("pnl_basis")
    raw["evidence"].pop("funding_coverage")
    store.path_for("lab", "test").write_text(json.dumps(raw))
    legacy = store.load("lab", "test")
    assert legacy.evidence.pnl_basis == "legacy_unspecified"
    assert legacy.evidence.funding_coverage == "unknown"
    assert evidence_from_records(
        [record],
        window_closed_trades=30,
        initial_balance=Decimal("10000"),
        fail_closed_rate=0,
    ).closed_pnl_pct == pytest.approx(0.98)
