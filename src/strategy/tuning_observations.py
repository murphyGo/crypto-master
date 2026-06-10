"""Persisted recommendation observations for strategy-tuning.

The live recommender is pure and cheap to call, but operators need a durable
trail of what it recommended for each ``(sub-account, strategy)`` pair over
time. This module stores the latest applied/recommended state plus a bounded
history of recent evidence snapshots, following the same atomic JSON snapshot
pattern as ``PromotionObservationStore``.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel, Field

from src.config import get_settings
from src.strategy.tuning import StrategyAction
from src.strategy.tuning_recommender import RecommenderEvidence
from src.utils.io import atomic_write_text
from src.utils.pydantic_mixins import UtcTimestampMixin
from src.utils.time import ensure_utc, now_utc

DEFAULT_STRATEGY_TUNING_OBSERVATION_DIR = Path("data/strategy_tuning/observations")
DEFAULT_HISTORY_LIMIT = 20


class StrategyTuningEvidenceSnapshot(BaseModel):
    """Scalar evidence snapshot persisted with a recommendation."""

    closed_trades: int = Field(ge=0)
    win_rate: float = Field(ge=0.0, le=1.0)
    profit_factor: float | None = None
    closed_pnl_pct: float
    max_drawdown_pct: float
    fail_closed_rate: float = Field(ge=0.0, le=1.0)

    @classmethod
    def from_recommender_evidence(
        cls, evidence: RecommenderEvidence
    ) -> StrategyTuningEvidenceSnapshot:
        """Build a persisted snapshot from live recommender evidence."""
        return cls(
            closed_trades=evidence.closed_trades,
            win_rate=evidence.win_rate,
            profit_factor=evidence.profit_factor,
            closed_pnl_pct=evidence.closed_pnl_pct,
            max_drawdown_pct=evidence.max_drawdown_pct,
            fail_closed_rate=evidence.fail_closed_rate,
        )


class StrategyTuningRecommendationPoint(UtcTimestampMixin, BaseModel):
    """One timestamped recommendation observation."""

    timestamp: datetime = Field(default_factory=now_utc)
    applied: StrategyAction
    recommended: StrategyAction
    live_recommendation: StrategyAction | None = None
    evidence: StrategyTuningEvidenceSnapshot


class StrategyTuningObservation(UtcTimestampMixin, BaseModel):
    """Persisted recommendation state for one ``(sub-account, strategy)`` pair."""

    sub_account_id: str
    strategy: str
    applied: StrategyAction
    recommended: StrategyAction
    live_recommendation: StrategyAction | None = None
    evidence: StrategyTuningEvidenceSnapshot
    observations_count: int = Field(default=1, ge=1)
    first_seen_at: datetime = Field(default_factory=now_utc)
    last_evaluated_at: datetime = Field(default_factory=now_utc)
    history: list[StrategyTuningRecommendationPoint] = Field(default_factory=list)


class StrategyTuningObservationStore:
    """Atomic JSON snapshot store for strategy-tuning recommendation history."""

    def __init__(
        self,
        state_dir: Path | None = None,
        *,
        data_dir: Path | None = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        if state_dir is not None:
            self.state_dir = state_dir
        else:
            base = data_dir if data_dir is not None else get_settings().data_dir
            self.state_dir = base / "strategy_tuning" / "observations"
        self.history_limit = history_limit

    def path_for(self, sub_account_id: str, strategy: str) -> Path:
        """Return the snapshot path for a strategy-tuning observation."""
        account_dir = quote(sub_account_id, safe="")
        strategy_file = f"{quote(strategy, safe='')}.json"
        return self.state_dir / account_dir / strategy_file

    def save(self, observation: StrategyTuningObservation) -> None:
        """Persist an observation snapshot atomically."""
        path = self.path_for(observation.sub_account_id, observation.strategy)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, observation.model_dump_json(indent=2))

    def load(self, sub_account_id: str, strategy: str) -> StrategyTuningObservation:
        """Load a persisted observation."""
        path = self.path_for(sub_account_id, strategy)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return StrategyTuningObservation(**payload)

    def list_observations(
        self,
        *,
        sub_account_id: str | None = None,
    ) -> list[StrategyTuningObservation]:
        """Return readable observations sorted by most recent evaluation."""
        root = (
            self.state_dir / quote(sub_account_id, safe="")
            if sub_account_id is not None
            else self.state_dir
        )
        if not root.exists():
            return []

        paths = sorted(root.glob("*.json") if sub_account_id else root.glob("*/*.json"))
        observations: list[StrategyTuningObservation] = []
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                observations.append(StrategyTuningObservation(**payload))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return sorted(
            observations,
            key=lambda observation: observation.last_evaluated_at,
            reverse=True,
        )

    def record_recommendation(
        self,
        *,
        sub_account_id: str,
        strategy: str,
        applied: StrategyAction,
        recommended: StrategyAction,
        evidence: RecommenderEvidence | StrategyTuningEvidenceSnapshot,
        live_recommendation: StrategyAction | None = None,
        evaluated_at: datetime | None = None,
    ) -> StrategyTuningObservation:
        """Upsert recommendation history from the latest recommender output."""
        evaluated_at = ensure_utc(evaluated_at or now_utc())
        evidence_snapshot = (
            evidence
            if isinstance(evidence, StrategyTuningEvidenceSnapshot)
            else StrategyTuningEvidenceSnapshot.from_recommender_evidence(evidence)
        )
        point = StrategyTuningRecommendationPoint(
            timestamp=evaluated_at,
            applied=applied,
            recommended=recommended,
            live_recommendation=live_recommendation,
            evidence=evidence_snapshot,
        )
        existing = self._load_if_exists(sub_account_id, strategy)
        history = [point]
        if existing is not None:
            history.extend(existing.history)
        history = history[: self.history_limit]

        observation = StrategyTuningObservation(
            sub_account_id=sub_account_id,
            strategy=strategy,
            applied=applied,
            recommended=recommended,
            live_recommendation=live_recommendation,
            evidence=evidence_snapshot,
            observations_count=(existing.observations_count + 1) if existing else 1,
            first_seen_at=existing.first_seen_at if existing else evaluated_at,
            last_evaluated_at=evaluated_at,
            history=history,
        )
        self.save(observation)
        return observation

    def _load_if_exists(
        self,
        sub_account_id: str,
        strategy: str,
    ) -> StrategyTuningObservation | None:
        path = self.path_for(sub_account_id, strategy)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return StrategyTuningObservation(**payload)


__all__ = [
    "DEFAULT_HISTORY_LIMIT",
    "DEFAULT_STRATEGY_TUNING_OBSERVATION_DIR",
    "StrategyTuningEvidenceSnapshot",
    "StrategyTuningObservation",
    "StrategyTuningObservationStore",
    "StrategyTuningRecommendationPoint",
]
