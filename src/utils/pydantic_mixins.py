"""Reusable Pydantic validators shared across persistence models."""

from __future__ import annotations

from datetime import datetime

from pydantic import field_validator

from src.utils.time import ensure_utc


class UtcTimestampMixin:
    """Coerce common persisted timestamp fields to UTC-aware datetimes."""

    @field_validator(
        "timestamp",
        "created_at",
        "updated_at",
        "first_seen_at",
        "last_evaluated_at",
        mode="after",
        check_fields=False,
    )
    @classmethod
    def _coerce_timestamp_fields_to_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


__all__ = ["UtcTimestampMixin"]
