"""Deterministic identity helpers for snapshot-backed backtests.

The digest surface deliberately excludes run UUIDs, wall-clock timestamps,
filesystem paths, and transport payloads.  Promotion reports can therefore
compare the configuration that produced a decision without leaking local or
credential-bearing state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class ReplayIdentity(BaseModel):
    """Immutable identity of the snapshot selected for one replay."""

    schema_version: Literal[1, 2]
    generation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_version_identity(self) -> Self:
        if self.schema_version == 1 and self.generation_id is not None:
            raise ValueError("schema v1 replay cannot declare a generation id")
        if self.schema_version == 2 and self.generation_id is None:
            raise ValueError("schema v2 replay requires a generation id")
        for value in (self.source, self.symbol, self.timeframe):
            if value != value.strip():
                raise ValueError("replay identity text must be canonical")
        return self


def canonical_configuration_digest(payload: dict[str, Any]) -> str:
    """Return a stable SHA-256 digest for an allowlisted configuration map."""

    normalized = _normalize(payload)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("configuration timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Enum):
        return _normalize(value.value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported configuration digest value: {type(value).__name__}")


__all__ = ["ReplayIdentity", "canonical_configuration_digest"]
