"""Tests for ``src.strategy.tuning_recommender``.

Each bucket-priority threshold is pinned by an explicit boundary test
so we know the recommender returns the spec-defined action at the
edge of every band. The priority-ordering test pins
``pause > shadow > scout > retune > keep > promote`` — the spec's
canonical order.
"""

from __future__ import annotations

import pytest

from src.strategy.performance import TechniquePerformance
from src.strategy.tuning import (
    KeepThresholds,
    PauseThresholds,
    PromoteThresholds,
    RetuneThresholds,
    ScoutThresholds,
    ShadowThresholds,
    StrategyAction,
    ThresholdSpec,
)
from src.strategy.tuning_recommender import (
    RecommenderEvidence,
    evidence_from_performance,
    recommend_action,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _evidence(
    *,
    closed_trades: int = 30,
    win_rate: float = 0.5,
    profit_factor: float | None = 1.4,
    closed_pnl_pct: float = 5.0,
    max_drawdown_pct: float = 3.0,
    fail_closed_rate: float = 0.1,
) -> RecommenderEvidence:
    """Build evidence with sensible defaults — tests override one knob at a time."""
    return RecommenderEvidence(
        closed_trades=closed_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        closed_pnl_pct=closed_pnl_pct,
        max_drawdown_pct=max_drawdown_pct,
        fail_closed_rate=fail_closed_rate,
    )


# ---------------------------------------------------------------------------
# Bucket boundaries
# ---------------------------------------------------------------------------


def test_pause_fires_on_cumulative_loss_with_enough_evidence() -> None:
    """``closed_pnl_pct <= -5`` with at least ``sample_size_min`` closed trades."""
    thresholds = ThresholdSpec()
    evidence = _evidence(closed_trades=15, closed_pnl_pct=-5.5, profit_factor=0.5)
    assert recommend_action(evidence, thresholds) == StrategyAction.PAUSE


def test_pause_fires_on_fail_closed_rate_alone() -> None:
    """``fail_closed_rate >= 0.80`` is sufficient — even with positive PnL."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=5,
        closed_pnl_pct=10.0,
        profit_factor=2.0,
        fail_closed_rate=0.85,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.PAUSE


def test_pause_does_not_fire_below_sample_size_floor() -> None:
    """Cumulative-loss pause requires enough closed-trade evidence."""
    thresholds = ThresholdSpec(pause=PauseThresholds(sample_size_min=15))
    # Loss is below the threshold but only 5 closed trades — too thin.
    evidence = _evidence(
        closed_trades=5,
        closed_pnl_pct=-10.0,
        profit_factor=0.5,
        fail_closed_rate=0.0,
    )
    assert recommend_action(evidence, thresholds) != StrategyAction.PAUSE


def test_shadow_fires_for_systematic_losers_with_enough_evidence() -> None:
    """``profit_factor<=0.6`` and ``closed_pnl_pct<=-2.0`` with samples>=20."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=20,
        profit_factor=0.5,
        closed_pnl_pct=-3.0,
        # Stay under pause threshold:
        fail_closed_rate=0.1,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.SHADOW


def test_shadow_requires_low_profit_factor_AND_loss() -> None:
    """Low profit factor alone is not enough — closed PnL must also be down."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=25,
        profit_factor=0.4,
        closed_pnl_pct=1.0,  # not a loss
        fail_closed_rate=0.0,
    )
    # Should NOT shadow — closed_pnl_pct is not <= -2.0.
    assert recommend_action(evidence, thresholds) != StrategyAction.SHADOW


def test_scout_fires_for_under_sampled_positive_edge() -> None:
    """``profit_factor in [1.0, 1.5]`` with ``closed_trades <= 10``."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=8,
        profit_factor=1.2,
        win_rate=0.55,
        closed_pnl_pct=2.0,
        fail_closed_rate=0.1,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.SCOUT


def test_scout_does_not_fire_above_sample_size_cap() -> None:
    """Scout is *under-sampled*; with enough samples, keep takes precedence."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=20,
        profit_factor=1.2,
        win_rate=0.55,
        closed_pnl_pct=2.0,
        fail_closed_rate=0.1,
    )
    # 20 closed trades exceeds the scout sample_size_max of 10 — should
    # not be scout. It also fails keep's profit_factor_min=1.3, so the
    # recommender returns None (insufficient evidence) for this band.
    assert recommend_action(evidence, thresholds) != StrategyAction.SCOUT


def test_keep_fires_in_healthy_band() -> None:
    """``profit_factor>=1.3`` and ``win_rate>=0.40`` with samples>=15."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=20,
        profit_factor=1.5,
        win_rate=0.45,
        closed_pnl_pct=3.0,
        fail_closed_rate=0.1,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.KEEP


def test_promote_fires_when_strong_evidence_clears_keep_AND_promote() -> None:
    """``profit_factor>=1.8`` + ``win_rate>=0.50`` + samples>=30 + low fail-closed."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=40,
        profit_factor=2.0,
        win_rate=0.6,
        closed_pnl_pct=10.0,
        fail_closed_rate=0.05,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.PROMOTE


def test_promote_falls_back_to_keep_when_fail_closed_rate_too_high() -> None:
    """High fail-closed rate disqualifies promote even with strong profit factor."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=40,
        profit_factor=2.0,
        win_rate=0.6,
        closed_pnl_pct=10.0,
        fail_closed_rate=0.5,  # > promote.fail_closed_rate_max=0.30
    )
    # Falls through to keep, since keep doesn't require a fail-closed
    # ceiling.
    assert recommend_action(evidence, thresholds) == StrategyAction.KEEP


def test_retune_fires_for_mediocre_band() -> None:
    """``profit_factor in [0.8, 1.2]`` with samples>=20 and drawdown <= 8%."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=25,
        profit_factor=1.0,
        win_rate=0.45,
        closed_pnl_pct=0.5,
        max_drawdown_pct=5.0,
        fail_closed_rate=0.1,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.RETUNE


def test_retune_does_not_fire_when_drawdown_exceeds_ceiling() -> None:
    """Mediocre band with deep drawdown should NOT retune (waits for pause/shadow)."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=25,
        profit_factor=1.0,
        win_rate=0.45,
        closed_pnl_pct=-0.5,  # tiny loss, below shadow's -2.0 threshold
        max_drawdown_pct=10.0,  # > retune's max_drawdown_pct_max=8.0
        fail_closed_rate=0.1,
    )
    # Drawdown disqualifies retune; doesn't clear any other bucket
    # cleanly => None (insufficient evidence).
    assert recommend_action(evidence, thresholds) != StrategyAction.RETUNE


def test_returns_none_when_no_bucket_matches() -> None:
    """Insufficient evidence => ``None``; leave applied state untouched."""
    thresholds = ThresholdSpec()
    evidence = _evidence(closed_trades=0, profit_factor=None, win_rate=0.0)
    assert recommend_action(evidence, thresholds) is None


def test_returns_none_when_profit_factor_undefined_and_no_pause_signal() -> None:
    """No losses yet AND no other signal => profit_factor=None => None."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=5,
        profit_factor=None,
        win_rate=1.0,
        closed_pnl_pct=10.0,
        fail_closed_rate=0.0,
    )
    assert recommend_action(evidence, thresholds) is None


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


def test_pause_beats_shadow_when_both_would_fire() -> None:
    """Pause has the highest priority — fires even when shadow would too."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=25,
        profit_factor=0.3,
        win_rate=0.2,
        closed_pnl_pct=-8.0,  # pause AND shadow both qualify
        fail_closed_rate=0.0,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.PAUSE


def test_shadow_beats_scout_when_both_would_fire() -> None:
    """Loose construction where scout's band overlaps shadow's loser band."""
    # Custom thresholds to force overlap: scout floor lowered, shadow
    # band widened so both qualify for a low-PF + small-sample run.
    thresholds = ThresholdSpec(
        scout=ScoutThresholds(profit_factor_min=0.5, sample_size_max=25),
        shadow=ShadowThresholds(
            profit_factor_max=0.7,
            sample_size_min=20,
            closed_pnl_pct_max=-2.0,
        ),
    )
    evidence = _evidence(
        closed_trades=22,
        profit_factor=0.6,
        win_rate=0.3,
        closed_pnl_pct=-3.0,
        fail_closed_rate=0.0,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.SHADOW


def test_scout_beats_retune_when_both_would_fire() -> None:
    """Under-sampled mediocre band -> scout wins over retune."""
    # The retune sample_size_min is lowered to 5 so retune *would* fire
    # for an 8-sample 1.1-PF strategy — but scout fires first because
    # 8 <= scout.sample_size_max=10.
    thresholds = ThresholdSpec(
        retune=RetuneThresholds(sample_size_min=5),
    )
    evidence = _evidence(
        closed_trades=8,
        profit_factor=1.1,
        win_rate=0.45,
        closed_pnl_pct=1.0,
        max_drawdown_pct=2.0,
        fail_closed_rate=0.0,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.SCOUT


def test_retune_beats_keep_in_mediocre_band() -> None:
    """A mediocre-PF strategy with enough samples => retune, not keep."""
    # Drop keep.profit_factor_min so PF=1.0 would technically clear
    # keep — retune's mediocre band still wins because it's checked
    # before keep in priority order.
    thresholds = ThresholdSpec(
        keep=KeepThresholds(profit_factor_min=0.9),
    )
    evidence = _evidence(
        closed_trades=22,
        profit_factor=1.0,
        win_rate=0.45,
        closed_pnl_pct=0.5,
        max_drawdown_pct=3.0,
        fail_closed_rate=0.05,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.RETUNE


def test_keep_beats_promote_when_only_keep_band_cleared() -> None:
    """Keep band but not promote => keep, not promote."""
    thresholds = ThresholdSpec()
    evidence = _evidence(
        closed_trades=20,
        profit_factor=1.5,  # < promote.profit_factor_min=1.8
        win_rate=0.45,
        closed_pnl_pct=4.0,
        fail_closed_rate=0.1,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.KEEP


def test_promote_overrides_keep_when_promote_thresholds_clear() -> None:
    """When promote thresholds clear, return promote (stronger signal)."""
    thresholds = ThresholdSpec(
        promote=PromoteThresholds(
            profit_factor_min=1.5,
            win_rate_min=0.45,
            sample_size_min=15,
            fail_closed_rate_max=0.5,
        ),
    )
    evidence = _evidence(
        closed_trades=20,
        profit_factor=1.6,
        win_rate=0.5,
        closed_pnl_pct=8.0,
        fail_closed_rate=0.1,
    )
    assert recommend_action(evidence, thresholds) == StrategyAction.PROMOTE


# ---------------------------------------------------------------------------
# evidence_from_performance helper
# ---------------------------------------------------------------------------


def test_evidence_from_performance_reconstructs_inputs() -> None:
    """Constructor wraps true PF/drawdown metrics + a fail-closed rate."""
    perf = TechniquePerformance(
        technique_name="rsi_universal",
        technique_version="1.0",
        total_trades=12,
        wins=6,
        losses=4,
        breakevens=2,
        pending=0,
        win_rate=0.5,
        avg_pnl_percent=1.0,
        total_pnl_percent=12.0,
        best_trade_pnl=20.0,
        worst_trade_pnl=-4.0,
        gross_win_pct=12.0,
        gross_loss_pct=8.0,
        max_drawdown_pct=6.5,
    )
    evidence = evidence_from_performance(perf, fail_closed_rate=0.2)
    assert evidence.closed_trades == 12
    assert evidence.win_rate == pytest.approx(0.5)
    assert evidence.closed_pnl_pct == pytest.approx(12.0)
    assert evidence.max_drawdown_pct == pytest.approx(6.5)
    assert evidence.fail_closed_rate == pytest.approx(0.2)
    # True profit factor is gross win / gross loss. It intentionally
    # ignores the old best/worst-trade approximation.
    assert evidence.profit_factor is not None
    assert evidence.profit_factor == pytest.approx(1.5)


def test_evidence_from_performance_returns_none_profit_factor_without_losses() -> None:
    """No losses => profit factor undefined."""
    perf = TechniquePerformance(
        technique_name="x",
        technique_version="1.0",
        total_trades=3,
        wins=3,
        losses=0,
        breakevens=0,
        pending=0,
        win_rate=1.0,
        best_trade_pnl=5.0,
        worst_trade_pnl=0.0,
        gross_win_pct=15.0,
        gross_loss_pct=0.0,
    )
    evidence = evidence_from_performance(perf, fail_closed_rate=0.0)
    assert evidence.profit_factor is None
