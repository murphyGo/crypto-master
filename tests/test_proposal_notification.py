"""Tests for the notification subsystem (Phase 6.3)."""

from __future__ import annotations

import io
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.proposal.engine import Proposal, ProposalScore
from src.proposal.notification import (
    ConsoleNotifier,
    FileNotifier,
    Notification,
    NotificationDispatcher,
    NotificationLevel,
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
    proposal = make_proposal(signal="long", symbol="BTC/USDT")

    msg = build_default_message(proposal, NotificationLevel.GOOD_OPPORTUNITY)

    assert "Good opportunity" in msg
    assert "LONG" in msg
    assert "BTC/USDT" in msg
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
    n = make_notification()
    delta = datetime.now() - n.created_at
    assert delta.total_seconds() < 5
