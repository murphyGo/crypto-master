"""Tests for :func:`src.utils.io.atomic_write_text` (Phase 22.1 / DEBT-028).

The contract under test:

1. **Happy path**: target lands with the requested payload; no
   ``.tmp`` sibling is left behind.
2. **Crash mid-write**: simulating a failure during the temp write
   leaves the destination's *previous* contents intact (or absent if
   the destination didn't exist), and any ``.tmp`` artefact is
   cleaned up so the directory listing stays clean.
3. **Crash between tmp-write and replace**: simulating a failure
   after the temp file has been written but before ``os.replace``
   runs leaves the destination's *previous* contents intact. This is
   the precise failure mode DEBT-028 calls out.
4. **No half-written file**: the destination's size, when present,
   matches one of the well-formed payloads (old or new) — never a
   truncated prefix.
5. **Concurrent writers**: two writers racing against the same path
   resolve last-writer-wins; both candidate payloads are well-formed
   on disk for any reader observing intermediate states.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from src.utils.io import atomic_write_text, read_text

# =============================================================================
# Happy path
# =============================================================================


class TestHappyPath:
    """The destination lands fully written; no debris left behind."""

    def test_writes_payload_to_destination(self, tmp_path: Path) -> None:
        path = tmp_path / "record.json"
        atomic_write_text(path, '{"k": "v"}')
        assert path.read_text(encoding="utf-8") == '{"k": "v"}'

    def test_no_tmp_sibling_left_after_success(self, tmp_path: Path) -> None:
        path = tmp_path / "record.json"
        atomic_write_text(path, '{"k": "v"}')
        # Per-call tmp paths use a uuid token; assert no ``.tmp``
        # debris of any shape lingers in the destination directory.
        leftover = list(tmp_path.glob("*.tmp"))
        assert (
            leftover == []
        ), f"Successful write should leave no .tmp debris; got {leftover}"

    def test_overwrites_existing_destination(self, tmp_path: Path) -> None:
        path = tmp_path / "record.json"
        path.write_text("OLD", encoding="utf-8")
        atomic_write_text(path, "NEW")
        assert path.read_text(encoding="utf-8") == "NEW"

    def test_respects_explicit_encoding(self, tmp_path: Path) -> None:
        path = tmp_path / "record.txt"
        # The character below survives utf-16 round-trip.
        atomic_write_text(path, "é", encoding="utf-16")
        assert path.read_text(encoding="utf-16") == "é"

    def test_no_suffix_path_still_atomic(self, tmp_path: Path) -> None:
        # Pathological: callers occasionally hand suffix-less paths.
        # The helper builds the tmp name from the suffix string, so
        # an empty suffix is still legal and the result is still
        # well-defined.
        path = tmp_path / "record"
        atomic_write_text(path, "hello")
        assert path.read_text(encoding="utf-8") == "hello"
        leftover = list(tmp_path.glob("*.tmp"))
        assert (
            leftover == []
        ), f"Successful write should leave no .tmp debris; got {leftover}"


# =============================================================================
# Failure modes — pre-replace and at-replace
# =============================================================================


class TestCrashMidWrite:
    """Failures during the temp-write phase leave the destination intact."""

    def test_temp_write_failure_preserves_prior_contents(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ``Path.write_text`` raises mid-write, destination is unchanged."""
        path = tmp_path / "record.json"
        path.write_text("OLD", encoding="utf-8")

        original_write_text = Path.write_text

        def boom(self: Path, *args: object, **kwargs: object) -> int:
            # Only fail for the .tmp sibling; let the test fixture
            # write to the real path through the original.
            if self.name.endswith(".tmp"):
                raise OSError("simulated disk failure")
            return original_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "write_text", boom)

        with pytest.raises(OSError, match="simulated disk failure"):
            atomic_write_text(path, "NEW")

        # Destination still carries the prior contents — the partial
        # write never reached ``os.replace``.
        assert path.read_text(encoding="utf-8") == "OLD"

    def test_temp_write_failure_cleans_up_partial_tmp(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A partial ``.tmp`` from a failed write does not linger."""
        path = tmp_path / "record.json"
        path.write_text("OLD", encoding="utf-8")

        original_write_text = Path.write_text

        def write_then_boom(
            self: Path,
            *args: object,
            **kwargs: object,
        ) -> int:
            if self.name.endswith(".tmp"):
                # Simulate the partial-write case: the bytes hit disk,
                # then the OS reports a failure (e.g. ENOSPC after
                # buffer flush). The .tmp now exists on disk.
                original_write_text(self, "PARTIAL", encoding="utf-8")
                raise OSError("simulated post-write fault")
            return original_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "write_text", write_then_boom)

        with pytest.raises(OSError, match="simulated post-write fault"):
            atomic_write_text(path, "NEW")

        assert path.read_text(encoding="utf-8") == "OLD"
        leftover = list(tmp_path.glob("*.tmp"))
        assert (
            leftover == []
        ), f"Helper should clean up its own .tmp after a failure; got {leftover}"


class TestCrashBeforeReplace:
    """The DEBT-028 case: tmp file written, but ``os.replace`` raises."""

    def test_replace_failure_preserves_prior_contents(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = tmp_path / "record.json"
        path.write_text("OLD", encoding="utf-8")

        def boom(src: object, dst: object) -> None:
            raise OSError("simulated rename failure")

        monkeypatch.setattr("src.utils.io.os.replace", boom)

        with pytest.raises(OSError, match="simulated rename failure"):
            atomic_write_text(path, "NEW")

        # Destination unchanged — the swap never happened.
        assert path.read_text(encoding="utf-8") == "OLD"

    def test_replace_failure_cleans_up_tmp(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = tmp_path / "record.json"
        path.write_text("OLD", encoding="utf-8")

        def boom(src: object, dst: object) -> None:
            raise OSError("simulated rename failure")

        monkeypatch.setattr("src.utils.io.os.replace", boom)

        with pytest.raises(OSError, match="simulated rename failure"):
            atomic_write_text(path, "NEW")

        leftover = list(tmp_path.glob("*.tmp"))
        assert leftover == [], (
            f"Helper should clean up its .tmp after a failed replace; "
            f"got {leftover}"
        )

    def test_destination_size_never_truncated(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Best-effort: at any observable moment, target size matches a
        well-formed payload (old or new) — never a partial prefix.
        """
        path = tmp_path / "record.json"
        old_payload = "X" * 100
        path.write_text(old_payload, encoding="utf-8")

        def boom(src: object, dst: object) -> None:
            # Observe the destination right at the failure boundary.
            assert path.stat().st_size == len(
                old_payload
            ), "Destination must never be truncated mid-rename"
            raise OSError("simulated rename failure")

        monkeypatch.setattr("src.utils.io.os.replace", boom)

        with pytest.raises(OSError):
            atomic_write_text(path, "Y" * 200)

        # Final state: still the old payload, full length.
        assert path.read_text(encoding="utf-8") == old_payload


# =============================================================================
# Concurrent writers
# =============================================================================


class TestConcurrentWrites:
    """Two writers racing the same path: last-writer-wins, no truncation."""

    def test_concurrent_writers_resolve_to_one_winner(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "record.json"
        # Distinct, equal-length payloads so we can pin "the winner is
        # one of {A, B}, not a mix".
        payload_a = "A" * 1024
        payload_b = "B" * 1024
        errors: list[BaseException] = []

        def writer(payload: str) -> None:
            try:
                # Multiple iterations to widen the race window.
                for _ in range(50):
                    atomic_write_text(path, payload)
            except BaseException as e:  # pragma: no cover - defensive
                errors.append(e)

        t1 = threading.Thread(target=writer, args=(payload_a,))
        t2 = threading.Thread(target=writer, args=(payload_b,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == [], f"No writer should fail; got {errors}"
        final = path.read_text(encoding="utf-8")
        assert final in (
            payload_a,
            payload_b,
        ), "Final payload must be one of the candidates, never a mix"
        # No tmp debris left behind by either thread.
        leftover = list(tmp_path.glob("*.tmp"))
        assert leftover == [], (
            f"No .tmp debris should remain after concurrent writes; " f"got {leftover}"
        )

    def test_concurrent_writers_never_produce_truncated_file(
        self,
        tmp_path: Path,
    ) -> None:
        """Sample the file size mid-race; it always matches a valid payload."""
        path = tmp_path / "record.json"
        payload_a = "A" * 1024
        payload_b = "B" * 1024
        # Seed so the file always exists for the observer.
        atomic_write_text(path, payload_a)

        stop = threading.Event()
        observed_sizes: set[int] = set()

        def writer(payload: str) -> None:
            for _ in range(100):
                if stop.is_set():
                    return
                atomic_write_text(path, payload)

        def observer() -> None:
            for _ in range(500):
                if stop.is_set():
                    return
                try:
                    observed_sizes.add(path.stat().st_size)
                except FileNotFoundError:
                    # ``os.replace`` is atomic; this should not fire,
                    # but on hypothetical hosts where it transiently
                    # might, a missing file is still better than a
                    # truncated one.
                    pass

        threads = [
            threading.Thread(target=writer, args=(payload_a,)),
            threading.Thread(target=writer, args=(payload_b,)),
            threading.Thread(target=observer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stop.set()

        # Both candidates have the same length here, so the only
        # legal observed size is that length. Any other size means a
        # truncated mid-write was observed.
        assert observed_sizes <= {
            len(payload_a)
        }, f"Observed truncated sizes during race: {observed_sizes}"


# =============================================================================
# Sanity: helper does not create parent directories
# =============================================================================


def test_missing_parent_directory_raises(tmp_path: Path) -> None:
    """The helper does not create parent dirs — callers do that themselves.

    Pinning this here so a future refactor doesn't silently widen the
    contract; the call sites all ``mkdir(parents=True, exist_ok=True)``
    before invoking us.
    """
    path = tmp_path / "missing_dir" / "record.json"
    with pytest.raises((FileNotFoundError, OSError)):
        atomic_write_text(path, "data")


def test_helper_uses_os_replace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pin the implementation choice: ``os.replace`` is what makes us atomic.

    A future refactor that swaps in ``shutil.move`` would silently
    break the cross-device-rename case (``shutil.move`` falls back to
    copy + delete, which is not atomic). This test guards against
    that drift by patching ``os.replace`` and asserting it ran.
    """
    path = tmp_path / "record.json"
    calls: list[tuple[object, object]] = []
    real_replace = os.replace

    def spy(src: object, dst: object) -> None:
        calls.append((src, dst))
        real_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr("src.utils.io.os.replace", spy)
    atomic_write_text(path, "hello")
    assert len(calls) == 1, "atomic_write_text must call os.replace exactly once"


def test_per_call_tmp_uses_unique_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Per-call uuid token: two writes touch *different* tmp paths.

    Pins the concurrency contract — without per-call tokens, two
    threads racing the same destination would race the same tmp file
    and corrupt each other. The fix lives in the helper; this test
    ensures it doesn't regress to a fixed ``.tmp`` sibling.
    """
    path = tmp_path / "record.json"
    seen_tmp_paths: list[Path] = []
    real_replace = os.replace

    def spy(src: object, dst: object) -> None:
        seen_tmp_paths.append(Path(str(src)))
        real_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr("src.utils.io.os.replace", spy)
    atomic_write_text(path, "first")
    atomic_write_text(path, "second")

    assert len(seen_tmp_paths) == 2
    assert seen_tmp_paths[0] != seen_tmp_paths[1], (
        "Two writes must use distinct tmp paths so concurrent callers "
        "don't race on the same file"
    )


# =============================================================================
# read_text — CAH-14 read counterpart
# =============================================================================


class TestReadText:
    """:func:`src.utils.io.read_text` round-trips and propagates OSError."""

    def test_round_trip_with_atomic_write(self, tmp_path: Path) -> None:
        """``read_text`` returns exactly what ``atomic_write_text`` wrote."""
        path = tmp_path / "payload.json"
        atomic_write_text(path, '{"a": 1}')
        assert read_text(path) == '{"a": 1}'

    def test_missing_file_raises_oserror(self, tmp_path: Path) -> None:
        """A missing path propagates ``OSError`` (FileNotFoundError) —
        same semantics callers' ``except OSError`` already handles."""
        with pytest.raises(OSError):
            read_text(tmp_path / "does-not-exist.json")

    def test_custom_encoding(self, tmp_path: Path) -> None:
        """Non-default encoding round-trips."""
        path = tmp_path / "latin.txt"
        path.write_text("café", encoding="latin-1")
        assert read_text(path, encoding="latin-1") == "café"
