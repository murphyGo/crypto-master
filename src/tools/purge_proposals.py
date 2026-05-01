"""Operator CLI: archive proposal records older than retention.

Phase 11.4 manual lever. The ``src.main`` startup hook runs the same
purge automatically before the engine begins cycling, so this CLI is
mainly useful for one-off windows that differ from
``Settings.log_retention_months`` (e.g. a tighter cleanup before a
disk-pressure event) or for cron-driven invocations on hosts that
keep the trader process running across long retention windows.

Usage::

    # Use the configured retention window:
    python -m src.tools.purge_proposals

    # Override for a one-off tighter window:
    python -m src.tools.purge_proposals --retention-months 6

Reads :class:`Settings` so ``DATA_DIR`` and
``LOG_RETENTION_MONTHS`` env vars apply the same way they do for the
runtime. Idempotent — re-running with the same retention is a no-op
because the archive lives under a subdirectory the top-level glob
ignores.

Related Requirements:
- NFR-008 (mode-separated storage extends to retention).
"""

from __future__ import annotations

import argparse

from src.config import get_settings
from src.proposal.interaction import ProposalHistory


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Archive proposal records older than the retention window. "
            "Defaults to Settings.log_retention_months."
        )
    )
    parser.add_argument(
        "--retention-months",
        type=int,
        default=None,
        help=(
            "One-off override for the retention window in months. "
            "When omitted, falls back to Settings.log_retention_months."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (always ``0``).

    Args:
        argv: Optional argv override; tests pass a list to avoid
            depending on the real ``sys.argv``.

    Returns:
        ``0`` on success. The CLI does not surface a non-zero exit on
        empty results — "nothing to purge" is a valid steady-state
        outcome, not an error.
    """
    args = _build_parser().parse_args(argv)

    settings = get_settings()
    retention = (
        args.retention_months
        if args.retention_months is not None
        else settings.log_retention_months
    )

    history = ProposalHistory()
    archived = history.purge_old(retention_months=retention)

    if archived:
        print(
            f"Purged {len(archived)} proposal record(s) older than "
            f"{retention} months."
        )
    else:
        print(
            f"No proposal records older than {retention} months; " "nothing to purge."
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
