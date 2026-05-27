"""Closed vocabulary for the proposal-gate ``gate_reason`` discriminator (CAH-13).

The trading engine tags rejected / advisory proposal activity events with a
``details["gate_reason"]`` discriminator naming the gate that fired. That value
is a **closed vocabulary** written in :mod:`src.runtime.engine` and read by
string equality at several consumer sites:

* :mod:`src.runtime.safety_score` (the runtime-pausing kill-switch rollup)
* :mod:`src.dashboard.pages.proposals` (per-gate sample-event bucketing)
* :mod:`src.dashboard.pages.engine_cross_account_risk` (cross-account risk
  panels)

Before this enum the vocabulary lived only as bare string literals on both the
producer and consumer sides — a typo on either side failed silently. This enum
centralizes the vocabulary so producer/consumer drift is a type/test error.

**On-disk contract.** Each member's ``.value`` is byte-identical to the string
historically written to the activity-log JSONL. The JSONL is an append-only
back-compat contract, so the values here MUST NOT change. Producers write
``GateReason.X.value`` and consumers compare against ``GateReason.X.value`` (or
membership in a set of values), keeping the persisted payload unchanged.

This module is a pure leaf (stdlib only) so both the runtime IO/engine layer
and the dashboard read layer can import it without creating a cycle.

Related Requirements:
- FR-014: Proposal Auto-Accept/Reject
- FR-015: Trading History / Runtime Visibility
- FR-042: Operator-facing runtime safety score
"""

from __future__ import annotations

from enum import Enum


class GateReason(str, Enum):
    """The closed set of ``details["gate_reason"]`` discriminator values.

    ``str``-backed so a member compares equal to its raw string and
    serializes to its ``.value`` inside the free-form ``details`` dict —
    keeping the on-disk JSONL byte-identical.
    """

    # Per-proposal risk sizing failure (no fill produced).
    RISK_SIZING = "risk_sizing"

    # Per-account kill switches (``_account_kill_switch_gate``).
    DAILY_LOSS_KILL_SWITCH = "daily_loss_kill_switch"
    OPEN_DRAWDOWN_KILL_SWITCH = "open_drawdown_kill_switch"
    OPEN_STOP_RISK_KILL_SWITCH = "open_stop_risk_kill_switch"

    # Global / portfolio kill switches (``_global_kill_switch_gate``).
    PORTFOLIO_KILL_SWITCH = "portfolio_kill_switch"
    PORTFOLIO_DAILY_LOSS_KILL_SWITCH = "portfolio_daily_loss_kill_switch"

    # Position-count / notional caps.
    TOTAL_CAP = "total_cap"
    SYMBOL_CAP = "symbol_cap"
    ACCOUNT_AGGREGATE_CAP = "account_aggregate_cap"
    GLOBAL_CAP = "global_cap"

    # Stale-position entry block.
    STALE_POSITION_BLOCK = "stale_position_block"

    # Sibling-family dedup.
    SIBLING_FAMILY_DEDUP = "sibling_family_dedup"

    # Runtime safety pause.
    RUNTIME_SAFETY_PAUSED = "runtime_safety_paused"

    # Trend filter.
    TREND_FILTER_BLOCKED = "trend_filter_blocked"

    # Market-regime gate.
    MARKET_REGIME_BLOCKED = "market_regime_blocked"

    # Strategy-action gate (shadow records the proposal; pause rejects it).
    STRATEGY_ACTION_SHADOW = "strategy_action_shadow"
    STRATEGY_ACTION_PAUSE = "strategy_action_pause"

    # Correlation governor hard-block.
    CORRELATION_BLOCKED = "correlation_blocked"

    # Stale quote with no live data to revalidate against.
    STALE_QUOTE_NO_LIVE_DATA = "stale_quote_no_live_data"

    # Operator manual freeze (DEBT-068(d)). Carried on the per-proposal
    # rejection detail; consumed by the cross-account-risk panel's
    # risk-gate set. (The freeze rejection detail uses the ``reason`` key,
    # but the value belongs to this same closed vocabulary.)
    OPERATOR_FREEZE = "operator_freeze"


__all__ = ["GateReason"]
