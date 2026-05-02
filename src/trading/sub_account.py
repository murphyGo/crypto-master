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
        auto_approve_threshold: Override on the proposal composite
            score threshold for this sub-account.
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
        initial_balance: Paper-mode seed balance keyed by upper-case
            currency code (e.g. ``{"USDT": Decimal("10000")}``).
        strategy_filter: Optional whitelist of technique names. ``None``
            = all available strategies are eligible for this
            sub-account; a list narrows it.
        risk_overrides: Per-sub-account risk-knob overrides; see
            :class:`RiskOverrides`.
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


__all__ = [
    "RiskOverrides",
    "SubAccount",
    "SubAccountError",
    "SubAccountNotFoundError",
]
