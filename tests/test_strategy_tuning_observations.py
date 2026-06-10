"""Tests for strategy-tuning recommendation observation persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.strategy.tuning import StrategyAction
from src.strategy.tuning_observations import StrategyTuningObservationStore
from src.strategy.tuning_recommender import RecommenderEvidence


def _evidence(
    *,
    closed_trades: int = 12,
    profit_factor: float | None = 1.4,
) -> RecommenderEvidence:
    return RecommenderEvidence(
        closed_trades=closed_trades,
        win_rate=0.5,
        profit_factor=profit_factor,
        closed_pnl_pct=4.0,
        max_drawdown_pct=2.0,
        fail_closed_rate=0.1,
    )


def test_observation_store_records_first_recommendation(tmp_path: Path) -> None:
    store = StrategyTuningObservationStore(state_dir=tmp_path / "observations")

    observation = store.record_recommendation(
        sub_account_id="paper/alt",
        strategy="rsi_universal",
        applied=StrategyAction.KEEP,
        recommended=StrategyAction.SCOUT,
        live_recommendation=None,
        evidence=_evidence(profit_factor=None),
        evaluated_at=datetime(2026, 6, 10, 1, 0, tzinfo=timezone.utc),
    )
    loaded = store.load("paper/alt", "rsi_universal")

    assert observation == loaded
    assert loaded.sub_account_id == "paper/alt"
    assert loaded.strategy == "rsi_universal"
    assert loaded.applied == StrategyAction.KEEP
    assert loaded.recommended == StrategyAction.SCOUT
    assert loaded.live_recommendation is None
    assert loaded.evidence.profit_factor is None
    assert loaded.observations_count == 1
    assert loaded.first_seen_at == datetime(2026, 6, 10, 1, 0, tzinfo=timezone.utc)
    assert loaded.history[0].recommended == StrategyAction.SCOUT


def test_observation_store_preserves_first_seen_and_caps_history(
    tmp_path: Path,
) -> None:
    store = StrategyTuningObservationStore(
        state_dir=tmp_path / "observations",
        history_limit=2,
    )
    first_at = datetime(2026, 6, 10, 1, 0, tzinfo=timezone.utc)
    second_at = datetime(2026, 6, 10, 2, 0, tzinfo=timezone.utc)
    third_at = datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)

    store.record_recommendation(
        sub_account_id="lab",
        strategy="rsi",
        applied=StrategyAction.KEEP,
        recommended=StrategyAction.SCOUT,
        evidence=_evidence(closed_trades=5),
        evaluated_at=first_at,
    )
    store.record_recommendation(
        sub_account_id="lab",
        strategy="rsi",
        applied=StrategyAction.SCOUT,
        recommended=StrategyAction.KEEP,
        live_recommendation=StrategyAction.KEEP,
        evidence=_evidence(closed_trades=15),
        evaluated_at=second_at,
    )
    observation = store.record_recommendation(
        sub_account_id="lab",
        strategy="rsi",
        applied=StrategyAction.SCOUT,
        recommended=StrategyAction.PROMOTE,
        live_recommendation=StrategyAction.PROMOTE,
        evidence=_evidence(closed_trades=40, profit_factor=2.0),
        evaluated_at=third_at,
    )

    assert observation.observations_count == 3
    assert observation.first_seen_at == first_at
    assert observation.last_evaluated_at == third_at
    assert [point.timestamp for point in observation.history] == [third_at, second_at]
    assert [point.recommended for point in observation.history] == [
        StrategyAction.PROMOTE,
        StrategyAction.KEEP,
    ]


def test_observation_store_lists_most_recent_first_and_skips_malformed(
    tmp_path: Path,
) -> None:
    store = StrategyTuningObservationStore(state_dir=tmp_path / "observations")

    store.record_recommendation(
        sub_account_id="lab",
        strategy="older",
        applied=StrategyAction.KEEP,
        recommended=StrategyAction.RETUNE,
        evidence=_evidence(),
        evaluated_at=datetime(2026, 6, 10, 1, 0, tzinfo=timezone.utc),
    )
    store.record_recommendation(
        sub_account_id="lab",
        strategy="newer",
        applied=StrategyAction.KEEP,
        recommended=StrategyAction.KEEP,
        live_recommendation=StrategyAction.KEEP,
        evidence=_evidence(closed_trades=20),
        evaluated_at=datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc),
    )
    malformed = store.path_for("lab", "bad")
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_text("{not-json", encoding="utf-8")

    observations = store.list_observations(sub_account_id="lab")

    assert [observation.strategy for observation in observations] == [
        "newer",
        "older",
    ]


def test_observation_path_encodes_sub_account_and_strategy(tmp_path: Path) -> None:
    store = StrategyTuningObservationStore(state_dir=tmp_path / "observations")

    path = store.path_for("paper/alt", "strategy with spaces")

    assert path.parent.name == "paper%2Falt"
    assert path.name == "strategy%20with%20spaces.json"
