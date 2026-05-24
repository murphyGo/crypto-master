"""Operator runtime-flag loader (cross-account-risk-policy DEBT-068(d)).

A tiny, fail-safe reader for ``config/runtime_flags.yaml`` — the
file-based operator manual freeze toggle described in the
cross-account-risk-policy spec §"Operator Manual Freeze". The file is
re-read at the START of every cycle so an operator can freeze a RUNNING
engine without a restart:

    runtime_flags:
      trading_freeze: false

When ``trading_freeze`` is ``true`` the engine rejects ALL proposals
with ``reason="operator_freeze"`` ahead of every other gate (earliest
reject). Spec §"Hysteresis": operator freeze NEVER auto-releases — only
an explicit operator edit clears it.

**Fail-safe semantics** — freeze is an explicit opt-in, so any case
where the flag cannot be read as an unambiguous ``true`` resolves to
"not frozen":

- Missing file ⇒ ``trading_freeze=False`` (absence = normal trading).
- Malformed / unreadable YAML ⇒ a LOUD warning is logged and the flag is
  treated as ``False`` — a bad flag file must never crash the cycle, and
  it must never silently freeze trading either.

Related Requirements:
- FR-038 / NFR-007 / NFR-012: operator-controlled trading halt.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.logger import get_logger
from src.utils.io import atomic_write_text

logger = get_logger(__name__)

# Default config-file location. Mirrors the
# ``SubAccountRegistry.DEFAULT_CONFIG_PATH`` convention — a
# project-root-relative ``config/`` path the operator edits in place.
DEFAULT_RUNTIME_FLAGS_PATH = Path("config/runtime_flags.yaml")


def read_trading_freeze(path: Path | None = None) -> bool:
    """Return the operator ``trading_freeze`` flag, fail-safe to ``False``.

    Reads ``runtime_flags.trading_freeze`` from the YAML file at ``path``
    (default :data:`DEFAULT_RUNTIME_FLAGS_PATH`). The read is intended to
    run once per cycle from ``TradingEngine.run_cycle``.

    Fail-safe direction (freeze is an explicit opt-in):

    - Missing file ⇒ ``False`` (no warning — absence is the normal,
      not-frozen state).
    - Unreadable / malformed YAML, non-mapping document, or a
      ``trading_freeze`` value that is not an unambiguous boolean ⇒ a
      loud warning is logged and ``False`` is returned. The cycle never
      crashes on a bad flag file, and a bad file never silently freezes
      trading.

    Args:
        path: Optional override for the flag-file location. Defaults to
            ``config/runtime_flags.yaml`` relative to the working
            directory (the project root in production).

    Returns:
        ``True`` only when the file is present, parseable, and carries
        ``runtime_flags.trading_freeze: true``; ``False`` otherwise.
    """
    flags_path = path or DEFAULT_RUNTIME_FLAGS_PATH

    if not flags_path.exists():
        # Absence is the normal, not-frozen case — no warning.
        return False

    try:
        with flags_path.open("r", encoding="utf-8") as fh:
            parsed = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        logger.warning(
            "Operator freeze flag file %s is unreadable/malformed (%s); "
            "treating trading_freeze as False (NOT frozen). Fix the file to "
            "engage the freeze.",
            flags_path,
            exc,
        )
        return False

    if parsed is None:
        # Empty file ⇒ no flags configured ⇒ not frozen.
        return False

    if not isinstance(parsed, dict):
        logger.warning(
            "Operator freeze flag file %s top-level document is not a mapping "
            "(%r); treating trading_freeze as False (NOT frozen).",
            flags_path,
            type(parsed).__name__,
        )
        return False

    section = parsed.get("runtime_flags")
    if section is None:
        # File present but no ``runtime_flags`` block ⇒ not frozen.
        return False
    if not isinstance(section, dict):
        logger.warning(
            "Operator freeze flag file %s 'runtime_flags' is not a mapping "
            "(%r); treating trading_freeze as False (NOT frozen).",
            flags_path,
            type(section).__name__,
        )
        return False

    value = section.get("trading_freeze")
    if value is None:
        return False
    if not isinstance(value, bool):
        logger.warning(
            "Operator freeze flag file %s 'runtime_flags.trading_freeze' is not "
            "a boolean (%r); treating trading_freeze as False (NOT frozen). Use "
            "'true' or 'false'.",
            flags_path,
            value,
        )
        return False

    return value


class RuntimeFlagsWriteError(RuntimeError):
    """Raised when the freeze flag cannot be written safely.

    The dashboard surfaces the message verbatim so the operator knows the
    toggle did NOT take effect (e.g. the existing file was malformed and we
    refused to clobber it). Never swallowed silently — a failed freeze write
    must be loud, since the operator believes trading is (un)frozen.
    """


def write_trading_freeze(value: bool, path: Path | None = None) -> None:
    """Write the operator ``trading_freeze`` flag, atomically and merge-safe.

    Write-side counterpart to :func:`read_trading_freeze` (DEBT-068(f-2)).
    The dashboard freeze toggle calls this on an explicit, confirmed operator
    action; the engine never calls it.

    Behavior:

    - Writes ``runtime_flags.trading_freeze: <true|false>`` such that
      :func:`read_trading_freeze` round-trips the same bool back.
    - **Merge-preserving**: if the file already exists and parses to a
      mapping, every other top-level key and every other key under
      ``runtime_flags`` is preserved — only ``trading_freeze`` is set. This
      stops the toggle from clobbering unrelated operator-edited flags.
    - **Atomic**: delegates to :func:`src.utils.io.atomic_write_text`, which
      writes to a per-call-unique sibling ``.tmp`` then ``os.replace``es it
      over the target, so a crash mid-write can never leave a half-written
      flag file that the fail-safe reader then mis-parses. The temp file is
      cleaned up on any failure (no orphan ``.tmp`` left behind).
    - Creates the parent ``config/`` directory if missing.

    Malformed-existing-file policy (deliberate, documented choice):
        If the file exists but cannot be read or does not parse to a mapping
        (or its ``runtime_flags`` block is not a mapping), we **refuse** and
        raise :class:`RuntimeFlagsWriteError` rather than overwrite it. The
        read side fails SAFE (an unparseable file reads as "not frozen"), so
        silently overwriting a hand-edited-but-broken file here could both
        destroy operator intent AND mask the breakage. Refusing surfaces the
        problem to the operator, who can fix the file by hand. This is the
        opposite stance to the reader (which must never crash a cycle) on
        purpose: a write is an explicit, interactive operator action where a
        loud failure is the safe outcome.

    Hysteresis (spec §"Hysteresis and Reset Semantics"): the operator freeze
    NEVER auto-releases. DISENGAGING is therefore just as much an explicit
    operator write — ``write_trading_freeze(False)`` — as engaging it; there
    is no automatic path that clears the flag.

    Args:
        value: The boolean to persist under ``runtime_flags.trading_freeze``.
        path: Optional override for the flag-file location. Defaults to
            :data:`DEFAULT_RUNTIME_FLAGS_PATH`.

    Raises:
        RuntimeFlagsWriteError: If an existing file cannot be parsed as a
            mapping (refusal to clobber), or if the atomic write fails.
    """
    flags_path = path or DEFAULT_RUNTIME_FLAGS_PATH

    document = _load_existing_document(flags_path)
    section = document.get("runtime_flags")
    if section is None:
        section = {}
        document["runtime_flags"] = section
    elif not isinstance(section, dict):
        raise RuntimeFlagsWriteError(
            f"Refusing to write {flags_path}: existing 'runtime_flags' is not "
            f"a mapping ({type(section).__name__!r}); fix the file by hand "
            f"before toggling the freeze so unrelated flags are not lost."
        )
    section["trading_freeze"] = value

    flags_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(document, default_flow_style=False, sort_keys=False)
    try:
        # Single source of truth for atomic writes (DEBT-028). A crash
        # mid-write leaves the prior file intact rather than a half-written
        # flag the fail-safe reader would mis-parse.
        atomic_write_text(flags_path, rendered)
    except OSError as exc:
        raise RuntimeFlagsWriteError(
            f"Failed to atomically write {flags_path}: {exc}"
        ) from exc
    logger.info(
        "Operator wrote trading_freeze=%s to %s (freeze never auto-releases; "
        "disengaging requires an explicit write of false).",
        value,
        flags_path,
    )


def _load_existing_document(flags_path: Path) -> dict:
    """Return the parsed file as a mutable mapping, or ``{}`` if absent/empty.

    Refuses (raises :class:`RuntimeFlagsWriteError`) on an existing file that
    is unreadable or does not parse to a mapping — see the write policy in
    :func:`write_trading_freeze`. A missing or empty file is the normal
    fresh-start case and yields an empty mapping to merge into.
    """
    if not flags_path.exists():
        return {}
    try:
        with flags_path.open("r", encoding="utf-8") as fh:
            parsed = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeFlagsWriteError(
            f"Refusing to write {flags_path}: existing file is "
            f"unreadable/malformed ({exc}); fix it by hand before toggling "
            f"the freeze so its contents are not lost."
        ) from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise RuntimeFlagsWriteError(
            f"Refusing to write {flags_path}: existing top-level document is "
            f"not a mapping ({type(parsed).__name__!r}); fix it by hand "
            f"before toggling the freeze."
        )
    return parsed


__all__ = [
    "DEFAULT_RUNTIME_FLAGS_PATH",
    "RuntimeFlagsWriteError",
    "read_trading_freeze",
    "write_trading_freeze",
]
