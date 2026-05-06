"""Reusable sub-account experiment templates.

The marketplace layer is intentionally small: it defines a validated template
that can materialise a normal ``SubAccount`` without adding another runtime
account model. Rendering those templates into YAML fragments is a later
construction step.

Related Requirements:
- FR-036: Sub-Account Capital Isolation
- FR-038: Strategy-combination A/B backtests by sub-account
- FR-040: Reusable sub-account experiment templates
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.trading.sub_account import RiskOverrides, SubAccount

_TEMPLATE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ExperimentTemplate(BaseModel):
    """Reusable template for creating a sub-account experiment."""

    template_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    mode: Literal["paper", "live"] = "paper"
    exchange_ref: str | None = "default"
    quote_currency: str = "USDT"
    starting_balance: Decimal = Field(gt=Decimal("0"))
    strategy_filter: list[str] | None = None
    risk_overrides: RiskOverrides = Field(default_factory=RiskOverrides)
    notification_route: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)

    @field_validator("template_id")
    @classmethod
    def _validate_template_id(cls, value: str) -> str:
        if not _TEMPLATE_ID_PATTERN.match(value):
            raise ValueError(
                "template_id must be filesystem-safe: lowercase letter then "
                "[a-z0-9_]*"
            )
        return value

    @field_validator("quote_currency")
    @classmethod
    def _validate_quote_currency(cls, value: str) -> str:
        if value != value.upper():
            raise ValueError("quote_currency must be upper-case")
        return value

    @field_validator("strategy_filter")
    @classmethod
    def _reject_empty_strategy_filter(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        if value == []:
            raise ValueError("strategy_filter must be null or contain strategy names")
        return value

    def to_sub_account(
        self,
        *,
        sub_account_id: str | None = None,
        name: str | None = None,
    ) -> SubAccount:
        """Materialise this template as a normal ``SubAccount``."""
        return SubAccount(
            id=sub_account_id or self.template_id,
            name=name or self.name,
            mode=self.mode,
            exchange_ref=self.exchange_ref,
            initial_balance={self.quote_currency: self.starting_balance},
            strategy_filter=self.strategy_filter,
            risk_overrides=self.risk_overrides,
            notification_route=self.notification_route,
            enabled=self.enabled,
        )


__all__ = ["ExperimentTemplate"]
