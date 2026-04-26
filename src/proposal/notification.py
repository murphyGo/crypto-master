"""Notification system for trading proposals (Phase 6.3).

When the engine surfaces a "good" trading opportunity, the user wants
to know — but how depends on the runtime. A CLI user wants stdout; an
operator running headless wants a durable log; a future dashboard
might wire in Slack or push notifications.

This module keeps that fan-out simple and pluggable:

* ``Notification`` — what gets sent: a proposal, a level, a short hook.
* ``Notifier`` (Protocol) — anything that implements ``async send``.
* ``ConsoleNotifier`` — writes a banner to a configurable text stream.
* ``FileNotifier`` — appends JSONL to ``data/notifications/proposals.jsonl``;
  same shape as ``src.feedback.audit.AuditLog`` so we get the same
  append-only / human-greppable / replayable guarantees.
* ``NotificationDispatcher`` — fans out to multiple notifiers, isolates
  per-channel failures so one bad backend can't silence the others, and
  applies an optional ``min_score`` filter so only "good" opportunities
  notify (FR-015).

Related Requirements:
- FR-015: Proposal Notification
"""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol, TextIO, runtime_checkable

from pydantic import BaseModel, Field

from src.logger import get_logger
from src.proposal.engine import Proposal

logger = get_logger("crypto_master.proposal.notification")


DEFAULT_NOTIFICATION_LOG = Path("data/notifications/proposals.jsonl")


# =============================================================================
# Models
# =============================================================================


class NotificationLevel(str, Enum):
    """Severity / category of a notification.

    ``INFO`` — generic; ``GOOD_OPPORTUNITY`` — the headline event for
    FR-015 (a high-quality proposal worth a user's attention).
    """

    INFO = "info"
    GOOD_OPPORTUNITY = "good_opportunity"


class Notification(BaseModel):
    """One notification event tied to a single proposal.

    Attributes:
        notification_id: UUID generated at construction.
        created_at: When the notification was built.
        level: ``INFO`` or ``GOOD_OPPORTUNITY``.
        proposal: The full ``Proposal`` payload — embedded so a JSONL
            log on disk is self-contained even if the proposal record
            is later mutated.
        message: Short human-readable hook displayed by console
            backends. Free-form; defaults are produced by
            :func:`build_default_message`.
    """

    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    level: NotificationLevel
    proposal: Proposal
    message: str

    model_config = {"use_enum_values": True}


def build_default_message(proposal: Proposal, level: NotificationLevel) -> str:
    """One-line summary used as the default notification message.

    Kept short on purpose — the console backend prints this prominently
    and the file backend stores it alongside the proposal payload, so
    operators grepping the log get a useful preview without parsing
    JSON.
    """
    label = (
        "🚀 Good opportunity"
        if level is NotificationLevel.GOOD_OPPORTUNITY
        else "Proposal"
    )
    return (
        f"{label}: {proposal.signal.upper()} {proposal.symbol} "
        f"@ {proposal.entry_price} "
        f"(R/R={proposal.risk_reward_ratio:.2f}, "
        f"score={proposal.score.composite:.4f})"
    )


# =============================================================================
# Notifier protocol
# =============================================================================


@runtime_checkable
class Notifier(Protocol):
    """Anything that can deliver a ``Notification``.

    Implementations should be idempotent only when their backend is —
    the dispatcher does not deduplicate.
    """

    async def send(self, notification: Notification) -> None: ...


# =============================================================================
# Console backend
# =============================================================================


class ConsoleNotifier:
    """Writes a short banner to a text stream (stdout by default).

    Kept simple — the stream is held by reference so tests can pass
    ``io.StringIO`` and assert on the captured output without the
    capsys fixture.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        """Initialize the console notifier.

        Args:
            stream: Where to write. Defaults to ``sys.stdout``. Tests
                should pass an ``io.StringIO`` to capture output.
        """
        self._stream = stream if stream is not None else sys.stdout

    async def send(self, notification: Notification) -> None:
        """Print a one-line banner for the notification."""
        # ``NotificationLevel`` is a str-Enum and pydantic stores it as
        # the raw string (``use_enum_values=True``), so .upper() is safe
        # in either form.
        level_str = str(notification.level)
        line = (
            f"[{notification.created_at.isoformat(timespec='seconds')}] "
            f"[{level_str.upper()}] "
            f"{notification.message}"
        )
        self._stream.write(line + "\n")
        self._stream.flush()


# =============================================================================
# File backend
# =============================================================================


class FileNotifier:
    """Append-only JSONL log for notifications.

    Mirrors ``src.feedback.audit.AuditLog`` — one JSON object per line,
    independent open/append/close per ``send`` so concurrent writers
    don't corrupt earlier entries.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the file notifier.

        Args:
            path: Where to append. Defaults to
                ``data/notifications/proposals.jsonl``. Tests should
                supply ``tmp_path / "notifications.jsonl"``.
        """
        self.path = path or DEFAULT_NOTIFICATION_LOG

    async def send(self, notification: Notification) -> None:
        """Append one notification as a JSON line."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = notification.model_dump_json()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        logger.debug(
            f"Notification logged: {notification.level} "
            f"proposal={notification.proposal.proposal_id}"
        )

    def read_all(self) -> list[Notification]:
        """Load every notification from the log.

        Skips malformed lines (the only kind a crash can produce) with
        a warning rather than aborting. Empty / missing files return an
        empty list.
        """
        if not self.path.exists():
            return []
        out: list[Notification] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                    out.append(Notification(**payload))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        f"Skipping malformed notification line {lineno} "
                        f"in {self.path}: {e}"
                    )
        return out


# =============================================================================
# Dispatcher
# =============================================================================


class NotificationDispatcher:
    """Fan a single notification out to multiple notifiers.

    Two cross-cutting concerns are owned here so individual notifiers
    stay simple:

    1. **Quality gate (FR-015's "good trading opportunities")** — the
       optional ``min_score`` threshold filters out low-composite
       proposals so users aren't paged for noise. Set to ``0.0`` to
       notify every proposal.
    2. **Failure isolation** — a notifier raising must not silence the
       others. We catch broadly, log the error, and continue.
    """

    def __init__(
        self,
        notifiers: Sequence[Notifier],
        min_score: float = 0.0,
    ) -> None:
        """Initialize the dispatcher.

        Args:
            notifiers: Backends to fan out to. Order is preserved.
            min_score: Minimum ``proposal.score.composite`` required to
                send. Proposals below this score are ignored and
                ``notify_proposal`` returns ``None``.
        """
        self._notifiers = list(notifiers)
        self.min_score = min_score

    async def notify_proposal(
        self,
        proposal: Proposal,
        level: NotificationLevel | None = None,
        message: str | None = None,
    ) -> Notification | None:
        """Emit a notification for one proposal across all backends.

        Args:
            proposal: The proposal to surface.
            level: Override the inferred level. By default, proposals
                meeting ``min_score`` are tagged ``GOOD_OPPORTUNITY``;
                anything else is ``INFO``.
            message: Override the default message text.

        Returns:
            The constructed ``Notification`` if it was dispatched (even
            if individual backends failed). ``None`` if the proposal
            was filtered out by ``min_score``.
        """
        if proposal.score.composite < self.min_score:
            logger.debug(
                f"Skipping notification for {proposal.proposal_id}: "
                f"composite={proposal.score.composite:.4f} < "
                f"min_score={self.min_score}"
            )
            return None

        resolved_level = level or NotificationLevel.GOOD_OPPORTUNITY
        notification = Notification(
            level=resolved_level,
            proposal=proposal,
            message=message or build_default_message(proposal, resolved_level),
        )

        for notifier in self._notifiers:
            try:
                await notifier.send(notification)
            except Exception as e:
                # Failure isolation: one bad backend must not silence
                # the others. Log, continue.
                logger.warning(
                    f"Notifier {type(notifier).__name__} failed for "
                    f"proposal {proposal.proposal_id}: {e}"
                )

        return notification


__all__ = [
    "ConsoleNotifier",
    "DEFAULT_NOTIFICATION_LOG",
    "FileNotifier",
    "Notification",
    "NotificationDispatcher",
    "NotificationLevel",
    "Notifier",
    "build_default_message",
]
