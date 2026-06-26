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
            breakevens`` count toward the window. DEBT-073: profit
            factor and closed-PnL are taken from the fee-inclusive
            ``net_*`` aggregates (not the gross price-move ones the
            dashboard displays) so a marginal recommendation is not
            granted on fees-omitted optimism.
        fail_closed_rate: ``proposals_fail_closed / proposals_emitted``
            from :class:`~src.proposal.fail_closed_metrics.\
StrategyFailClosedCounts`.
        max_drawdown_pct: Optional explicit max-drawdown override.
            Defaults to ``perf.max_drawdown_pct``.
    """
    closed = perf.wins + perf.losses + perf.breakevens
    if max_drawdown_pct is None:
        max_drawdown_pct = perf.max_drawdown_pct
    # DEBT-073: edge metrics are fee-inclusive. ``net_loss_pct`` can be
    # non-zero even when ``gross_loss_pct`` is zero (an all-gross-winners
    # window where fees push a trade net-negative), so PF is defined on the
    # net split.
    profit_factor = None
    if perf.net_loss_pct > 0.0:
        profit_factor = perf.net_win_pct / perf.net_loss_pct

    return RecommenderEvidence(
        closed_trades=closed,
        win_rate=perf.win_rate,
        profit_factor=profit_factor,
        closed_pnl_pct=perf.net_total_pnl_percent,
        max_drawdown_pct=max_drawdown_pct,
        fail_closed_rate=fail_closed_rate,
    )


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


# =============================================================================
# Initial-action seeding for named strategy families (DEBT-069(b)).
# =============================================================================
#
# Seed map for the *Recommended column fallback only*. See the functional
# spec §"Initial Actions for Named Strategy Families". On day one a strategy
# has no (or too-thin) closed-trade evidence, so ``recommend_action`` returns
# ``None`` (profit-factor undefined). Rather than render nothing, the
# dashboard falls back to a static per-strategy seed so the operator sees a
# starting recommendation derived from the Fly 2026-05-13 snapshot evidence.
#
# Framing (load-bearing): this is a *fallback, not an override*. It NEVER
# changes the applied state (which stays whatever the config says, typically
# ``keep``), and it NEVER gates trades. The instant live evidence is
# sufficient, ``recommend_action`` returns a non-``None`` action which
# supersedes the seed — see ``build_strategy_tuning_rows``.
#
# Keys are the registered technique ``name`` (= ``TECHNIQUE_INFO["name"]
# .lower()``), the same key the dashboard rows and ``applied_action_for`` use
# — NOT the strategy filename. Two name traps: ``rsi.py`` registers
# ``"rsi_universal"`` and ``bollinger_bands.py`` registers
# ``"bollinger_band_reversion"``.
STRATEGY_SEED_ACTIONS: dict[str, StrategyAction] = {
    "rsi_universal": StrategyAction.SCOUT,
    "rsi_4h": StrategyAction.SCOUT,
    "rsi_15m": StrategyAction.SCOUT,
    "momentum_pinball_orb": StrategyAction.PAUSE,
    "vwap_mean_reversion": StrategyAction.PAUSE,
    "bollinger_band_reversion": StrategyAction.PAUSE,
    "turtle_soup_reclaim": StrategyAction.PAUSE,
    "raschke_holy_grail": StrategyAction.SCOUT,
    "ma_crossover": StrategyAction.SCOUT,
    "vcp_breakout": StrategyAction.RETUNE,
    "session_vwap_pullback": StrategyAction.RETUNE,
    "tsmom_vol_breakout": StrategyAction.RETUNE,
    "weinstein_stage2_filter": StrategyAction.RETUNE,
}

# Catch-all for any technique name not in the seed map: the spec's
# "default / simple-trend / LLM-generated -> retune" row. ``vcp_breakout`` /
# ``session_vwap_pullback`` also resolve to ``retune`` because their
# conditional ("keep if PF>=threshold else retune") cannot meet the keep band
# under thin evidence (PF undefined), so they collapse to the retune leg.
SEED_DEFAULT_ACTION: StrategyAction = StrategyAction.RETUNE


def seed_action_for(name: str) -> StrategyAction:
    """Return the seeded fallback action for a technique ``name``.

    Recommended-column fallback only (DEBT-069(b)). This is consulted by
    the dashboard *only* when the live :func:`recommend_action` returns
    ``None`` (evidence too thin to recommend). It is a fallback, not an
    override: it never mutates the applied state and never gates trades.
    Once live evidence is sufficient, the recommender's output supersedes
    this seed.

    Lookup is ``STRATEGY_SEED_ACTIONS.get(name, SEED_DEFAULT_ACTION)`` so
    any unnamed / deprecated / LLM-generated strategy falls through to the
    spec's ``retune`` default.

    Args:
        name: The registered technique ``name`` (``TECHNIQUE_INFO["name"]
            .lower()``), matching the key the dashboard rows and
            ``applied_action_for`` use.

    Returns:
        The seeded :class:`StrategyAction` for ``name``, or
        :data:`SEED_DEFAULT_ACTION` (``retune``) when ``name`` is not a
        named family.
    """
    return STRATEGY_SEED_ACTIONS.get(name, SEED_DEFAULT_ACTION)


__all__ = [
    "SEED_DEFAULT_ACTION",
    "STRATEGY_SEED_ACTIONS",
    "RecommenderEvidence",
    "evidence_from_performance",
    "recommend_action",
    "seed_action_for",
]
