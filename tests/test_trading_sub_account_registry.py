"""Tests for ``src.trading.sub_account_registry`` (Phase 19.1).

Phase 19.1 contract: when ``config_path`` does not exist, the
registry materialises one synthesised ``default`` ``SubAccount`` from
``Settings``. ``get_trader`` returns the single shared trader for any
registered id; unknown ids raise.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.config import ExchangeCredential, Settings
from src.runtime.activity_log import ActivityLog
from src.strategy.base import BaseStrategy, TechniqueInfo
from src.strategy.loader import load_all_strategies
from src.trading.live import LiveTrader
from src.trading.paper import PaperTrader
from src.trading.sub_account import (
    CapitalPolicy,
    RiskOverrides,
    StrategyPolicy,
    SubAccount,
    SubAccountNotFoundError,
)
from src.trading.sub_account_registry import (
    DEFAULT_SUB_ACCOUNT_ID,
    MissingExchangeCredentialsError,
    SubAccountConfigError,
    SubAccountRegistry,
)


def _make_settings(
    *,
    mode: str = "paper",
    initial_balance: float = 10000.0,
    exchange_credentials: dict[str, ExchangeCredential] | None = None,
) -> Settings:
    """Build a ``Settings`` snapshot with explicit fields.

    Avoids touching the user's real ``.env``.
    """
    return Settings(
        trading_mode=mode,  # type: ignore[arg-type]
        paper_initial_balance=initial_balance,
        exchange_credentials=exchange_credentials or {},
    )


def _make_trader() -> Any:
    """Stub trader. The registry only stores the reference; it does
    not call any ``Trader`` method in 19.1."""
    return MagicMock()


class _StubStrategy(BaseStrategy):
    """Minimal ``BaseStrategy`` so ``filter_strategies`` has a real
    object to filter on. ``analyze`` is never invoked here."""

    async def analyze(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


def _stub_strategy(name: str) -> _StubStrategy:
    return _StubStrategy(
        info=TechniqueInfo(
            name=name,
            version="1.0.0",
            description="stub",
            technique_type="code",
        )
    )


# =============================================================================
# Default-materialisation
# =============================================================================


def test_default_materialisation_reads_settings(tmp_path: Path) -> None:
    """Absent config file → registry synthesises one ``default``
    ``SubAccount`` whose mode and seed balance come from ``Settings``.

    Two subcases inline: paper-mode reads ``paper_initial_balance``
    onto ``USDT`` seed; live-mode propagates onto ``mode`` and keeps
    the conventional ``"default"`` ``exchange_ref`` so the live-
    requires-exchange-ref invariant is satisfied without a config
    file.
    """
    # Paper-mode + custom seed balance.
    settings = _make_settings(mode="paper", initial_balance=12345.0)
    registry = SubAccountRegistry(
        settings=settings,
        trader=_make_trader(),
        # Pin to a non-existent path so the synth-from-Settings
        # branch fires regardless of CWD.
        config_path=tmp_path / "missing-sub-accounts.yaml",
    )

    sub = registry.get(DEFAULT_SUB_ACCOUNT_ID)
    assert sub.id == DEFAULT_SUB_ACCOUNT_ID
    assert sub.name == "Default Account"
    assert sub.mode == "paper"
    assert sub.exchange_ref == "default"
    assert sub.initial_balance == {}
    assert sub.capital_policy == CapitalPolicy(
        initial_balance={"USDT": Decimal("12345.0")}
    )
    assert sub.strategy_filter is None
    assert sub.strategy_policy == StrategyPolicy(strategy_filter=None)
    assert sub.effective_initial_balance() == {"USDT": Decimal("12345.0")}
    assert sub.effective_strategy_filter() is None
    assert sub.risk_overrides == RiskOverrides()
    assert sub.enabled is True

    # Live-mode picks up the trading mode from Settings.
    live_registry = SubAccountRegistry(
        settings=_make_settings(mode="live"),
        trader=_make_trader(),
        config_path=tmp_path / "missing-live.yaml",
    )
    live_sub = live_registry.get(DEFAULT_SUB_ACCOUNT_ID)
    assert live_sub.mode == "live"
    assert live_sub.exchange_ref == "default"


# =============================================================================
# Public API
# =============================================================================


def test_list_active_returns_only_enabled_sub_accounts(tmp_path: Path) -> None:
    """``list_active`` excludes disabled records. 19.1 has only the
    enabled ``default`` so this is one entry; we assert the shape so
    19.3's multi-sub-account loader inherits the contract."""
    settings = _make_settings()
    registry = SubAccountRegistry(
        settings=settings,
        trader=_make_trader(),
        config_path=tmp_path / "missing.yaml",
    )

    active = registry.list_active()
    assert [s.id for s in active] == [DEFAULT_SUB_ACCOUNT_ID]
    assert all(s.enabled for s in active)


def test_get_returns_registered_sub_account(tmp_path: Path) -> None:
    """``get`` returns the registered record by id."""
    settings = _make_settings()
    registry = SubAccountRegistry(
        settings=settings,
        trader=_make_trader(),
        config_path=tmp_path / "missing.yaml",
    )

    sub = registry.get(DEFAULT_SUB_ACCOUNT_ID)
    assert isinstance(sub, SubAccount)
    assert sub.id == DEFAULT_SUB_ACCOUNT_ID


def test_get_unknown_id_raises(tmp_path: Path) -> None:
    """Unknown id raises ``SubAccountNotFoundError`` so a typo in a
    consumer surfaces here rather than as a silent wrong-bucket
    write later."""
    settings = _make_settings()
    registry = SubAccountRegistry(
        settings=settings,
        trader=_make_trader(),
        config_path=tmp_path / "missing.yaml",
    )

    with pytest.raises(SubAccountNotFoundError, match="experimental"):
        registry.get("experimental")


def test_get_trader_returns_shared_instance(tmp_path: Path) -> None:
    """19.1 returns the single shared ``Trader`` regardless of id;
    19.2 will replace this with a per-sub-account map. Unknown id
    still raises (validated through ``get``)."""
    settings = _make_settings()
    trader = _make_trader()
    registry = SubAccountRegistry(
        settings=settings,
        trader=trader,
        config_path=tmp_path / "missing.yaml",
    )

    assert registry.get_trader(DEFAULT_SUB_ACCOUNT_ID) is trader
    with pytest.raises(SubAccountNotFoundError):
        registry.get_trader("experimental")


# =============================================================================
# filter_strategies
# =============================================================================


def test_filter_strategies_passthrough_when_filter_is_none(tmp_path: Path) -> None:
    """``strategy_filter is None`` → registry returns the input list
    unchanged. This is the 19.1 default for the synthesised
    ``default`` sub-account; the back-compat single-seed deployment
    sees every loaded technique."""
    settings = _make_settings()
    registry = SubAccountRegistry(
        settings=settings,
        trader=_make_trader(),
        config_path=tmp_path / "missing.yaml",
    )

    available = [_stub_strategy("rsi_4h"), _stub_strategy("bollinger")]
    filtered = registry.filter_strategies(DEFAULT_SUB_ACCOUNT_ID, available)
    assert filtered == available


def test_filter_strategies_narrows_to_whitelist(tmp_path: Path) -> None:
    """A non-``None`` ``strategy_filter`` narrows ``available`` to its
    whitelist. 19.1 always materialises ``strategy_filter=None`` from
    settings, so we exercise the path by injecting a custom registry
    record post-construction. Order from ``available`` is preserved
    so ranking-sensitive callers see no shuffle.
    """
    settings = _make_settings()
    registry = SubAccountRegistry(
        settings=settings,
        trader=_make_trader(),
        config_path=tmp_path / "missing.yaml",
    )
    # Replace the default record with one carrying a whitelist. This
    # is a test seam — the public 19.3 path will be a YAML config
    # field; the seam exercises the ``filter_strategies`` branch
    # without waiting for that.
    registry._sub_accounts[DEFAULT_SUB_ACCOUNT_ID] = SubAccount(
        id=DEFAULT_SUB_ACCOUNT_ID,
        name="Default Account",
        mode="paper",
        exchange_ref="default",
        initial_balance={"USDT": Decimal("10000")},
        strategy_filter=["rsi_4h"],
    )

    available = [
        _stub_strategy("rsi_4h"),
        _stub_strategy("bollinger"),
        _stub_strategy("breakout"),
    ]
    filtered = registry.filter_strategies(DEFAULT_SUB_ACCOUNT_ID, available)
    assert [s.info.name for s in filtered] == ["rsi_4h"]


# =============================================================================
# YAML config loading (Phase 19.3)
# =============================================================================


def _write_sub_accounts_config(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_yaml_config_happy_path_three_sub_accounts(tmp_path: Path) -> None:
    config_path = tmp_path / "sub_accounts.yaml"
    _write_sub_accounts_config(
        config_path,
        """
sub_accounts:
  - id: default
    name: Default
    mode: paper
    exchange_ref: default
    initial_balance: {USDT: 10000}
    strategy_filter: null
    enabled: true
  - id: btc_only
    name: BTC Only
    mode: paper
    exchange_ref: default
    initial_balance: {USDT: 5000}
    strategy_filter: [rsi_4h]
    enabled: true
  - id: experimental
    name: Experimental
    mode: paper
    exchange_ref: default
    initial_balance: {USDT: 2500}
    notification_route: lab
    risk_overrides:
      risk_percent: 0.5
      max_open_positions_total: 1
    enabled: false
""",
    )

    registry = SubAccountRegistry(
        settings=_make_settings(),
        trader=_make_trader(),
        config_path=config_path,
    )

    assert [sub.id for sub in registry.list_active()] == ["default", "btc_only"]
    assert registry.get("experimental").enabled is False
    assert registry.get("btc_only").strategy_filter == ["rsi_4h"]
    assert registry.get("experimental").risk_overrides.risk_percent == Decimal("0.5")
    assert registry.get("experimental").notification_route == "lab"
    assert registry.get_trader("btc_only") is not registry.get_trader("default")


def test_yaml_paper_sub_account_inherits_runtime_wiring(tmp_path: Path) -> None:
    config_path = tmp_path / "sub_accounts.yaml"
    _write_sub_accounts_config(
        config_path,
        """
sub_accounts:
  - id: default
    name: Default
    mode: paper
    exchange_ref: default
    initial_balance: {USDT: 10000}
  - id: lab
    name: Lab
    mode: paper
    exchange_ref: default
    initial_balance: {USDT: 2500}
""",
    )
    exchange = MagicMock()
    exchange.testnet = True
    exchange.name = "binance"
    activity_log = ActivityLog(path=tmp_path / "activity.jsonl")

    registry = SubAccountRegistry(
        settings=_make_settings(),
        trader=_make_trader(),
        config_path=config_path,
        exchange=exchange,
        activity_log=activity_log,
        paper_auto_deposit_on_liquidation=True,
    )

    trader = registry.get_trader("lab")
    assert isinstance(trader, PaperTrader)
    assert trader._exchange is exchange
    assert trader._activity_log is activity_log
    assert trader._auto_deposit_on_liquidation is True


def test_committed_sub_account_config_filters_existing_strategies() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    registry = SubAccountRegistry(
        settings=_make_settings(),
        trader=_make_trader(),
        config_path=repo_root / "config" / "sub_accounts.yaml",
    )
    strategies = load_all_strategies(repo_root / "strategies")
    strategy_names = set(strategies)
    active = registry.list_active()

    assert len(active) == 12
    for sub in active:
        strategy_filter = sub.effective_strategy_filter()
        assert strategy_filter is not None
        assert len(strategy_filter) == 1
        assert strategy_filter[0] in strategy_names


def test_yaml_config_live_sub_account_uses_named_credentials(tmp_path: Path) -> None:
    config_path = tmp_path / "sub_accounts.yaml"
    _write_sub_accounts_config(
        config_path,
        """
sub_accounts:
  - id: live_alt
    name: Live Alt
    mode: live
    exchange_ref: binance_alt
    initial_balance: {USDT: 10000}
""",
    )

    registry = SubAccountRegistry(
        settings=_make_settings(
            mode="live",
            exchange_credentials={
                "binance_alt": ExchangeCredential(
                    ref="binance_alt",
                    exchange="binance",
                    api_key="alt-key",
                    api_secret="alt-secret",
                    testnet=False,
                )
            },
        ),
        trader=_make_trader(),
        config_path=config_path,
    )

    trader = registry.get_trader("live_alt")
    assert isinstance(trader, LiveTrader)
    assert trader.exchange.config.api_key == "alt-key"


def test_yaml_config_paper_sub_account_uses_named_exchange_for_market_data(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "sub_accounts.yaml"
    _write_sub_accounts_config(
        config_path,
        """
sub_accounts:
  - id: paper_alt
    name: Paper Alt
    mode: paper
    exchange_ref: binance_alt
    initial_balance: {USDT: 10000}
""",
    )

    registry = SubAccountRegistry(
        settings=_make_settings(
            exchange_credentials={
                "binance_alt": ExchangeCredential(
                    ref="binance_alt",
                    exchange="binance",
                    api_key="alt-key",
                    api_secret="alt-secret",
                    testnet=True,
                )
            },
        ),
        trader=_make_trader(),
        config_path=config_path,
    )

    trader = registry.get_trader("paper_alt")
    assert isinstance(trader, PaperTrader)
    assert trader.exchange is not None
    assert trader.exchange.config.api_key == "alt-key"
    assert trader.exchange.testnet is True


def test_yaml_config_rejects_live_missing_credentials(tmp_path: Path) -> None:
    config_path = tmp_path / "sub_accounts.yaml"
    _write_sub_accounts_config(
        config_path,
        """
sub_accounts:
  - id: live_alt
    name: Live Alt
    mode: live
    exchange_ref: binance_alt
    initial_balance: {USDT: 10000}
""",
    )

    with pytest.raises(MissingExchangeCredentialsError, match="binance_alt"):
        SubAccountRegistry(
            settings=_make_settings(mode="live"),
            trader=_make_trader(),
            config_path=config_path,
        )


def test_yaml_config_rejects_duplicate_ids(tmp_path: Path) -> None:
    config_path = tmp_path / "sub_accounts.yaml"
    _write_sub_accounts_config(
        config_path,
        """
sub_accounts:
  - id: default
    name: One
    mode: paper
    initial_balance: {USDT: 10000}
  - id: default
    name: Two
    mode: paper
    initial_balance: {USDT: 5000}
""",
    )

    with pytest.raises(SubAccountConfigError, match="duplicate"):
        SubAccountRegistry(
            settings=_make_settings(),
            trader=_make_trader(),
            config_path=config_path,
        )


def test_yaml_config_rejects_unresolved_exchange_ref(tmp_path: Path) -> None:
    config_path = tmp_path / "sub_accounts.yaml"
    _write_sub_accounts_config(
        config_path,
        """
sub_accounts:
  - id: alt
    name: Alt
    mode: paper
    exchange_ref: binance_alt
    initial_balance: {USDT: 10000}
""",
    )

    with pytest.raises(SubAccountConfigError, match="exchange_ref"):
        SubAccountRegistry(
            settings=_make_settings(),
            trader=_make_trader(),
            config_path=config_path,
        )
