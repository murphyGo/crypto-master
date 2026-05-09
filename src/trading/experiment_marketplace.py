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
from collections.abc import Collection
from decimal import Decimal
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.config import Settings
from src.trading.sub_account import (
    CapitalPolicy,
    NotificationPolicy,
    RiskPolicy,
    StrategyPolicy,
    SubAccount,
)

_TEMPLATE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ExperimentTemplateValidationError(ValueError):
    """Raised when a template is not safe to publish into runtime config."""


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
    risk_policy: RiskPolicy = Field(default_factory=RiskPolicy)
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
            capital_policy=CapitalPolicy(
                initial_balance={self.quote_currency: self.starting_balance},
                quote_currency=self.quote_currency,
                sizing_balance=self.starting_balance,
            ),
            strategy_policy=StrategyPolicy(strategy_filter=self.strategy_filter),
            risk_policy=self.risk_policy,
            notification_policy=NotificationPolicy(route=self.notification_route),
            enabled=self.enabled,
        )

    def to_sub_account_fragment(
        self,
        *,
        sub_account_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Return a YAML-ready ``config/sub_accounts.yaml`` mapping."""
        return self.to_sub_account(
            sub_account_id=sub_account_id,
            name=name,
        ).model_dump(mode="json")


def render_sub_account_yaml_fragment(
    templates: list[ExperimentTemplate],
) -> str:
    """Render templates as a copyable ``sub_accounts`` YAML fragment."""
    return yaml.safe_dump(
        {
            "sub_accounts": [
                template.to_sub_account_fragment() for template in templates
            ]
        },
        sort_keys=False,
    )


def validate_experiment_template(
    template: ExperimentTemplate,
    *,
    settings: Settings | None = None,
    notification_routes: Collection[str] | None = None,
) -> None:
    """Validate template overrides against runtime guardrails."""
    routes = (
        set(notification_routes)
        if notification_routes is not None
        else set((settings or Settings()).notification_slack_webhook_urls)
    )
    errors: list[str] = []
    risk_percent = template.risk_policy.risk_percent
    if risk_percent is not None and not (Decimal("0") < risk_percent <= Decimal("100")):
        errors.append("risk_percent must be > 0 and <= 100")
    if (
        template.notification_route is not None
        and template.notification_route not in routes
    ):
        errors.append(
            f"notification_route {template.notification_route!r} is not configured"
        )
    if errors:
        raise ExperimentTemplateValidationError("; ".join(errors))


__all__ = [
    "ExperimentTemplate",
    "ExperimentTemplateValidationError",
    "render_sub_account_yaml_fragment",
    "validate_experiment_template",
]
