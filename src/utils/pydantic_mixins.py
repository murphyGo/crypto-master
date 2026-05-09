"""Reusable Pydantic validators shared across persistence models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import field_validator

from src.utils.time import ensure_utc


class DecimalFieldsMixin:
    """Coerce common persisted numeric fields to ``Decimal``."""

    @field_validator(
        "entry_price",
        "stop_loss",
        "take_profit",
        "quantity",
        "actual_entry_price",
        "actual_exit_price",
        "entry_quantity",
        "exit_price",
        "exit_quantity",
        "pnl",
        "fees",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def _coerce_decimal_fields(
        cls, value: str | int | float | Decimal | None
    ) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))


class UtcTimestampMixin:
    """Coerce common persisted timestamp fields to UTC-aware datetimes."""

    @field_validator(
        "timestamp",
        "created_at",
        "updated_at",
        "first_seen_at",
        "last_evaluated_at",
        "analysis_timestamp",
        "exit_timestamp",
        "entry_time",
        "exit_time",
        "decision_at",
        "outcome_recorded_at",
        mode="after",
        check_fields=False,
    )
    @classmethod
    def _coerce_timestamp_fields_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return ensure_utc(value)


__all__ = ["DecimalFieldsMixin", "UtcTimestampMixin"]
