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

from src.config import Settings
from src.strategy.base import BaseStrategy
from src.trading.base import Trader
from src.trading.sub_account import (
    RiskOverrides,
    SubAccount,
    SubAccountNotFoundError,
)

# Default config-file location. 19.3 will parse this; 19.1 only
# falls through to the synthesised-from-Settings path when the file
# is absent (which is the 19.1 default for every deployment).
DEFAULT_CONFIG_PATH = Path("config/sub_accounts.yaml")

# The id reserved for the auto-materialised back-compat sub-account.
DEFAULT_SUB_ACCOUNT_ID = "default"


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

        # Single shared trader — the wiring seam for 19.2's per-sub
        # trader map. Phase 19.1 keeps the existing single-Trader
        # behaviour bytewise.
        self._trader = trader

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
        # 19.1: YAML parsing is out of scope. If a config file already
        # sits on disk (e.g. an operator pre-staged one for 19.3) we
        # still take the default branch — 19.3 will replace this body.
        # The early return makes the seam obvious at the call site.
        if self.config_path.exists():
            # 19.3 placeholder: parse YAML into a list of SubAccount
            # instances. For 19.1 we deliberately ignore the file and
            # fall through to the default-materialisation branch.
            pass

        default = self._materialise_default()
        self._sub_accounts[default.id] = default

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
            initial_balance={
                "USDT": Decimal(str(self.settings.paper_initial_balance)),
            },
            strategy_filter=None,
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
        # Validate the id even though we hand back the shared trader —
        # the consumer expectation is "get_trader(unknown_id) raises".
        self.get(id)
        return self._trader

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
        if sub.strategy_filter is None:
            return available
        whitelist = set(sub.strategy_filter)
        return [s for s in available if s.info.name in whitelist]


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_SUB_ACCOUNT_ID",
    "SubAccountRegistry",
]
