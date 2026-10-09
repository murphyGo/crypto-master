"""Encoded dashboard queries and explicit completeness/freshness contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

MiB = 1024 * 1024


@dataclass(frozen=True)
class Limits:
    result_bytes: int = 2 * MiB
    cache_bytes: int = 16 * MiB
    cache_entries: int = 64
    state_bytes: int = 16 * MiB
    manifest_bytes: int = 4 * MiB
    identities: int = 50_000
    accounts: int = 128
    strategies: int = 256
    admitted: int = 4
    roots: int = 2
    wait_seconds: float = 4.0
    quantum_bytes: int = 512 * MiB
    fresh_seconds: float = 2.0
    stale_seconds: float = 30.0


@dataclass(frozen=True)
class Query:
    root: Path
    kind: str
    mode: str = "paper"
    accounts: tuple[str, ...] = ("default",)
    scope: str = "Aggregate"
    window: str = "lifetime"
    at: datetime | None = None
    source: Path | None = None
    version: int = 1

    def normalized(self) -> Query:
        defaults = {
            "activity": self.root / "runtime" / "activity.jsonl",
            "proposals": self.root / "proposals",
            "candidates": self.root / "feedback" / "state",
        }
        source = self.source or defaults.get(self.kind)
        return Query(
            self.root.resolve(),
            self.kind,
            self.mode,
            self.accounts,
            self.scope,
            self.window,
            self.at,
            source.resolve() if source else None,
            self.version,
        )


@dataclass(frozen=True)
class ReadResult:
    status: Literal["complete", "stale", "pending", "unavailable"]
    payload: bytes | None = None
    evaluated_at: datetime | None = None
    reason: str = ""
    verified_monotonic: float = 0.0

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    def data(self) -> dict[str, Any]:
        return json.loads(self.payload) if self.payload else {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
