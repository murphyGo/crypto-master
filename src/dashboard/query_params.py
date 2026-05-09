"""Shared Streamlit query-param helpers for dashboard pages."""

from __future__ import annotations

import streamlit as st


def query_param_first(name: str) -> str | None:
    """Return the first query-param value for dashboard drill-through."""
    raw = st.query_params.get(name)
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


def query_param_values(name: str) -> set[str]:
    """Return comma-aware query-param values for dashboard drill-through."""
    raw = st.query_params.get(name)
    if raw is None:
        return set()
    values = raw if isinstance(raw, list) else [raw]
    split_values: set[str] = set()
    for value in values:
        split_values.update(part for part in str(value).split(",") if part)
    return split_values


__all__ = ["query_param_first", "query_param_values"]
