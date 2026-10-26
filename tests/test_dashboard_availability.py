"""Loading checks are shared per render without suppressing section coverage."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, current_thread

import pytest

from src.dashboard import availability
from src.dashboard.read_models import ReadResult


@pytest.fixture
def loading_ui(monkeypatch):
    messages = []
    watchers = []
    monkeypatch.setattr(availability.st, "info", messages.append)
    monkeypatch.setattr(availability.st, "warning", messages.append)
    monkeypatch.setattr(availability.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        availability, "_watch_background", lambda label: watchers.append(label)
    )
    return messages, watchers


def test_pending_sections_share_watcher_and_keep_each_coverage_message(loading_ui):
    messages, watchers = loading_ui

    @availability.watch_loading
    def render():
        return [
            availability.show_availability(ReadResult("pending"), label)
            for label in ("Activity", "Ledger", "Snapshots", "Candidates", "Funnel")
        ]

    assert render() == [False] * 5
    assert len(watchers) == 1
    assert len(messages) == 5
    assert all("loading in the background" in message for message in messages)
    assert {message.split(":", 1)[0] for message in messages} == {
        "Activity",
        "Ledger",
        "Snapshots",
        "Candidates",
        "Funnel",
    }


@pytest.mark.parametrize("status", ["complete", "unavailable", "stale"])
def test_terminal_or_complete_sections_do_not_schedule_loading(loading_ui, status):
    messages, watchers = loading_ui

    @availability.watch_loading
    def render():
        return availability.show_availability(ReadResult(status), "Ledger")

    assert render() is (status == "complete")
    assert not watchers
    assert bool(messages) is (status != "complete")


def test_stale_rebuild_keeps_one_loading_check(loading_ui):
    messages, watchers = loading_ui

    @availability.watch_loading
    def render():
        for label in ("Activity", "Snapshots"):
            availability.show_availability(
                ReadResult("stale", reason="rebuild_pending"), label
            )

    render()
    assert len(watchers) == 1
    assert len(messages) == 2
    assert all("current data is unavailable" in message for message in messages)


def test_nested_render_and_next_render_have_independent_watchers(loading_ui):
    messages, watchers = loading_ui

    @availability.watch_loading
    def inner():
        availability.show_availability(ReadResult("pending"), "Funnel")

    @availability.watch_loading
    def outer():
        availability.show_availability(ReadResult("pending"), "Activity")
        inner()
        availability.show_availability(ReadResult("pending"), "Ledger")

    outer()
    assert len(messages) == 3
    assert len(watchers) == 1
    inner()
    assert len(watchers) == 2


@pytest.mark.parametrize("error", [RuntimeError, BaseException])
def test_failed_or_interrupted_render_releases_loading_scope(loading_ui, error):
    _, watchers = loading_ui

    @availability.watch_loading
    def broken():
        availability.show_availability(ReadResult("pending"), "Activity")
        raise error("stop")

    with pytest.raises(error):
        broken()
    assert not watchers
    availability.show_availability(ReadResult("pending"), "Standalone")
    assert watchers == ["Standalone"]


def test_concurrent_renders_each_schedule_one_watcher(loading_ui, monkeypatch):
    messages, watchers = loading_ui
    barrier = Barrier(2)
    monkeypatch.setattr(
        availability,
        "_watch_background",
        lambda label: watchers.append(current_thread().name),
    )

    @availability.watch_loading
    def render(_):
        availability.show_availability(ReadResult("pending"), "Activity")
        barrier.wait(timeout=5)
        availability.show_availability(ReadResult("pending"), "Ledger")
        barrier.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(render, range(2)))
    assert len(messages) == 4
    assert len(watchers) == len(set(watchers)) == 2


@pytest.mark.parametrize("status", ["unavailable", "stale"])
def test_queue_full_sections_keep_one_page_watcher(loading_ui, status):
    messages, watchers = loading_ui

    @availability.watch_loading
    def render():
        for kind in ("Activity", "Snapshots"):
            availability.show_availability(
                ReadResult(status, reason="queue_full"), kind
            )

    render()
    assert len(messages) == 2
    assert len(watchers) == 1


def test_terminal_home_sections_have_one_explicit_retry_and_no_watcher(
    loading_ui, monkeypatch
):
    messages, watchers = loading_ui
    buttons = []
    monkeypatch.setattr(
        availability.st,
        "button",
        lambda label, **kwargs: buttons.append((label, kwargs)) or False,
    )

    @availability.watch_loading
    def render():
        for kind in ("Activity", "Ledger", "Snapshots", "Candidates", "Funnel"):
            result = (
                ReadResult("unavailable", reason="source_changed")
                if kind in {"Activity", "Snapshots"}
                else ReadResult("complete")
            )
            availability.show_availability(result, kind)

    render()
    assert len(messages) == 2
    assert not watchers
    assert len(buttons) == 1
    assert buttons[0][0] == "Refresh data"


def test_explicit_retry_invokes_only_terminal_actions_once_and_cleans_context(
    loading_ui, monkeypatch
):
    calls = []

    class Rerun(BaseException):
        pass

    def rerun():
        raise Rerun()

    monkeypatch.setattr(availability.st, "button", lambda *args, **kwargs: True)
    monkeypatch.setattr(availability.st, "rerun", rerun)
    failure = ReadResult(
        "stale", reason="source_changed", retry=lambda: calls.append("retry")
    )

    @availability.watch_loading
    def render():
        availability.show_availability(failure, "Activity")
        availability.show_availability(failure, "Activity nested")

    with pytest.raises(Rerun):
        render()
    assert calls == ["retry"]
    assert availability._page_reads.get() is None
    assert "retry=" not in repr(failure)
    assert failure == ReadResult("stale", reason="source_changed")


def test_mixed_terminal_and_pending_without_fragments_has_one_retry_control(
    loading_ui, monkeypatch
):
    buttons, actions = [], []
    monkeypatch.delattr(availability.st, "fragment")
    monkeypatch.setattr(
        availability.st, "button", lambda label, **kwargs: buttons.append(label) or True
    )
    monkeypatch.setattr(availability.st, "rerun", lambda: actions.append("rerun"))

    @availability.watch_loading
    def render():
        availability.show_availability(ReadResult("pending"), "Activity")
        availability.show_availability(
            ReadResult(
                "unavailable",
                reason="invalid_record",
                retry=lambda: actions.append("retry"),
            ),
            "Snapshots",
        )

    render()
    assert buttons == ["Refresh data"]
    assert actions == ["retry", "rerun"]
