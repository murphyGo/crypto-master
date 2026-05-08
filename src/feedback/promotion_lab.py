"""Strategy promotion scoring for generated candidates.

The feedback loop already enforces the hard gate: a generated candidate stops
at ``AWAITING_APPROVAL`` and only moves to active strategies when an operator
calls ``approve``. This module adds a side-effect-free scoring layer that helps
the operator decide whether the candidate should be promoted, rejected, or kept
under observation.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from src.backtest.analyzer import PerformanceAnalyzer, PerformanceMetrics
from src.backtest.engine import BacktestResult
from src.backtest.validator import GateStatus, RobustnessReport
from src.config import get_settings
from src.feedback.loop import CandidateRecord, LoopStatus
from src.utils.io import atomic_write_text
from src.utils.pydantic_mixins import UtcTimestampMixin
from src.utils.time import ensure_utc, now_utc

DEFAULT_PROMOTION_LAB_STATE_DIR = Path("data/feedback/promotion_lab")


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


class PromotionObservation(UtcTimestampMixin, BaseModel):
    """Persisted observation-period state for one candidate."""

    candidate_id: str
    technique_name: str
    decision: PromotionDecision
    score: int = Field(ge=0, le=100)
    evaluations_count: int = Field(default=1, ge=1)
    first_seen_at: datetime = Field(default_factory=now_utc)
    last_evaluated_at: datetime = Field(default_factory=now_utc)
    factors: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)


class PromotionObservationStore:
    """Atomic JSON snapshot store for promotion-lab observations."""

    def __init__(
        self,
        state_dir: Path | None = None,
        *,
        data_dir: Path | None = None,
    ) -> None:
        if state_dir is not None:
            self.state_dir = state_dir
        else:
            base = data_dir if data_dir is not None else get_settings().data_dir
            self.state_dir = base / "feedback" / "promotion_lab"

    def path_for(self, candidate_id: str) -> Path:
        """Return the snapshot path for a candidate observation."""
        return self.state_dir / f"{candidate_id}.json"

    def save(self, observation: PromotionObservation) -> None:
        """Persist an observation snapshot atomically."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.path_for(observation.candidate_id),
            observation.model_dump_json(indent=2),
        )

    def load(self, candidate_id: str) -> PromotionObservation:
        """Load a persisted observation by candidate ID."""
        path = self.path_for(candidate_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PromotionObservation(**payload)

    def list_observations(self) -> list[PromotionObservation]:
        """Return readable observations sorted by most recent evaluation."""
        if not self.state_dir.exists():
            return []
        observations: list[PromotionObservation] = []
        for path in sorted(self.state_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                observations.append(PromotionObservation(**payload))
            except (json.JSONDecodeError, ValueError):
                continue
        return sorted(
            observations,
            key=lambda observation: observation.last_evaluated_at,
            reverse=True,
        )

    def record_evaluation(
        self,
        evaluation: PromotionEvaluation,
        *,
        evaluated_at: datetime | None = None,
    ) -> PromotionObservation:
        """Upsert observation state from the latest promotion evaluation."""
        evaluated_at = ensure_utc(evaluated_at or now_utc())
        existing = self._load_if_exists(evaluation.candidate_id)
        observation = PromotionObservation(
            candidate_id=evaluation.candidate_id,
            technique_name=evaluation.technique_name,
            decision=evaluation.decision,
            score=evaluation.score,
            evaluations_count=(existing.evaluations_count + 1) if existing else 1,
            first_seen_at=existing.first_seen_at if existing else evaluated_at,
            last_evaluated_at=evaluated_at,
            factors=list(evaluation.factors),
            blocking_reasons=list(evaluation.blocking_reasons),
        )
        self.save(observation)
        return observation

    def _load_if_exists(self, candidate_id: str) -> PromotionObservation | None:
        path = self.path_for(candidate_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PromotionObservation(**payload)


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
