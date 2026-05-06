"""Strategy promotion scoring for generated candidates.

The feedback loop already enforces the hard gate: a generated candidate stops
at ``AWAITING_APPROVAL`` and only moves to active strategies when an operator
calls ``approve``. This module adds a side-effect-free scoring layer that helps
the operator decide whether the candidate should be promoted, rejected, or kept
under observation.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.backtest.analyzer import PerformanceAnalyzer, PerformanceMetrics
from src.backtest.engine import BacktestResult
from src.backtest.validator import GateStatus, RobustnessReport
from src.feedback.loop import CandidateRecord, LoopStatus


class PromotionDecision(str, Enum):
    """Operator recommendation produced by the promotion lab."""

    PROMOTE = "promote"
    KEEP_WATCHING = "keep_watching"
    REJECT = "reject"


class PromotionPolicy(BaseModel):
    """Thresholds for the first-pass strategy promotion lab."""

    min_trades: int = Field(default=20, ge=1)
    min_sharpe: float = Field(default=1.0)
    max_drawdown_percent: float = Field(default=20.0, ge=0.0)
    min_return_percent: float = Field(default=0.0)
    promote_score: int = Field(default=90, ge=0, le=100)
    reject_score: int = Field(default=40, ge=0, le=100)


class PromotionEvaluation(BaseModel):
    """Scored promotion recommendation with human-readable factors."""

    candidate_id: str
    technique_name: str
    decision: PromotionDecision
    score: int = Field(ge=0, le=100)
    factors: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)


def evaluate_promotion_candidate(
    *,
    record: CandidateRecord,
    backtest: BacktestResult,
    robustness: RobustnessReport,
    metrics: PerformanceMetrics | None = None,
    policy: PromotionPolicy | None = None,
) -> PromotionEvaluation:
    """Score a candidate using existing feedback/backtest evidence."""
    policy = policy or PromotionPolicy()
    metrics = metrics or PerformanceAnalyzer().analyze(backtest)

    score = 100
    factors: list[str] = []
    blockers: list[str] = []

    if record.status != LoopStatus.AWAITING_APPROVAL.value:
        blockers.append(f"candidate status is {record.status}, not awaiting_approval")
        score -= 60
    else:
        factors.append("candidate is awaiting operator approval")

    if not robustness.overall_passed:
        failed = [
            gate.name
            for gate in robustness.gates
            if gate.status == GateStatus.FAILED.value
        ]
        blockers.append(f"robustness failed: {', '.join(failed) or 'unknown gate'}")
        score -= 45
    else:
        factors.append("robustness gates passed")

    if backtest.liquidated:
        blockers.append("backtest liquidated")
        score -= 45

    if metrics.total_trades < policy.min_trades:
        factors.append(
            f"trade sample is small: {metrics.total_trades}/{policy.min_trades}"
        )
        score -= 20
    else:
        factors.append(f"trade sample meets floor: {metrics.total_trades}")

    if metrics.sharpe_ratio is None:
        factors.append("sharpe is unavailable")
        score -= 15
    elif metrics.sharpe_ratio < policy.min_sharpe:
        factors.append(
            f"sharpe below floor: {metrics.sharpe_ratio:.2f} < {policy.min_sharpe:.2f}"
        )
        score -= 20
    else:
        factors.append(f"sharpe meets floor: {metrics.sharpe_ratio:.2f}")

    if metrics.max_drawdown_percent > policy.max_drawdown_percent:
        factors.append(
            "drawdown above ceiling: "
            f"{metrics.max_drawdown_percent:.2f}% > {policy.max_drawdown_percent:.2f}%"
        )
        score -= 20
    else:
        factors.append(f"drawdown within ceiling: {metrics.max_drawdown_percent:.2f}%")

    if metrics.return_percent <= policy.min_return_percent:
        factors.append(
            f"return below floor: {metrics.return_percent:.2f}% "
            f"<= {policy.min_return_percent:.2f}%"
        )
        score -= 20
    else:
        factors.append(f"return is positive: {metrics.return_percent:.2f}%")

    score = max(0, min(100, score))
    decision = _decision_for(score=score, blockers=blockers, policy=policy)
    return PromotionEvaluation(
        candidate_id=record.candidate_id,
        technique_name=record.technique_name,
        decision=decision,
        score=score,
        factors=factors,
        blocking_reasons=blockers,
    )


def _decision_for(
    *,
    score: int,
    blockers: list[str],
    policy: PromotionPolicy,
) -> PromotionDecision:
    if blockers or score < policy.reject_score:
        return PromotionDecision.REJECT
    if score >= policy.promote_score:
        return PromotionDecision.PROMOTE
    return PromotionDecision.KEEP_WATCHING
