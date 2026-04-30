"""Atomic filesystem helpers (Phase 22.1 / DEBT-028).

The 2026-04-30 audit found multiple persistence sites using a
load-all → mutate → ``Path.write_text(json.dumps(...))`` shape against
a shared file. Two failure modes apply:

1. **Crash mid-write**: ``Path.write_text`` truncates the destination
   before writing the new payload. A crash between ``open(..., "w")``
   and the buffer flush leaves a zero-length or half-written file —
   readers (and the next round of load → mutate → save) lose the
   prior contents.
2. **Concurrent writers**: two callers loading the same JSON / JSONL
   file, mutating in memory, and writing back race; the last writer
   wins and silently drops the other's mutation.

Phase 19's sub-account fan-out multiplies the number of concurrent
writers per cycle against the same persistence files, so this helper
lands *before* 19.x to keep the surface bounded.

This module is the single source of truth for atomic writes. Callers
build the full payload in memory (``json.dumps``,
``model_dump_json``, etc.), then hand it here for the durable
write-then-rename. The helper writes to a sibling ``<path>.tmp`` file
and uses :func:`os.replace` to swap it into place — atomic on POSIX
and Windows per the stdlib docs.

**Scope**: this helper addresses *load-all → save-all* sites only.
Append-only JSONL streams (see ``src/runtime/jsonl_rotator.py``) are
already crash-tolerant via line-at-a-time append and do **not** need
to route through here.

Related Requirements:
- NFR-006: Backtesting Result Storage (JSON format).
- NFR-007: Trading History Storage.
- NFR-008: Asset/PnL History (mode separation).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

__all__ = ["atomic_write_text"]


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Write ``text`` to ``path`` atomically.

    Implementation: write to a per-call unique sibling
    ``<path>.<uuid>.tmp`` file, then :func:`os.replace` it into the
    destination. ``os.replace`` is atomic on POSIX (rename(2)) and
    Windows (MoveFileEx with ``MOVEFILE_REPLACE_EXISTING``) per the
    stdlib docs, so a reader observing ``path`` sees either the
    previous contents or the new contents — never a half-written file.

    The per-call ``uuid`` token in the temp filename keeps two
    concurrent writers from racing on the *same* tmp path: both can
    write their candidate side-by-side and then ``os.replace`` into
    the destination one after the other. Last-writer-wins on the
    destination, which is the expected resolution for the load →
    mutate → save sites this helper services. Sites that need
    stronger ordering (e.g. true serialisation across processes) need
    a file lock on top of this — see DEBT-028 hand-off notes.

    On failure (the temp write raises, or :func:`os.replace` raises),
    the destination is left untouched. The caller is responsible for
    re-raising; we deliberately do **not** swallow exceptions so
    persistence-layer bugs surface to the engine's retry logic.

    Best-effort cleanup: if the temp file exists after a failure, we
    attempt to remove it so a stale ``.tmp`` doesn't linger and
    confuse the next operator inspecting the directory. The cleanup
    itself is silent on its own failure (the original exception is
    what the caller cares about).

    Args:
        path: Destination path. Parent directory must already exist
            — this helper does not create directories. Callers
            already create their parents (e.g. ``mkdir(parents=True,
            exist_ok=True)``); we don't duplicate that here so the
            error surface stays narrow.
        text: Full payload to write. Builds the file from scratch;
            this is not an append helper.
        encoding: Text encoding. Defaults to ``"utf-8"`` to match the
            project-wide convention for on-disk records.

    Raises:
        OSError: Propagated from the underlying temp-file write or
            ``os.replace`` call. Callers wrap or log as appropriate.
    """
    # Per-call unique token: two concurrent writers must not race on
    # the same .tmp path. ``uuid4().hex`` is collision-resistant
    # within process and across processes on the same host.
    token = uuid.uuid4().hex
    tmp_path = path.with_suffix(f"{path.suffix}.{token}.tmp")
    try:
        tmp_path.write_text(text, encoding=encoding)
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup so a stale ``.tmp`` doesn't outlive the
        # failed write. ``missing_ok=True`` keeps this safe even when
        # the original failure was during ``write_text`` itself (no
        # tmp file produced) or when ``os.replace`` already consumed
        # the tmp file before raising.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
