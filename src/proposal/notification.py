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

import asyncio
import json
import smtplib
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from email.message import EmailMessage
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TextIO, runtime_checkable

from pydantic import BaseModel, Field

from src.config import get_settings
from src.logger import get_logger
from src.proposal.engine import Proposal
from src.runtime.safety_score import (
    RuntimeSafetyScore,
    format_runtime_safety_summary,
)
from src.utils.time import now_utc

logger = get_logger("crypto_master.proposal.notification")


# Relative-path marker; the live default is derived from
# ``Settings.data_dir`` at construction time so the notification log
# survives container recycles on managed hosts (Phase 10.5).
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
        safety_score: Optional operator-facing runtime safety rollup to
            include in rich notification summaries.
    """

    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=now_utc)
    level: NotificationLevel
    proposal: Proposal
    message: str
    safety_score: RuntimeSafetyScore | None = None

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
        f"{label} [{proposal.sub_account_id}]: "
        f"{proposal.signal.upper()} {proposal.symbol} "
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

    def __init__(
        self,
        path: Path | None = None,
        *,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize the file notifier.

        Args:
            path: Where to append. When supplied, this explicit path
                wins (tests should supply
                ``tmp_path / "notifications.jsonl"``).
            data_dir: Optional override for the notification data
                root. When ``path`` is not given, the file notifier
                defaults to ``<data_dir>/notifications/proposals.jsonl``.
                ``data_dir`` itself defaults to ``Settings().data_dir``
                so the log lands on the persistent volume (Phase 10.5).
        """
        if path is not None:
            self.path = path
        else:
            base = data_dir if data_dir is not None else get_settings().data_dir
            self.path = base / "notifications" / "proposals.jsonl"

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
# Slack backend (Phase 11.3)
# =============================================================================


def _build_slack_payload(notification: Notification) -> dict[str, Any]:
    """Build the Slack incoming-webhook payload for a notification.

    Two cooperating fields:

    * ``text`` — fallback for clients that don't render Block Kit.
      One-line summary matching the spec format
      ``{symbol} {side} score={composite:.2f} entry={price}``.
    * ``blocks`` — Block Kit summary section + a code-fenced detail
      section listing the rationale-relevant fields (proposal id,
      technique, SL/TP, qty, leverage, R/R). The code fence keeps
      monospace alignment so operators glancing at Slack can read
      prices vertically without rendering issues.
    """
    proposal = notification.proposal
    safety_summary = _format_optional_safety_summary(notification)
    summary = (
        f"[{proposal.sub_account_id}] {proposal.symbol} {proposal.signal} "
        f"score={proposal.score.composite:.2f} "
        f"entry={proposal.entry_price}"
    )
    if safety_summary is not None:
        summary = f"{summary} {safety_summary}"
    detail = (
        "```\n"
        f"proposal_id: {proposal.proposal_id}\n"
        f"sub_account_id: {proposal.sub_account_id}\n"
        f"technique: {proposal.technique_name}\n"
        f"SL: {proposal.stop_loss}\n"
        f"TP: {proposal.take_profit}\n"
        f"qty: {proposal.quantity}\n"
        f"leverage: {proposal.leverage}x\n"
        f"rr: {proposal.risk_reward_ratio:.2f}\n"
        f"{_format_optional_safety_detail(notification)}"
        "```"
    )
    return {
        "text": summary,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*[{proposal.sub_account_id}] "
                        f"{proposal.symbol} {proposal.signal}* "
                        f"score={proposal.score.composite:.2f} "
                        f"entry={proposal.entry_price}"
                        f"{_format_optional_safety_suffix(notification)}"
                    ),
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": detail},
            },
        ],
    }


class SlackNotifier:
    """POSTs notifications to a Slack incoming webhook (Phase 11.3).

    The webhook URL is a secret — it is never logged, and ``__repr__``
    deliberately omits it. The HTTP call uses ``urllib.request`` from
    the standard library (zero extra dependency) wrapped in
    ``asyncio.to_thread`` so the dispatcher's event loop is not
    blocked.

    Failure isolation is enforced by ``NotificationDispatcher``: if
    the webhook returns 4xx/5xx or times out, ``send`` raises and the
    dispatcher logs + continues to the next backend. We deliberately
    do not catch internally so the dispatcher's existing isolation
    contract is the single owner of "one bad backend can't silence
    the others".
    """

    def __init__(self, webhook_url: str, *, timeout: float = 5.0) -> None:
        """Initialize the Slack notifier.

        Args:
            webhook_url: Slack incoming-webhook URL. Treated as a
                secret — never logged, never returned by ``__repr__``.
            timeout: Per-request timeout in seconds. Defaults to 5s
                so a slow Slack endpoint can't stall the cycle.
        """
        self._webhook_url = webhook_url
        self.timeout = timeout

    def __repr__(self) -> str:
        # Mask the URL — only its presence is informative for logs.
        return f"{type(self).__name__}(webhook_url=<redacted>)"

    async def send(self, notification: Notification) -> None:
        """POST the Slack-formatted payload to the webhook."""
        payload = _build_slack_payload(notification)
        body = json.dumps(payload).encode("utf-8")
        # Bind to a local so the worker thread captures stable refs.
        url = self._webhook_url
        timeout = self.timeout

        def _post() -> None:
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # Slack returns 200 with body "ok" on success; any
                # non-2xx is raised by urlopen as HTTPError. Drain the
                # body so the connection can be reused.
                resp.read()

        await asyncio.to_thread(_post)
        logger.debug(
            f"Slack notification dispatched for "
            f"proposal={notification.proposal.proposal_id}"
        )


# =============================================================================
# Telegram backend (Phase 12.4)
# =============================================================================


def _build_telegram_text(notification: Notification) -> str:
    """Build the Telegram ``text`` body for a notification.

    Mirrors :func:`_build_slack_payload`'s summary + code-fenced detail
    so the on-the-wire content of Slack and Telegram alerts stays in
    sync — operators reading either backend get the exact same fields.
    Telegram has no "blocks" concept, so we collapse both into one
    Markdown string: a bolded headline followed by a triple-backtick
    code block with the rationale-relevant fields. Markdown is enabled
    via ``parse_mode=Markdown`` on the request.
    """
    proposal = notification.proposal
    safety_summary = _format_optional_safety_suffix(notification)
    headline = (
        f"*[{proposal.sub_account_id}] {proposal.symbol} {proposal.signal}* "
        f"score={proposal.score.composite:.2f} "
        f"entry={proposal.entry_price}"
        f"{safety_summary}"
    )
    detail = (
        "```\n"
        f"proposal_id: {proposal.proposal_id}\n"
        f"sub_account_id: {proposal.sub_account_id}\n"
        f"technique: {proposal.technique_name}\n"
        f"SL: {proposal.stop_loss}\n"
        f"TP: {proposal.take_profit}\n"
        f"qty: {proposal.quantity}\n"
        f"leverage: {proposal.leverage}x\n"
        f"rr: {proposal.risk_reward_ratio:.2f}\n"
        f"{_format_optional_safety_detail(notification)}"
        "```"
    )
    return f"{headline}\n{detail}"


def _format_optional_safety_summary(notification: Notification) -> str | None:
    if notification.safety_score is None:
        return None
    return format_runtime_safety_summary(notification.safety_score)


def _format_optional_safety_suffix(notification: Notification) -> str:
    safety_summary = _format_optional_safety_summary(notification)
    if safety_summary is None:
        return ""
    return f" {safety_summary}"


def _format_optional_safety_detail(notification: Notification) -> str:
    safety_summary = _format_optional_safety_summary(notification)
    if safety_summary is None:
        return ""
    return f"{safety_summary}\n"


class TelegramNotifier:
    """POSTs notifications to the Telegram Bot API (Phase 12.4).

    Both the bot token and the chat id are secrets — anyone with the
    token can drive the bot, and the chat id reveals the destination
    chat. ``__repr__`` masks both, and we never log either value.

    The HTTP call uses ``urllib.request`` from the standard library
    (zero extra dependency) wrapped in ``asyncio.to_thread`` so the
    dispatcher's event loop is not blocked. Mirrors
    :class:`SlackNotifier` from Phase 11.3.

    Failure isolation is enforced by ``NotificationDispatcher``: if
    Telegram returns 4xx/5xx or times out, ``send`` raises and the
    dispatcher logs + continues to the next backend. We deliberately
    do not catch internally so the dispatcher's existing isolation
    contract is the single owner of "one bad backend can't silence
    the others".
    """

    _API_BASE = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        timeout: float = 5.0,
    ) -> None:
        """Initialize the Telegram notifier.

        Args:
            bot_token: Telegram Bot API token (from @BotFather). Treated
                as a secret — never logged, never returned by
                ``__repr__``.
            chat_id: Destination chat id (numeric or ``@channel``).
                Treated as a secret — masked in ``__repr__``.
            timeout: Per-request timeout in seconds. Defaults to 5s so
                a slow Telegram endpoint can't stall the cycle.
        """
        self._bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self.url = f"{self._API_BASE}/bot{bot_token}/sendMessage"

    def __repr__(self) -> str:
        # Mask the token AND chat id — only their presence is
        # informative for logs. The chat id is sensitive on its own
        # because it identifies the operator's destination channel.
        return f"{type(self).__name__}(bot_token=<redacted>, chat_id=<redacted>)"

    async def send(self, notification: Notification) -> None:
        """POST the Telegram-formatted payload to the Bot API."""
        text = _build_telegram_text(notification)
        body = urllib.parse.urlencode(
            {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }
        ).encode("utf-8")
        # Bind to locals so the worker thread captures stable refs.
        url = self.url
        timeout = self.timeout

        def _post() -> None:
            req = urllib.request.Request(url, data=body, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # Telegram returns 200 with a JSON ``{"ok": true, ...}``
                # on success; non-2xx is raised by urlopen as HTTPError.
                # Drain the body so the connection can be reused.
                resp.read()

        await asyncio.to_thread(_post)
        logger.debug(
            f"Telegram notification dispatched for "
            f"proposal={notification.proposal.proposal_id}"
        )


# =============================================================================
# Email backend (Phase 13.4)
# =============================================================================


def _build_email_subject(notification: Notification) -> str:
    """Build the email subject line for a notification.

    Spec format (Phase 13.4): ``Crypto Master: {symbol} {side} score={c:.2f}``.
    Kept short on purpose so it renders cleanly in mail-client preview
    panes; the full proposal detail lives in the body.
    """
    proposal = notification.proposal
    return (
        f"Crypto Master: {proposal.symbol} {proposal.signal} "
        f"score={proposal.score.composite:.2f} [{proposal.sub_account_id}]"
    )


def _build_email_body(notification: Notification) -> str:
    """Build the email body for a notification.

    Reuses :func:`_build_telegram_text` so Slack / Telegram / email all
    carry the exact same fields — operators reading any backend get
    identical content. The Markdown bold + triple-backtick fence
    renders fine in Markdown-aware clients (Apple Mail, modern Gmail
    web with Markdown plugins) and degrades to plain text everywhere
    else, which is acceptable: the headline still reads cleanly even
    without bold formatting, and the code-fenced detail block still
    aligns vertically because it's plain ASCII.
    """
    return _build_telegram_text(notification)


class EmailNotifier:
    """Sends notifications via SMTP (Phase 13.4, Phase 14.2).

    Uses stdlib :mod:`smtplib` + :class:`email.message.EmailMessage`
    (zero new dependency) wrapped in :func:`asyncio.to_thread` so the
    dispatcher's event loop is not blocked. Two transports are
    supported:

    * **STARTTLS** (default, port 587): plain ``smtplib.SMTP`` upgraded
      via ``starttls()`` after connect. Works for Gmail, Mailgun,
      SendGrid, most corporate relays.
    * **SMTP_SSL** (``use_ssl=True``, port 465): ``smtplib.SMTP_SSL``
      with the TLS handshake on connect; ``starttls()`` is NOT called
      because the channel is already encrypted. Required by some
      providers (Yahoo Mail, AT&T, ProtonMail) that don't offer
      STARTTLS — Phase 14.2 / DEBT-012.

    The SMTP password is a secret — never logged, masked in
    ``__repr__``.

    Failure isolation is enforced by ``NotificationDispatcher``: if
    the SMTP server is unreachable, refuses authentication, or rejects
    the message, ``send`` raises and the dispatcher logs + continues
    to the next backend. We deliberately do not catch internally so
    the dispatcher's existing isolation contract is the single owner
    of "one bad backend can't silence the others".
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        to_addr: str,
        *,
        timeout: float = 10.0,
        use_ssl: bool = False,
    ) -> None:
        """Initialize the email notifier.

        Args:
            host: SMTP server hostname (e.g. ``smtp.gmail.com``).
            port: SMTP server port. Default 587 = STARTTLS; pair
                ``use_ssl=True`` with port 465 for SMTP_SSL providers.
            user: SMTP auth username (typically the From address).
            password: SMTP auth password (or app password). Treated as
                a secret — never logged, masked in ``__repr__``.
            from_addr: ``From`` header value. May include a display
                name, e.g. ``"Crypto Master <bot@example.com>"``.
            to_addr: ``To`` header value (single recipient or comma-
                separated list per RFC 5322).
            timeout: Per-request timeout in seconds. Defaults to 10s
                so a slow SMTP server can't stall the cycle.
            use_ssl: When True, use ``smtplib.SMTP_SSL`` (TLS on
                connect, no STARTTLS upgrade). Default False uses the
                existing ``smtplib.SMTP`` + ``starttls()`` path so
                pre-Phase 14.2 callers behave identically. Phase 14.2
                / DEBT-012.
        """
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from = from_addr
        self._to = to_addr
        self._timeout = timeout
        self._use_ssl = use_ssl

    def __repr__(self) -> str:
        # Mask the password — only its presence is informative for
        # logs. Host / user / from / to are not secrets in the same
        # sense (they're operationally useful for log triage), but the
        # password unconditionally must be hidden.
        return (
            f"{type(self).__name__}("
            f"host={self._host}, port={self._port}, "
            f"user={self._user}, password=<redacted>, "
            f"from={self._from}, to={self._to})"
        )

    async def send(self, notification: Notification) -> None:
        """Build and send the SMTP message for a notification."""
        subject = _build_email_subject(notification)
        body = _build_email_body(notification)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = self._to
        msg.set_content(body)

        # Bind to locals so the worker thread captures stable refs.
        host = self._host
        port = self._port
        user = self._user
        password = self._password
        timeout = self._timeout
        use_ssl = self._use_ssl

        def _send() -> None:
            # Phase 14.2: ``smtplib.SMTP_SSL`` handshakes TLS on connect,
            # so ``starttls()`` is intentionally skipped on that path.
            # ``smtplib.SMTP`` (the default) still upgrades via STARTTLS
            # after connect, matching the pre-14.2 behaviour exactly.
            smtp: smtplib.SMTP
            if use_ssl:
                smtp = smtplib.SMTP_SSL(host, port, timeout=timeout)
            else:
                smtp = smtplib.SMTP(host, port, timeout=timeout)
            with smtp:
                if not use_ssl:
                    smtp.starttls()
                smtp.login(user, password)
                smtp.send_message(msg)

        await asyncio.to_thread(_send)
        logger.debug(
            f"Email notification dispatched for "
            f"proposal={notification.proposal.proposal_id}"
        )


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
        on_notifier_failure: (
            Callable[[str, Notification, BaseException], None] | None
        ) = None,
    ) -> None:
        """Initialize the dispatcher.

        Args:
            notifiers: Backends to fan out to. Order is preserved.
            min_score: Minimum ``proposal.score.composite`` required to
                send. Proposals below this score are ignored and
                ``notify_proposal`` returns ``None``.
            on_notifier_failure: Optional callback invoked once per
                per-notifier failure with
                ``(notifier_class_name, notification, exception)``.
                Wired up by the engine to emit
                ``NOTIFICATION_FAILED`` activity events tagged with the
                backend name (consistency-hardening CH-03), so per-backend
                outages feed the runtime safety score instead of being
                buried in warnings.
        """
        self._notifiers = list(notifiers)
        self.min_score = min_score
        self._on_notifier_failure = on_notifier_failure

    async def notify_proposal(
        self,
        proposal: Proposal,
        level: NotificationLevel | None = None,
        message: str | None = None,
        safety_score: RuntimeSafetyScore | None = None,
        min_score: float | None = None,
    ) -> Notification | None:
        """Emit a notification for one proposal across all backends.

        Args:
            proposal: The proposal to surface.
            level: Override the inferred level. By default, proposals
                meeting ``min_score`` are tagged ``GOOD_OPPORTUNITY``;
                anything else is ``INFO``.
            message: Override the default message text.
            safety_score: Optional runtime safety rollup to include in
                Slack/Telegram/email notification summaries.

        Returns:
            The constructed ``Notification`` if it was dispatched (even
            if individual backends failed). ``None`` if the proposal
            was filtered out by ``min_score``.
        """
        threshold = self.min_score if min_score is None else min_score
        if proposal.score.composite < threshold:
            logger.debug(
                f"Skipping notification for {proposal.proposal_id}: "
                f"composite={proposal.score.composite:.4f} < "
                f"min_score={threshold}"
            )
            return None

        resolved_level = level or NotificationLevel.GOOD_OPPORTUNITY
        notification = Notification(
            level=resolved_level,
            proposal=proposal,
            message=message or build_default_message(proposal, resolved_level),
            safety_score=safety_score,
        )

        for notifier in self._notifiers:
            try:
                await notifier.send(notification)
            except Exception as e:
                # Failure isolation: one bad backend must not silence
                # the others. Log, hand off to the engine via the
                # callback (so it can emit a NOTIFICATION_FAILED activity
                # event tagged with the backend name and feed the runtime
                # safety score), continue.
                notifier_name = type(notifier).__name__
                logger.warning(
                    f"Notifier {notifier_name} failed for "
                    f"proposal {proposal.proposal_id}: {e}"
                )
                if self._on_notifier_failure is not None:
                    try:
                        self._on_notifier_failure(notifier_name, notification, e)
                    except Exception as cb_exc:  # pragma: no cover - defensive
                        # The failure surface itself failing must not
                        # mask the original notifier failure.
                        logger.error(f"on_notifier_failure callback raised: {cb_exc}")

        return notification


class RoutedNotificationDispatcher(NotificationDispatcher):
    """Route proposal notifications by sub-account route refs.

    The default dispatcher remains the fallback for every proposal.
    When ``proposal.sub_account_id`` has a configured route and that
    route has a dispatcher, only the route dispatcher sends the event.
    This lets noisy experimental accounts use a separate push channel
    while preserving the base console/file notifier set inside the
    route dispatcher.
    """

    def __init__(
        self,
        *,
        default_dispatcher: NotificationDispatcher,
        sub_account_routes: dict[str, str],
        route_dispatchers: dict[str, NotificationDispatcher],
        sub_account_min_scores: dict[str, float] | None = None,
    ) -> None:
        super().__init__(notifiers=[], min_score=default_dispatcher.min_score)
        self.default_dispatcher = default_dispatcher
        self.sub_account_routes = dict(sub_account_routes)
        self.route_dispatchers = dict(route_dispatchers)
        self.sub_account_min_scores = dict(sub_account_min_scores or {})
        # Preserve the historical inspection surface used by tests and
        # diagnostics; dispatch still delegates through ``default_dispatcher``.
        self._notifiers = list(default_dispatcher._notifiers)

    async def notify_proposal(
        self,
        proposal: Proposal,
        level: NotificationLevel | None = None,
        message: str | None = None,
        safety_score: RuntimeSafetyScore | None = None,
        min_score: float | None = None,
    ) -> Notification | None:
        """Dispatch using a sub-account route when one is configured."""
        route = self.sub_account_routes.get(proposal.sub_account_id)
        dispatcher = self.route_dispatchers.get(route) if route is not None else None
        score_override = self.sub_account_min_scores.get(proposal.sub_account_id)
        effective_min_score = score_override if min_score is None else min_score
        if dispatcher is None:
            return await self.default_dispatcher.notify_proposal(
                proposal,
                level=level,
                message=message,
                safety_score=safety_score,
                min_score=effective_min_score,
            )
        return await dispatcher.notify_proposal(
            proposal,
            level=level,
            message=message,
            safety_score=safety_score,
            min_score=effective_min_score,
        )


__all__ = [
    "ConsoleNotifier",
    "DEFAULT_NOTIFICATION_LOG",
    "EmailNotifier",
    "FileNotifier",
    "Notification",
    "NotificationDispatcher",
    "NotificationLevel",
    "Notifier",
    "RoutedNotificationDispatcher",
    "SlackNotifier",
    "TelegramNotifier",
    "build_default_message",
]
