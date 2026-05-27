"""Cross-Account Risk subsystem (CAH-09 / DASH-F1 split).

Extracted verbatim from ``dashboard/pages/engine.py``
(cross-account-risk-policy DEBT-068(f-1)/(f-2)). Holds the read-only per-account
risk metrics + cap-utilization + symbol/side exposure + risk-gate event tables,
plus the operator-freeze read model, the write-side freeze toggle, and the panel
``render_cross_account_risk`` orchestrator. ``engine.py`` re-exports every public
symbol so existing imports resolve.

READ-ONLY panels built entirely from ``ActivityEvent``s. The interactive
operator-freeze TOGGLE (write to ``config/runtime_flags.yaml``) is gated behind
``st.form`` submit + a mandatory confirmation checkbox.

Sourcing note (reported back to the lead): the engine does NOT emit a
dedicated portfolio-snapshot ActivityEvent — ``_record_portfolio_
snapshot`` writes to ``PortfolioTracker`` (``data/performance/...``),
not the activity log. So per-account equity / realized-PnL-today /
open-unrealized / stop-risk / gross-notional are only opportunistically
sourceable from the risk-gate event ``details`` that DO carry them
(kill-switch and cap events emitted on a breach). Fields with no event
source are surfaced as "n/a" rather than invented. Which fields come
from where:
  - equity:               kill-switch event ``details.equity``.
  - realized_pnl_today:    daily-loss kill-switch ``details.realized_pnl_today``.
  - open_unrealized_pnl:   open-drawdown kill-switch ``details.unrealized_pnl_open``.
  - open_stop_risk_total:  open-stop-risk kill-switch ``details.open_stop_risk``
                           OR account-aggregate cap ``details.open_stop_risk_total``.
  - gross_open_notional:   account-aggregate cap ``details.gross_notional_total``.
An account that has never tripped a gate appears with all-"n/a" metrics
but is still listed (derived from any risk event referencing it).

Related Requirements:
- FR-030 / FR-032 / NFR-003: engine cycle status surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd
import streamlit as st

from src.runtime.activity_log import ActivityEvent, ActivityEventType

# Color bands mirror the reconciliation banner's stable-string contract so
# the render layer can branch on these without depending on Streamlit's
# styling vocabulary. Thresholds per spec §"Dashboard Behavior":
# GREEN <70%, AMBER 70-90%, RED 90-100%, BREACH >100%.
CapBand = Literal["green", "amber", "red", "breach"]

# Activity event types that reference a sub-account for the risk panel.
_RISK_EVENT_TYPES = (
    ActivityEventType.RISK_CAP_ADVISORY.value,
    ActivityEventType.RISK_KILL_SWITCH_TRIPPED.value,
    ActivityEventType.OPERATOR_FREEZE_ENGAGED.value,
    ActivityEventType.STALE_POSITION_DETECTED.value,
    ActivityEventType.STALE_POSITION_AUTO_CLOSED.value,
)

CROSS_ACCOUNT_RISK_RECENT_LIMIT = 25


def _cap_band(pct: float | None) -> CapBand | None:
    """Map a percent-of-cap to a color band, or ``None`` when unknown."""
    if pct is None:
        return None
    if pct > 100.0:
        return "breach"
    if pct >= 90.0:
        return "red"
    if pct >= 70.0:
        return "amber"
    return "green"


# (label, total_key, limit_key) for each global cap, shared by the
# cap-utilization table and the closest-cap picker (DASH-F2 dedup).
_GLOBAL_CAP_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "open_positions_per_symbol_side",
        "open_positions_per_symbol_side_total",
        "max_open_positions_per_symbol_side",
    ),
    (
        "gross_notional_per_symbol_side",
        "gross_notional_per_symbol_side_total",
        "max_gross_notional_per_symbol_side",
    ),
    (
        "gross_notional_per_symbol",
        "gross_notional_per_symbol_total",
        "max_gross_notional_per_symbol",
    ),
)


def _pct_of_cap(
    details: dict[str, object], total_key: str, limit_key: str
) -> float | None:
    """Percent-of-limit for one cap key in a global-cap payload.

    Returns ``None`` when the limit is unset/unparseable, the total is
    unset/unparseable, or the limit is zero (no meaningful ratio). The
    arithmetic is identical to the previously-inlined
    ``total_val / limit_val * 100.0`` (DASH-F2 dedup, behavior-preserving).
    """
    limit_raw = details.get(limit_key)
    if limit_raw in (None, ""):
        return None
    total_raw = details.get(total_key)
    if total_raw in (None, ""):
        return None
    try:
        limit_val = float(str(limit_raw))
        total_val = float(str(total_raw))
    except (TypeError, ValueError):
        return None
    if not limit_val:
        return None
    return total_val / limit_val * 100.0


def _latest_by(
    events: list[ActivityEvent],
    *,
    event_types: tuple[str, ...],
    key: str,
) -> dict[str, ActivityEvent]:
    """Most-recent event per ``details[key]`` among the given event types."""
    latest: dict[str, ActivityEvent] = {}
    for event in events:
        if event.event_type not in event_types:
            continue
        value = (event.details or {}).get(key)
        if value in (None, ""):
            continue
        ident = str(value)
        seen = latest.get(ident)
        if seen is None or event.timestamp > seen.timestamp:
            latest[ident] = event
    return latest


def _latest_cycle_id(events: list[ActivityEvent]) -> str | None:
    """The ``cycle_id`` of the most recent event that carries one."""
    latest_ts: datetime | None = None
    latest_cycle: str | None = None
    for event in events:
        if event.cycle_id is None:
            continue
        if latest_ts is None or event.timestamp > latest_ts:
            latest_ts = event.timestamp
            latest_cycle = event.cycle_id
    return latest_cycle


def kill_switch_state_for_account(
    events: list[ActivityEvent],
    sub_account_id: str,
    *,
    cycle_id: str | None,
) -> str:
    """Derive a sub-account's current kill-switch / stale-block state.

    The "current state" window is the latest cycle (``cycle_id``): a
    kill-switch / stale block is a per-cycle gate decision, so an account
    that tripped three cycles ago but not in the current cycle reads
    ``none`` (the gate is stateless across cycles except for daily-loss,
    which re-trips each cycle while it holds). When ``cycle_id`` is
    ``None`` (no cycle context) we fall back to the most-recent event
    overall so a single-shot synthetic log still resolves.

    Returns one of: ``none`` / ``daily-loss-tripped`` /
    ``drawdown-tripped`` / ``stop-risk-tripped`` / ``stale-block``. When
    multiple gates tripped on the same cycle, kill-switch trips win over
    a stale block, and the most-recent trip's gate_reason decides between
    the kill-switch sub-states.
    """
    kill_reason_map = {
        "daily_loss_kill_switch": "daily-loss-tripped",
        "portfolio_daily_loss_kill_switch": "daily-loss-tripped",
        "open_drawdown_kill_switch": "drawdown-tripped",
        "portfolio_kill_switch": "drawdown-tripped",
        "open_stop_risk_kill_switch": "stop-risk-tripped",
    }

    def _in_window(event: ActivityEvent) -> bool:
        if cycle_id is None:
            return True
        return event.cycle_id == cycle_id

    kill_events = [
        e
        for e in events
        if e.event_type == ActivityEventType.RISK_KILL_SWITCH_TRIPPED.value
        and str((e.details or {}).get("sub_account_id", "")) == sub_account_id
        and _in_window(e)
    ]
    if kill_events:
        latest = max(kill_events, key=lambda e: e.timestamp)
        gate_reason = str((latest.details or {}).get("gate_reason", ""))
        return kill_reason_map.get(gate_reason, "drawdown-tripped")

    stale_events = [
        e
        for e in events
        if e.event_type == ActivityEventType.STALE_POSITION_DETECTED.value
        and str((e.details or {}).get("sub_account_id", "")) == sub_account_id
        and _in_window(e)
    ]
    if stale_events:
        return "stale-block"
    return "none"


def build_cross_account_risk_dataframe(events: list[ActivityEvent]) -> pd.DataFrame:
    """Per-sub-account risk metrics table (DEBT-068(f-1) item 1 + 2).

    One row per sub-account referenced by any risk event, with current
    equity, realized-PnL-today, open unrealized PnL, open stop-risk total,
    gross open notional, and the current kill-switch state. Metric values
    are sourced opportunistically from the latest risk-gate event that
    carries each field (see the module-level sourcing note); unavailable
    fields render as ``"n/a"``.
    """
    columns = [
        "Sub-account",
        "Equity",
        "Realized PnL (today)",
        "Open Unrealized PnL",
        "Open Stop-Risk",
        "Gross Open Notional",
        "Kill-switch State",
    ]
    sub_account_ids: set[str] = set()
    for event in events:
        if event.event_type not in _RISK_EVENT_TYPES:
            continue
        value = (event.details or {}).get("sub_account_id")
        if value not in (None, ""):
            sub_account_ids.add(str(value))
    if not sub_account_ids:
        return pd.DataFrame(columns=columns)

    cycle_id = _latest_cycle_id(events)

    # For metric fields, walk every risk event for the account newest-first
    # and pick the first event that carries the field. Different fields may
    # come from different events (a daily-loss trip carries realized PnL; an
    # aggregate-cap event carries gross notional).
    by_account: dict[str, list[ActivityEvent]] = {sa: [] for sa in sub_account_ids}
    for event in events:
        if event.event_type not in _RISK_EVENT_TYPES:
            continue
        value = (event.details or {}).get("sub_account_id")
        if value in (None, ""):
            continue
        by_account[str(value)].append(event)

    def _pick(account_events: list[ActivityEvent], *keys: str) -> str:
        for event in sorted(account_events, key=lambda e: e.timestamp, reverse=True):
            details = event.details or {}
            for key in keys:
                raw = details.get(key)
                if raw not in (None, ""):
                    return str(raw)
        return "n/a"

    rows: list[dict[str, object]] = []
    for sub_account_id in sorted(sub_account_ids):
        account_events = by_account[sub_account_id]
        rows.append(
            {
                "Sub-account": sub_account_id,
                "Equity": _pick(account_events, "equity"),
                "Realized PnL (today)": _pick(
                    account_events,
                    "realized_pnl_today",
                    "portfolio_realized_pnl_today",
                ),
                "Open Unrealized PnL": _pick(
                    account_events,
                    "unrealized_pnl_open",
                    "portfolio_unrealized_pnl",
                ),
                "Open Stop-Risk": _pick(
                    account_events, "open_stop_risk_total", "open_stop_risk"
                ),
                "Gross Open Notional": _pick(account_events, "gross_notional_total"),
                "Kill-switch State": kill_switch_state_for_account(
                    events, sub_account_id, cycle_id=cycle_id
                ),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def build_portfolio_cap_utilization(events: list[ActivityEvent]) -> pd.DataFrame:
    """Portfolio totals vs each configured global cap, with a color band.

    DEBT-068(f-1) item 3. Sourced from the latest global-cap event
    (``RISK_CAP_ADVISORY`` / ``PROPOSAL_REJECTED`` with
    ``gate_reason="global_cap"``): that payload carries both the running
    totals (``*_total``) and the configured limits (``max_*``). One row per
    configured cap (a cap with ``max=None`` is inert and skipped, mirroring
    the runtime's "configured bounds only" rule). Columns: ``Cap``,
    ``Total``, ``Limit``, ``Pct of Cap``, ``Band`` — ``Band`` is one of the
    :data:`CapBand` stable strings so the render layer reuses the
    reconciliation color pattern.

    Note: the limits come from the gate event ``details`` (the only event
    source the page reads). When global caps are configured but have never
    fired a gate, there is no event to read and the table is empty — the
    engine emits no parallel "caps configured" event today, so the page
    cannot show 0%-utilization rows without a config source. Reported back
    to the lead as a known sourcing gap.
    """
    columns = ["Cap", "Total", "Limit", "Pct of Cap", "Band"]
    global_events = [
        e
        for e in events
        if (e.details or {}).get("gate_reason") == "global_cap"
        and e.event_type
        in (
            ActivityEventType.RISK_CAP_ADVISORY.value,
            ActivityEventType.PROPOSAL_REJECTED.value,
        )
    ]
    if not global_events:
        return pd.DataFrame(columns=columns)
    latest = max(global_events, key=lambda e: e.timestamp)
    details = latest.details or {}

    rows: list[dict[str, object]] = []
    for label, total_key, limit_key in _GLOBAL_CAP_SPECS:
        limit_raw = details.get(limit_key)
        if limit_raw in (None, ""):
            continue  # cap not configured — inert.
        total_raw = details.get(total_key)
        try:
            float(str(limit_raw))  # both must parse, or the row is dropped
            if total_raw not in (None, ""):
                float(str(total_raw))
        except (TypeError, ValueError):
            continue
        pct = _pct_of_cap(details, total_key, limit_key)
        rows.append(
            {
                "Cap": label,
                "Total": str(total_raw) if total_raw not in (None, "") else "n/a",
                "Limit": str(limit_raw),
                "Pct of Cap": round(pct, 1) if pct is not None else None,
                "Band": _cap_band(pct) or "n/a",
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def build_symbol_side_exposure_dataframe(
    events: list[ActivityEvent],
) -> pd.DataFrame:
    """Cross-(symbol, side) exposure summary (DEBT-068(f-1) item 4).

    One row per active ``(symbol, side)`` tuple observed in global-cap
    events, with the count of DISTINCT accounts holding exposure on that
    key, the latest total notional on the key, and which global cap (if
    any) it is closest to breaching. "Active" is sourced from global-cap
    events because those are the only events carrying the cross-account
    aggregate view; per-account events do not roll up a portfolio total.

    The distinct-account count is reconstructed from the latest global-cap
    event's ``existing_holders`` (other accounts already on the key) plus
    the proposing account. "Closest cap" picks the cap with the highest
    percent-of-limit among the configured caps in that event's payload.
    """
    columns = [
        "Symbol",
        "Side",
        "Accounts",
        "Total Notional",
        "Closest Cap",
    ]
    latest_by_key: dict[tuple[str, str], ActivityEvent] = {}
    for event in events:
        details = event.details or {}
        if details.get("gate_reason") != "global_cap":
            continue
        if event.event_type not in (
            ActivityEventType.RISK_CAP_ADVISORY.value,
            ActivityEventType.PROPOSAL_REJECTED.value,
        ):
            continue
        symbol = str(details.get("symbol") or "")
        side = str(details.get("side") or "")
        if not symbol or not side:
            continue
        key = (symbol, side)
        seen = latest_by_key.get(key)
        if seen is None or event.timestamp > seen.timestamp:
            latest_by_key[key] = event
    if not latest_by_key:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for (symbol, side), event in sorted(latest_by_key.items()):
        details = event.details or {}
        holders = details.get("existing_holders") or []
        accounts: set[str] = {str(h) for h in holders if h not in (None, "")}
        proposer = details.get("proposer_account") or details.get("sub_account_id")
        if proposer not in (None, ""):
            accounts.add(str(proposer))
        ss_notional = details.get("gross_notional_per_symbol_side_total")
        closest = _closest_global_cap(details)
        rows.append(
            {
                "Symbol": symbol,
                "Side": side,
                "Accounts": len(accounts),
                "Total Notional": (
                    str(ss_notional) if ss_notional not in (None, "") else "n/a"
                ),
                "Closest Cap": closest,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _closest_global_cap(details: dict[str, object]) -> str:
    """Cap label with the highest percent-of-limit in a global-cap payload."""
    best_label = "—"
    best_pct = -1.0
    for label, total_key, limit_key in _GLOBAL_CAP_SPECS:
        pct = _pct_of_cap(details, total_key, limit_key)
        if pct is None:
            continue
        if pct > best_pct:
            best_pct = pct
            best_label = label
    return best_label


def build_risk_gate_events_dataframe(
    events: list[ActivityEvent],
    *,
    limit: int = CROSS_ACCOUNT_RISK_RECENT_LIMIT,
) -> pd.DataFrame:
    """Recent risk-gate-blocked / advisory proposal events (item 5).

    Surfaces ``RISK_CAP_ADVISORY`` / ``RISK_KILL_SWITCH_TRIPPED`` /
    ``OPERATOR_FREEZE_ENGAGED`` plus the live cap / kill-switch
    ``PROPOSAL_REJECTED`` rows (keyed on ``gate_reason`` so unrelated
    proposal rejections like stale-quote are excluded). Newest-first,
    capped at ``limit``. The ``Advisory`` column makes the paper-advisory
    vs hard-block distinction explicit per the spec's paper-first model.
    """
    columns = [
        "Timestamp",
        "Event",
        "Sub-account",
        "Symbol",
        "Side",
        "Gate Reason",
        "Mode",
        "Advisory",
    ]
    risk_gate_reasons = {
        "account_aggregate_cap",
        "global_cap",
        "daily_loss_kill_switch",
        "open_drawdown_kill_switch",
        "open_stop_risk_kill_switch",
        "portfolio_kill_switch",
        "portfolio_daily_loss_kill_switch",
        "operator_freeze",
    }
    dedicated_types = {
        ActivityEventType.RISK_CAP_ADVISORY.value,
        ActivityEventType.RISK_KILL_SWITCH_TRIPPED.value,
        ActivityEventType.OPERATOR_FREEZE_ENGAGED.value,
    }
    selected: list[ActivityEvent] = []
    for event in events:
        details = event.details or {}
        if event.event_type in dedicated_types:
            selected.append(event)
        elif (
            event.event_type == ActivityEventType.PROPOSAL_REJECTED.value
            and str(details.get("gate_reason", "")) in risk_gate_reasons
        ):
            selected.append(event)
    selected.sort(key=lambda e: e.timestamp, reverse=True)
    selected = selected[:limit]
    if not selected:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, object]] = []
    for event in selected:
        details = event.details or {}
        rows.append(
            {
                "Timestamp": event.timestamp.isoformat(timespec="seconds"),
                "Event": event.event_type,
                "Sub-account": str(details.get("sub_account_id", "—")),
                "Symbol": str(details.get("symbol", "—")),
                "Side": str(details.get("side") or details.get("signal") or "—"),
                "Gate Reason": str(details.get("gate_reason", "—")),
                "Mode": str(details.get("mode", "—")),
                "Advisory": bool(details.get("advisory")),
            }
        )
    return pd.DataFrame(rows, columns=columns)


@dataclass
class OperatorFreezeState:
    """Read-only operator-freeze indicator (DEBT-068(f-1)).

    Derived purely from ``OPERATOR_FREEZE_ENGAGED`` events — the write-side
    toggle is deferred to f-2. ``engaged`` is ``True`` when at least one
    freeze-engaged event exists in the current/most-recent cycle; the
    timestamp is the most recent such event. The freeze never auto-releases
    (spec §"Hysteresis"), but a cycle with no freeze events means no
    proposal was blocked by a freeze on that cycle, which is the best
    read-only signal the activity log offers.
    """

    engaged: bool
    last_engaged_at: datetime | None


def build_operator_freeze_state(events: list[ActivityEvent]) -> OperatorFreezeState:
    """Read-only freeze-state indicator from ``OPERATOR_FREEZE_ENGAGED``."""
    freeze_events = [
        e
        for e in events
        if e.event_type == ActivityEventType.OPERATOR_FREEZE_ENGAGED.value
    ]
    if not freeze_events:
        return OperatorFreezeState(engaged=False, last_engaged_at=None)
    latest = max(freeze_events, key=lambda e: e.timestamp)
    cycle_id = _latest_cycle_id(events)
    engaged = cycle_id is None or latest.cycle_id == cycle_id
    return OperatorFreezeState(engaged=engaged, last_engaged_at=latest.timestamp)


@dataclass(frozen=True)
class FreezeTogglePlan:
    """Pure plan for the operator-freeze write toggle (DEBT-068(f-2)).

    Keeps the ENGAGE/DISENGAGE decision and its confirmation copy out of the
    ``st.*`` widget so it is unit-testable. The widget renders this plan and,
    only on an explicit confirm+submit, calls
    :func:`src.runtime.runtime_flags.write_trading_freeze` with ``next_value``.

    Attributes:
        currently_frozen: The current operator-freeze flag value (the file
            READ side), i.e. what the toggle would flip.
        next_value: The boolean the operator's action would write — the
            negation of ``currently_frozen``.
        action_label: Short button label, ``"Engage freeze"`` /
            ``"Disengage freeze"``.
        confirmation_prompt: Mandatory acknowledgement copy the operator must
            check before the action can fire. Spells out that this is a
            trading-wide halt/resume.
    """

    currently_frozen: bool
    next_value: bool
    action_label: str
    confirmation_prompt: str


def build_freeze_toggle_plan(currently_frozen: bool) -> FreezeTogglePlan:
    """Decide the next freeze value + mandatory confirmation copy.

    Pure helper (no Streamlit, no I/O) so the toggle's decision logic is
    tested directly. Disengaging is an explicit operator write of ``false``
    (the freeze never auto-releases — spec §"Hysteresis"), so it is treated
    as a deliberate, confirmation-gated action exactly like engaging.
    """
    if currently_frozen:
        return FreezeTogglePlan(
            currently_frozen=True,
            next_value=False,
            action_label="Disengage freeze",
            confirmation_prompt=(
                "I understand this RESUMES all new entries across every "
                "sub-account."
            ),
        )
    return FreezeTogglePlan(
        currently_frozen=False,
        next_value=True,
        action_label="Engage freeze",
        confirmation_prompt=(
            "I understand this HALTS all new entries across every "
            "sub-account."
        ),
    )


def render_operator_freeze_toggle(flags_path: Path | None = None) -> None:
    """Render the interactive operator-freeze toggle (DEBT-068(f-2)).

    Replaces the f-1 read-only indicator: shows the CURRENT freeze state read
    from ``config/runtime_flags.yaml`` and lets the operator engage/disengage
    it with a MANDATORY confirmation (spec §"Dashboard Behavior").

    Rerun-safety: the file write happens ONLY inside the ``st.form`` submit
    branch AND only when the confirmation checkbox is ticked. Streamlit
    re-runs the whole script on every interaction; a form's submit value is
    ``True`` for exactly the one rerun triggered by the click and ``False``
    on a plain page refresh, so a refresh can never re-toggle the freeze.
    The actual file mutation lives in
    :func:`src.runtime.runtime_flags.write_trading_freeze`, keeping this
    widget thin.
    """
    # Local imports so the page stays importable without the runtime package
    # being side-effect-loaded, matching the rest of the dashboard's thin
    # widget style.
    from src.runtime.runtime_flags import (
        RuntimeFlagsWriteError,
        read_trading_freeze,
        write_trading_freeze,
    )

    try:
        currently_frozen = read_trading_freeze(flags_path)
    except Exception as exc:  # defensive: read is fail-safe, but never crash UI
        st.warning(f"Could not read freeze state: {exc}")
        currently_frozen = False

    if currently_frozen:
        st.error("Operator manual freeze: ENGAGED — all new entries blocked.")
    else:
        st.success("Operator manual freeze: not engaged.")

    plan = build_freeze_toggle_plan(currently_frozen)
    with st.form("operator_freeze_toggle", clear_on_submit=True):
        st.caption(
            "Toggling the operator freeze is a trading-wide action and never "
            "auto-releases — disengaging requires this same explicit step."
        )
        acknowledged = st.checkbox(plan.confirmation_prompt, value=False)
        submitted = st.form_submit_button(plan.action_label)

    # Write ONLY on an explicit submit with the acknowledgement ticked.
    if submitted and acknowledged:
        try:
            write_trading_freeze(plan.next_value, flags_path)
        except RuntimeFlagsWriteError as exc:
            st.error(f"Freeze NOT changed — write failed: {exc}")
        else:
            verb = "ENGAGED" if plan.next_value else "DISENGAGED"
            st.success(f"Operator manual freeze {verb}.")
    elif submitted and not acknowledged:
        st.warning("Confirmation required — tick the acknowledgement to proceed.")


def render_cross_account_risk(events: list[ActivityEvent]) -> None:
    """Render the Cross-Account Risk panel (read-only, DEBT-068(f-1)).

    Guards empty data gracefully: when no risk events exist at all, shows
    a friendly info message rather than a clutter of empty tables.
    """
    st.subheader("Cross-Account Risk")

    metrics_df = build_cross_account_risk_dataframe(events)
    cap_df = build_portfolio_cap_utilization(events)
    exposure_df = build_symbol_side_exposure_dataframe(events)
    gate_df = build_risk_gate_events_dataframe(events)
    freeze = build_operator_freeze_state(events)

    if (
        metrics_df.empty
        and cap_df.empty
        and exposure_df.empty
        and gate_df.empty
        and not freeze.engaged
        and freeze.last_engaged_at is None
    ):
        st.info(
            "No cross-account risk data yet. Either no global risk policy is "
            "enabled, or no risk gate (cap / kill-switch / freeze / stale) has "
            "fired on the recorded window."
        )
        # The operator-freeze toggle still renders below the info message so an
        # operator can ENGAGE a freeze even on a quiet log (the file-based flag
        # is independent of whether any risk event has fired yet).
        render_operator_freeze_toggle()
        return

    # Interactive operator-freeze toggle (DEBT-068(f-2)). Replaces the f-1
    # read-only indicator: shows the file-based freeze state and lets the
    # operator engage/disengage it with mandatory confirmation.
    render_operator_freeze_toggle()

    if not metrics_df.empty:
        st.caption("Per-sub-account risk metrics")
        st.dataframe(metrics_df, hide_index=True, use_container_width=True)

    if not cap_df.empty:
        st.caption("Portfolio totals vs global caps (band: green<70% / amber / red / breach>100%)")
        st.dataframe(cap_df, hide_index=True, use_container_width=True)

    if not exposure_df.empty:
        st.caption("Cross-account (symbol, side) exposure")
        st.dataframe(exposure_df, hide_index=True, use_container_width=True)

    if not gate_df.empty:
        st.caption("Recent risk-gate events")
        st.dataframe(gate_df, hide_index=True, use_container_width=True)


__all__ = [
    "CROSS_ACCOUNT_RISK_RECENT_LIMIT",
    "CapBand",
    "FreezeTogglePlan",
    "OperatorFreezeState",
    "build_cross_account_risk_dataframe",
    "build_freeze_toggle_plan",
    "build_operator_freeze_state",
    "build_portfolio_cap_utilization",
    "build_risk_gate_events_dataframe",
    "build_symbol_side_exposure_dataframe",
    "kill_switch_state_for_account",
    "render_cross_account_risk",
    "render_operator_freeze_toggle",
]
