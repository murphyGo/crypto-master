"""Tests for ``src.trading.sub_account`` (Phase 19.1).

Covers the ``SubAccount`` model's three validators and its frozen
behaviour. The registry-side and migration-side behaviour live in
sibling test files (``test_trading_sub_account_registry.py`` /
``test_trading_sub_account_migration.py``).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.trading.sub_account import (
    CapitalPolicy,
    ExecutionPolicy,
    MarketRegimePolicy,
    ProposalPolicy,
    RiskOverrides,
    RiskPolicy,
    StrategyPolicy,
    SubAccount,
)


def test_id_regex_accepts_valid_filesystem_safe_keys() -> None:
    """``id`` matches ``^[a-z][a-z0-9_]*$``: lowercase, digits,
    underscore, leading letter. The set covered here mirrors the
    canonical examples from DESIGN.md §9.2 plus a single-char edge."""
    for valid in ("default", "main", "btc_only", "alt2", "a", "a1_b2"):
        sa = SubAccount(id=valid, name="x", mode="paper")
        assert sa.id == valid


def test_id_regex_rejects_unsafe_keys() -> None:
    """Path-unsafe shapes raise at construction so directory creation
    under ``data/.../{id}/...`` never sees them."""
    invalid_ids = [
        "Default",  # uppercase letter
        "1main",  # leading digit
        "_main",  # leading underscore
        "btc-only",  # hyphen
        "btc.alt",  # dot
        "btc only",  # whitespace
        "../escape",  # path traversal
    ]
    for invalid in invalid_ids:
        with pytest.raises(ValidationError):
            SubAccount(id=invalid, name="x", mode="paper")


def test_enabled_live_requires_exchange_ref() -> None:
    """DESIGN.md §9.7: an enabled live sub-account whose
    ``exchange_ref`` is ``None`` is a startup failure — silent
    fallback would leak risk. We catch it at the model boundary so
    the wiring layer doesn't need a second check.

    Disabled live records and paper records are intentionally exempt:
    operators stage future-live records before credentials are wired,
    and paper mode covers the single-account case via testnet keys.
    """
    # Hard reject: enabled live without exchange_ref.
    with pytest.raises(ValidationError, match="exchange_ref"):
        SubAccount(id="m", name="x", mode="live", exchange_ref=None, enabled=True)

    # Accepted: enabled live WITH exchange_ref.
    sa_live = SubAccount(
        id="m",
        name="x",
        mode="live",
        exchange_ref="binance_main",
        enabled=True,
    )
    assert sa_live.exchange_ref == "binance_main"

    # Accepted: disabled live without exchange_ref.
    sa_disabled = SubAccount(
        id="m", name="x", mode="live", exchange_ref=None, enabled=False
    )
    assert sa_disabled.enabled is False

    # Accepted: paper without exchange_ref.
    sa_paper = SubAccount(id="m", name="x", mode="paper", exchange_ref=None)
    assert sa_paper.exchange_ref is None


def test_initial_balance_keys_must_be_upper_case() -> None:
    """``Balance`` records elsewhere normalise on upper-case
    (``"USDT"`` / ``"BTC"``); a lower-case or mixed-case key would
    silently bifurcate the ``PaperTrader`` ledger from the rest of
    the codebase. The validator rejects both shapes."""
    with pytest.raises(ValidationError, match="upper-case"):
        SubAccount(
            id="m",
            name="x",
            mode="paper",
            initial_balance={"usdt": Decimal("10000")},
        )

    with pytest.raises(ValidationError, match="upper-case"):
        SubAccount(
            id="m",
            name="x",
            mode="paper",
            initial_balance={"Usdt": Decimal("10000")},
        )

    sa = SubAccount(
        id="m",
        name="x",
        mode="paper",
        initial_balance={"USDT": Decimal("10000"), "BTC": Decimal("0.1")},
    )
    assert sa.initial_balance == {
        "USDT": Decimal("10000"),
        "BTC": Decimal("0.1"),
    }


def test_sub_account_is_frozen() -> None:
    """Frozen so registry consumers cannot mutate behind the
    registry's back; any change requires a fresh instance."""
    sa = SubAccount(id="m", name="x", mode="paper")
    with pytest.raises(ValidationError):
        sa.id = "other"  # type: ignore[misc]


def test_risk_overrides_defaults_and_validation() -> None:
    """``RiskOverrides`` defaults to all-``None`` (fall through to
    engine globals); non-None fields enforce the same bounds as the
    engine-wide knobs they shadow. Frozen for the same reason as
    ``SubAccount``."""
    ro = RiskOverrides()
    assert ro.risk_percent is None
    assert ro.max_open_positions_total is None
    assert ro.max_open_positions_per_symbol is None
    assert ro.leverage_cap is None
    assert ro.auto_approve_threshold is None

    # Bounds enforcement.
    with pytest.raises(ValidationError):
        RiskOverrides(max_open_positions_total=0)
    with pytest.raises(ValidationError):
        RiskOverrides(leverage_cap=200)

    # Frozen.
    ro2 = RiskOverrides(risk_percent=Decimal("1.5"))
    with pytest.raises(ValidationError):
        ro2.risk_percent = Decimal("2.0")  # type: ignore[misc]


def test_policy_models_validate_and_are_frozen() -> None:
    capital = CapitalPolicy(
        initial_balance={"USDT": Decimal("10000")},
        sizing_balance=Decimal("7500"),
    )
    strategy = StrategyPolicy(strategy_filter=["rsi_4h"], symbols=["BTC/USDT"])
    proposal = ProposalPolicy(auto_approve_threshold=0.0, notify_min_score=0.0)
    risk = RiskPolicy(risk_percent=Decimal("0.5"), leverage_cap=2)
    execution = ExecutionPolicy(
        reject_if_past_stop_loss=False,
        reject_if_stale_quote=False,
        fill_slippage_tolerance=Decimal("1"),
    )

    assert capital.initial_balance == {"USDT": Decimal("10000")}
    assert strategy.strategy_filter == ["rsi_4h"]
    assert proposal.auto_approve_threshold == 0.0
    assert risk.leverage_cap == 2
    assert execution.reject_if_stale_quote is False
    with pytest.raises(ValidationError):
        strategy.strategy_filter = ["other"]  # type: ignore[misc]
    with pytest.raises(ValidationError):
        CapitalPolicy(initial_balance={"usdt": Decimal("10000")})
    with pytest.raises(ValidationError):
        StrategyPolicy(strategy_filter=[])


def test_sub_account_effective_policy_prefers_new_policy_blocks() -> None:
    sub = SubAccount(
        id="rsi_4h",
        name="RSI 4h",
        mode="paper",
        risk_overrides=RiskOverrides(
            risk_percent=Decimal("1"),
            auto_approve_threshold=2.0,
        ),
        capital_policy=CapitalPolicy(
            initial_balance={"USDT": Decimal("5000")},
            sizing_balance=Decimal("2500"),
        ),
        strategy_policy=StrategyPolicy(strategy_filter=["rsi_4h"]),
        proposal_policy=ProposalPolicy(auto_approve_threshold=0.0),
        risk_policy=RiskPolicy(risk_percent=Decimal("0.25")),
    )

    assert sub.effective_initial_balance() == {"USDT": Decimal("5000")}
    assert sub.effective_sizing_balance(Decimal("10000")) == Decimal("2500")
    assert sub.effective_strategy_filter() == ["rsi_4h"]
    assert sub.effective_risk_percent() == Decimal("0.25")
    assert sub.effective_auto_approve_threshold() == 0.0


def test_legacy_root_fields_match_policy_block_runtime() -> None:
    legacy = SubAccount(
        id="legacy",
        name="Legacy",
        mode="paper",
        initial_balance={"USDT": Decimal("10000")},
        strategy_filter=["rsi_4h"],
    )
    policy = SubAccount(
        id="policy",
        name="Policy",
        mode="paper",
        capital_policy=CapitalPolicy(initial_balance={"USDT": Decimal("10000")}),
        strategy_policy=StrategyPolicy(strategy_filter=["rsi_4h"]),
    )

    assert legacy.effective_initial_balance() == policy.effective_initial_balance()
    assert legacy.effective_strategy_filter() == policy.effective_strategy_filter()


def test_market_regime_policy_defaults_are_no_op() -> None:
    """Absent / default ``market_regime`` block leaves the account
    unchanged from pre-feature behaviour: gating disabled,
    BTC/USDT 4h reference, all three classifier labels allowed."""
    sub = SubAccount(id="m", name="x", mode="paper")
    assert sub.market_regime.enabled is False
    assert sub.market_regime.reference_symbol == "BTC/USDT"
    assert sub.market_regime.timeframe == "4h"
    assert sub.market_regime.allowed_regimes == ["bull", "bear", "sideways"]


def test_market_regime_policy_parses_valid_block() -> None:
    """An explicit block with a custom subset of regimes round-trips
    through the model unchanged. ``unknown`` is a legal label so
    accounts can opt-in to advisory pass-through on no-data."""
    policy = MarketRegimePolicy(
        enabled=True,
        reference_symbol="ETH/USDT",
        timeframe="1d",
        allowed_regimes=["sideways", "unknown"],
    )
    assert policy.enabled is True
    assert policy.reference_symbol == "ETH/USDT"
    assert policy.timeframe == "1d"
    assert policy.allowed_regimes == ["sideways", "unknown"]

    sub = SubAccount(
        id="mean_rev",
        name="Mean Reversion",
        mode="paper",
        market_regime=policy,
    )
    assert sub.market_regime is policy


def test_market_regime_policy_is_frozen() -> None:
    policy = MarketRegimePolicy(enabled=True, allowed_regimes=["bull"])
    with pytest.raises(ValidationError):
        policy.enabled = False  # type: ignore[misc]


def test_market_regime_policy_rejects_empty_allowed_regimes() -> None:
    """Spec §3: empty ``allowed_regimes`` is INVALID — gating with
    no allowed regime would silently block every proposal, which is
    almost certainly a config error rather than an operator intent."""
    with pytest.raises(ValidationError, match="at least one regime label"):
        MarketRegimePolicy(enabled=True, allowed_regimes=[])


def test_market_regime_policy_rejects_unknown_regime_values() -> None:
    """Typos in YAML must not be silently accepted — an unknown label
    would always fail-block at runtime which presents as a mysterious
    100% rejection rate. Reject at the config boundary instead."""
    with pytest.raises(ValidationError, match="invalid label"):
        MarketRegimePolicy(enabled=True, allowed_regimes=["bull", "trending"])


def test_dual_source_root_and_policy_fields_raise_clear_conflict() -> None:
    with pytest.raises(ValidationError, match="capital_policy.initial_balance"):
        SubAccount(
            id="dual_balance",
            name="Dual Balance",
            mode="paper",
            initial_balance={"USDT": Decimal("10000")},
            capital_policy=CapitalPolicy(initial_balance={"USDT": Decimal("10000")}),
        )

    with pytest.raises(ValidationError, match="strategy_policy.strategy_filter"):
        SubAccount(
            id="dual_strategy",
            name="Dual Strategy",
            mode="paper",
            strategy_filter=["legacy"],
            strategy_policy=StrategyPolicy(strategy_filter=["legacy"]),
        )
