"""Tests for ``src.trading.sub_account_migration`` (Phase 19.1).

The migration is a one-shot, idempotent rename that slots the
``default`` sub-account id into legacy ``trades`` / ``portfolio`` /
``proposals`` paths. A marker file at the data-dir root short-
circuits subsequent runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.trading.sub_account_migration import (
    MARKER_FILENAME,
    PERFORMANCE_MARKER_FILENAME,
    migrate_legacy_paths,
)


def _seed_legacy_layout(data_dir: Path) -> None:
    """Plant legacy records under ``data_dir`` for all three modes
    plus a top-level proposal file. The shapes mirror what a pre-19.1
    deployment writes today."""
    for mode in ("paper", "live", "backtest"):
        (data_dir / "trades" / mode).mkdir(parents=True, exist_ok=True)
        (data_dir / "trades" / mode / "trades.json").write_text(
            f'{{"mode":"{mode}","trades":[]}}'
        )
        (data_dir / "portfolio" / mode).mkdir(parents=True, exist_ok=True)
        (data_dir / "portfolio" / mode / "snapshots.json").write_text(
            f'{{"mode":"{mode}","snapshots":[]}}'
        )
    proposals = data_dir / "proposals"
    proposals.mkdir(parents=True, exist_ok=True)
    (proposals / "2026-05-01_BTC-USDT.json").write_text("{}")
    (proposals / "2026-05-01_ETH-USDT.json").write_text("{}")


def test_fresh_dir_renames_all_three_components(tmp_path: Path) -> None:
    """Fresh data dir with full legacy layout: every legacy file
    moves under ``default/`` and the marker is written. Counts
    reflect the actual rename volume so the operator log is truthful."""
    _seed_legacy_layout(tmp_path)

    counts = migrate_legacy_paths(tmp_path)

    # Three modes × one trades file = 3 trades; same for portfolio.
    # Two top-level proposal files.
    assert counts == {
        "trades": 3,
        "portfolio": 3,
        "proposals": 2,
        "performance": 0,
    }

    # Trades migrated under default/ for each mode; legacy file gone.
    for mode in ("paper", "live", "backtest"):
        assert (tmp_path / "trades" / mode / "default" / "trades.json").is_file()
        assert not (tmp_path / "trades" / mode / "trades.json").exists()
        assert (tmp_path / "portfolio" / mode / "default" / "snapshots.json").is_file()
        assert not (tmp_path / "portfolio" / mode / "snapshots.json").exists()

    # Proposals migrated under proposals/default/.
    assert (tmp_path / "proposals" / "default" / "2026-05-01_BTC-USDT.json").is_file()
    assert (tmp_path / "proposals" / "default" / "2026-05-01_ETH-USDT.json").is_file()

    # Marker present so subsequent runs short-circuit.
    assert (tmp_path / MARKER_FILENAME).is_file()


def test_idempotent_rerun_short_circuits(tmp_path: Path) -> None:
    """Marker present → migration is a no-op. Second invocation
    returns zero counts and does not touch the filesystem (we plant
    a sentinel file under the legacy path that should *not* move)."""
    # First pass: real migration completes.
    _seed_legacy_layout(tmp_path)
    migrate_legacy_paths(tmp_path)
    assert (tmp_path / MARKER_FILENAME).is_file()

    # Plant a sentinel file at a legacy location to verify the
    # second pass does not touch it.
    sentinel_dir = tmp_path / "trades" / "paper"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel = sentinel_dir / "trades.json"
    sentinel.write_text('{"second_pass":"sentinel"}')

    # Second pass: short-circuits.
    counts = migrate_legacy_paths(tmp_path)
    assert counts == {
        "trades": 0,
        "portfolio": 0,
        "proposals": 0,
        "performance": 0,
    }
    # Sentinel still in place — proves no rename happened.
    assert sentinel.read_text() == '{"second_pass":"sentinel"}'


def test_no_source_files_writes_marker_and_returns_zero(tmp_path: Path) -> None:
    """Empty data dir (no legacy records yet, e.g. a fresh deploy on
    a new host): migration writes the marker so subsequent boots
    short-circuit, and returns all-zero counts. No error."""
    counts = migrate_legacy_paths(tmp_path)

    assert counts == {
        "trades": 0,
        "portfolio": 0,
        "proposals": 0,
        "performance": 0,
    }
    # Marker IS written even on the no-source path so subsequent
    # boots don't keep re-scanning empty directories.
    assert (tmp_path / MARKER_FILENAME).is_file()


def test_marker_writes_use_atomic_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completion markers route through the shared atomic write helper."""
    calls: list[Path] = []

    def fake_atomic_write(path: Path, text: str) -> None:
        calls.append(path)
        path.write_text(text, encoding="utf-8")

    monkeypatch.setattr(
        "src.trading.sub_account_migration.atomic_write_text",
        fake_atomic_write,
    )

    counts = migrate_legacy_paths(tmp_path)

    assert counts == {
        "trades": 0,
        "portfolio": 0,
        "proposals": 0,
        "performance": 0,
    }
    assert calls == [
        tmp_path / MARKER_FILENAME,
        tmp_path / PERFORMANCE_MARKER_FILENAME,
    ]


def test_partial_pre_existing_finishes_the_rest(tmp_path: Path) -> None:
    """One mode has been hand-migrated already (operator pre-staged
    the new layout), others have not. With the marker absent the
    function still runs and finishes the remaining work; the
    pre-staged file is left untouched."""
    _seed_legacy_layout(tmp_path)

    # Operator hand-migrated paper trades: legacy file removed, new
    # layout already populated with a slightly different content
    # to prove the migrator does not clobber it.
    legacy_paper_trades = tmp_path / "trades" / "paper" / "trades.json"
    legacy_paper_trades.unlink()
    pre_staged_dir = tmp_path / "trades" / "paper" / "default"
    pre_staged_dir.mkdir(parents=True, exist_ok=True)
    pre_staged = pre_staged_dir / "trades.json"
    pre_staged.write_text('{"hand_migrated":"true"}')

    counts = migrate_legacy_paths(tmp_path)

    # Only live + backtest trades migrated this pass (paper already done).
    assert counts["trades"] == 2
    # Portfolio + proposals fully migrated.
    assert counts["portfolio"] == 3
    assert counts["proposals"] == 2

    # Pre-staged file is not clobbered.
    assert pre_staged.read_text() == '{"hand_migrated":"true"}'
    # The other modes did get migrated.
    assert (tmp_path / "trades" / "live" / "default" / "trades.json").is_file()
    assert (tmp_path / "trades" / "backtest" / "default" / "trades.json").is_file()
    # Marker written.
    assert (tmp_path / MARKER_FILENAME).is_file()


def test_skip_when_target_already_exists(tmp_path: Path) -> None:
    """When BOTH the legacy file AND the new-layout target exist
    simultaneously (a half-completed prior run, or operator pre-stage
    mid-flight), the migrator leaves the legacy file alone rather
    than clobbering the target. Marker is not written because a later
    boot must keep surfacing the unresolved legacy record."""
    # Plant only paper-mode legacy + pre-staged target.
    paper_dir = tmp_path / "trades" / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    legacy = paper_dir / "trades.json"
    legacy.write_text('{"legacy":"data"}')
    target_dir = paper_dir / "default"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "trades.json"
    target.write_text('{"target":"existing"}')

    counts = migrate_legacy_paths(tmp_path)

    # Nothing renamed for trades — target already existed.
    assert counts["trades"] == 0
    # Legacy file and target both still exist with their original
    # contents, untouched.
    assert legacy.read_text() == '{"legacy":"data"}'
    assert target.read_text() == '{"target":"existing"}'
    # Marker withheld so unresolved legacy data is not permanently hidden.
    assert not (tmp_path / MARKER_FILENAME).exists()


def test_performance_tree_migrates_under_default_even_after_19_1_marker(
    tmp_path: Path,
) -> None:
    """Phase 19.2 performance migration has its own marker, so a
    deployment that already completed 19.1 still picks it up."""
    (tmp_path / MARKER_FILENAME).write_text("")
    tech_dir = tmp_path / "performance" / "rsi_4h"
    tech_dir.mkdir(parents=True)
    (tech_dir / "records.json").write_text("[]")

    counts = migrate_legacy_paths(tmp_path)

    assert counts["performance"] == 1
    assert (tmp_path / "performance" / "default" / "rsi_4h" / "records.json").is_file()
    assert not tech_dir.exists()
