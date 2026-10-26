"""Skip unused checkpoint admission work without weakening source proof."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.dashboard import projections
from src.dashboard.checkpoint_store import CheckpointStore
from src.dashboard.read_models import Limits, Query
from src.dashboard.sources import Manifest
from src.proposal.interaction import ProposalRecord
from src.utils.bounded_read import ReadFailure
from tests.test_dashboard_trading import _make_proposal

NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


def checkpoint_store(root):
    directory = root / "derived"
    directory.mkdir(exist_ok=True)
    return CheckpointStore(directory)


def write_proposal(root, name="one", size=None):
    folder = root / "proposals"
    folder.mkdir(exist_ok=True)
    record = ProposalRecord(
        proposal=_make_proposal(name).model_copy(update={"created_at": NOW})
    )
    raw = record.model_dump_json().encode()
    if size is not None:
        assert len(raw) <= size
        raw += b" " * (size - len(raw))
    path = folder / f"{name}.json"
    path.write_bytes(raw)
    return path


def project(query, *, previous=None, store=None):
    result = None
    for value in projections.build_projection(
        query, Limits(), previous=previous, checkpoint_store=store
    ):
        if value is not None:
            result = value
    assert result is not None
    return result


def count_optional_source_walks(monkeypatch):
    counts = {"outside_verification": 0, "verified": 0}
    verifying = False
    files, verify = Manifest.files.fget, Manifest.verify

    def counted_files(manifest):
        if not verifying:
            counts["outside_verification"] += 1
        yield from files(manifest)

    def counted_verify(manifest):
        nonlocal verifying
        verifying = True
        try:
            verify(manifest)
            counts["verified"] += 1
        finally:
            verifying = False

    monkeypatch.setattr(Manifest, "files", property(counted_files))
    monkeypatch.setattr(Manifest, "verify", counted_verify)
    return counts


@pytest.mark.parametrize("enabled_store", [False, True])
def test_unchanged_proposals_skip_unused_source_walk_but_verify_manifest(
    tmp_path, monkeypatch, enabled_store
):
    write_proposal(tmp_path)
    query = Query(tmp_path, "proposals", at=NOW)
    expected = project(query)
    store = checkpoint_store(tmp_path) if enabled_store else None
    counts = count_optional_source_walks(monkeypatch)
    assert (
        project(query, previous=json.dumps(expected).encode(), store=store) == expected
    )
    assert counts == {"outside_verification": 0, "verified": 1}


def test_disabled_checkpoint_preparation_skips_only_the_eligibility_walk(
    tmp_path, monkeypatch
):
    write_proposal(tmp_path)
    query = Query(tmp_path, "proposals", at=NOW)
    expected = project(query)
    store = checkpoint_store(tmp_path)
    monkeypatch.setattr(store, "prepare", lambda query: False)
    counts = count_optional_source_walks(monkeypatch)
    assert project(query, store=store) == expected
    # The canonical reduction and final captured-byte coverage still walk all
    # sources; the unused optional-cache eligibility walk is the only removal.
    assert counts == {"outside_verification": 2, "verified": 2}


@pytest.mark.parametrize("mutation", ["file", "membership"])
def test_unchanged_fast_path_still_rejects_concurrent_source_changes(
    tmp_path, monkeypatch, mutation
):
    path = write_proposal(tmp_path)
    query = Query(tmp_path, "proposals", at=NOW)
    previous = json.dumps(project(query)).encode()
    refresh = projections.refresh_projection

    def changing_refresh(*args, **kwargs):
        value = refresh(*args, **kwargs)
        if mutation == "file":
            path.write_bytes(path.read_bytes() + b" ")
        else:
            write_proposal(tmp_path, "added")
        return value

    monkeypatch.setattr(projections, "refresh_projection", changing_refresh)
    with pytest.raises(ReadFailure, match="source_changed"):
        project(query, previous=previous, store=checkpoint_store(tmp_path))


@pytest.mark.parametrize(
    "sizes,eligible",
    [
        ([], False),
        ([16383], False),
        ([16384], True),
        ([16385], True),
        ([8192, 24575], False),
        ([8192, 24576], True),
    ],
)
def test_checkpoint_average_size_boundary_is_unchanged(
    tmp_path, monkeypatch, sizes, eligible
):
    for index, size in enumerate(sizes):
        write_proposal(tmp_path, str(index), size)
    query = Query(tmp_path, "proposals", at=NOW)
    expected = project(query)
    store = checkpoint_store(tmp_path)
    calls = []
    session = store.session

    def counted_session(query):
        calls.append(query)
        return session(query)

    monkeypatch.setattr(store, "session", counted_session)
    assert project(query, store=store) == expected
    assert bool(calls) is eligible


def test_changed_membership_rebuilds_and_malformed_changed_file_is_not_reused(tmp_path):
    path = write_proposal(tmp_path)
    query = Query(tmp_path, "proposals", at=NOW)
    old = json.dumps(project(query)).encode()
    write_proposal(tmp_path, "two")
    store = checkpoint_store(tmp_path)
    updated = project(query, previous=old, store=store)
    assert updated == project(query)
    assert updated["source_coverage"]["files"] == 2
    path.write_text("{")
    with pytest.raises(ReadFailure, match="malformed_json"):
        project(query, previous=json.dumps(updated).encode(), store=store)


def test_unchanged_digest_still_rejects_reversed_evaluation_clock(tmp_path):
    write_proposal(tmp_path)
    previous = json.dumps(project(Query(tmp_path, "proposals", at=NOW))).encode()
    with pytest.raises(ReadFailure, match="evaluation_clock_reversed"):
        project(
            Query(tmp_path, "proposals", at=NOW - timedelta(seconds=1)),
            previous=previous,
            store=checkpoint_store(tmp_path),
        )
