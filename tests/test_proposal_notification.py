"""Tests for the notification subsystem (Phase 6.3, extended for 11.3)."""

from __future__ import annotations

import io
import json
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal
from email.message import EmailMessage
from pathlib import Path

import pytest

from src.config import reload_settings
from src.proposal.engine import Proposal, ProposalScore
from src.proposal.notification import (
    ConsoleNotifier,
    EmailNotifier,
    FileNotifier,
    Notification,
    NotificationDispatcher,
    NotificationLevel,
    RoutedNotificationDispatcher,
    SlackNotifier,
    TelegramNotifier,
    _build_email_body,
    _build_email_subject,
    _build_slack_payload,
    _build_telegram_text,
    build_default_message,
)

# =============================================================================
# Helpers
# =============================================================================


def make_score(composite: float = 1.6) -> ProposalScore:
    return ProposalScore(
        confidence=0.8,
        win_rate=0.6,
        sample_size=25,
        expected_value=2.0,
        sample_factor=1.0,
        edge_factor=2.0,
        composite=composite,
    )


def make_proposal(
    *,
    proposal_id: str | None = None,
    composite: float = 1.6,
    signal: str = "long",
    symbol: str = "BTC/USDT",
    rr: float = 3.0,
    sub_account_id: str = "default",
) -> Proposal:
    kwargs: dict[str, object] = {
        "symbol": symbol,
        "timeframe": "1h",
        "signal": signal,
        "technique_name": "tech_a",
        "technique_version": "1.0.0",
        "entry_price": Decimal("50000"),
        "stop_loss": Decimal("49500"),
        "take_profit": Decimal("51500"),
        "quantity": Decimal("0.1"),
        "leverage": 1,
        "risk_reward_ratio": rr,
        "score": make_score(composite=composite),
        "reasoning": "Test reasoning.",
        "sub_account_id": sub_account_id,
    }
    if proposal_id is not None:
        kwargs["proposal_id"] = proposal_id
    return Proposal(**kwargs)


def make_notification(
    proposal: Proposal | None = None,
    level: NotificationLevel = NotificationLevel.GOOD_OPPORTUNITY,
    message: str | None = None,
) -> Notification:
    proposal = proposal or make_proposal()
    return Notification(
        level=level,
        proposal=proposal,
        message=message or build_default_message(proposal, level),
    )


class RecordingNotifier:
    """Test double that records every Notification it receives."""

    def __init__(self) -> None:
        self.received: list[Notification] = []

    async def send(self, notification: Notification) -> None:
        self.received.append(notification)


class FailingNotifier:
    """Test double that raises on send."""

    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc or RuntimeError("boom")

    async def send(self, notification: Notification) -> None:
        raise self.exc


# =============================================================================
# build_default_message
# =============================================================================


def test_build_default_message_marks_good_opportunity() -> None:
    proposal = make_proposal(
        signal="long",
        symbol="BTC/USDT",
        sub_account_id="experimental",
    )

    msg = build_default_message(proposal, NotificationLevel.GOOD_OPPORTUNITY)

    assert "Good opportunity" in msg
    assert "LONG" in msg
    assert "BTC/USDT" in msg
    assert "[experimental]" in msg
    assert "50000" in msg
    assert "R/R=3.00" in msg


def test_build_default_message_info_level() -> None:
    proposal = make_proposal()

    msg = build_default_message(proposal, NotificationLevel.INFO)

    assert "Good opportunity" not in msg
    assert "Proposal" in msg


# =============================================================================
# ConsoleNotifier
# =============================================================================


async def test_console_notifier_writes_message_to_stream() -> None:
    buf = io.StringIO()
    notifier = ConsoleNotifier(stream=buf)
    notification = make_notification()

    await notifier.send(notification)

    output = buf.getvalue()
    assert notification.message in output
    assert "GOOD_OPPORTUNITY" in output


async def test_console_notifier_includes_timestamp() -> None:
    buf = io.StringIO()
    notifier = ConsoleNotifier(stream=buf)
    notification = make_notification()

    await notifier.send(notification)

    output = buf.getvalue()
    # ISO timestamp prefix in brackets — at least the year should appear.
    assert str(notification.created_at.year) in output


async def test_console_notifier_default_stream_is_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    notifier = ConsoleNotifier()

    await notifier.send(make_notification())

    out = capsys.readouterr().out
    assert "GOOD_OPPORTUNITY" in out


# =============================================================================
# FileNotifier
# =============================================================================


def test_file_notifier_constructor_respects_settings_data_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default notification path is rooted under Settings.data_dir (Phase 10.5)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reload_settings()
    try:
        notifier = FileNotifier()
    finally:
        monkeypatch.delenv("DATA_DIR", raising=False)
        reload_settings()

    assert notifier.path == tmp_path / "notifications" / "proposals.jsonl"
    assert tmp_path in notifier.path.parents


async def test_file_notifier_appends_jsonl(tmp_path: Path) -> None:
    log_path = tmp_path / "notifications.jsonl"
    notifier = FileNotifier(path=log_path)
    notification = make_notification()

    await notifier.send(notification)

    contents = log_path.read_text(encoding="utf-8")
    assert contents.endswith("\n")
    # One JSON object per line.
    assert contents.count("\n") == 1


async def test_file_notifier_creates_parent_directory_lazily(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "a" / "b" / "notifications.jsonl"
    notifier = FileNotifier(path=nested)

    await notifier.send(make_notification())

    assert nested.is_dir() is False  # it's the file itself
    assert nested.exists()
    assert nested.parent.is_dir()


async def test_file_notifier_round_trip(tmp_path: Path) -> None:
    log_path = tmp_path / "notifications.jsonl"
    notifier = FileNotifier(path=log_path)
    n1 = make_notification(proposal=make_proposal(proposal_id="p1"))
    n2 = make_notification(proposal=make_proposal(proposal_id="p2"))

    await notifier.send(n1)
    await notifier.send(n2)

    loaded = notifier.read_all()
    assert [n.notification_id for n in loaded] == [
        n1.notification_id,
        n2.notification_id,
    ]
    assert [n.proposal.proposal_id for n in loaded] == ["p1", "p2"]


def test_file_notifier_read_all_missing_file_returns_empty(
    tmp_path: Path,
) -> None:
    notifier = FileNotifier(path=tmp_path / "never_written.jsonl")

    assert notifier.read_all() == []


async def test_file_notifier_read_all_skips_malformed_lines(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "notifications.jsonl"
    notifier = FileNotifier(path=log_path)
    await notifier.send(make_notification())
    # Append a corrupted line (e.g. a partial write after a crash).
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")

    loaded = notifier.read_all()

    assert len(loaded) == 1


# =============================================================================
# NotificationDispatcher
# =============================================================================


async def test_dispatcher_fans_out_to_all_notifiers() -> None:
    a, b = RecordingNotifier(), RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[a, b])
    proposal = make_proposal(composite=1.0)

    notification = await dispatcher.notify_proposal(proposal)

    assert notification is not None
    assert a.received == [notification]
    assert b.received == [notification]


async def test_dispatcher_filters_below_min_score() -> None:
    notifier = RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[notifier], min_score=1.0)
    weak = make_proposal(composite=0.4)

    result = await dispatcher.notify_proposal(weak)

    assert result is None
    assert notifier.received == []


async def test_dispatcher_passes_at_threshold() -> None:
    notifier = RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[notifier], min_score=1.0)
    on_threshold = make_proposal(composite=1.0)

    result = await dispatcher.notify_proposal(on_threshold)

    assert result is not None
    assert notifier.received == [result]


async def test_dispatcher_isolates_notifier_failures() -> None:
    """One bad backend must not silence the others."""
    bad = FailingNotifier(RuntimeError("file disk full"))
    good = RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[bad, good])

    notification = await dispatcher.notify_proposal(make_proposal())

    assert notification is not None
    # Good still received it even though bad raised.
    assert good.received == [notification]


async def test_dispatcher_uses_default_good_opportunity_level() -> None:
    notifier = RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[notifier])

    await dispatcher.notify_proposal(make_proposal())

    assert notifier.received[0].level == NotificationLevel.GOOD_OPPORTUNITY.value


async def test_dispatcher_respects_explicit_level_and_message() -> None:
    notifier = RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[notifier])

    await dispatcher.notify_proposal(
        make_proposal(),
        level=NotificationLevel.INFO,
        message="custom hook",
    )

    sent = notifier.received[0]
    assert sent.level == NotificationLevel.INFO.value
    assert sent.message == "custom hook"


async def test_dispatcher_with_empty_notifier_list_still_returns_notification() -> None:
    dispatcher = NotificationDispatcher(notifiers=[])

    result = await dispatcher.notify_proposal(make_proposal())

    assert result is not None


async def test_routed_dispatcher_sends_matching_sub_account_to_route() -> None:
    default = RecordingNotifier()
    experimental = RecordingNotifier()
    dispatcher = RoutedNotificationDispatcher(
        default_dispatcher=NotificationDispatcher(notifiers=[default]),
        sub_account_routes={"experimental": "lab"},
        route_dispatchers={"lab": NotificationDispatcher(notifiers=[experimental])},
    )

    notification = await dispatcher.notify_proposal(
        make_proposal(sub_account_id="experimental")
    )

    assert notification is not None
    assert experimental.received == [notification]
    assert default.received == []


async def test_routed_dispatcher_falls_back_without_route_match() -> None:
    default = RecordingNotifier()
    experimental = RecordingNotifier()
    dispatcher = RoutedNotificationDispatcher(
        default_dispatcher=NotificationDispatcher(notifiers=[default]),
        sub_account_routes={"experimental": "missing"},
        route_dispatchers={"lab": NotificationDispatcher(notifiers=[experimental])},
    )

    notification = await dispatcher.notify_proposal(
        make_proposal(sub_account_id="experimental")
    )

    assert notification is not None
    assert default.received == [notification]
    assert experimental.received == []


# =============================================================================
# End-to-end: dispatcher → file backend
# =============================================================================


async def test_dispatcher_persists_via_file_notifier(tmp_path: Path) -> None:
    log_path = tmp_path / "notifications.jsonl"
    file_notifier = FileNotifier(path=log_path)
    console_buf = io.StringIO()
    console_notifier = ConsoleNotifier(stream=console_buf)
    dispatcher = NotificationDispatcher(notifiers=[file_notifier, console_notifier])

    sent = await dispatcher.notify_proposal(make_proposal(proposal_id="abc"))

    # File backend captured it durably.
    loaded = file_notifier.read_all()
    assert len(loaded) == 1
    assert loaded[0].notification_id == sent.notification_id  # type: ignore[union-attr]
    assert loaded[0].proposal.proposal_id == "abc"
    # Console backend produced visible output.
    assert "abc" not in console_buf.getvalue()  # console shows message, not id
    assert "GOOD_OPPORTUNITY" in console_buf.getvalue()


# =============================================================================
# Notification model
# =============================================================================


def test_notification_default_id_is_unique() -> None:
    a = make_notification()
    b = make_notification()
    assert a.notification_id != b.notification_id


def test_notification_created_at_default_recent() -> None:
    """Phase 21.2: Notification.created_at is UTC-aware via ``now_utc``."""
    n = make_notification()
    assert n.created_at.tzinfo is not None
    delta = datetime.now(tz=timezone.utc) - n.created_at
    assert delta.total_seconds() < 5


# =============================================================================
# SlackNotifier (Phase 11.3)
# =============================================================================


WEBHOOK_URL = "https://hooks.slack.com/services/T00000/B00000/XXXXXXXXXX"


def test_build_slack_payload_text_matches_spec() -> None:
    """Payload ``text`` field is the one-line summary spec'd in 11.3."""
    proposal = make_proposal(
        symbol="BTC/USDT",
        signal="short",
        composite=1.234,
    )
    payload = _build_slack_payload(make_notification(proposal=proposal))

    assert payload["text"] == "[default] BTC/USDT short score=1.23 entry=50000"


def test_build_slack_payload_blocks_have_summary_and_detail() -> None:
    proposal = make_proposal(
        symbol="ETH/USDT",
        signal="long",
        composite=1.5,
    )
    payload = _build_slack_payload(make_notification(proposal=proposal))

    blocks = payload["blocks"]
    assert len(blocks) == 2
    summary, detail = blocks

    # Summary block — bolded headline.
    assert summary["type"] == "section"
    assert "*[default] ETH/USDT long*" in summary["text"]["text"]
    assert "score=1.50" in summary["text"]["text"]

    # Detail block — code-fenced multi-line key/value.
    assert detail["type"] == "section"
    detail_text = detail["text"]["text"]
    assert detail_text.startswith("```\n")
    assert detail_text.endswith("```")
    assert f"proposal_id: {proposal.proposal_id}" in detail_text
    assert "sub_account_id: default" in detail_text
    assert f"technique: {proposal.technique_name}" in detail_text
    assert f"SL: {proposal.stop_loss}" in detail_text
    assert f"TP: {proposal.take_profit}" in detail_text
    assert f"qty: {proposal.quantity}" in detail_text
    assert f"leverage: {proposal.leverage}x" in detail_text


def test_slack_notifier_repr_redacts_url() -> None:
    """Webhook URL is a secret — ``__repr__`` must mask it."""
    notifier = SlackNotifier(WEBHOOK_URL)

    rendered = repr(notifier)

    assert WEBHOOK_URL not in rendered
    assert "redacted" in rendered.lower()


async def test_slack_notify_proposal_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Notifying a proposal POSTs a Slack-shaped JSON payload."""
    notifier = SlackNotifier(WEBHOOK_URL)
    proposal = make_proposal(symbol="BTC/USDT", signal="short", composite=1.23)
    notification = make_notification(proposal=proposal)

    captured: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    def _fake_urlopen(req: object, timeout: float = 0) -> _FakeResponse:
        # ``Request`` records URL and body for assertions.
        captured["url"] = req.full_url  # type: ignore[attr-defined]
        captured["data"] = req.data  # type: ignore[attr-defined]
        captured["method"] = req.get_method()  # type: ignore[attr-defined]
        captured["headers"] = dict(req.headers)  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(
        "src.proposal.notification.urllib.request.urlopen", _fake_urlopen
    )

    await notifier.send(notification)

    assert captured["url"] == WEBHOOK_URL
    assert captured["method"] == "POST"
    # Headers are normalized — Content-type is the urllib-style key.
    assert captured["headers"].get("Content-type") == "application/json"

    payload = json.loads(captured["data"])  # type: ignore[arg-type]
    # Spec format: ``{symbol} {side} score={composite:.2f} entry={price}``
    assert payload["text"] == "[default] BTC/USDT short score=1.23 entry=50000"
    assert len(payload["blocks"]) == 2
    # Summary + code-fence detail.
    assert "*[default] BTC/USDT short*" in payload["blocks"][0]["text"]["text"]
    assert "```" in payload["blocks"][1]["text"]["text"]


async def test_slack_http_failure_does_not_crash_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 500 from Slack must not silence other notifiers."""
    import urllib.error

    def _raise_500(*args: object, **kwargs: object) -> None:
        raise urllib.error.HTTPError(
            url=WEBHOOK_URL,
            code=500,
            msg="Internal Server Error",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

    monkeypatch.setattr("src.proposal.notification.urllib.request.urlopen", _raise_500)

    slack = SlackNotifier(WEBHOOK_URL)
    good = RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[slack, good])

    notification = await dispatcher.notify_proposal(make_proposal())

    # Notification was constructed and the second backend still
    # received it even though Slack raised.
    assert notification is not None
    assert good.received == [notification]


async def test_slack_notifier_does_not_log_webhook_url(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The webhook URL must never appear in logs (it's a secret)."""
    import logging

    class _FakeResponse:
        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    monkeypatch.setattr(
        "src.proposal.notification.urllib.request.urlopen",
        lambda *a, **kw: _FakeResponse(),
    )

    notifier = SlackNotifier(WEBHOOK_URL)
    with caplog.at_level(logging.DEBUG, logger="crypto_master.proposal.notification"):
        await notifier.send(make_notification())

    for record in caplog.records:
        assert WEBHOOK_URL not in record.getMessage()


def test_slack_notifier_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constructor's timeout flows into the urllib call."""
    notifier = SlackNotifier(WEBHOOK_URL, timeout=2.5)
    assert notifier.timeout == 2.5


# =============================================================================
# TelegramNotifier (Phase 12.4)
# =============================================================================


TELEGRAM_BOT_TOKEN = "123456789:AAH-secret-token-XYZ"
TELEGRAM_CHAT_ID = "-1001234567890"


def test_build_telegram_text_has_summary_and_detail() -> None:
    """Telegram body collapses Slack's two blocks into one Markdown
    string: a bolded headline and a code-fenced detail section."""
    proposal = make_proposal(
        symbol="ETH/USDT",
        signal="long",
        composite=1.5,
    )
    text = _build_telegram_text(make_notification(proposal=proposal))

    # Bolded headline.
    assert "*[default] ETH/USDT long*" in text
    assert "score=1.50" in text
    assert "entry=50000" in text

    # Code-fenced detail with the same fields as Slack.
    assert "```" in text
    assert f"proposal_id: {proposal.proposal_id}" in text
    assert "sub_account_id: default" in text
    assert f"technique: {proposal.technique_name}" in text
    assert f"SL: {proposal.stop_loss}" in text
    assert f"TP: {proposal.take_profit}" in text
    assert f"qty: {proposal.quantity}" in text
    assert f"leverage: {proposal.leverage}x" in text
    assert "rr: 3.00" in text


def test_telegram_notifier_repr_masks_token() -> None:
    """Bot token AND chat id are secrets — ``__repr__`` masks both."""
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

    rendered = repr(notifier)

    assert TELEGRAM_BOT_TOKEN not in rendered
    assert TELEGRAM_CHAT_ID not in rendered
    assert "redacted" in rendered.lower()


async def test_telegram_notifier_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Notifying a proposal POSTs a form-encoded Telegram payload."""
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    proposal = make_proposal(symbol="BTC/USDT", signal="short", composite=1.23)
    notification = make_notification(proposal=proposal)

    captured: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok":true}'

    def _fake_urlopen(req: object, timeout: float = 0) -> _FakeResponse:
        captured["url"] = req.full_url  # type: ignore[attr-defined]
        captured["data"] = req.data  # type: ignore[attr-defined]
        captured["method"] = req.get_method()  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(
        "src.proposal.notification.urllib.request.urlopen", _fake_urlopen
    )

    await notifier.send(notification)

    # URL has the bot/<TOKEN>/sendMessage path (matches Telegram Bot API).
    assert captured["url"] == (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )
    assert captured["method"] == "POST"

    # Form-encoded body has chat_id, text (Markdown), parse_mode.
    parsed = urllib.parse.parse_qs(captured["data"].decode("utf-8"))  # type: ignore[union-attr]
    assert parsed["chat_id"] == [TELEGRAM_CHAT_ID]
    assert parsed["parse_mode"] == ["Markdown"]
    text = parsed["text"][0]
    # Spec format: bolded headline + code-fenced detail.
    assert "*[default] BTC/USDT short*" in text
    assert "score=1.23" in text
    assert "entry=50000" in text
    assert "```" in text
    assert f"proposal_id: {proposal.proposal_id}" in text


async def test_telegram_http_failure_does_not_crash_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 500 from Telegram must not silence other notifiers."""
    import urllib.error

    def _raise_500(*args: object, **kwargs: object) -> None:
        raise urllib.error.HTTPError(
            url=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            code=500,
            msg="Internal Server Error",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

    monkeypatch.setattr("src.proposal.notification.urllib.request.urlopen", _raise_500)

    telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    good = RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[telegram, good])

    notification = await dispatcher.notify_proposal(make_proposal())

    # Notification was constructed and the second backend still
    # received it even though Telegram raised.
    assert notification is not None
    assert good.received == [notification]


async def test_telegram_notifier_does_not_log_secrets(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The bot token and chat id must never appear in logs."""
    import logging

    class _FakeResponse:
        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok":true}'

    monkeypatch.setattr(
        "src.proposal.notification.urllib.request.urlopen",
        lambda *a, **kw: _FakeResponse(),
    )

    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    with caplog.at_level(logging.DEBUG, logger="crypto_master.proposal.notification"):
        await notifier.send(make_notification())

    for record in caplog.records:
        message = record.getMessage()
        assert TELEGRAM_BOT_TOKEN not in message
        assert TELEGRAM_CHAT_ID not in message


def test_telegram_notifier_uses_configured_timeout() -> None:
    """The constructor's timeout flows into the urllib call."""
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, timeout=2.5)
    assert notifier.timeout == 2.5


# =============================================================================
# EmailNotifier (Phase 13.4)
# =============================================================================


EMAIL_SMTP_HOST = "smtp.example.com"
EMAIL_SMTP_PORT = 587
EMAIL_SMTP_USER = "bot@example.com"
EMAIL_SMTP_PASSWORD = "super-secret-app-password"
EMAIL_FROM = "Crypto Master <bot@example.com>"
EMAIL_TO = "alerts@example.com"


class _FakeSMTP:
    """Stand-in for ``smtplib.SMTP`` that records every method call.

    Mirrors the relevant subset of the real client (context-manager
    plus ``starttls`` / ``login`` / ``send_message``) so the tests can
    assert handshake order without speaking to a real server.
    """

    instances: list[_FakeSMTP] = []

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.starttls_called = False
        self.login_args: tuple[str, str] | None = None
        self.sent_messages: list[EmailMessage] = []
        self.quit_called = False
        type(self).instances.append(self)

    def __enter__(self) -> _FakeSMTP:
        return self

    def __exit__(self, *exc: object) -> None:
        self.quit_called = True
        return None

    def starttls(self) -> None:
        self.starttls_called = True

    def login(self, user: str, password: str) -> None:
        self.login_args = (user, password)

    def send_message(self, msg: EmailMessage) -> None:
        self.sent_messages.append(msg)


def _make_email_notifier() -> EmailNotifier:
    return EmailNotifier(
        host=EMAIL_SMTP_HOST,
        port=EMAIL_SMTP_PORT,
        user=EMAIL_SMTP_USER,
        password=EMAIL_SMTP_PASSWORD,
        from_addr=EMAIL_FROM,
        to_addr=EMAIL_TO,
    )


def test_build_email_subject_matches_spec() -> None:
    """Subject includes the sub-account suffix for routed alerts."""
    proposal = make_proposal(
        symbol="BTC/USDT",
        signal="short",
        composite=1.234,
        sub_account_id="experimental",
    )

    subject = _build_email_subject(make_notification(proposal=proposal))

    assert subject == "Crypto Master: BTC/USDT short score=1.23 [experimental]"


def test_notifier_payloads_include_sub_account_id() -> None:
    proposal = make_proposal(sub_account_id="btc_only")
    notification = make_notification(proposal=proposal)

    slack_payload = _build_slack_payload(notification)
    telegram_text = _build_telegram_text(notification)
    email_subject = _build_email_subject(notification)

    assert "[btc_only]" in slack_payload["text"]
    assert "sub_account_id: btc_only" in json.dumps(slack_payload)
    assert "sub_account_id: btc_only" in telegram_text
    assert email_subject.endswith("[btc_only]")


def test_build_email_body_matches_telegram_text() -> None:
    """Email body reuses the Telegram Markdown content verbatim."""
    proposal = make_proposal(symbol="ETH/USDT", signal="long", composite=1.5)
    notification = make_notification(proposal=proposal)

    assert _build_email_body(notification) == _build_telegram_text(notification)


async def test_email_notifier_subject_and_body_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Notifying a proposal sends an SMTP message with the spec'd
    subject + body and the configured From/To headers."""
    _FakeSMTP.instances = []
    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP", _FakeSMTP)

    notifier = _make_email_notifier()
    proposal = make_proposal(symbol="BTC/USDT", signal="short", composite=1.23)
    notification = make_notification(proposal=proposal)

    await notifier.send(notification)

    assert len(_FakeSMTP.instances) == 1
    fake = _FakeSMTP.instances[0]
    assert fake.host == EMAIL_SMTP_HOST
    assert fake.port == EMAIL_SMTP_PORT
    assert len(fake.sent_messages) == 1

    msg = fake.sent_messages[0]
    assert msg["Subject"] == "Crypto Master: BTC/USDT short score=1.23 [default]"
    assert msg["From"] == EMAIL_FROM
    assert msg["To"] == EMAIL_TO
    body = msg.get_content()
    assert "*[default] BTC/USDT short*" in body
    assert "score=1.23" in body
    assert "entry=50000" in body
    assert "```" in body
    assert f"proposal_id: {proposal.proposal_id}" in body


def test_email_notifier_repr_masks_password() -> None:
    """Password is a secret — ``__repr__`` must mask it."""
    notifier = _make_email_notifier()

    rendered = repr(notifier)

    assert EMAIL_SMTP_PASSWORD not in rendered
    assert "redacted" in rendered.lower()
    # Host / user / from / to are operationally useful for log triage,
    # so they remain visible. Only the password is masked.
    assert EMAIL_SMTP_HOST in rendered
    assert EMAIL_SMTP_USER in rendered


async def test_email_notifier_uses_starttls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STARTTLS handshake must be called before login (Phase 13.4 spec)."""
    _FakeSMTP.instances = []
    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP", _FakeSMTP)

    notifier = _make_email_notifier()
    await notifier.send(make_notification())

    assert len(_FakeSMTP.instances) == 1
    fake = _FakeSMTP.instances[0]
    assert fake.starttls_called is True


async def test_email_notifier_login_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SMTP authentication is required for our typical providers."""
    _FakeSMTP.instances = []
    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP", _FakeSMTP)

    notifier = _make_email_notifier()
    await notifier.send(make_notification())

    assert len(_FakeSMTP.instances) == 1
    fake = _FakeSMTP.instances[0]
    assert fake.login_args == (EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD)


async def test_email_smtp_failure_does_not_crash_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An SMTP-side error must not silence other notifiers."""
    import smtplib as _smtplib_real

    def _raising_smtp(*args: object, **kwargs: object) -> _FakeSMTP:
        raise _smtplib_real.SMTPException("connection refused")

    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP", _raising_smtp)

    email_notifier = _make_email_notifier()
    good = RecordingNotifier()
    dispatcher = NotificationDispatcher(notifiers=[email_notifier, good])

    notification = await dispatcher.notify_proposal(make_proposal())

    # Notification was constructed and the second backend still
    # received it even though SMTP raised.
    assert notification is not None
    assert good.received == [notification]


async def test_email_notifier_does_not_log_password(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The SMTP password must never appear in logs (it's a secret)."""
    import logging

    _FakeSMTP.instances = []
    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP", _FakeSMTP)

    notifier = _make_email_notifier()
    with caplog.at_level(logging.DEBUG, logger="crypto_master.proposal.notification"):
        await notifier.send(make_notification())

    for record in caplog.records:
        assert EMAIL_SMTP_PASSWORD not in record.getMessage()


async def test_email_notifier_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constructor's timeout flows into the smtplib call."""
    _FakeSMTP.instances = []
    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP", _FakeSMTP)

    notifier = EmailNotifier(
        host=EMAIL_SMTP_HOST,
        port=EMAIL_SMTP_PORT,
        user=EMAIL_SMTP_USER,
        password=EMAIL_SMTP_PASSWORD,
        from_addr=EMAIL_FROM,
        to_addr=EMAIL_TO,
        timeout=3.5,
    )

    await notifier.send(make_notification())

    assert len(_FakeSMTP.instances) == 1
    assert _FakeSMTP.instances[0].timeout == 3.5


# =============================================================================
# EmailNotifier SMTP_SSL alternative (Phase 14.2 / DEBT-012)
# =============================================================================


async def test_email_notifier_uses_smtp_ssl_when_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``use_ssl=True`` routes through ``smtplib.SMTP_SSL`` and skips
    ``starttls()`` (the channel is already encrypted on connect).

    Phase 14.2 / DEBT-012: Yahoo Mail, AT&T, and ProtonMail only offer
    SMTP-over-SSL on port 465. The notifier must construct
    ``SMTP_SSL`` (not ``SMTP``) and must NOT call ``starttls`` on the
    SSL path — calling it on an already-TLS connection raises
    ``SMTPNotSupportedError`` at runtime.
    """
    _FakeSMTP.instances = []
    # Patch ``SMTP_SSL`` for the SSL path; also patch ``SMTP`` to a
    # raising stub so the test fails loudly if the wrong constructor
    # is selected.
    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP_SSL", _FakeSMTP)

    def _wrong_constructor(*args: object, **kwargs: object) -> _FakeSMTP:
        raise AssertionError("smtplib.SMTP must not be called when use_ssl=True")

    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP", _wrong_constructor)

    notifier = EmailNotifier(
        host=EMAIL_SMTP_HOST,
        port=465,
        user=EMAIL_SMTP_USER,
        password=EMAIL_SMTP_PASSWORD,
        from_addr=EMAIL_FROM,
        to_addr=EMAIL_TO,
        use_ssl=True,
    )

    await notifier.send(make_notification())

    assert len(_FakeSMTP.instances) == 1
    fake = _FakeSMTP.instances[0]
    assert fake.host == EMAIL_SMTP_HOST
    assert fake.port == 465
    # The SSL channel is already encrypted — STARTTLS must NOT fire.
    assert fake.starttls_called is False
    # Login + send_message still happen on the SSL path.
    assert fake.login_args == (EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD)
    assert len(fake.sent_messages) == 1


async def test_email_notifier_uses_starttls_when_flag_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default ``use_ssl=False`` keeps the existing STARTTLS path
    intact — backward compatibility for pre-Phase 14.2 callers.

    The notifier must construct ``smtplib.SMTP`` (not ``SMTP_SSL``)
    and must call ``starttls()`` before login.
    """
    _FakeSMTP.instances = []
    monkeypatch.setattr("src.proposal.notification.smtplib.SMTP", _FakeSMTP)

    def _wrong_constructor(*args: object, **kwargs: object) -> _FakeSMTP:
        raise AssertionError("smtplib.SMTP_SSL must not be called when use_ssl=False")

    monkeypatch.setattr(
        "src.proposal.notification.smtplib.SMTP_SSL", _wrong_constructor
    )

    notifier = _make_email_notifier()  # use_ssl defaults to False

    await notifier.send(make_notification())

    assert len(_FakeSMTP.instances) == 1
    fake = _FakeSMTP.instances[0]
    assert fake.host == EMAIL_SMTP_HOST
    assert fake.port == EMAIL_SMTP_PORT
    # STARTTLS handshake fires on the default path.
    assert fake.starttls_called is True
    assert fake.login_args == (EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD)
    assert len(fake.sent_messages) == 1
