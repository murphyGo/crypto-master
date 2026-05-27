"""Market-regime visibility read models (CAH-09 / DASH-F1 split).

Extracted verbatim from ``dashboard/pages/engine.py`` (market-regime unit).
Pure read-models / DataFrame builders over ``ActivityEvent``s; no Streamlit
render here (the master ``render`` in ``engine.py`` still wires the tables).
``engine.py`` re-exports every public symbol so existing imports resolve.

Related Requirements:
- FR-030 / FR-032 / NFR-003: engine cycle status surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.runtime.activity_log import ActivityEvent, ActivityEventType

# How many recent MARKET_REGIME_BLOCKED events to surface in the table.
MARKET_REGIME_RECENT_LIMIT = 25


@dataclass
class MarketRegimeStatusRow:
    """Latest regime classification observed for one (symbol, timeframe) pair.

    Derived from the most recent ``MARKET_REGIME_BLOCKED`` event — the
    engine only emits the classifier read on the block path today, so
    the dashboard surfaces the same view operators see in the activity
    timeline. Once the proposal-runtime emits a parallel pass-through
    event (future work), this read model expands without a schema
    change on the page.
    """

    reference_symbol: str
    timeframe: str
    regime: str
    baseline: str
    close: str
    last_observed_at: datetime


@dataclass
class MarketRegimeAccountPolicyRow:
    """Per-sub-account policy + current allow/block status row."""

    sub_account_id: str
    last_regime: str
    last_observed_at: datetime
    last_decision: str


def build_market_regime_status_rows(
    events: list[ActivityEvent],
) -> list[MarketRegimeStatusRow]:
    """Most recent classifier read per (reference_symbol, timeframe).

    Sorted newest-first so the operator sees fresh classifications at
    the top.
    """
    latest: dict[tuple[str, str], ActivityEvent] = {}
    for event in events:
        if event.event_type != ActivityEventType.MARKET_REGIME_BLOCKED.value:
            continue
        symbol = str(event.details.get("symbol", ""))
        timeframe = str(event.details.get("timeframe", ""))
        if not symbol or not timeframe:
            continue
        key = (symbol, timeframe)
        seen = latest.get(key)
        if seen is None or event.timestamp > seen.timestamp:
            latest[key] = event

    rows: list[MarketRegimeStatusRow] = []
    for (symbol, timeframe), event in latest.items():
        rows.append(
            MarketRegimeStatusRow(
                reference_symbol=symbol,
                timeframe=timeframe,
                regime=str(event.details.get("regime", "unknown")),
                baseline=str(event.details.get("baseline") or "—"),
                close=str(event.details.get("close") or "—"),
                last_observed_at=event.timestamp,
            )
        )
    rows.sort(key=lambda row: row.last_observed_at, reverse=True)
    return rows


def build_market_regime_status_dataframe(
    rows: list[MarketRegimeStatusRow],
) -> pd.DataFrame:
    columns = [
        "Reference Symbol",
        "Timeframe",
        "Regime",
        "Baseline (SMA)",
        "Close",
        "Last Observed",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Reference Symbol": row.reference_symbol,
                "Timeframe": row.timeframe,
                "Regime": row.regime,
                "Baseline (SMA)": row.baseline,
                "Close": row.close,
                "Last Observed": row.last_observed_at.isoformat(timespec="seconds"),
            }
            for row in rows
        ],
        columns=columns,
    )


def build_market_regime_account_rows(
    events: list[ActivityEvent],
) -> list[MarketRegimeAccountPolicyRow]:
    """Per-sub-account latest regime decision observed in the log.

    The engine emits ``MARKET_REGIME_BLOCKED`` only on the block path;
    "last_decision" therefore reads "block" for any account that has
    been classified, and the absence of an event is the silent "pass"
    state. Without ranking the events that's the most honest view we
    can give operators today.
    """
    latest: dict[str, ActivityEvent] = {}
    for event in events:
        if event.event_type != ActivityEventType.MARKET_REGIME_BLOCKED.value:
            continue
        sub_account_id = str(event.details.get("sub_account_id", ""))
        if not sub_account_id:
            continue
        seen = latest.get(sub_account_id)
        if seen is None or event.timestamp > seen.timestamp:
            latest[sub_account_id] = event

    rows = [
        MarketRegimeAccountPolicyRow(
            sub_account_id=sub_account_id,
            last_regime=str(event.details.get("regime", "unknown")),
            last_observed_at=event.timestamp,
            last_decision=str(event.details.get("policy_decision", "block")),
        )
        for sub_account_id, event in latest.items()
    ]
    rows.sort(key=lambda row: row.last_observed_at, reverse=True)
    return rows


def build_market_regime_account_dataframe(
    rows: list[MarketRegimeAccountPolicyRow],
) -> pd.DataFrame:
    columns = ["Sub-account", "Last Regime", "Last Decision", "Last Observed"]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Sub-account": row.sub_account_id,
                "Last Regime": row.last_regime,
                "Last Decision": row.last_decision,
                "Last Observed": row.last_observed_at.isoformat(timespec="seconds"),
            }
            for row in rows
        ],
        columns=columns,
    )


def build_market_regime_events_dataframe(
    events: list[ActivityEvent],
    *,
    limit: int = MARKET_REGIME_RECENT_LIMIT,
) -> pd.DataFrame:
    """Recent regime-blocked events, newest-first, capped at ``limit``."""
    columns = [
        "Timestamp",
        "Sub-account",
        "Reference Symbol",
        "Timeframe",
        "Regime",
        "Reason",
    ]
    blocked = [
        event
        for event in events
        if event.event_type == ActivityEventType.MARKET_REGIME_BLOCKED.value
    ]
    blocked.sort(key=lambda event: event.timestamp, reverse=True)
    blocked = blocked[:limit]
    if not blocked:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Timestamp": event.timestamp.isoformat(timespec="seconds"),
                "Sub-account": str(event.details.get("sub_account_id", "—")),
                "Reference Symbol": str(event.details.get("symbol", "—")),
                "Timeframe": str(event.details.get("timeframe", "—")),
                "Regime": str(event.details.get("regime", "—")),
                "Reason": str(event.details.get("reason", "—")),
            }
            for event in blocked
        ],
        columns=columns,
    )


def build_market_regime_degraded_events_dataframe(
    events: list[ActivityEvent],
    *,
    limit: int = MARKET_REGIME_RECENT_LIMIT,
) -> pd.DataFrame:
    """Recent regime-degraded fail-open events, newest-first.

    Surfaces the quant-trader audit follow-up:
    ``MARKET_REGIME_DEGRADED`` is emitted whenever the gate's OHLCV
    fetch raises and the gate falls open. Without this surface the
    silent disablement is invisible to the operator (DEBT-061
    anti-pattern). Capped at ``limit`` for symmetry with the blocked
    events table.
    """
    columns = [
        "Timestamp",
        "Sub-account",
        "Reference Symbol",
        "Timeframe",
        "Error Type",
        "Decision",
    ]
    degraded = [
        event
        for event in events
        if event.event_type == ActivityEventType.MARKET_REGIME_DEGRADED.value
    ]
    degraded.sort(key=lambda event: event.timestamp, reverse=True)
    degraded = degraded[:limit]
    if not degraded:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Timestamp": event.timestamp.isoformat(timespec="seconds"),
                "Sub-account": str(event.details.get("sub_account_id", "—")),
                "Reference Symbol": str(event.details.get("symbol", "—")),
                "Timeframe": str(event.details.get("timeframe", "—")),
                "Error Type": str(event.details.get("error_type", "—")),
                "Decision": str(
                    event.details.get("policy_decision", "pass_through_degraded")
                ),
            }
            for event in degraded
        ],
        columns=columns,
    )


__all__ = [
    "MARKET_REGIME_RECENT_LIMIT",
    "MarketRegimeAccountPolicyRow",
    "MarketRegimeStatusRow",
    "build_market_regime_account_dataframe",
    "build_market_regime_account_rows",
    "build_market_regime_degraded_events_dataframe",
    "build_market_regime_events_dataframe",
    "build_market_regime_status_dataframe",
    "build_market_regime_status_rows",
]
