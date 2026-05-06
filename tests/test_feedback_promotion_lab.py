"""Tests for the strategy promotion lab scoring model."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.backtest.analyzer import PerformanceMetrics
from src.backtest.engine import BacktestResult
from src.backtest.validator import GateResult, GateStatus, RobustnessReport
from src.feedback.loop import CandidateRecord, LoopStatus
from src.feedback.promotion_lab import (
    PromotionDecision,
    PromotionObservationStore,
    PromotionPolicy,
    evaluate_promotion_candidate,
)


def make_record(status: LoopStatus = LoopStatus.AWAITING_APPROVAL) -> CandidateRecord:
    return CandidateRecord(
        candidate_id="cand-1",
        kind="new_idea",
        technique_name="lab_candidate",
        technique_version="0.1.0",
        source_path=Path("strategies/experimental/lab_candidate.py"),
        status=status,
    )


def make_backtest(*, liquidated: bool = False) -> BacktestResult:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return BacktestResult(
        run_id="run-1",
        technique_name="lab_candidate",
        technique_version="0.1.0",
        symbol="BTC/USDT",
        timeframe="1h",
        start_time=now,
        end_time=now,
        initial_balance=Decimal("10000"),
        final_balance=Decimal("11200"),
        total_trades=30,
        wins=18,
        losses=12,
        breakevens=0,
        total_pnl=Decimal("1200"),
        total_fees=Decimal("12"),
        win_rate=0.6,
        return_percent=12.0,
        liquidated=liquidated,
    )


def make_metrics(
    *,
    total_trades: int = 30,
    sharpe_ratio: float | None = 1.4,
    max_drawdown_percent: float = 8.0,
    return_percent: float = 12.0,
) -> PerformanceMetrics:
    return PerformanceMetrics(
        total_trades=total_trades,
        wins=18,
        losses=12,
        win_rate=0.6,
        return_percent=return_percent,
        sharpe_ratio=sharpe_ratio,
        max_drawdown_percent=max_drawdown_percent,
    )


def make_robustness(*, passed: bool = True) -> RobustnessReport:
    status = GateStatus.PASSED if passed else GateStatus.FAILED
    return RobustnessReport(
        overall_passed=passed,
        gates=[
            GateResult(
                name="oos",
                status=status,
                score=0.8 if passed else 0.2,
                threshold=0.7,
                reason="test gate",
            )
        ],
        summary="test robustness",
        baseline_sharpe=1.2,
        baseline_trades=30,
    )


def test_promotes_high_quality_awaiting_candidate() -> None:
    evaluation = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(),
        robustness=make_robustness(),
        metrics=make_metrics(),
    )

    assert evaluation.decision == PromotionDecision.PROMOTE
    assert evaluation.score == 100
    assert evaluation.blocking_reasons == []


def test_rejects_failed_robustness_even_with_good_metrics() -> None:
    evaluation = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(),
        robustness=make_robustness(passed=False),
        metrics=make_metrics(),
    )

    assert evaluation.decision == PromotionDecision.REJECT
    assert "robustness failed: oos" in evaluation.blocking_reasons


def test_keeps_watching_small_trade_sample() -> None:
    evaluation = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(),
        robustness=make_robustness(),
        metrics=make_metrics(total_trades=8),
    )

    assert evaluation.decision == PromotionDecision.KEEP_WATCHING
    assert evaluation.score == 80
    assert any("trade sample is small" in factor for factor in evaluation.factors)


def test_rejects_liquidated_backtest() -> None:
    evaluation = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(liquidated=True),
        robustness=make_robustness(),
        metrics=make_metrics(),
    )

    assert evaluation.decision == PromotionDecision.REJECT
    assert "backtest liquidated" in evaluation.blocking_reasons


def test_policy_can_make_watch_band_stricter() -> None:
    evaluation = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(),
        robustness=make_robustness(),
        metrics=make_metrics(sharpe_ratio=1.1),
        policy=PromotionPolicy(min_sharpe=1.5),
    )

    assert evaluation.decision == PromotionDecision.KEEP_WATCHING
    assert any("sharpe below floor" in factor for factor in evaluation.factors)


def test_observation_store_records_first_evaluation(tmp_path: Path) -> None:
    evaluation = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(),
        robustness=make_robustness(),
        metrics=make_metrics(total_trades=8),
    )
    store = PromotionObservationStore(state_dir=tmp_path / "promotion_lab")

    observation = store.record_evaluation(
        evaluation,
        evaluated_at=datetime(2026, 5, 7, 1, 0, tzinfo=timezone.utc),
    )
    loaded = store.load(evaluation.candidate_id)

    assert observation == loaded
    assert observation.candidate_id == "cand-1"
    assert observation.decision == PromotionDecision.KEEP_WATCHING
    assert observation.evaluations_count == 1
    assert observation.first_seen_at == datetime(2026, 5, 7, 1, 0, tzinfo=timezone.utc)


def test_observation_store_preserves_first_seen_on_update(tmp_path: Path) -> None:
    store = PromotionObservationStore(state_dir=tmp_path / "promotion_lab")
    first = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(),
        robustness=make_robustness(),
        metrics=make_metrics(total_trades=8),
    )
    second = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(),
        robustness=make_robustness(),
        metrics=make_metrics(),
    )

    store.record_evaluation(
        first,
        evaluated_at=datetime(2026, 5, 7, 1, 0, tzinfo=timezone.utc),
    )
    observation = store.record_evaluation(
        second,
        evaluated_at=datetime(2026, 5, 7, 2, 0, tzinfo=timezone.utc),
    )

    assert observation.decision == PromotionDecision.PROMOTE
    assert observation.evaluations_count == 2
    assert observation.first_seen_at == datetime(2026, 5, 7, 1, 0, tzinfo=timezone.utc)
    assert observation.last_evaluated_at == datetime(
        2026, 5, 7, 2, 0, tzinfo=timezone.utc
    )


def test_observation_store_lists_most_recent_first(tmp_path: Path) -> None:
    store = PromotionObservationStore(state_dir=tmp_path / "promotion_lab")
    first = evaluate_promotion_candidate(
        record=make_record(),
        backtest=make_backtest(),
        robustness=make_robustness(),
        metrics=make_metrics(total_trades=8),
    )
    second = first.model_copy(
        update={"candidate_id": "cand-2", "technique_name": "lab_candidate_2"}
    )

    store.record_evaluation(
        first,
        evaluated_at=datetime(2026, 5, 7, 1, 0, tzinfo=timezone.utc),
    )
    store.record_evaluation(
        second,
        evaluated_at=datetime(2026, 5, 7, 3, 0, tzinfo=timezone.utc),
    )

    assert [observation.candidate_id for observation in store.list_observations()] == [
        "cand-2",
        "cand-1",
    ]
