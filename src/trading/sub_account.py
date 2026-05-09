"""Sub-account entity for capital segmentation (Phase 19.1).

A ``SubAccount`` declares one isolated capital pool: its mode,
exchange binding, seed balance, optional strategy whitelist, and
risk overrides. The runtime engine, persistence layer, and dashboard
key off the ``id`` field. Phase 19.1 only introduces the entity and
a registry that materialises a single ``default`` sub-account from
``Settings`` so legacy single-seed deployments operate unchanged;
later sub-tasks (19.2 / 19.3) wire it through the engine, persistence
paths, and YAML configuration.

Models are **frozen** so registry consumers can't mutate behind the
registry's back — any change requires the registry to hand back a
fresh instance.

Related Requirements:
- FR-036: Sub-Account Capital Isolation (the entity that will own a
  balance pool; single-account materialisation is the back-compat
  floor for 19.1).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Filesystem-safe id pattern: lowercase ASCII, digits, underscore,
# leading letter. Matches sub-account ids used both as registry keys
# and as path segments under ``data/.../{sub_account_id}/...``.
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class SubAccountError(Exception):
    """Base exception for sub-account errors."""


class SubAccountNotFoundError(SubAccountError):
    """Raised when a sub-account id is not registered.

    Lives next to the model rather than the registry because callers
    on the engine / dashboard side already import ``SubAccount``; the
    exception belongs in the same module to avoid a second import for
    the catch site.
    """


class CapitalPolicy(BaseModel):
    """Per-sub-account capital and sizing inputs."""

    initial_balance: dict[str, Decimal] | None = None
    quote_currency: str = "USDT"
    sizing_balance: Decimal | None = Field(default=None, gt=Decimal("0"))

    model_config = ConfigDict(frozen=True)

    @field_validator("quote_currency")
    @classmethod
    def _validate_quote_currency(cls, value: str) -> str:
        if value != value.upper():
            raise ValueError("quote_currency must be upper-case")
        return value

    @field_validator("initial_balance")
    @classmethod
    def _validate_initial_balance_keys(
        cls,
        value: dict[str, Decimal] | None,
    ) -> dict[str, Decimal] | None:
        if value is None:
            return None
        for key in value:
            if key != key.upper():
                raise ValueError(
                    f"initial_balance currency code must be upper-case; got {key!r}"
                )
        return value


class StrategyPolicy(BaseModel):
    """Per-sub-account strategy universe and scan scope."""

    strategy_filter: list[str] | None = None
    bitcoin_symbol: str | None = None
    symbols: list[str] | None = None
    top_k: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(frozen=True)

    @field_validator("strategy_filter")
    @classmethod
    def _reject_empty_strategy_filter(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        if value == []:
            raise ValueError("strategy_filter must be null or contain strategy names")
        return value

    @field_validator("symbols")
    @classmethod
    def _reject_empty_symbols(cls, value: list[str] | None) -> list[str] | None:
        if value == []:
            raise ValueError("symbols must be null or contain symbols")
        return value


class ProposalPolicy(BaseModel):
    """Per-sub-account proposal decision and notification scoring policy."""

    auto_approve_threshold: float | None = Field(default=None, ge=0.0)
    notify_min_score: float | None = Field(default=None, ge=0.0)

    model_config = ConfigDict(frozen=True)


class RiskPolicy(BaseModel):
    """Per-sub-account risk knobs used by runtime and backtests."""

    risk_percent: Decimal | None = None
    max_open_positions_total: int | None = Field(default=None, ge=1)
    max_open_positions_per_symbol: int | None = Field(default=None, ge=1)
    leverage_cap: int | None = Field(default=None, ge=1, le=125)

    model_config = ConfigDict(frozen=True)


class ExecutionPolicy(BaseModel):
    """Per-sub-account post-decision execution gates."""

    runtime_safety_pause_min_score: int | None = Field(default=None, ge=0, le=100)
    fill_slippage_tolerance: Decimal | None = Field(default=None, ge=0)
    reject_if_past_stop_loss: bool | None = None
    reject_if_stale_quote: bool | None = None
    max_ticker_age_seconds: float | None = Field(default=None, gt=0)
    correlation_gate_enabled: bool | None = None
    correlation_max_sub_accounts_per_symbol_side: int | None = Field(
        default=None,
        ge=1,
    )
    correlation_max_sub_accounts_per_strategy_symbol_side: int | None = Field(
        default=None,
        ge=1,
    )

    model_config = ConfigDict(frozen=True)


class NotificationPolicy(BaseModel):
    """Per-sub-account notification routing overrides."""

    route: str | None = None
    min_score: float | None = Field(default=None, ge=0.0)

    model_config = ConfigDict(frozen=True)


class RiskOverrides(BaseModel):
    """Per-sub-account overrides on engine-wide risk knobs.

    Each field is optional — ``None`` means "fall through to the
    engine's global value". 19.1 only stores the structure; 19.2
    consumes the values inside the proposal and execution paths.

    Attributes:
        risk_percent: Override on the per-trade risk fraction
            (engine default is ``Settings.engine_*`` derived).
        max_open_positions_total: Override on the cap of open
            positions across all symbols inside this sub-account.
        max_open_positions_per_symbol: Override on the per-symbol
            open-position cap (Phase 12.1 cross-cycle gate).
        leverage_cap: Override on the maximum leverage allowed for
            any trade routed through this sub-account.
        auto_approve_threshold: Legacy override on the proposal composite
            score threshold for this sub-account. New configs should use
            ``proposal_policy.auto_approve_threshold``.
    """

    risk_percent: Decimal | None = None
    max_open_positions_total: int | None = Field(default=None, ge=1)
    max_open_positions_per_symbol: int | None = Field(default=None, ge=1)
    leverage_cap: int | None = Field(default=None, ge=1, le=125)
    auto_approve_threshold: float | None = Field(default=None, ge=0.0)

    model_config = ConfigDict(frozen=True)


class SubAccount(BaseModel):
    """One isolated capital pool inside the runtime.

    Attributes:
        id: Stable filesystem-safe key (``^[a-z][a-z0-9_]*$``). Used
            as both the registry key and a path segment under
            ``data/.../{id}/...``.
        name: Human-readable display name for dashboards / logs.
        mode: Trading mode for this sub-account (``"paper"`` /
            ``"live"``). 19.1 takes the global ``Settings.trading_mode``
            verbatim; 19.3 will support per-sub-account overrides.
        exchange_ref: Logical exchange reference (e.g. ``"default"``,
            ``"binance_main"``, ``"binance_alt"``). Live-mode enabled
            sub-accounts must declare a non-null ``exchange_ref`` so
            credentials can be resolved at startup (DESIGN.md §9.7).
        initial_balance: Deprecated legacy paper-mode seed balance.
            New writes must use ``capital_policy.initial_balance``.
        strategy_filter: Deprecated legacy technique whitelist.
            New writes must use ``strategy_policy.strategy_filter``.
        risk_overrides: Deprecated legacy risk-knob override block.
            New writes must use ``risk_policy`` / ``proposal_policy``.
        notification_route: Optional route ref used by the runtime
            notification router. ``None`` means the account uses the
            global notification push backends.
        enabled: Soft-disable switch. ``False`` excludes the
            sub-account from ``SubAccountRegistry.list_active``
            without deleting its on-disk records.
    """

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    mode: Literal["paper", "live"]
    exchange_ref: str | None = None
    initial_balance: dict[str, Decimal] = Field(default_factory=dict)
    strategy_filter: list[str] | None = None
    risk_overrides: RiskOverrides = Field(default_factory=RiskOverrides)
    capital_policy: CapitalPolicy = Field(default_factory=CapitalPolicy)
    strategy_policy: StrategyPolicy = Field(default_factory=StrategyPolicy)
    proposal_policy: ProposalPolicy = Field(default_factory=ProposalPolicy)
    risk_policy: RiskPolicy = Field(default_factory=RiskPolicy)
    execution_policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    notification_policy: NotificationPolicy = Field(default_factory=NotificationPolicy)
    notification_route: str | None = None
    enabled: bool = True

    # Frozen so registry consumers can't mutate behind the registry's
    # back — any change requires constructing a fresh instance.
    model_config = ConfigDict(frozen=True)

    @field_validator("id")
    @classmethod
    def _validate_id_pattern(cls, value: str) -> str:
        """Enforce filesystem-safe ``id`` (``^[a-z][a-z0-9_]*$``).

        Sub-account ids land in directory names under
        ``data/.../{id}/...``; rejecting unsafe patterns at the model
        boundary keeps the persistence layer free of escaping logic.
        """
        if not _ID_PATTERN.match(value):
            raise ValueError(
                f"sub-account id must match {_ID_PATTERN.pattern} "
                f"(lowercase letter then [a-z0-9_]*); got {value!r}"
            )
        return value

    @field_validator("initial_balance")
    @classmethod
    def _validate_currency_keys(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        """Currency codes are upper-case ASCII.

        ``Balance`` records elsewhere in the codebase normalise on
        upper-case (``"USDT"`` / ``"BTC"``); rejecting lowercase keys
        here prevents a silent mismatch when the registry hands the
        balance dict to ``PaperTrader``.
        """
        for key in value:
            if key != key.upper():
                raise ValueError(
                    f"initial_balance currency code must be upper-case; " f"got {key!r}"
                )
        return value

    @model_validator(mode="after")
    def _reject_dual_source_policy_fields(self) -> SubAccount:
        """Reject configs that write both legacy root and policy block fields."""
        if self.initial_balance and self.capital_policy.initial_balance is not None:
            raise ValueError(
                "initial_balance conflicts with capital_policy.initial_balance; "
                "write initial balances only under capital_policy"
            )
        if (
            self.strategy_filter is not None
            and self.strategy_policy.strategy_filter is not None
        ):
            raise ValueError(
                "strategy_filter conflicts with strategy_policy.strategy_filter; "
                "write strategy filters only under strategy_policy"
            )
        return self

    @model_validator(mode="after")
    def _live_requires_exchange_ref(self) -> SubAccount:
        """Live + enabled requires a non-null ``exchange_ref``.

        The DESIGN §9.7 invariant: a live, enabled sub-account whose
        ``exchange_ref`` cannot resolve to a credential set is a
        startup failure (silent fallback would leak risk). Catching
        the missing ``exchange_ref`` at model construction time keeps
        the registry's loader free of this check.
        """
        if self.enabled and self.mode == "live" and self.exchange_ref is None:
            raise ValueError(
                "enabled live sub-account requires a non-null exchange_ref"
            )
        return self

    def effective_initial_balance(self) -> dict[str, Decimal]:
        """Return the active initial-balance mapping for this account."""
        return self.capital_policy.initial_balance or self.initial_balance

    def effective_quote_currency(self) -> str:
        """Return the account quote currency."""
        return self.capital_policy.quote_currency

    def effective_sizing_balance(self, fallback: Decimal) -> Decimal:
        """Return proposal sizing balance for this account."""
        return self.capital_policy.sizing_balance or fallback

    def effective_strategy_filter(self) -> list[str] | None:
        """Return the active strategy whitelist for this account."""
        if self.strategy_policy.strategy_filter is not None:
            return self.strategy_policy.strategy_filter
        return self.strategy_filter

    def effective_risk_percent(self) -> Decimal | None:
        """Return account-specific risk percent, if configured."""
        return self.risk_policy.risk_percent

    def effective_leverage_cap(self) -> int | None:
        """Return account-specific leverage cap, if configured."""
        return self.risk_policy.leverage_cap

    def effective_max_open_positions_total(self) -> int | None:
        """Return account-specific total open-position cap, if configured."""
        return self.risk_policy.max_open_positions_total

    def effective_max_open_positions_per_symbol(self) -> int | None:
        """Return account-specific per-symbol open-position cap, if configured."""
        return self.risk_policy.max_open_positions_per_symbol

    def effective_auto_approve_threshold(self) -> float | None:
        """Return account-specific proposal decision threshold, if configured."""
        return self.proposal_policy.auto_approve_threshold

    def effective_notification_route(self) -> str | None:
        """Return account-specific notification route, if configured."""
        if self.notification_policy.route is not None:
            return self.notification_policy.route
        return self.notification_route


__all__ = [
    "CapitalPolicy",
    "ExecutionPolicy",
    "NotificationPolicy",
    "ProposalPolicy",
    "RiskOverrides",
    "RiskPolicy",
    "StrategyPolicy",
    "SubAccount",
    "SubAccountError",
    "SubAccountNotFoundError",
]
