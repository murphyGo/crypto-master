"""Strategy-tuning action state, thresholds, and policy model.

`strategy-tuning` ships the *above-strategy* action state per
``(sub-account, strategy)`` pair: ``keep``, ``shadow``, ``scout``,
``pause``, ``promote``, ``retune``. The unit is intentionally separate
from the strategies themselves — individual strategies keep owning
entry/exit rules; this module owns the runtime decision *whether* to
emit / open / scale a proposal at all based on observed evidence.

This module is the data layer for the unit. It does not perform any
IO. The pure-function recommender lives in
:mod:`src.strategy.tuning_recommender`; the runtime gate that enforces
the *applied* state lives in :mod:`src.runtime.engine`.

Resolutions baked in (2026-05-13, see the functional spec):

* Action state is keyed per ``(sub-account, strategy)``.
* ``scout_size_factor`` is per-account *and* may be overridden per
  strategy via ``strategy_overrides[<name>].scout_size_factor``.
* ``pause`` resets the evidence window on unpause — handled in the
  recommender by treating "no recent records" as insufficient evidence
  rather than carrying stale closed-trade context across the pause.

Related Requirements:
- FR-005: Strategy performance tracking — the evidence input.
- FR-013 / FR-014: proposal lifecycle visibility — the runtime gate
  emits ``PROPOSAL_REJECTED`` events for ``pause`` and persists
  ``shadow=True`` records for ``shadow``.
- DEBT-061: per-strategy fail-closed metrics feed the recommender's
  pause threshold.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrategyAction(str, Enum):
    """Action state for one ``(sub-account, strategy)`` pair.

    See the functional spec §"Action States" for the full transition
    table. The enum carries the canonical string value persisted in
    YAML and JSONL.

    Values:
        KEEP: Strategy is performing within thresholds; runtime emits
            and opens proposals normally.
        SHADOW: Runtime records proposal evidence (with ``shadow=True``
            on the record) but blocks any open. Equivalent to
            "paper-paper" — signals are measured, no capital committed.
        SCOUT: Runtime allows opens but at a reduced risk budget
            (``scout_size_factor``; default ``0.25``). Used to keep a
            positive-edge but under-sampled strategy alive at reduced
            size.
        PAUSE: Runtime fully blocks opens. Strategy config is
            preserved; ``pause`` is sticky and stays until an operator
            explicitly changes it.
        PROMOTE: Recommendation-only — strategy should graduate to a
            higher-tier sub-account. Applied state behaves like the
            underlying recommended state (``keep`` or ``scout``);
            promotion target resolution is operator-only for v1.
        RETUNE: Runtime opens are still allowed but the strategy is
            flagged for parameter retuning. Attention signal, not a
            block.
    """

    KEEP = "keep"
    SHADOW = "shadow"
    SCOUT = "scout"
    PAUSE = "pause"
    PROMOTE = "promote"
    RETUNE = "retune"


# DEBT-069(f): discriminator written into the strategy-action PAUSE rejection
# event's ``details.pause_reason``. The runtime gate fires on the OPERATOR-APPLIED
# action (config / seed YAML), never on live evidence — so the only thing the gate
# can honestly assert is that the pause is the applied/config action. The
# evidence-vs-config *corroboration* judgement is computed dashboard-side by
# joining this against the live recommender output (quant ruling 2026-06-04,
# Option b: single ``PAUSE`` action + observability-only details discriminator;
# the funnel terminal / ``gate_reason`` stay a single ``STRATEGY_ACTION_PAUSE``).
PAUSE_REASON_GATE_CONFIG: str = "gate_config"


# Default thresholds mirror the YAML example in the functional spec.
# Kept as module-level constants (not hard-coded inside
# ``ThresholdSpec``) so test fixtures can override one knob at a time
# without re-typing the whole block.
DEFAULT_WINDOW_CLOSED_TRADES: int = 30
DEFAULT_SCOUT_SIZE_FACTOR: Decimal = Decimal("0.25")


class PauseThresholds(BaseModel):
    """``pause`` recommendation thresholds.

    Either ``closed_pnl_pct_max`` (paired with ``sample_size_min``)
    *or* ``fail_closed_rate_min`` fires the pause recommendation —
    the YAML example uses the explicit ``OR_fail_closed_rate_min``
    key but the recommender treats either condition as sufficient.
    """

    closed_pnl_pct_max: float = -5.0
    sample_size_min: int = Field(default=15, ge=0)
    fail_closed_rate_min: float = Field(default=0.80, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=True)


class ShadowThresholds(BaseModel):
    """``shadow`` recommendation thresholds (systematic-loss band)."""

    profit_factor_max: float = 0.6
    sample_size_min: int = Field(default=20, ge=0)
    closed_pnl_pct_max: float = -2.0

    model_config = ConfigDict(frozen=True)


class ScoutThresholds(BaseModel):
    """``scout`` recommendation thresholds (positive but under-sampled)."""

    profit_factor_min: float = 1.0
    profit_factor_max: float = 1.5
    sample_size_max: int = Field(default=10, ge=0)

    model_config = ConfigDict(frozen=True)


class KeepThresholds(BaseModel):
    """``keep`` recommendation thresholds (healthy band)."""

    profit_factor_min: float = 1.3
    win_rate_min: float = Field(default=0.40, ge=0.0, le=1.0)
    sample_size_min: int = Field(default=15, ge=0)

    model_config = ConfigDict(frozen=True)


class PromoteThresholds(BaseModel):
    """``promote`` recommendation thresholds (strong evidence)."""

    profit_factor_min: float = 1.8
    win_rate_min: float = Field(default=0.50, ge=0.0, le=1.0)
    sample_size_min: int = Field(default=30, ge=0)
    fail_closed_rate_max: float = Field(default=0.30, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=True)


class RetuneThresholds(BaseModel):
    """``retune`` recommendation thresholds (mediocre band)."""

    profit_factor_min: float = 0.8
    profit_factor_max: float = 1.2
    sample_size_min: int = Field(default=20, ge=0)
    max_drawdown_pct_max: float = 8.0

    model_config = ConfigDict(frozen=True)


class ThresholdSpec(BaseModel):
    """All evidence thresholds the recommender consumes.

    The recommender evaluates buckets in priority order
    ``pause -> shadow -> scout -> retune -> keep -> promote``; the
    first match wins. Insufficient evidence returns ``None`` so the
    applied state is left untouched.

    Defaults match the YAML example in the functional spec §"Evidence
    Thresholds". Operators override per ``(sub-account, strategy)``
    via the ``strategy_tuning.thresholds_overrides`` block on a
    sub-account.
    """

    window_closed_trades: int = Field(
        default=DEFAULT_WINDOW_CLOSED_TRADES,
        ge=1,
    )
    pause: PauseThresholds = Field(default_factory=PauseThresholds)
    shadow: ShadowThresholds = Field(default_factory=ShadowThresholds)
    scout: ScoutThresholds = Field(default_factory=ScoutThresholds)
    keep: KeepThresholds = Field(default_factory=KeepThresholds)
    promote: PromoteThresholds = Field(default_factory=PromoteThresholds)
    retune: RetuneThresholds = Field(default_factory=RetuneThresholds)

    model_config = ConfigDict(frozen=True)


class StrategyOverride(BaseModel):
    """Per-strategy override block on a sub-account.

    ``applied`` overrides the default ``keep`` applied state.
    ``scout_size_factor`` overrides the account-level factor for this
    strategy (per the spec's per-strategy resolution); ``None`` means
    "fall through to the account default". ``thresholds`` overrides
    the recommender's bucket thresholds; ``None`` means "use account
    or unit defaults".
    """

    applied: StrategyAction = StrategyAction.KEEP
    scout_size_factor: Decimal | None = Field(default=None, gt=Decimal("0"))
    thresholds: ThresholdSpec | None = None

    model_config = ConfigDict(frozen=True)


class StrategyTuningPolicy(BaseModel):
    """Per-sub-account strategy-tuning policy block.

    Lives next to ``risk_policy`` / ``market_regime`` on
    :class:`~src.trading.sub_account.SubAccount`. The defaults are
    deliberately conservative: ``enabled=False`` so the runtime gate
    is a no-op for accounts that have not opted in (no gating, no
    behaviour change).

    Attributes:
        enabled: Master switch. ``False`` preserves current behaviour
            for the account: the runtime gate is bypassed and the
            recommender does not run.
        scout_size_factor: Account-default factor applied under the
            ``scout`` action. Defaults to ``0.25`` per the resolved
            Open Decision (2026-05-13). May be overridden per strategy
            via ``strategy_overrides[<name>].scout_size_factor``.
        thresholds: Account-default recommender thresholds. Strategies
            may override per-bucket via
            ``strategy_overrides[<name>].thresholds``.
        strategy_overrides: Map of strategy name → per-strategy
            override block. Missing entries default to applied=KEEP
            with no per-strategy threshold or scout-factor override.
    """

    enabled: bool = False
    scout_size_factor: Decimal = Field(
        default=DEFAULT_SCOUT_SIZE_FACTOR,
        gt=Decimal("0"),
    )
    thresholds: ThresholdSpec = Field(default_factory=ThresholdSpec)
    strategy_overrides: dict[str, StrategyOverride] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _scout_size_factor_must_not_exceed_one(self) -> StrategyTuningPolicy:
        """``scout_size_factor > 1`` would *increase* size under scout.

        ``scout`` is by definition a reduced-risk action; a factor
        above ``1.0`` would silently amplify size for an explicitly
        under-sampled strategy. Reject at parse time so the operator
        sees the typo immediately.
        """
        if self.scout_size_factor > Decimal("1"):
            raise ValueError(
                "strategy_tuning.scout_size_factor must be <= 1 "
                f"(got {self.scout_size_factor})"
            )
        for name, override in self.strategy_overrides.items():
            if (
                override.scout_size_factor is not None
                and override.scout_size_factor > Decimal("1")
            ):
                raise ValueError(
                    f"strategy_tuning.strategy_overrides[{name!r}]."
                    f"scout_size_factor must be <= 1 "
                    f"(got {override.scout_size_factor})"
                )
        return self

    def applied_action_for(self, strategy_name: str) -> StrategyAction:
        """Return the applied action for ``strategy_name``.

        Missing entries default to :attr:`StrategyAction.KEEP` so
        every strategy has a deterministic applied state without
        requiring an explicit YAML entry per strategy.
        """
        override = self.strategy_overrides.get(strategy_name)
        if override is None:
            return StrategyAction.KEEP
        return override.applied

    def scout_size_factor_for(self, strategy_name: str) -> Decimal:
        """Return the scout size factor for ``strategy_name``.

        Per-strategy override wins; falls through to the account
        default (typically ``0.25``).
        """
        override = self.strategy_overrides.get(strategy_name)
        if override is not None and override.scout_size_factor is not None:
            return override.scout_size_factor
        return self.scout_size_factor

    def thresholds_for(self, strategy_name: str) -> ThresholdSpec:
        """Return the recommender thresholds for ``strategy_name``."""
        override = self.strategy_overrides.get(strategy_name)
        if override is not None and override.thresholds is not None:
            return override.thresholds
        return self.thresholds


__all__ = [
    "DEFAULT_SCOUT_SIZE_FACTOR",
    "DEFAULT_WINDOW_CLOSED_TRADES",
    "PAUSE_REASON_GATE_CONFIG",
    "KeepThresholds",
    "PauseThresholds",
    "PromoteThresholds",
    "RetuneThresholds",
    "ScoutThresholds",
    "ShadowThresholds",
    "StrategyAction",
    "StrategyOverride",
    "StrategyTuningPolicy",
    "ThresholdSpec",
]
