"""Persisted applied-state snapshot for strategy-tuning (DEBT-069(d)).

The runtime gate enforces ``sub_account.strategy_tuning.applied_action_for(
strategy)`` — the *applied* state. That state lives only in the YAML config
(operators apply a recommendation by hand + restart, per the resolved
Open Decision). When an operator flips a strategy's applied action and
restarts the engine, nothing records the transition: the
``ActivityEventType.STRATEGY_ACTION_APPLIED`` enum value has existed since
strategy-tuning Slice 1 but was never emitted.

This module owns the small durable snapshot that lets the engine detect
``prior-state -> new-state`` transitions across restarts:

* :func:`load_snapshot` reads the prior applied-state map (or ``None`` on a
  first run / missing / malformed file — fail-soft, never crash the engine).
* :func:`diff_snapshots` is the pure transition detector.
* :func:`save_snapshot` persists the current map via the canonical
  :func:`src.utils.io.atomic_write_text` (DEBT-028 single source of truth).

The emission of the activity events themselves stays in
:mod:`src.runtime.engine` so it follows the existing
``self.activity_log.append(...)`` idiom; this module is IO + pure diff only.

Snapshot shape on disk (JSON)::

    {
      "version": 1,
      "applied": {
        "<sub_account_id>": {"<strategy>": "<action value>", ...},
        ...
      }
    }

First run with no prior snapshot ⇒ :func:`load_snapshot` returns ``None`` and
the engine seeds the snapshot WITHOUT emitting any events (avoids a spurious
event storm on first deploy).

Related:
- DEBT-069(d): ``STRATEGY_ACTION_APPLIED`` emission.
- DEBT-028: ``atomic_write_text`` single source of truth for atomic writes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.logger import get_logger
from src.utils.io import atomic_write_text

logger = get_logger("crypto_master.runtime.strategy_action_snapshot")

DEFAULT_STRATEGY_ACTION_SNAPSHOT_PATH = Path("data/runtime/strategy_action_snapshot.json")
SNAPSHOT_VERSION = 1

# A snapshot maps sub_account_id -> {strategy_name -> applied action value}.
AppliedStateMap = dict[str, dict[str, str]]


@dataclass(frozen=True)
class StrategyActionTransition:
    """One detected ``prior -> new`` applied-action change.

    Attributes:
        sub_account_id: Sub-account whose strategy changed.
        strategy: Technique name.
        prior_action: Applied action value on the previous run.
        new_action: Applied action value on this run.
    """

    sub_account_id: str
    strategy: str
    prior_action: str
    new_action: str


def load_snapshot(path: Path = DEFAULT_STRATEGY_ACTION_SNAPSHOT_PATH) -> AppliedStateMap | None:
    """Load the prior applied-state snapshot.

    Returns ``None`` when the file is missing (first run) or unreadable /
    malformed. ``None`` is the signal to the caller to SEED the snapshot
    and emit nothing — never to treat a corrupt file as "everything
    changed" and storm the activity log. Malformed files log a warning
    and are treated like a first run.
    """
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning(
            "strategy-action snapshot %s unreadable (%s); treating as first run",
            path,
            exc,
        )
        return None
    applied = raw.get("applied") if isinstance(raw, dict) else None
    if not isinstance(applied, dict):
        logger.warning(
            "strategy-action snapshot %s malformed (no 'applied' map); "
            "treating as first run",
            path,
        )
        return None
    # Coerce to the strict ``dict[str, dict[str, str]]`` shape, dropping any
    # row that does not match so a partially-corrupt file degrades to a
    # first-run reseed rather than crashing the diff.
    result: AppliedStateMap = {}
    for sub_account_id, strategies in applied.items():
        if not isinstance(strategies, dict):
            continue
        coerced: dict[str, str] = {
            str(name): str(action)
            for name, action in strategies.items()
            if isinstance(action, str)
        }
        result[str(sub_account_id)] = coerced
    return result


def diff_snapshots(
    prior: AppliedStateMap,
    current: AppliedStateMap,
) -> list[StrategyActionTransition]:
    """Return one transition per ``(sub_account, strategy)`` whose action changed.

    Pure. Only strategies present in BOTH snapshots with a *different*
    action produce a transition. A strategy that newly appears (or one
    that disappears) is NOT a transition — the engine's applied-state
    default is ``keep`` for any missing strategy, and a brand-new
    ``(sub_account, strategy)`` pair has no meaningful "prior" applied
    action to transition from, so emitting on it would be noise.
    """
    transitions: list[StrategyActionTransition] = []
    for sub_account_id in sorted(current):
        prior_strategies = prior.get(sub_account_id)
        if prior_strategies is None:
            continue
        current_strategies = current[sub_account_id]
        for strategy in sorted(current_strategies):
            new_action = current_strategies[strategy]
            prior_action = prior_strategies.get(strategy)
            if prior_action is None or prior_action == new_action:
                continue
            transitions.append(
                StrategyActionTransition(
                    sub_account_id=sub_account_id,
                    strategy=strategy,
                    prior_action=prior_action,
                    new_action=new_action,
                )
            )
    return transitions


def save_snapshot(
    current: AppliedStateMap,
    path: Path = DEFAULT_STRATEGY_ACTION_SNAPSHOT_PATH,
) -> None:
    """Persist the current applied-state map atomically.

    Creates the parent directory if needed (``atomic_write_text`` itself
    does not), then writes via the canonical atomic helper so a reader
    never observes a half-written snapshot.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": SNAPSHOT_VERSION, "applied": current}
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))


__all__ = [
    "DEFAULT_STRATEGY_ACTION_SNAPSHOT_PATH",
    "SNAPSHOT_VERSION",
    "AppliedStateMap",
    "StrategyActionTransition",
    "diff_snapshots",
    "load_snapshot",
    "save_snapshot",
]
