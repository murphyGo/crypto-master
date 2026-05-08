"""Sub-account registry (Phase 19.1 — single ``default`` materialisation).

The registry is the runtime's source of truth for which sub-accounts
exist, which trader each one is bound to, and which strategies a
given sub-account is allowed to run. Phase 19.1 ships the **seam**:
the registry holds exactly one synthesised ``default`` entry derived
from ``Settings`` (no YAML parsing yet — that's 19.3) and hands back
the same shared ``Trader`` instance ``build_trader`` already
constructs today, just addressed by ``id="default"``.

Phase 19.2 will populate per-sub-account ``Trader`` instances behind
``get_trader``; phase 19.3 will populate ``__init__`` from a YAML
config file. Both surfaces are stubbed here so callers can begin
threading the registry through the engine without further signature
churn.

Related Requirements:
- FR-036: Sub-Account Capital Isolation (single-account
  materialisation is the back-compat floor for 19.1).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.config import ExchangeCredential, Settings
from src.exchange.base import BaseExchange
from src.exchange.binance import BinanceExchange
from src.exchange.bybit import BybitExchange
from src.runtime.activity_log import ActivityLog
from src.strategy.base import BaseStrategy
from src.trading.base import Trader
from src.trading.live import LiveTrader
from src.trading.paper import PaperTrader
from src.trading.sub_account import (
    CapitalPolicy,
    RiskOverrides,
    StrategyPolicy,
    SubAccount,
    SubAccountError,
    SubAccountNotFoundError,
)

# Default config-file location. 19.3 will parse this; 19.1 only
# falls through to the synthesised-from-Settings path when the file
# is absent (which is the 19.1 default for every deployment).
DEFAULT_CONFIG_PATH = Path("config/sub_accounts.yaml")

# The id reserved for the auto-materialised back-compat sub-account.
DEFAULT_SUB_ACCOUNT_ID = "default"


class SubAccountConfigError(SubAccountError):
    """Raised when ``config/sub_accounts.yaml`` is present but invalid."""


class MissingExchangeCredentialsError(SubAccountConfigError):
    """Raised when a live sub-account references missing credentials."""


class SubAccountRegistry:
    """In-memory registry of active sub-accounts.

    19.1 contract: when ``config_path`` does not exist on disk, the
    registry materialises one synthesised ``SubAccount(id="default",
    ...)`` whose fields come from ``Settings`` (mode, paper seed
    balance). The single ``Trader`` passed at construction time is
    handed back from ``get_trader`` regardless of id (only ``default``
    exists at this stage anyway).

    Attributes:
        settings: ``Settings`` snapshot used to seed the default
            sub-account when no config file is present.
        config_path: Path to the YAML config (parsed in 19.3). 19.1
            only checks for absence to pick the default-materialisation
            branch.
    """

    def __init__(
        self,
        settings: Settings,
        trader: Trader,
        config_path: Path | None = None,
        exchange: BaseExchange | None = None,
        activity_log: ActivityLog | None = None,
        paper_auto_deposit_on_liquidation: bool = False,
    ) -> None:
        """Build the registry.

        Args:
            settings: Snapshot of application settings. Read-only —
                mutating after construction is not supported.
            trader: The single shared ``Trader`` instance the registry
                returns from :meth:`get_trader` for every sub-account
                in 19.1. 19.2 will replace this with a per-sub-account
                trader map.
            config_path: Optional override for the YAML config file
                location. Defaults to ``config/sub_accounts.yaml``.
                19.1 only inspects whether the file exists; YAML
                parsing arrives in 19.3.
        """
        self.settings = settings
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.exchange = exchange
        self.activity_log = activity_log
        self.paper_auto_deposit_on_liquidation = paper_auto_deposit_on_liquidation

        # Single shared trader — the wiring seam for 19.2's per-sub
        # trader map. The default sub-account keeps this exact object;
        # YAML-loaded paper siblings get isolated PaperTrader instances.
        self._trader = trader
        self._traders: dict[str, Trader] = {}
        self._owned_live_exchanges: list[BinanceExchange | BybitExchange] = []

        # Stable insertion order keeps ``list_active`` deterministic
        # for tests and dashboards.
        self._sub_accounts: dict[str, SubAccount] = {}
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Populate ``self._sub_accounts``.

        19.1 always takes the fall-through branch: synthesise one
        ``default`` sub-account from ``Settings``. 19.3 will replace
        this with a YAML loader; the absence-check on
        ``self.config_path`` is the seam.
        """
        if self.config_path.exists():
            self._load_from_yaml()
            return

        default = self._materialise_default()
        self._sub_accounts[default.id] = default
        self._traders[default.id] = self._trader

    def _load_from_yaml(self) -> None:
        """Parse ``config/sub_accounts.yaml`` into validated accounts."""
        raw_accounts = self._read_config_file()
        seen: set[str] = set()
        for index, raw in enumerate(raw_accounts, start=1):
            if not isinstance(raw, dict):
                raise SubAccountConfigError(
                    f"{self.config_path}: sub_accounts[{index}] must be a mapping"
                )
            try:
                sub = SubAccount(**raw)
            except ValidationError as exc:
                raise SubAccountConfigError(
                    f"{self.config_path}: invalid sub_accounts[{index}]: {exc}"
                ) from exc
            if sub.id in seen:
                raise SubAccountConfigError(
                    f"{self.config_path}: duplicate sub-account id {sub.id!r}"
                )
            seen.add(sub.id)
            self._validate_phase_19_3_boundaries(sub)
            self._sub_accounts[sub.id] = sub
            self._traders[sub.id] = self._build_trader_for(sub)

        if not self._sub_accounts:
            raise SubAccountConfigError(
                f"{self.config_path}: sub_accounts must contain at least one entry"
            )

    def _read_config_file(self) -> list[Any]:
        try:
            with self.config_path.open("r", encoding="utf-8") as fh:
                parsed = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise SubAccountConfigError(
                f"failed to read sub-account config {self.config_path}: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise SubAccountConfigError(
                f"{self.config_path}: top-level YAML document must be a mapping"
            )
        accounts = parsed.get("sub_accounts")
        if not isinstance(accounts, list):
            raise SubAccountConfigError(
                f"{self.config_path}: sub_accounts must be a list"
            )
        return accounts

    def _validate_phase_19_3_boundaries(self, sub: SubAccount) -> None:
        if sub.mode == "live":
            if sub.exchange_ref == "default" and sub.id == DEFAULT_SUB_ACCOUNT_ID:
                return
            if sub.exchange_ref is None:
                raise MissingExchangeCredentialsError(
                    f"live sub-account {sub.id!r} must declare exchange_ref"
                )
            if sub.exchange_ref not in self.settings.exchange_credentials:
                raise MissingExchangeCredentialsError(
                    f"live sub-account {sub.id!r} references exchange_ref "
                    f"{sub.exchange_ref!r}, but no matching credentials are configured"
                )
            return

        if sub.exchange_ref in (None, "default"):
            return
        configured = set(self.settings.get_configured_exchanges()) | set(
            self.settings.get_configured_exchange_refs()
        )
        if sub.exchange_ref not in configured:
            raise SubAccountConfigError(
                f"sub-account {sub.id!r} references exchange_ref "
                f"{sub.exchange_ref!r}, but configured exchanges are "
                f"{sorted(configured) or ['default']}"
            )

    def _build_trader_for(self, sub: SubAccount) -> Trader:
        if sub.id == DEFAULT_SUB_ACCOUNT_ID and sub.exchange_ref in (None, "default"):
            return self._trader
        if sub.mode == "paper":
            exchange = self.exchange
            if sub.exchange_ref not in (None, "default"):
                exchange_ref = sub.exchange_ref
                if exchange_ref is None:
                    raise SubAccountConfigError(
                        f"paper sub-account {sub.id!r} has no exchange_ref"
                    )
                credential = self.settings.exchange_credentials.get(exchange_ref)
                if credential is not None:
                    exchange = self._exchange_from_credential(credential)
                    self._owned_live_exchanges.append(exchange)
            return PaperTrader(
                initial_balance=sub.effective_initial_balance(),
                data_dir=self.settings.data_dir / "trades",
                exchange=exchange,
                activity_log=self.activity_log,
                auto_deposit_on_liquidation=self.paper_auto_deposit_on_liquidation,
                sub_account_id=sub.id,
            )
        if sub.exchange_ref is None:
            raise MissingExchangeCredentialsError(
                f"live sub-account {sub.id!r} must declare exchange_ref"
            )
        credential = self.settings.exchange_credentials[sub.exchange_ref]
        exchange = self._exchange_from_credential(credential)
        self._owned_live_exchanges.append(exchange)
        return LiveTrader(
            exchange=exchange,
            data_dir=self.settings.data_dir / "trades",
            sub_account_id=sub.id,
            confirmation_callback=_auto_confirm_live_sub_account,
        )

    @staticmethod
    def _exchange_from_credential(
        credential: ExchangeCredential,
    ) -> BinanceExchange | BybitExchange:
        if credential.exchange == "binance":
            return BinanceExchange(
                credential.to_binance_config(),
                testnet=credential.testnet,
            )
        return BybitExchange(
            credential.to_bybit_config(),
            testnet=credential.testnet,
        )

    async def connect_owned_exchanges(self) -> None:
        """Connect live exchanges constructed by this registry."""
        for exchange in self._owned_live_exchanges:
            await exchange.connect()

    async def disconnect_owned_exchanges(self) -> None:
        """Disconnect live exchanges constructed by this registry."""
        for exchange in self._owned_live_exchanges:
            await exchange.disconnect()

    def _materialise_default(self) -> SubAccount:
        """Build the back-compat ``default`` sub-account from settings.

        Mirrors today's single-seed wiring: one paper or live mode
        bucket, ``USDT`` initial balance from
        ``Settings.paper_initial_balance``, no strategy filter, no
        risk overrides.
        """
        return SubAccount(
            id=DEFAULT_SUB_ACCOUNT_ID,
            name="Default Account",
            mode=self.settings.trading_mode,
            # ``"default"`` is also the conventional exchange_ref for
            # the single-credential single-trader configuration.
            exchange_ref="default",
            capital_policy=CapitalPolicy(
                initial_balance={
                    "USDT": Decimal(str(self.settings.paper_initial_balance)),
                },
            ),
            strategy_policy=StrategyPolicy(strategy_filter=None),
            risk_overrides=RiskOverrides(),
            enabled=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_active(self) -> list[SubAccount]:
        """Return all enabled sub-accounts in insertion order.

        Disabled sub-accounts (``enabled=False``) are excluded so
        callers iterate exactly the buckets that should receive
        proposals. 19.1 always has one entry (``default``).
        """
        return [sub for sub in self._sub_accounts.values() if sub.enabled]

    def get(self, id: str) -> SubAccount:
        """Look up a sub-account by id.

        Args:
            id: Sub-account id (filesystem-safe key).

        Returns:
            The matching :class:`SubAccount`.

        Raises:
            SubAccountNotFoundError: If the id is not registered.
        """
        try:
            return self._sub_accounts[id]
        except KeyError as exc:
            raise SubAccountNotFoundError(
                f"sub-account {id!r} is not registered"
            ) from exc

    def get_trader(self, id: str) -> Trader:
        """Return the trader bound to a sub-account.

        19.1 returns the single shared ``Trader`` regardless of id;
        the id is still validated through :meth:`get` so a typo in a
        caller surfaces here rather than as a silent wrong-bucket
        write later. 19.2 will replace the body with a per-sub
        trader map lookup.

        Raises:
            SubAccountNotFoundError: If the id is not registered.
        """
        self.get(id)
        return self._traders[id]

    def filter_strategies(
        self,
        id: str,
        available: list[BaseStrategy],
    ) -> list[BaseStrategy]:
        """Narrow an available-strategy list to a sub-account's whitelist.

        ``strategy_filter is None`` is the back-compat default
        (today's behaviour: every strategy runs against the single
        seed). A non-empty list is treated as a strict whitelist —
        a strategy whose ``info.name`` is not in the filter is
        excluded. Order in the returned list is preserved from
        ``available`` so ranking-sensitive callers see no shuffle.

        Args:
            id: Sub-account id to look up the filter for.
            available: All loaded strategies (typically the value of
                ``load_all_strategies()``).

        Returns:
            The filtered list. Returns ``available`` unchanged when
            the sub-account's ``strategy_filter`` is ``None``.

        Raises:
            SubAccountNotFoundError: If the id is not registered.
        """
        sub = self.get(id)
        strategy_filter = sub.effective_strategy_filter()
        if strategy_filter is None:
            return available
        whitelist = set(strategy_filter)
        return [s for s in available if s.info.name in whitelist]


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_SUB_ACCOUNT_ID",
    "MissingExchangeCredentialsError",
    "SubAccountConfigError",
    "SubAccountRegistry",
]


async def _auto_confirm_live_sub_account(position: object, action: str) -> bool:
    """Headless confirmation used for registry-built live traders."""
    return True
