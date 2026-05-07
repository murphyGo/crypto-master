"""One-shot migration of legacy on-disk paths into the sub-account layout.

Phase 19.1 introduces the ``{sub_account_id}`` segment to the
persistence layout (DESIGN.md §9.5). Existing deployments have
records under the legacy paths::

    data/trades/{mode}/trades.json
    data/portfolio/{mode}/snapshots.json
    data/proposals/{date}_{symbol}.json

This module renames each into the new layout, slotting the back-compat
``default`` sub-account id into the path::

    data/trades/{mode}/default/trades.json
    data/portfolio/{mode}/default/snapshots.json
    data/proposals/default/{date}_{symbol}.json

The performance subtree (``data/performance/{technique}/...``) is
**deferred to 19.2** because the new layout adds a sub-account level
*above* the technique level — moving it correctly requires the engine
fan-out work landing in 19.2.

The migration is **idempotent** via a marker file
(``data/.subaccounts_migrated_v19_1``) written on the first successful
run; subsequent invocations short-circuit immediately. The marker
sits at ``data_dir`` root so a fresh data dir on a new host is
detected and migrated on first boot regardless of whether records
exist.

Related Requirements:
- FR-036: Sub-Account Capital Isolation (the on-disk migration that
  unlocks the new layout for the existing single-seed deployment).
"""

from __future__ import annotations

import os
from pathlib import Path

from src.logger import get_logger
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID

logger = get_logger("crypto_master.trading.sub_account_migration")

# Marker file written at ``data_dir / MARKER_FILENAME`` once the
# migration has run successfully. Versioned in the name so a future
# reorganisation (e.g. Phase 19.2 performance subtree migration) can
# ship a separate marker without overlapping this one.
MARKER_FILENAME = ".subaccounts_migrated_v19_1"
PERFORMANCE_MARKER_FILENAME = ".performance_migrated_v19_2"

# Modes whose records sit under ``{root}/{mode}/...``. The backtest
# subtree is included so backtester output produced by an upgraded
# binary lands under the correct ``default/`` namespace from the
# start.
_MODE_DIRS = ("paper", "live", "backtest")


def migrate_legacy_paths(data_dir: Path) -> dict[str, int]:
    """Move legacy records into the ``default`` sub-account subtree.

    Idempotent across restarts: the first successful invocation writes
    a marker file at ``data_dir / MARKER_FILENAME``; subsequent calls
    short-circuit and return zero counts without touching the
    filesystem.

    Args:
        data_dir: Root data directory (typically
            ``Settings.data_dir``). The marker file is written here
            so it survives mode-dir renames.

    Returns:
        Dict of component name to the number of files renamed by this
        invocation: ``{"trades": N, "portfolio": M, "proposals": K}``.
        Always ``{"trades": 0, "portfolio": 0, "proposals": 0}`` on
        the short-circuit path. Operator-log friendly: callers can
        skip the log line entirely when the sum is zero.
    """
    counts = {"trades": 0, "portfolio": 0, "proposals": 0, "performance": 0}

    marker = data_dir / MARKER_FILENAME
    data_dir.mkdir(parents=True, exist_ok=True)

    if not marker.exists():
        counts["trades"] = _migrate_mode_subtree(
            root=data_dir / "trades",
            leaf_name="trades.json",
        )
        counts["portfolio"] = _migrate_mode_subtree(
            root=data_dir / "portfolio",
            leaf_name="snapshots.json",
        )
        counts["proposals"] = _migrate_proposals(data_dir / "proposals")
        if not _has_v19_1_conflicts(data_dir):
            marker.write_text("")

    performance_marker = data_dir / PERFORMANCE_MARKER_FILENAME
    if not performance_marker.exists():
        counts["performance"] = _migrate_performance(data_dir / "performance")
        if not _has_performance_conflicts(data_dir / "performance"):
            performance_marker.write_text("")
    return counts


def _has_v19_1_conflicts(data_dir: Path) -> bool:
    return (
        _has_mode_subtree_conflicts(data_dir / "trades", "trades.json")
        or _has_mode_subtree_conflicts(data_dir / "portfolio", "snapshots.json")
        or _has_proposal_conflicts(data_dir / "proposals")
    )


def _has_mode_subtree_conflicts(root: Path, leaf_name: str) -> bool:
    for mode in _MODE_DIRS:
        mode_dir = root / mode
        legacy_leaf = mode_dir / leaf_name
        target_leaf = mode_dir / DEFAULT_SUB_ACCOUNT_ID / leaf_name
        if legacy_leaf.exists() and target_leaf.exists():
            return True
    return False


def _has_proposal_conflicts(root: Path) -> bool:
    if not root.exists():
        return False
    for entry in root.iterdir():
        if entry.is_file() and entry.suffix == ".json":
            if (root / DEFAULT_SUB_ACCOUNT_ID / entry.name).exists():
                return True
    return False


def _has_performance_conflicts(root: Path) -> bool:
    if not root.exists():
        return False
    target_root = root / DEFAULT_SUB_ACCOUNT_ID
    for entry in root.iterdir():
        if not entry.is_dir() or entry.name == DEFAULT_SUB_ACCOUNT_ID:
            continue
        if not ((entry / "records.json").exists() or (entry / "summary.json").exists()):
            continue
        if (target_root / entry.name).exists():
            return True
    return False


def _migrate_mode_subtree(*, root: Path, leaf_name: str) -> int:
    """Migrate ``{root}/{mode}/{leaf}`` → ``{root}/{mode}/default/{leaf}``.

    Iterates over the canonical mode dirs (``paper``, ``live``,
    ``backtest``). Missing dirs are skipped silently — a deployment
    that has only ever run paper mode will not have a ``live/``
    subtree, and that's fine.

    The ``default`` subdirectory is created on demand. If a legacy
    leaf is missing but a ``default/`` subdirectory already exists
    (partial migration mid-flight from a previous half-completed
    boot), we leave it alone.

    Args:
        root: Component root, e.g. ``data/trades`` or ``data/portfolio``.
        leaf_name: Filename to look for under each mode dir, e.g.
            ``"trades.json"`` or ``"snapshots.json"``.

    Returns:
        The number of files successfully renamed by this call.
    """
    if not root.exists():
        return 0

    moved = 0
    for mode in _MODE_DIRS:
        mode_dir = root / mode
        legacy_leaf = mode_dir / leaf_name
        if not legacy_leaf.is_file():
            continue
        target_dir = mode_dir / DEFAULT_SUB_ACCOUNT_ID
        target_dir.mkdir(parents=True, exist_ok=True)
        target_leaf = target_dir / leaf_name
        if target_leaf.exists():
            # The new-layout target already exists (e.g. an operator
            # pre-staged it). Don't clobber — leave the legacy file
            # in place for manual reconciliation; the marker still
            # gets written so we don't loop on it forever.
            logger.warning(
                "sub-account migration: %s already exists; "
                "leaving legacy %s in place",
                target_leaf,
                legacy_leaf,
            )
            continue
        os.replace(legacy_leaf, target_leaf)
        moved += 1
    return moved


def _migrate_proposals(root: Path) -> int:
    """Migrate ``{root}/{date}_{symbol}.json`` → ``{root}/default/...``.

    The proposals dir is not mode-keyed today; legacy records sit
    directly at the root. We scan for top-level ``.json`` files and
    move each one into the ``default/`` subdirectory.

    Existing subdirectories at ``root`` (e.g. an ``archive/`` from
    Phase 11.4 or a pre-staged ``default/``) are left untouched —
    only top-level ``.json`` files are candidates.
    """
    if not root.exists():
        return 0

    target_dir = root / DEFAULT_SUB_ACCOUNT_ID
    moved = 0
    for entry in root.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix != ".json":
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        target_leaf = target_dir / entry.name
        if target_leaf.exists():
            logger.warning(
                "sub-account migration: %s already exists; "
                "leaving legacy %s in place",
                target_leaf,
                entry,
            )
            continue
        os.replace(entry, target_leaf)
        moved += 1
    return moved


def _migrate_performance(root: Path) -> int:
    """Migrate ``performance/{technique}`` → ``performance/default/{technique}``.

    Phase 19.2 introduces the sub-account level above each technique
    directory. The migration moves only top-level technique directories
    that contain either ``records.json`` or ``summary.json``; existing
    ``default/`` or other operator-created sub-account directories are
    left untouched.
    """
    if not root.exists():
        return 0

    target_root = root / DEFAULT_SUB_ACCOUNT_ID
    moved = 0
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name == DEFAULT_SUB_ACCOUNT_ID:
            continue
        if not ((entry / "records.json").exists() or (entry / "summary.json").exists()):
            continue
        target = target_root / entry.name
        if target.exists():
            logger.warning(
                "sub-account migration: %s already exists; "
                "leaving legacy performance dir %s in place",
                target,
                entry,
            )
            continue
        target_root.mkdir(parents=True, exist_ok=True)
        os.replace(entry, target)
        moved += 1
    return moved


__all__ = [
    "MARKER_FILENAME",
    "PERFORMANCE_MARKER_FILENAME",
    "migrate_legacy_paths",
]
