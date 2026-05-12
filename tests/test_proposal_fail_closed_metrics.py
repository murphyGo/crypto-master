"""Tests for the DEBT-061 fail-closed metrics tracker.

Pins the persistence + restart-safety contract that
``src/proposal/fail_closed_metrics.py`` is built on. The proposal
engine increment-site tests live in ``test_proposal_engine.py``
alongside the engine's other behaviour pins.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.proposal.fail_closed_metrics import (
    FailClosedMetricsTracker,
    StrategyFailClosedCounts,
)

# =============================================================================
# StrategyFailClosedCounts.fail_closed_rate
# =============================================================================


def test_fail_closed_rate_zero_when_no_emissions() -> None:
    counts = StrategyFailClosedCounts(technique_name="tech_a")

    assert counts.fail_closed_rate == 0.0


def test_fail_closed_rate_is_ratio_of_counters() -> None:
    counts = StrategyFailClosedCounts(
        technique_name="tech_a",
        proposals_emitted=10,
        proposals_fail_closed=3,
    )

    assert counts.fail_closed_rate == 0.3


def test_fail_closed_rate_one_when_all_emissions_fail() -> None:
    counts = StrategyFailClosedCounts(
        technique_name="tech_a",
        proposals_emitted=5,
        proposals_fail_closed=5,
    )

    assert counts.fail_closed_rate == 1.0


# =============================================================================
# FailClosedMetricsTracker — empty / missing state
# =============================================================================


def test_get_returns_zero_snapshot_when_no_file(tmp_path: Path) -> None:
    """The 'never emitted' case is just the zero snapshot, not an error."""
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)

    counts = tracker.get("tech_a")

    assert counts.technique_name == "tech_a"
    assert counts.proposals_emitted == 0
    assert counts.proposals_fail_closed == 0
    assert counts.fail_closed_rate == 0.0


def test_list_techniques_empty_when_dir_missing(tmp_path: Path) -> None:
    tracker = FailClosedMetricsTracker(data_dir=tmp_path / "does_not_exist")

    assert tracker.list_techniques() == []


# =============================================================================
# Increment + persistence round-trip
# =============================================================================


def test_record_emitted_persists_and_round_trips(tmp_path: Path) -> None:
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)

    tracker.record_emitted("tech_a", "1.0.0")
    tracker.record_emitted("tech_a", "1.0.0")
    tracker.record_emitted("tech_a", "1.0.0")

    counts = tracker.get("tech_a")
    assert counts.proposals_emitted == 3
    assert counts.proposals_fail_closed == 0
    assert counts.technique_version == "1.0.0"


def test_record_fail_closed_persists_and_round_trips(tmp_path: Path) -> None:
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)

    tracker.record_fail_closed("tech_a", "1.0.0")

    counts = tracker.get("tech_a")
    assert counts.proposals_emitted == 0
    assert counts.proposals_fail_closed == 1


def test_emitted_and_fail_closed_track_independently(tmp_path: Path) -> None:
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)

    for _ in range(4):
        tracker.record_emitted("tech_a", "1.0.0")
    for _ in range(3):
        tracker.record_fail_closed("tech_a", "1.0.0")

    counts = tracker.get("tech_a")
    assert counts.proposals_emitted == 4
    assert counts.proposals_fail_closed == 3
    assert counts.fail_closed_rate == 0.75


def test_counters_survive_tracker_re_instantiation(tmp_path: Path) -> None:
    """DEBT-061 restart-safety: counters must survive process restart."""
    tracker_1 = FailClosedMetricsTracker(data_dir=tmp_path)
    tracker_1.record_emitted("tech_a", "1.0.0")
    tracker_1.record_emitted("tech_a", "1.0.0")
    tracker_1.record_fail_closed("tech_a", "1.0.0")

    # Simulate restart: fresh tracker against the same data dir.
    tracker_2 = FailClosedMetricsTracker(data_dir=tmp_path)
    counts = tracker_2.get("tech_a")

    assert counts.proposals_emitted == 2
    assert counts.proposals_fail_closed == 1


def test_counters_scoped_per_sub_account(tmp_path: Path) -> None:
    """Two sub-accounts running the same strategy keep separate counters.

    Legacy form: a tracker constructed with ``sub_account_id=X`` uses
    ``X`` as the default fallback for record/get calls that don't
    supply one. This pin keeps the pre-quant-fix constructor knob
    working so callers that haven't migrated still get per-sub-account
    isolation.
    """
    paper = FailClosedMetricsTracker(data_dir=tmp_path, sub_account_id="paper")
    live = FailClosedMetricsTracker(data_dir=tmp_path, sub_account_id="live")

    paper.record_emitted("tech_a", "1.0.0")
    paper.record_emitted("tech_a", "1.0.0")
    live.record_emitted("tech_a", "1.0.0")

    assert paper.get("tech_a").proposals_emitted == 2
    assert live.get("tech_a").proposals_emitted == 1


def test_counters_routed_per_call_sub_account(tmp_path: Path) -> None:
    """Per-call ``sub_account_id`` routes to its own namespace.

    The post-quant-fix contract: a single tracker instance serves every
    sub-account in the engine, and each ``record_*`` / ``get`` call
    routes to ``<sub_account_id>/<technique>/fail_closed.json``.
    Two sub-accounts running the same strategy must NOT aggregate
    under a shared default — that's the per-sub-account observability
    plumbing defect this fix exists for.
    """
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)

    tracker.record_emitted("tech_a", "1.0.0", sub_account_id="paper")
    tracker.record_emitted("tech_a", "1.0.0", sub_account_id="paper")
    tracker.record_emitted("tech_a", "1.0.0", sub_account_id="paper_alt")
    tracker.record_fail_closed("tech_a", "1.0.0", sub_account_id="paper_alt")

    paper_counts = tracker.get("tech_a", sub_account_id="paper")
    paper_alt_counts = tracker.get("tech_a", sub_account_id="paper_alt")
    default_counts = tracker.get("tech_a")  # uses constructor default ("default")

    assert paper_counts.proposals_emitted == 2
    assert paper_counts.proposals_fail_closed == 0
    assert paper_counts.sub_account_id == "paper"

    assert paper_alt_counts.proposals_emitted == 1
    assert paper_alt_counts.proposals_fail_closed == 1
    assert paper_alt_counts.sub_account_id == "paper_alt"

    # The default sub-account namespace must be untouched — the bug
    # this regression-pin guards against was every sub-account's
    # emissions aggregating under ``default/``.
    assert default_counts.proposals_emitted == 0
    assert default_counts.proposals_fail_closed == 0


def test_per_call_sub_account_overrides_constructor_default(tmp_path: Path) -> None:
    """Per-call argument wins over the constructor's fallback."""
    tracker = FailClosedMetricsTracker(data_dir=tmp_path, sub_account_id="paper")

    tracker.record_emitted("tech_a", "1.0.0", sub_account_id="live")

    assert tracker.get("tech_a", sub_account_id="live").proposals_emitted == 1
    # The constructor's "paper" namespace did NOT see the increment.
    assert tracker.get("tech_a").proposals_emitted == 0


def test_per_call_writes_under_per_call_sub_account_path(tmp_path: Path) -> None:
    """File lands under the per-call sub-account, not the constructor's."""
    tracker = FailClosedMetricsTracker(data_dir=tmp_path, sub_account_id="paper")
    tracker.record_emitted("tech_a", "1.0.0", sub_account_id="live")

    assert (tmp_path / "live" / "tech_a" / "fail_closed.json").exists()
    assert not (tmp_path / "paper" / "tech_a" / "fail_closed.json").exists()


def test_list_techniques_scoped_to_per_call_sub_account(tmp_path: Path) -> None:
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)
    tracker.record_emitted("tech_a", "1.0.0", sub_account_id="paper")
    tracker.record_emitted("tech_b", "1.0.0", sub_account_id="paper_alt")

    assert tracker.list_techniques(sub_account_id="paper") == ["tech_a"]
    assert tracker.list_techniques(sub_account_id="paper_alt") == ["tech_b"]


def test_counters_isolated_per_technique(tmp_path: Path) -> None:
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)

    tracker.record_emitted("tech_a", "1.0.0")
    tracker.record_fail_closed("tech_b", "1.0.0")

    a = tracker.get("tech_a")
    b = tracker.get("tech_b")
    assert (a.proposals_emitted, a.proposals_fail_closed) == (1, 0)
    assert (b.proposals_emitted, b.proposals_fail_closed) == (0, 1)


def test_record_emitted_updates_technique_version(tmp_path: Path) -> None:
    """Version bumps refresh the stored version (forensic value), not reset counts."""
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)

    tracker.record_emitted("tech_a", "1.0.0")
    tracker.record_emitted("tech_a", "1.1.0")

    counts = tracker.get("tech_a")
    assert counts.proposals_emitted == 2
    assert counts.technique_version == "1.1.0"


def test_list_techniques_lists_only_techniques_with_snapshots(tmp_path: Path) -> None:
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)
    tracker.record_emitted("tech_b", "1.0.0")
    tracker.record_emitted("tech_a", "1.0.0")

    assert tracker.list_techniques() == ["tech_a", "tech_b"]


# =============================================================================
# On-disk layout — DEBT-061 spec says "persist alongside performance data"
# =============================================================================


def test_snapshot_written_under_sub_account_technique_path(tmp_path: Path) -> None:
    """File lands at data_dir/<sub_account>/<technique>/fail_closed.json."""
    tracker = FailClosedMetricsTracker(data_dir=tmp_path, sub_account_id="paper")
    tracker.record_emitted("tech_a", "1.0.0")

    expected = tmp_path / "paper" / "tech_a" / "fail_closed.json"
    assert expected.exists()


def test_snapshot_is_valid_json_with_known_keys(tmp_path: Path) -> None:
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)
    tracker.record_emitted("tech_a", "1.2.3")
    tracker.record_fail_closed("tech_a", "1.2.3")

    path = tmp_path / "default" / "tech_a" / "fail_closed.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["sub_account_id"] == "default"
    assert payload["technique_name"] == "tech_a"
    assert payload["technique_version"] == "1.2.3"
    assert payload["proposals_emitted"] == 1
    assert payload["proposals_fail_closed"] == 1
    assert "last_updated" in payload


def test_corrupt_json_falls_back_to_zero_snapshot(tmp_path: Path) -> None:
    """A torn write should not crash the tracker; degrade to zero snapshot."""
    tracker = FailClosedMetricsTracker(data_dir=tmp_path)
    path = tmp_path / "default" / "tech_a" / "fail_closed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    counts = tracker.get("tech_a")

    assert counts.proposals_emitted == 0
    assert counts.proposals_fail_closed == 0
