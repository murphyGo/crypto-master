"""Lossless per-file reductions; global joins/finalization remain canonical."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import replace
from datetime import datetime
from typing import Any, cast

from src.dashboard.checkpoint_store import (
    CacheMiss,
    StoreSession,
    decode_state,
    eligible_model,
    encode_state,
)
from src.dashboard.projections import (
    ActivityProjection,
    CycleState,
    HistoryProjection,
    StateBudget,
    _reduce_activity_source,
    proposal_state,
)
from src.dashboard.sources import Source
from src.proposal.interaction import ProposalRecord
from src.trading.portfolio import AssetSnapshot
from src.utils.bounded_read import ReadFailure, json_array_bytes, json_object

_MIB = 1024 * 1024
_ACTIVITY_FIELDS = (
    "cycles",
    "companions",
    "sub",
    "latest",
    "recent",
    "types",
    "crowding",
    "total",
)
_TOPS = ("timeline", "incidents", "unscoped_incidents")


def _activity_state(local: ActivityProjection) -> dict[str, Any]:
    state = {name: getattr(local, name) for name in _ACTIVITY_FIELDS}
    state["tops"] = {name: getattr(local, name).heap for name in _TOPS}
    state["tables"] = {name: top.heap for name, top in local.tables.items()}
    state["rejection_index"] = local.rejection_index
    state["accounts"] = local.budget.accounts
    return state


def _rebase(payload: dict[str, Any], base: int, seen: set[int]) -> None:
    if id(payload) not in seen:
        payload["_ordinal"] += base
        seen.add(id(payload))


def _validate_activity(state: dict[str, Any]) -> None:
    if set(state) != set(_ACTIVITY_FIELDS) | {
        "tops",
        "tables",
        "rejection_index",
        "accounts",
    }:
        raise CacheMiss("schema")
    if not isinstance(state["total"], int) or state["total"] < 0:
        raise CacheMiss("schema")
    for cid, cycle in state["cycles"].items():
        if not isinstance(cid, str) or not isinstance(cycle, CycleState):
            raise CacheMiss("schema")
        if (
            not isinstance(cycle.first, tuple)
            or len(cycle.first) != 2
            or not isinstance(cycle.first[0], datetime)
            or not isinstance(cycle.first[1], int)
        ):
            raise CacheMiss("schema")
        if cycle.start is not None and not isinstance(cycle.start, datetime):
            raise CacheMiss("schema")
        if cycle.end is not None and (
            not isinstance(cycle.end, list)
            or len(cycle.end) != 4
            or not isinstance(cycle.end[0], datetime)
            or not isinstance(cycle.end[1], int)
        ):
            raise CacheMiss("schema")
        if any(
            not isinstance(getattr(cycle, key), int) or getattr(cycle, key) < 0
            for key in ("Generated", "Accepted", "Rejected", "Opened", "Closed")
        ):
            raise CacheMiss("schema")
    for group in (state["tops"], state["tables"]):
        if not isinstance(group, dict):
            raise CacheMiss("schema")
        for entries in group.values():
            for at, tie, payload in entries:
                if (
                    not isinstance(at, datetime)
                    or not isinstance(tie, int)
                    or not isinstance(payload.get("_ordinal"), int)
                ):
                    raise CacheMiss("schema")
    if set(state["tops"]) != set(_TOPS) or set(state["tables"]) != {
        "risk",
        "regime",
        "degraded",
        "crowding",
    }:
        raise CacheMiss("schema")
    for key, (at, tie, payload) in state["latest"].items():
        if (
            not isinstance(key, tuple)
            or not key
            or not isinstance(at, datetime)
            or not isinstance(tie, int)
            or not isinstance(payload.get("_ordinal"), int)
        ):
            raise CacheMiss("schema")
    if not isinstance(state["types"], set) or not isinstance(state["recent"], list):
        raise CacheMiss("schema")


def _merge_activity(
    target: ActivityProjection, state: dict[str, Any], base: int
) -> None:
    budget = target.budget
    seen: set[int] = set()
    for account in state["accounts"]:
        budget.account(account)
    for cid, local in state["cycles"].items():
        first = (local.first[0], local.first[1] + base)
        if local.end is not None:
            local.end[1] += base
        existing = target.cycles.get(cid)
        if existing is None:
            local.first = first
            budget.change(None, [cid, local], new_key=True)
            target.cycles[cid] = local
            continue
        existing.first = min(existing.first, first)
        if local.start is not None:
            existing.start = (
                local.start
                if existing.start is None
                else min(existing.start, local.start)
            )
        if local.end is not None and (
            existing.end is None or tuple(local.end[:2]) < tuple(existing.end[:2])
        ):
            budget.change(existing.end, local.end)
            existing.end = local.end
        existing.error |= local.error
        for field in ("Generated", "Accepted", "Rejected", "Opened", "Closed"):
            setattr(existing, field, getattr(existing, field) + getattr(local, field))
    for key, count in state["companions"].items():
        if key not in target.companions:
            budget.change(None, key, new_key=True)
        target.companions[key] = target.companions.get(key, 0) + count
    for account, counts in state["sub"].items():
        budget.account(account)
        if account not in target.sub:
            budget.change(None, [account, counts], new_key=True)
            target.sub[account] = counts
        else:
            for field, count in counts.items():
                target.sub[account][field] += count
    for key, (at, tie, payload) in state["latest"].items():
        _rebase(payload, base, seen)
        tie += base if key[0] == "derivatives" else -base
        old = target.latest.get(key)
        if old is None or (at, tie) > (old[0], old[1]):
            budget.change(
                [key, old[2]] if old else None, [key, payload], new_key=old is None
            )
            target.latest[key] = (at, tie, payload)
    for raw in state["recent"]:
        if datetime.fromisoformat(raw["timestamp"]) >= target.cutoff:
            budget.change(None, raw, new_key=True)
            target.recent.append(raw)
    for typ in state["types"]:
        if typ not in target.types:
            budget.change(None, typ, new_key=True)
            target.types.add(typ)
    for key, count in state["crowding"].items():
        target.crowding[key] += count
    target.total += state["total"]
    for group in ("tops", "tables"):
        for name, entries in state[group].items():
            top = getattr(target, name) if group == "tops" else target.tables[name]
            for at, tie, payload in entries:
                _rebase(payload, base, seen)
                # Loaded payloads are independently decoded values, not aliases.
                ordinal = -(tie + (base if name == "timeline" else -base))
                top.add(at, ordinal, payload)


class SegmentCheckpoints:
    def __init__(
        self,
        session: StoreSession,
        budget: StateBudget,
        reducer: ActivityProjection | HistoryProjection,
    ):
        self.session = session
        self.budget = budget
        self.reducer = reducer
        self.rejections: list[set[tuple[str | None, str]] | None] = []
        self.enabled = True
        self.join_sources: list[Source] = []

    def start(self) -> Generator[None, None, None]:
        yield from self.session.load()
        if self.session.disabled:
            self.enabled = False

    def reduce(
        self, source: Source, ordinal_base: int, key: bytes
    ) -> Generator[None, None, bool]:
        if not self.enabled:
            return False
        query = self.reducer.query
        raw = None
        for part in self.session.lookup(key, source):
            if part is None:
                yield None
            else:
                raw = part
        state = None
        rejection = None
        cache_charge = 0
        # Optional codec/pack scratch is admitted against active state. The index
        # has its own reservation INSIDE the existing result-cache RAM budget.
        available = self.budget.limits.state_bytes - self.budget.bytes
        if raw is not None and len(raw) + 4 * _MIB < available:
            try:
                envelope = decode_state(raw, max_bytes=max(0, available - 4 * _MIB))
                if (
                    set(envelope) != {"schema", "key", "kind", "at", "state"}
                    or envelope["schema"] != 1
                    or envelope["key"] != key.hex()
                    or envelope["kind"] != query.kind
                ):
                    raise CacheMiss("identity")
                if envelope["at"] > self.reducer.now:
                    raise CacheMiss("clock")
                state = envelope["state"]
                if query.kind == "activity":
                    _validate_activity(state)
                elif query.kind == "proposals":
                    if (
                        set(state)
                        != {"timestamp", "threshold", "field", "account", "strategy"}
                        or not isinstance(state["timestamp"], datetime)
                        or state["threshold"] not in (0, 1)
                        or state["field"]
                        not in cast(HistoryProjection, self.reducer).counts
                        or not isinstance(state["account"], str)
                        or not isinstance(state["strategy"], str)
                    ):
                        raise CacheMiss("schema")
                elif query.kind == "snapshots":
                    if (
                        set(state) != {"latest", "latest_charges", "curves", "sampled"}
                        or set(state["latest"]) - {source.account}
                        or set(state["curves"]) - {source.account}
                    ):
                        raise CacheMiss("schema")
                    for timestamp, payload in state["latest"].values():
                        if not isinstance(timestamp, datetime) or not isinstance(
                            payload, (bytes, dict)
                        ):
                            raise CacheMiss("schema")
                    for curve in state["curves"].values():
                        for point, charge in curve:
                            if (
                                not isinstance(point, dict)
                                or not isinstance(charge, int)
                                or charge < 0
                            ):
                                raise CacheMiss("schema")
                cache_charge = self.budget.size(state) + 128
                if (
                    self.budget.bytes + cache_charge * 2 + 4 * _MIB
                    > self.budget.limits.state_bytes
                ):
                    raise CacheMiss("scratch")
            except (
                CacheMiss,
                ValueError,
                TypeError,
                KeyError,
                OverflowError,
                RecursionError,
            ):
                state = None
        del raw
        if state is None:
            store_scratch = 4 * _MIB + 4 * len(self.session.index)
            local_limit = min(4 * _MIB, max(0, available - store_scratch))
            if local_limit < 65536:
                return False
            local_budget = StateBudget(
                replace(self.budget.limits, state_bytes=local_limit)
            )
            try:
                if query.kind == "activity":
                    local = ActivityProjection(query, local_budget)
                    local.now = self.reducer.now
                    local.cutoff = cast(ActivityProjection, self.reducer).cutoff
                    local.rejection_index = set()
                    yield from _reduce_activity_source(local, source, 0)
                    state = _activity_state(local)
                elif query.kind == "proposals":
                    payload = None
                    for object_part in json_object(source.path, source.generation):
                        if object_part is None:
                            yield None
                        else:
                            payload = object_part
                    record = ProposalRecord.model_validate(payload)
                    if not eligible_model(record):
                        return False
                    state = proposal_state(record)
                elif query.kind == "snapshots":
                    history = HistoryProjection(query, local_budget)
                    history.now = self.reducer.now
                    iterator = json_array_bytes(source.path, source.generation)
                    try:
                        for part in iterator:
                            if part is None:
                                yield None
                                continue
                            snapshot = AssetSnapshot.model_validate_json(part)
                            if not eligible_model(snapshot):
                                return False
                            history.add_snapshot(snapshot, source, part)
                    finally:
                        iterator.close()
                    state = {
                        "latest": history.latest,
                        "latest_charges": history.latest_charges,
                        "curves": history.curves,
                        "sampled": history.sampled,
                    }
                else:
                    return False
                cache_charge = local_budget.size(state) + 128
                if (
                    self.budget.bytes + 2 * cache_charge + 4 * _MIB
                    > self.budget.limits.state_bytes
                ):
                    return False
                envelope = {
                    "schema": 1,
                    "key": key.hex(),
                    "kind": query.kind,
                    "at": self.reducer.now,
                    "state": state,
                }
                # Structural bound before building tagged/encoded scratch.
                if cache_charge + store_scratch < available:
                    try:
                        encoded = encode_state(envelope)
                        if self.session.key(source) == key:
                            yield from self.session.put(key, encoded)
                    except (
                        CacheMiss,
                        ValueError,
                        TypeError,
                        OverflowError,
                        RecursionError,
                    ):
                        pass
            except (ReadFailure, ValueError):
                return False
        self.budget.bytes += cache_charge
        try:
            if query.kind == "activity":
                rejection = state["rejection_index"]
                _merge_activity(
                    cast(ActivityProjection, self.reducer), state, ordinal_base
                )
            elif query.kind == "proposals":
                cast(HistoryProjection, self.reducer).add_proposal_state(state)
            elif query.kind == "snapshots":
                target = cast(HistoryProjection, self.reducer)
                for account, selected in state["latest"].items():
                    self.budget.account(account)
                    self.budget.change(None, [account, selected, 0], new_key=True)
                    target.latest[account] = selected
                    target.latest_charges[account] = self.budget.size(
                        [account, selected, 0]
                    )
                for account, curve in state["curves"].items():
                    self.budget.change(None, [account, curve], new_key=True)
                    target.curves[account] = curve
                target.sampled |= state["sampled"]
        finally:
            self.budget.bytes -= cache_charge
        if query.kind == "activity":
            # Source-local exact rejection evidence; incomplete indexes trigger
            # the existing canonical global companion join for that file.
            if rejection is not None:
                charge = self.budget.size(rejection) + 128
                if self.budget.bytes + charge > self.budget.limits.state_bytes:
                    rejection = None
                else:
                    self.budget.reserve(charge)
            self.rejections.append(rejection)
            if rejection is None:
                self.join_sources.append(source)
        return True

    def close(self) -> None:
        self.session.close()

    def flush(self) -> Generator[None, None, None]:
        if (
            self.budget.bytes + 4 * _MIB + 4 * len(self.session.index)
            > self.budget.limits.state_bytes
        ):
            self.session.pending.clear()
            self.session.entries.clear()
            return
        yield from self.session.flush()
