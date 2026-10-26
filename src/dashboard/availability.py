"""Foreground-only availability display; failed reads never become zeros."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import ParamSpec, TypeVar

import streamlit as st

from src.dashboard.read_models import ReadResult

_P = ParamSpec("_P")
_T = TypeVar("_T")
_MAX_PAGE_PROGRESS = 16


@dataclass
class _PageProgress:
    probes: list[Callable[[], bool]] = field(default_factory=list)
    legacy: bool = False
    fired: bool = False

    def add(self, probe: Callable[[], bool] | None) -> None:
        if probe is None:
            self.legacy = True
        elif probe not in self.probes:
            if len(self.probes) < _MAX_PAGE_PROGRESS:
                self.probes.append(probe)
            else:
                # Keep compatibility for unknown/overflow dependencies without
                # retaining more handles or hiding useful known progress.
                self.legacy = True


@dataclass
class _PageReads:
    pending: bool = False
    terminal: bool = False
    retries: list[Callable[[], None]] = field(default_factory=list)
    progress: _PageProgress = field(default_factory=_PageProgress)


_page_reads: ContextVar[_PageReads | None] = ContextVar("page_reads", default=None)


def watch_loading(render: Callable[_P, _T]) -> Callable[_P, _T]:
    """Share one loading watcher across this render and any nested sections."""

    @wraps(render)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        if _page_reads.get() is not None:
            return render(*args, **kwargs)
        page = _PageReads()
        token = _page_reads.set(page)
        try:
            result = render(*args, **kwargs)
            if page.terminal:
                _refresh_terminal(render.__qualname__, page.retries)
            if page.pending and (not page.terminal or hasattr(st, "fragment")):
                _refresh_loading(render.__qualname__, page.progress)
            return result
        finally:
            # Streamlit rerun/stop and failed renders must not leave a flag
            # behind. ContextVar keeps concurrent sessions independent.
            _page_reads.reset(token)

    return wrapped


def _refresh_loading(label: str, progress: _PageProgress | None = None) -> None:
    if hasattr(st, "fragment"):
        _watch_background(label, progress)
    elif st.button("Refresh data", key=f"refresh-{label}"):
        st.rerun()


def _refresh_terminal(label: str, retries: list[Callable[[], None]]) -> None:
    if st.button("Refresh data", key=f"refresh-data-{label}"):
        for retry in retries:
            retry()
        st.rerun()


def show_availability(result: ReadResult, label: str) -> bool:
    if result.complete:
        return True
    if result.status == "stale":
        at = (
            result.evaluated_at.isoformat(timespec="seconds")
            if result.evaluated_at
            else "unknown"
        )
        st.warning(
            f"{label}: last complete view at {at}; current data is unavailable. Refresh to retry."
        )
    elif result.status == "pending" or result.reason == "queue_full":
        st.info(f"{label}: loading in the background. Refresh to check progress.")
    else:
        st.warning(f"{label}: data could not be verified. Refresh to retry.")
    page = _page_reads.get()
    if result.status == "pending" or result.reason in {"rebuild_pending", "queue_full"}:
        if page is None:
            progress = _PageProgress()
            progress.add(result.progress)
            _refresh_loading(label, progress)
        else:
            page.pending = True
            page.progress.add(result.progress)
    else:
        if page is None:
            _refresh_terminal(label, [result.retry] if result.retry else [])
        else:
            page.terminal = True
            if result.retry is not None and result.retry not in page.retries:
                page.retries.append(result.retry)
    # Detailed reasons stay in bounded server diagnostics, not the user flow.
    return False


def _watch_background(label: str, progress: _PageProgress | None = None) -> None:
    from src.dashboard.data_service import get_data_service

    if progress is None:
        # Compatibility for callers/read services without progress handles.
        if get_data_service().stats()["admitted"] == 0:
            st.rerun()
        return
    if progress.fired:
        return
    if any(probe() for probe in progress.probes) or (
        progress.legacy and get_data_service().stats()["admitted"] == 0
    ):
        # Per-render latch: do not consume a shared job signal, and do not
        # repeatedly interrupt the new full render with this old fragment.
        progress.fired = True
        st.rerun()


if hasattr(st, "fragment"):
    _watch_background = st.fragment(run_every=0.5)(_watch_background)
