"""Foreground-only availability display; failed reads never become zeros."""

from __future__ import annotations

import streamlit as st

from src.dashboard.read_models import ReadResult


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
        if hasattr(st, "fragment"):
            _watch_background(label)
        elif st.button("Refresh data", key=f"refresh-{label}"):
            st.rerun()
    # Stable code aids diagnosis without displaying persisted payloads,
    # filesystem paths, exception strings or implementation internals.
    return False


def _watch_background(label: str) -> None:
    from src.dashboard.data_service import get_data_service

    if get_data_service().stats()["admitted"] == 0:
        st.rerun()


if hasattr(st, "fragment"):
    _watch_background = st.fragment(run_every=0.5)(_watch_background)
