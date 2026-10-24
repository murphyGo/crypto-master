"""Foreground-only availability display; failed reads never become zeros."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import ParamSpec, TypeVar

import streamlit as st

from src.dashboard.read_models import ReadResult

_P = ParamSpec("_P")
_T = TypeVar("_T")
_page_pending: ContextVar[bool | None] = ContextVar("page_pending", default=None)


def watch_loading(render: Callable[_P, _T]) -> Callable[_P, _T]:
    """Share one loading watcher across this render and any nested sections."""

    @wraps(render)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        if _page_pending.get() is not None:
            return render(*args, **kwargs)
        token = _page_pending.set(False)
        try:
            result = render(*args, **kwargs)
            if _page_pending.get():
                _refresh_loading(render.__qualname__)
            return result
        finally:
            # Streamlit rerun/stop and failed renders must not leave a flag
            # behind. ContextVar keeps concurrent sessions independent.
            _page_pending.reset(token)

    return wrapped


def _refresh_loading(label: str) -> None:
    if hasattr(st, "fragment"):
        _watch_background(label)
    elif st.button("Refresh data", key=f"refresh-{label}"):
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
    elif result.status == "pending":
        st.info(f"{label}: loading in the background. Refresh to check progress.")
    else:
        st.warning(f"{label}: data could not be verified. Refresh to retry.")
    if result.status == "pending" or result.reason == "rebuild_pending":
        if _page_pending.get() is None:
            _refresh_loading(label)
        else:
            _page_pending.set(True)
    # Stable code aids diagnosis without displaying persisted payloads,
    # filesystem paths, exception strings or implementation internals.
    return False


def _watch_background(label: str) -> None:
    from src.dashboard.data_service import get_data_service

    if get_data_service().stats()["admitted"] == 0:
        st.rerun()


if hasattr(st, "fragment"):
    _watch_background = st.fragment(run_every=0.5)(_watch_background)
