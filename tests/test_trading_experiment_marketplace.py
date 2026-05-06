"""Tests for reusable sub-account experiment templates."""

from __future__ import annotations

from decimal import Decimal

import pytest
import yaml
from pydantic import ValidationError

from src.config import Settings
from src.trading.experiment_marketplace import (
    ExperimentTemplate,
    render_sub_account_yaml_fragment,
)
from src.trading.sub_account import RiskOverrides, SubAccount
from src.trading.sub_account_registry import SubAccountRegistry


def test_experiment_template_materialises_sub_account() -> None:
    template = ExperimentTemplate(
        template_id="btc_swing_lab",
        name="BTC Swing Lab",
        description="BTC-only swing strategy lab",
        starting_balance=Decimal("5000"),
        strategy_filter=["chasulang_ict_smc", "rsi_4h"],
        risk_overrides=RiskOverrides(
            risk_percent=Decimal("0.5"),
            max_open_positions_total=1,
        ),
        notification_route="lab",
        tags=["btc", "swing"],
    )

    sub_account = template.to_sub_account()

    assert isinstance(sub_account, SubAccount)
    assert sub_account.id == "btc_swing_lab"
    assert sub_account.name == "BTC Swing Lab"
    assert sub_account.mode == "paper"
    assert sub_account.exchange_ref == "default"
    assert sub_account.initial_balance == {"USDT": Decimal("5000")}
    assert sub_account.strategy_filter == ["chasulang_ict_smc", "rsi_4h"]
    assert sub_account.risk_overrides.max_open_positions_total == 1
    assert sub_account.notification_route == "lab"


def test_experiment_template_can_override_instance_identity() -> None:
    template = ExperimentTemplate(
        template_id="btc_swing_lab",
        name="BTC Swing Lab",
        description="BTC-only swing strategy lab",
        starting_balance=Decimal("5000"),
    )

    sub_account = template.to_sub_account(
        sub_account_id="btc_swing_lab_2",
        name="BTC Swing Lab 2",
    )

    assert sub_account.id == "btc_swing_lab_2"
    assert sub_account.name == "BTC Swing Lab 2"


def test_experiment_template_rejects_unsafe_template_id() -> None:
    with pytest.raises(ValidationError, match="template_id"):
        ExperimentTemplate(
            template_id="../bad",
            name="Bad",
            description="Bad id",
            starting_balance=Decimal("1000"),
        )


def test_experiment_template_rejects_lowercase_quote_currency() -> None:
    with pytest.raises(ValidationError, match="quote_currency"):
        ExperimentTemplate(
            template_id="bad_currency",
            name="Bad Currency",
            description="Bad quote currency",
            quote_currency="usdt",
            starting_balance=Decimal("1000"),
        )


def test_experiment_template_rejects_empty_strategy_filter() -> None:
    with pytest.raises(ValidationError, match="strategy_filter"):
        ExperimentTemplate(
            template_id="empty_filter",
            name="Empty Filter",
            description="Empty filters are ambiguous",
            starting_balance=Decimal("1000"),
            strategy_filter=[],
        )


def test_experiment_template_renders_sub_account_fragment() -> None:
    template = ExperimentTemplate(
        template_id="btc_swing_lab",
        name="BTC Swing Lab",
        description="BTC-only swing strategy lab",
        starting_balance=Decimal("5000"),
        strategy_filter=["rsi_4h"],
        risk_overrides=RiskOverrides(max_open_positions_total=1),
        notification_route="lab",
    )

    fragment = template.to_sub_account_fragment()

    assert fragment["id"] == "btc_swing_lab"
    assert fragment["initial_balance"] == {"USDT": "5000"}
    assert fragment["strategy_filter"] == ["rsi_4h"]
    assert fragment["risk_overrides"]["max_open_positions_total"] == 1
    assert fragment["notification_route"] == "lab"


def test_render_sub_account_yaml_fragment_round_trips_through_registry(
    tmp_path,
) -> None:
    template = ExperimentTemplate(
        template_id="btc_swing_lab",
        name="BTC Swing Lab",
        description="BTC-only swing strategy lab",
        starting_balance=Decimal("5000"),
        strategy_filter=["rsi_4h"],
    )
    config_path = tmp_path / "sub_accounts.yaml"

    rendered = render_sub_account_yaml_fragment([template])
    config_path.write_text(rendered, encoding="utf-8")
    parsed = yaml.safe_load(rendered)
    registry = SubAccountRegistry(
        settings=Settings(),
        trader=object(),  # type: ignore[arg-type]
        config_path=config_path,
    )

    assert list(parsed) == ["sub_accounts"]
    assert registry.get("btc_swing_lab").initial_balance == {"USDT": Decimal("5000")}
    assert registry.get("btc_swing_lab").strategy_filter == ["rsi_4h"]
