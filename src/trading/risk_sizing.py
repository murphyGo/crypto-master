"""Risk-based position sizing for cross-account-risk-policy.

Pure helper module. Translates a per-trade ``risk_budget_pct`` policy
into a clamped position size, returning a structured rejection reason
on every failure mode (sub-floor notional, stop-too-tight, missing
equity, missing risk budget). The proposal-runtime sizing site wires
this in when ``RiskPolicy.sizing_mode == "risk_budget"``; the legacy
fixed-notional path remains untouched for accounts that don't opt in.

Formula (cross-account-risk-policy §"Risk-Based Sizing"):

* Long:  ``risk_per_unit = entry_price - stop_loss``
* Short: ``risk_per_unit = stop_loss - entry_price``
* ``account_risk_budget = equity * risk_budget_pct``
* Raw size ``Q = account_risk_budget / risk_per_unit``

The raw ``Q`` is clamped against three policy bounds before being
returned:

* ``min_notional_per_trade`` — sub-floor proposals are *rejected*
  (``RiskSizingRejection.reason == "below_min_notional"``), never
  silently rounded up.
* ``max_notional_per_trade`` — hard ceiling; tight-stop math that
  produces an oversized notional gets clamped down (size returned).
* ``min_stop_distance_bps`` — proposals whose stop is tighter than the
  floor in basis points are rejected as ``"stop_too_tight"``.

Everything is :class:`~decimal.Decimal` end-to-end; no ``float``
contamination.

Related Requirements:

* FR-036 (sub-account capital isolation): sizing pulls equity per
  account, not from a global balance.
* FR-038 (risk-aware sizing): every accepted proposal must consume a
  bounded fraction of the account's equity, not a fixed dollar slug.
* NFR-012 (live-trading observability): every rejection returns a
  structured reason the dashboard surfaces verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from src.trading.sub_account import RiskPolicy

# Reasons returned to the caller when a proposal cannot be sized.
# Stable string identifiers so dashboard/audit consumers can group on
# them without re-parsing the human message.
RiskSizingRejectionReason = Literal[
    "missing_equity",
    "missing_risk_budget",
    "invalid_stop_distance",
    "stop_too_tight",
    "below_min_notional",
]


@dataclass(frozen=True)
class RiskSizingRejection:
    """Structured rejection returned by :func:`compute_risk_budget_size`.

    Attributes:
        reason: One of the :data:`RiskSizingRejectionReason` literals.
        message: Operator-facing free-form text — included verbatim
            in activity events / dashboards.
        details: Optional mapping of structured key/value diagnostic
            data (e.g. ``stop_distance_bps`` for ``stop_too_tight``)
            so the dashboard can show the numbers without re-deriving
            them.
    """

    reason: RiskSizingRejectionReason
    message: str
    details: dict[str, str] | None = None


# Basis-point denominator for ``min_stop_distance_bps`` math. One bp =
# ``Decimal("0.0001")`` of price; the policy stores the integer
# numerator and we divide by ``10_000`` here to compare against the
# proportional stop distance.
_BPS_DIVISOR = Decimal("10000")


def compute_risk_budget_size(
    *,
    account_equity: Decimal | None,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    side: Literal["long", "short"],
    policy: RiskPolicy,
) -> Decimal | RiskSizingRejection:
    """Size a proposal under ``sizing_mode='risk_budget'``.

    Pure function. The caller is responsible for sourcing
    ``account_equity`` (live balance snapshot or the fall-back
    ``CapitalPolicy.sizing_balance``) and for ensuring the proposal's
    side / prices already passed proposal-runtime validation. This
    helper still defends against the obvious wrong-side / zero-stop
    inputs because silent fallthrough at the sizing site would burn
    money in live mode.

    Args:
        account_equity: The account's current equity in the quote
            currency, or ``None`` when a balance snapshot is
            unavailable. ``None`` produces a structured rejection
            (``"missing_equity"``) per spec — silent fallback to a
            hardcoded default is not allowed.
        entry_price: Proposed entry fill price.
        stop_loss_price: Proposed stop-loss price.
        side: ``"long"`` or ``"short"`` — selects the sign of
            ``risk_per_unit``.
        policy: The sub-account's :class:`RiskPolicy`. ``sizing_mode``
            must be ``"risk_budget"``; ``risk_budget_pct`` must be
            populated (already validated by the model). The notional
            floor / ceiling and ``min_stop_distance_bps`` are read off
            this same instance.

    Returns:
        A :class:`~decimal.Decimal` quantity (clamped to
        ``max_notional_per_trade`` when needed) on success, or a
        :class:`RiskSizingRejection` on any failure mode.
    """
    if account_equity is None or account_equity <= Decimal("0"):
        return RiskSizingRejection(
            reason="missing_equity",
            message="account equity unavailable; cannot apply risk-budget sizing",
        )

    if policy.risk_budget_pct is None:
        # Defended in the RiskPolicy validator, but defended again here
        # so misuse (caller invoking risk-budget path on a fixed-mode
        # account) surfaces a structured rejection rather than a None
        # arithmetic crash.
        return RiskSizingRejection(
            reason="missing_risk_budget",
            message="risk_policy.risk_budget_pct is required for risk-budget sizing",
        )

    # cross-account-risk-policy §"Risk-Based Sizing": signed
    # risk-per-unit so a wrong-side stop is caught explicitly.
    if side == "long":
        risk_per_unit = entry_price - stop_loss_price
    else:
        risk_per_unit = stop_loss_price - entry_price

    if risk_per_unit <= Decimal("0"):
        return RiskSizingRejection(
            reason="invalid_stop_distance",
            message=(
                f"stop_loss on wrong side of entry for {side}: "
                f"entry={entry_price} stop={stop_loss_price}"
            ),
        )

    # ``min_stop_distance_bps`` floor — proposals with stops tighter
    # than this floor are rejected outright rather than allowed to
    # consume the full notional ceiling.
    if policy.min_stop_distance_bps is not None:
        stop_distance_bps = (risk_per_unit / entry_price) * _BPS_DIVISOR
        floor_bps = Decimal(policy.min_stop_distance_bps)
        if stop_distance_bps < floor_bps:
            return RiskSizingRejection(
                reason="stop_too_tight",
                message=(
                    f"stop distance {stop_distance_bps:.2f}bps is below the "
                    f"per-account floor of {floor_bps}bps"
                ),
                details={
                    "stop_distance_bps": f"{stop_distance_bps:.4f}",
                    "min_stop_distance_bps": str(floor_bps),
                },
            )

    account_risk_budget = account_equity * policy.risk_budget_pct
    quantity = account_risk_budget / risk_per_unit
    notional = quantity * entry_price

    # ``max_notional_per_trade`` is a hard ceiling — clamp the
    # quantity down so a tight-stop proposal does not blow through
    # the per-trade ceiling. The ceiling is applied *before* the
    # ``min_notional_per_trade`` floor so a clamped trade that lands
    # below the floor still gets rejected as sub-minimum.
    if (
        policy.max_notional_per_trade is not None
        and notional > policy.max_notional_per_trade
    ):
        quantity = policy.max_notional_per_trade / entry_price
        notional = quantity * entry_price

    if (
        policy.min_notional_per_trade is not None
        and notional < policy.min_notional_per_trade
    ):
        return RiskSizingRejection(
            reason="below_min_notional",
            message=(
                f"sized notional {notional:.4f} is below the per-account "
                f"floor {policy.min_notional_per_trade}"
            ),
            details={
                "sized_notional": f"{notional:.4f}",
                "min_notional_per_trade": str(policy.min_notional_per_trade),
            },
        )

    return quantity


__all__ = [
    "RiskSizingRejection",
    "RiskSizingRejectionReason",
    "compute_risk_budget_size",
]
