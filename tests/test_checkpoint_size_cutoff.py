"""Codec split decisions may stop early; retained-state charges stay exact."""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.dashboard.checkpoint_store import CacheMiss, decode_state, encode_state
from src.dashboard.projections import CycleState, StateBudget
from src.dashboard.read_models import Limits
from src.utils.bounded_read import ReadFailure


@dataclass
class Nested:
    children: object
    label: str


def graph(kind: str) -> object:
    shared = {"decimal": Decimal("1.2300"), "bytes": b"x" * 40000}
    if kind == "shared":
        return [shared, shared, (shared, {"leaf"})]
    if kind == "recursive":
        rows: list[object] = [shared]
        rows.append(rows)
        return rows
    if kind == "dataclass":
        return Nested([shared, CycleState((datetime.now(timezone.utc), 1))], "x")
    return {"scalar": "x" * 100000, "empty": (), "class": Nested}


@pytest.mark.parametrize("kind", ["shared", "recursive", "dataclass", "scalar"])
@pytest.mark.parametrize("boundary", [-1, 0, 127, 128, "below", "equal", "above"])
def test_cutoff_preserves_exact_threshold_decision(kind: str, boundary: object) -> None:
    value = graph(kind)
    budget = StateBudget(Limits())
    exact = budget.size(value)
    cutoff = {"below": exact - 1, "equal": exact, "above": exact + 1}.get(
        boundary, boundary
    )
    assert isinstance(cutoff, int)
    measured = budget.size(value, stop_after=cutoff)
    assert (measured > cutoff) == (exact > cutoff)
    assert measured <= exact
    if exact <= cutoff:
        assert measured == exact
    assert budget.bytes == budget.identities == 0


def test_large_container_stops_before_visiting_every_child() -> None:
    value = [{"row": index, "text": str(index)} for index in range(20000)]
    budget = StateBudget(Limits())
    with patch("src.dashboard.projections.sys.getsizeof", wraps=sys.getsizeof) as size:
        bounded = budget.size(value, stop_after=32 * 1024)
        short_calls = size.call_count
        size.reset_mock()
        exact = budget.size(value)
        full_calls = size.call_count
    assert 32 * 1024 < bounded < exact
    assert short_calls < 10
    assert full_calls > 20000


def test_retained_budget_still_charges_full_graph_and_rejects_overflow() -> None:
    value = graph("shared")
    exact = StateBudget(Limits()).size(value)
    budget = StateBudget(replace(Limits(), state_bytes=exact))
    assert budget.replace(0, value) == exact
    assert budget.bytes == exact
    with pytest.raises(ReadFailure, match="state_budget_exhausted"):
        StateBudget(replace(Limits(), state_bytes=exact - 1)).replace(0, value)


@pytest.mark.parametrize("kind", ["list", "dict", "mixed"])
def test_codec_bytes_match_full_walk_oracle(kind: str) -> None:
    at = datetime(2026, 11, 17, tzinfo=timezone.utc)
    values = [{"timestamp": at, "equity": Decimal(str(index))} for index in range(700)]
    state = {
        "list": {"rows": values},
        "dict": {"cycles": {str(i): CycleState((at, i)) for i in range(700)}},
        "mixed": {"rows": values, "aliases": [values, values], "raw": b"abc"},
    }[kind]
    original = StateBudget.size
    cutoffs: list[int | None] = []

    def full_walk(
        self: StateBudget, value: object, *, stop_after: int | None = None
    ) -> int:
        cutoffs.append(stop_after)
        return original(self, value)

    with patch.object(StateBudget, "size", full_walk):
        expected = encode_state(state)
    actual = encode_state(state)
    assert actual == expected
    assert decode_state(actual) == state
    assert cutoffs and all(cutoff == 32 * 1024 for cutoff in cutoffs)
    for cap in (len(actual) - 1, 100):
        with pytest.raises(CacheMiss, match="logical_limit"):
            encode_state(state, cap=cap)


@pytest.mark.parametrize("bad", [float("inf"), Decimal("NaN"), object()])
def test_early_split_does_not_skip_invalid_later_values(bad: object) -> None:
    state = {"large": list(range(10000)), "bad": bad}
    with pytest.raises(CacheMiss):
        encode_state(state)
