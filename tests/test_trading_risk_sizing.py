"""Tests for ``src.trading.risk_sizing``.

cross-account-risk-policy §"Risk-Based Sizing" — pure-formula coverage
plus every rejection-reason branch. Mirrors the test density of the
existing risk-policy parsing tests (``test_trading_sub_account.py``).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.trading.risk_sizing import RiskSizingRejection, compute_risk_budget_size
from src.trading.sub_account import RiskPolicy


def _risk_policy(**overrides: object) -> RiskPolicy:
    """Build a ``risk_budget``-mode policy with sane defaults for tests.

    The public ``RiskPolicy`` validator currently rejects
    ``sizing_mode='risk_budget'`` until Slice 2 wires the helper into
    ``ProposalEngine`` (DEBT-068). These tests exercise the helper
    formula directly, so we use ``model_construct`` to bypass that
    config-time gate — the helper is unit-tested in isolation here,
    and the gate is tested separately below.
    """
    base: dict[str, object] = {
        "sizing_mode": "risk_budget",
        "risk_budget_pct": Decimal("0.005"),
    }
    base.update(overrides)
    return RiskPolicy.model_construct(**base)


def test_long_sizing_formula_returns_expected_quantity() -> None:
    """Long: ``Q = (E * pct) / (entry - stop)`` exact decimal arithmetic."""
    policy = _risk_policy()  # 0.5% per trade
    qty = compute_risk_budget_size(
        account_equity=Decimal("10000"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("95"),
        side="long",
        policy=policy,
    )
    # account_risk_budget = 10000 * 0.005 = 50
    # risk_per_unit = 100 - 95 = 5 => qty = 50 / 5 = 10
    assert isinstance(qty, Decimal)
    assert qty == Decimal("10")


def test_short_sizing_formula_returns_expected_quantity() -> None:
    """Short: ``Q = (E * pct) / (stop - entry)`` exact decimal arithmetic."""
    policy = _risk_policy()
    qty = compute_risk_budget_size(
        account_equity=Decimal("10000"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("105"),
        side="short",
        policy=policy,
    )
    # risk_per_unit = 105 - 100 = 5 => qty = 50 / 5 = 10
    assert qty == Decimal("10")


def test_wrong_side_stop_returns_invalid_stop_distance() -> None:
    """Stop on the wrong side of entry is rejected outright (no math)."""
    policy = _risk_policy()
    rejection = compute_risk_budget_size(
        account_equity=Decimal("10000"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("105"),  # higher than entry but side=long
        side="long",
        policy=policy,
    )
    assert isinstance(rejection, RiskSizingRejection)
    assert rejection.reason == "invalid_stop_distance"


def test_missing_equity_returns_structured_rejection() -> None:
    """Spec: missing equity must reject, not silent-fallback."""
    policy = _risk_policy()
    rejection = compute_risk_budget_size(
        account_equity=None,
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("95"),
        side="long",
        policy=policy,
    )
    assert isinstance(rejection, RiskSizingRejection)
    assert rejection.reason == "missing_equity"


def test_zero_equity_returns_missing_equity() -> None:
    """Equity <= 0 is treated as "missing" — no silent zero-sized fill."""
    policy = _risk_policy()
    rejection = compute_risk_budget_size(
        account_equity=Decimal("0"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("95"),
        side="long",
        policy=policy,
    )
    assert isinstance(rejection, RiskSizingRejection)
    assert rejection.reason == "missing_equity"


def test_stop_too_tight_below_bps_floor_rejects() -> None:
    """``min_stop_distance_bps`` rejects sub-floor stops before sizing."""
    # 100bps = 1% — entry 100, stop 99.5 = 50bps which is below the floor.
    policy = _risk_policy(min_stop_distance_bps=100)
    rejection = compute_risk_budget_size(
        account_equity=Decimal("10000"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("99.5"),
        side="long",
        policy=policy,
    )
    assert isinstance(rejection, RiskSizingRejection)
    assert rejection.reason == "stop_too_tight"
    assert rejection.details is not None
    assert "stop_distance_bps" in rejection.details


def test_max_notional_per_trade_clamps_down_quantity() -> None:
    """Tight stop produces oversized notional — clamp to the ceiling."""
    # entry=100, stop=99.9 (10bps) => risk_per_unit=0.1
    # budget=50 => Q=500, notional=50000. Cap notional at 1000 => Q=10.
    policy = _risk_policy(max_notional_per_trade=Decimal("1000"))
    qty = compute_risk_budget_size(
        account_equity=Decimal("10000"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("99.9"),
        side="long",
        policy=policy,
    )
    assert isinstance(qty, Decimal)
    assert qty == Decimal("10")


def test_min_notional_per_trade_rejects_sub_floor_size() -> None:
    """Sub-floor sized trades are rejected, not silently rounded up."""
    # entry=100, stop=50 (huge stop) => risk_per_unit=50; budget=50; Q=1; notional=100.
    # Floor at 200 => reject.
    policy = _risk_policy(min_notional_per_trade=Decimal("200"))
    rejection = compute_risk_budget_size(
        account_equity=Decimal("10000"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("50"),
        side="long",
        policy=policy,
    )
    assert isinstance(rejection, RiskSizingRejection)
    assert rejection.reason == "below_min_notional"


def test_clamped_to_max_still_above_min_returns_quantity() -> None:
    """Clamp-down lands at the ceiling; with equal floor it's still accepted.

    Pins the order-of-operations: max clamp first, then min floor. A
    clamped trade that equals the floor must pass — the floor is
    ``<``, not ``<=``.
    """
    # entry=100, stop=99.5 (50bps) => risk_per_unit=0.5; budget=50; Q=100; notional=10000.
    # Cap notional at 50 => Q=0.5, notional=50. Floor at 50 => accept (not below).
    policy = _risk_policy(
        max_notional_per_trade=Decimal("50"),
        min_notional_per_trade=Decimal("50"),
    )
    qty = compute_risk_budget_size(
        account_equity=Decimal("10000"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("99.5"),
        side="long",
        policy=policy,
    )
    assert isinstance(qty, Decimal)
    assert qty == Decimal("0.5")


def test_decimal_arithmetic_no_float_contamination() -> None:
    """Sized quantity is exact Decimal, not float-rounded."""
    # 0.333% of 9999 = 33.296670; risk_per_unit = 0.07; Q ≈ 475.66671428...
    # Exact division is fine; ensure the returned type is Decimal.
    policy = _risk_policy(risk_budget_pct=Decimal("0.00333"))
    qty = compute_risk_budget_size(
        account_equity=Decimal("9999"),
        entry_price=Decimal("100.07"),
        stop_loss_price=Decimal("100"),
        side="long",
        policy=policy,
    )
    assert isinstance(qty, Decimal)
    # Recompute exactly via Decimal:
    expected = (Decimal("9999") * Decimal("0.00333")) / Decimal("0.07")
    assert qty == expected


def test_risk_policy_validator_rejects_risk_budget_without_pct() -> None:
    """Model-level invariant: risk-budget mode requires a risk budget."""
    with pytest.raises(ValueError):
        RiskPolicy(sizing_mode="risk_budget")


def test_risk_policy_accepts_risk_budget_mode_when_pct_is_configured() -> None:
    """DEBT-068(a): runtime now wires the helper, so config can opt in."""
    policy = RiskPolicy(
        sizing_mode="risk_budget",
        risk_budget_pct=Decimal("0.005"),
    )
    assert policy.sizing_mode == "risk_budget"
    assert policy.risk_budget_pct == Decimal("0.005")


def test_risk_policy_validator_rejects_inverted_notional_bounds() -> None:
    """``min_notional_per_trade`` > ``max_notional_per_trade`` is a config bug."""
    with pytest.raises(ValueError, match="min_notional_per_trade"):
        RiskPolicy(
            sizing_mode="fixed_notional",
            min_notional_per_trade=Decimal("1000"),
            max_notional_per_trade=Decimal("500"),
        )


def test_risk_policy_stale_action_requires_max_hours() -> None:
    """``stale_position_action`` without ``max_time_in_position_hours`` fails."""
    with pytest.raises(ValueError, match="max_time_in_position_hours"):
        RiskPolicy(stale_position_action="block_new_entries")
