"""Tests for ``src.runtime.strategy_action_snapshot`` (DEBT-069(d)).

Covers the load / diff / save primitives the engine's
``STRATEGY_ACTION_APPLIED`` emitter is built on:

* first run (no file) ⇒ ``load_snapshot`` returns ``None`` (seed + silent);
* malformed file ⇒ ``None`` (treated like a first run, no storm);
* changed action ⇒ one transition per change with the correct fields;
* unchanged / new / removed-strategy cases produce no transition;
* round-trip persistence via the canonical atomic writer.
"""

from __future__ import annotations

from pathlib import Path

from src.runtime.strategy_action_snapshot import (
    AppliedStateMap,
    StrategyActionTransition,
    diff_snapshots,
    load_snapshot,
    save_snapshot,
)


def _snapshot_path(tmp_path: Path) -> Path:
    return tmp_path / "nested" / "strategy_action_snapshot.json"


# ---------------------------------------------------------------------------
# load_snapshot
# ---------------------------------------------------------------------------


def test_load_snapshot_missing_file_returns_none(tmp_path: Path) -> None:
    """First run: no file ⇒ None (caller seeds + emits nothing)."""
    assert load_snapshot(_snapshot_path(tmp_path)) is None


def test_load_snapshot_malformed_json_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "snap.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert load_snapshot(path) is None


def test_load_snapshot_missing_applied_key_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "snap.json"
    path.write_text('{"version": 1}', encoding="utf-8")
    assert load_snapshot(path) is None


def test_load_snapshot_coerces_and_drops_bad_rows(tmp_path: Path) -> None:
    path = tmp_path / "snap.json"
    path.write_text(
        '{"version": 1, "applied": {'
        '"acct": {"rsi": "scout", "bad": 5}, '
        '"broken": "not a dict"}}',
        encoding="utf-8",
    )
    loaded = load_snapshot(path)
    assert loaded == {"acct": {"rsi": "scout"}}


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    path = _snapshot_path(tmp_path)
    current: AppliedStateMap = {"acct": {"rsi": "scout", "orb": "pause"}}
    save_snapshot(current, path)
    assert path.exists()  # parent dir created by save_snapshot
    assert load_snapshot(path) == current


# ---------------------------------------------------------------------------
# diff_snapshots
# ---------------------------------------------------------------------------


def test_diff_no_change_returns_empty() -> None:
    prior: AppliedStateMap = {"acct": {"rsi": "scout"}}
    current: AppliedStateMap = {"acct": {"rsi": "scout"}}
    assert diff_snapshots(prior, current) == []


def test_diff_changed_action_returns_one_transition() -> None:
    prior: AppliedStateMap = {"acct": {"rsi": "scout"}}
    current: AppliedStateMap = {"acct": {"rsi": "keep"}}
    assert diff_snapshots(prior, current) == [
        StrategyActionTransition(
            sub_account_id="acct",
            strategy="rsi",
            prior_action="scout",
            new_action="keep",
        )
    ]


def test_diff_multiple_changes_one_event_each() -> None:
    prior: AppliedStateMap = {
        "acct": {"rsi": "scout", "orb": "pause"},
        "lab": {"vcp": "keep"},
    }
    current: AppliedStateMap = {
        "acct": {"rsi": "keep", "orb": "scout"},
        "lab": {"vcp": "pause"},
    }
    transitions = diff_snapshots(prior, current)
    assert len(transitions) == 3
    # Deterministic sub-account then strategy ordering.
    assert (transitions[0].sub_account_id, transitions[0].strategy) == ("acct", "orb")
    assert transitions[0].prior_action == "pause"
    assert transitions[0].new_action == "scout"
    assert (transitions[1].sub_account_id, transitions[1].strategy) == ("acct", "rsi")
    assert (transitions[2].sub_account_id, transitions[2].strategy) == ("lab", "vcp")


def test_diff_new_strategy_is_not_a_transition() -> None:
    """A strategy absent from the prior snapshot has no prior to transition from."""
    prior: AppliedStateMap = {"acct": {"rsi": "scout"}}
    current: AppliedStateMap = {"acct": {"rsi": "scout", "orb": "pause"}}
    assert diff_snapshots(prior, current) == []


def test_diff_new_sub_account_is_not_a_transition() -> None:
    prior: AppliedStateMap = {"acct": {"rsi": "scout"}}
    current: AppliedStateMap = {
        "acct": {"rsi": "scout"},
        "new": {"orb": "pause"},
    }
    assert diff_snapshots(prior, current) == []


def test_diff_removed_strategy_is_not_a_transition() -> None:
    """A disappearing key is not emitted (only present-in-both changes count)."""
    prior: AppliedStateMap = {"acct": {"rsi": "scout", "orb": "pause"}}
    current: AppliedStateMap = {"acct": {"rsi": "scout"}}
    assert diff_snapshots(prior, current) == []
