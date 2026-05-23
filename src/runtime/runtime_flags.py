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


__all__ = ["DEFAULT_RUNTIME_FLAGS_PATH", "read_trading_freeze"]
