"""Strategy-tuning recommender — pure function over evidence.

Translates ``(performance, fail-closed counts, exposure)`` into a
:class:`~src.strategy.tuning.StrategyAction` recommendation. No IO, no
global state, no side effects: callers feed in the snapshot and the
thresholds, and get back an action (or ``None`` when the evidence is
too thin to recommend anything).

The bucket-priority order is the spec's canonical
``pause -> shadow -> scout -> retune -> keep -> promote`` — first
match wins. The priority is *not* "best fit": pause is checked first
because losing capital is the worst outcome the recommender can act
on, and shadow / scout are checked before keep so an under-sampled
strategy gets the smaller-risk path rather than full size.

Related Requirements:
- FR-005: technique performance tracking — primary evidence input.
- FR-013 / FR-014: proposal lifecycle visibility — pause is informed
  by the fail-closed rate (DEBT-061).
- DEBT-061: per-strategy fail-closed metrics surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.strategy.performance import TechniquePerformance
from src.strategy.tuning import StrategyAction, ThresholdSpec


@dataclass(frozen=True)
class RecommenderEvidence:
    """Snapshot the recommender consumes for one ``(account, strategy)``.

    All fields are scalars so callers can construct evidence from any
    source — :class:`TechniquePerformance`, the DEBT-061 surface, or a
    test fixture — without leaking persistence concerns into the
    recommender.

    Attributes:
        closed_trades: Closed-trade count (``wins + losses +
            breakevens``). The bucket samples-size thresholds compare
            against this.
        win_rate: Win rate in ``[0.0, 1.0]``.
        profit_factor: ``gross_win / gross_loss`` over the window.
            ``None`` means "undefined" (no losses yet); treat as
            "insufficient evidence" for buckets that require an
            explicit profit-factor band.
        closed_pnl_pct: Cumulative closed PnL as percentage of starting
            balance over the window.
        max_drawdown_pct: Max closed-trade drawdown (absolute %, e.g.
            ``8.0`` for an 8% drawdown).
        fail_closed_rate: DEBT-061 ``proposals_fail_closed /
            proposals_emitted`` ratio in ``[0.0, 1.0]``. ``0.0`` when
            the strategy never emitted.
    """

    closed_trades: int
    win_rate: float
    profit_factor: float | None
    closed_pnl_pct: float
    max_drawdown_pct: float
    fail_closed_rate: float


def evidence_from_performance(
    perf: TechniquePerformance,
    *,
    fail_closed_rate: float,
    max_drawdown_pct: float | None = None,
) -> RecommenderEvidence:
    """Build a :class:`RecommenderEvidence` from a performance snapshot.

    Convenience constructor for the common path: the engine has a
    fresh :class:`TechniquePerformance` (already excludes synthetic
    rows per DEBT-065) and a DEBT-061 fail-closed-rate to thread
    through.

    Args:
        perf: Per-technique aggregate snapshot. ``wins / losses /
            breakevens`` count toward the window; ``total_pnl_percent``
            and ``worst_trade_pnl`` map to the recommender's inputs.
        fail_closed_rate: ``proposals_fail_closed / proposals_emitted``
            from :class:`~src.proposal.fail_closed_metrics.\
StrategyFailClosedCounts`.
        max_drawdown_pct: Optional explicit max-drawdown override.
            Defaults to ``|perf.worst_trade_pnl|`` — the
            ``PerformanceTracker`` does not currently compute a rolling
            drawdown series, so we approximate via the worst single
            closed trade. Operators can supply the true series-level
            drawdown when available.
    """
    closed = perf.wins + perf.losses + perf.breakevens
    if max_drawdown_pct is None:
        # Worst single-trade PnL stands in for the rolling drawdown
        # until a series-level metric lands. ``worst_trade_pnl`` is
        # already a percentage of entry; abs() gives the magnitude
        # the retune bucket compares against.
        max_drawdown_pct = abs(perf.worst_trade_pnl)

    profit_factor = _infer_profit_factor(perf)

    return RecommenderEvidence(
        closed_trades=closed,
        win_rate=perf.win_rate,
        profit_factor=profit_factor,
        closed_pnl_pct=perf.total_pnl_percent,
        max_drawdown_pct=max_drawdown_pct,
        fail_closed_rate=fail_closed_rate,
    )


def _infer_profit_factor(perf: TechniquePerformance) -> float | None:
    """Best-effort profit-factor reconstruction from a summary.

    :class:`TechniquePerformance` does not persist a profit-factor
    field today — it stores ``avg_pnl_percent`` / ``total_pnl_percent``
    / ``best_trade_pnl`` / ``worst_trade_pnl`` only. We approximate:

    * If there are no losses, profit factor is undefined; return
      ``None`` so buckets requiring an explicit ratio skip the
      strategy rather than infer infinite edge from one win.
    * If ``total_pnl_percent`` is positive with at least one loss,
      reconstruct a coarse ratio from win/loss counts × average
      magnitudes. This is intentionally rough — the recommender's
      job is to bucket, not to backtest.

    Callers that have a real profit-factor (from a backtester run or
    a future PerformanceTracker enhancement) should bypass this
    helper and build :class:`RecommenderEvidence` directly.
    """
    if perf.losses == 0:
        return None
    # Coarse reconstruction: assume win-side magnitudes scale with
    # best_trade_pnl and loss-side with |worst_trade_pnl|. This
    # produces a useful order-of-magnitude figure but is *not* a
    # substitute for tracking gross-win / gross-loss directly.
    gross_win = perf.wins * max(perf.best_trade_pnl, 0.0)
    gross_loss = perf.losses * abs(min(perf.worst_trade_pnl, 0.0))
    if gross_loss == 0:
        return None
    return gross_win / gross_loss


def recommend_action(
    evidence: RecommenderEvidence,
    thresholds: ThresholdSpec,
) -> StrategyAction | None:
    """Return the recommended action for the given evidence.

    Pure function. The recommender walks the buckets in priority order
    ``pause -> shadow -> scout -> retune -> keep -> promote`` and
    returns the first match. ``None`` means "insufficient evidence;
    leave the applied state untouched".

    Args:
        evidence: Snapshot for the ``(sub-account, strategy)`` pair.
        thresholds: Per-account or per-strategy threshold spec.

    Returns:
        The recommended :class:`StrategyAction`, or ``None`` when no
        bucket matches and the evidence does not even support a
        ``keep``/``promote`` recommendation (e.g. zero closed trades).
    """
    # Pause: any one of (cumulative loss AND enough evidence) or
    # (fail-closed rate alone) qualifies. Pause is the highest priority
    # because it is the only action that *stops* capital loss.
    pause_pnl_hit = (
        evidence.closed_trades >= thresholds.pause.sample_size_min
        and evidence.closed_pnl_pct <= thresholds.pause.closed_pnl_pct_max
    )
    pause_fail_closed_hit = (
        evidence.fail_closed_rate >= thresholds.pause.fail_closed_rate_min
    )
    if pause_pnl_hit or pause_fail_closed_hit:
        return StrategyAction.PAUSE

    # Shadow: systematic loser with enough evidence to be confident.
    # Requires both a low profit factor AND a meaningful closed-PnL
    # drag, so a single bad streak doesn't shadow a strategy.
    if (
        evidence.closed_trades >= thresholds.shadow.sample_size_min
        and evidence.profit_factor is not None
        and evidence.profit_factor <= thresholds.shadow.profit_factor_max
        and evidence.closed_pnl_pct <= thresholds.shadow.closed_pnl_pct_max
    ):
        return StrategyAction.SHADOW

    # Scout: positive but under-sampled. We *want* this strategy to
    # generate evidence — keep it alive at reduced size. The
    # under-sampled gate is the dominant constraint here.
    if (
        evidence.closed_trades <= thresholds.scout.sample_size_max
        and evidence.profit_factor is not None
        and thresholds.scout.profit_factor_min
        <= evidence.profit_factor
        <= thresholds.scout.profit_factor_max
    ):
        return StrategyAction.SCOUT

    # Retune: mediocre band with enough evidence to know it's mediocre,
    # AND drawdown is contained (otherwise pause/shadow would have
    # fired upstream). The mediocre band is wider than scout's so we
    # check the drawdown ceiling explicitly.
    if (
        evidence.closed_trades >= thresholds.retune.sample_size_min
        and evidence.profit_factor is not None
        and thresholds.retune.profit_factor_min
        <= evidence.profit_factor
        <= thresholds.retune.profit_factor_max
        and evidence.max_drawdown_pct <= thresholds.retune.max_drawdown_pct_max
    ):
        return StrategyAction.RETUNE

    # Keep: healthy band. Requires both profit factor *and* win rate
    # above floors; a high profit factor from one big win is not
    # enough.
    if (
        evidence.closed_trades >= thresholds.keep.sample_size_min
        and evidence.profit_factor is not None
        and evidence.profit_factor >= thresholds.keep.profit_factor_min
        and evidence.win_rate >= thresholds.keep.win_rate_min
    ):
        # Promote is strictly stronger than keep — only recommended
        # when the keep floor is also cleared.
        if (
            evidence.closed_trades >= thresholds.promote.sample_size_min
            and evidence.profit_factor >= thresholds.promote.profit_factor_min
            and evidence.win_rate >= thresholds.promote.win_rate_min
            and evidence.fail_closed_rate <= thresholds.promote.fail_closed_rate_max
        ):
            return StrategyAction.PROMOTE
        return StrategyAction.KEEP

    # No bucket matched: insufficient evidence. The caller should
    # leave the applied state untouched.
    return None


__all__ = [
    "RecommenderEvidence",
    "evidence_from_performance",
    "recommend_action",
]
