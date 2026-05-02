"""Trading status page (Phase 7.3).

Surfaces three things for paper or live mode:

* Active positions (FR-029) — what's currently open.
* Recent trade history — most-recent-first table of closed + open trades.
* Asset & PnL summary + equity curve (FR-031) — totals and chart.

Everything is read from on-disk state (`TradeHistoryTracker` and
`PortfolioTracker` snapshots). The page does not call exchanges or
compute live unrealized P&L — that requires fresh prices and is not a
chassis concern. Operators driving paper/live trading already record
snapshots regularly via the trader components, so the equity curve
reflects state up to the most recent snapshot.

Related Requirements:
- FR-029: Active Trading
- FR-031: Asset and Performance Summary
- NFR-007: Trading History Storage (consumed)
- NFR-008: Asset/PnL History (consumed)
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypedDict

import pandas as pd
import streamlit as st

from src.config import get_settings
from src.logger import get_logger
from src.proposal.interaction import ProposalHistory
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.trading.portfolio import AssetSnapshot, PortfolioTracker
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID

logger = get_logger("crypto_master.dashboard.trading")

DashboardMode = Literal["paper", "live"]
DEFAULT_HISTORY_LIMIT = 25
AGGREGATE_SUB_ACCOUNT = "Aggregate"

# Phase 15.1: matches the threshold-gate rejection reason emitted by
# ``src.runtime.engine.RuntimeEngine._auto_decide`` —
# ``f"composite {composite:.4f} below threshold {threshold:.4f}"``.
# The cap-rejection reason (Phase 12.1) starts with "symbol " and is a
# different cause, so it must not match this pattern.
_THRESHOLD_REJECTION_PATTERN = re.compile(
    r"^composite \d+\.\d+ below threshold \d+\.\d+$"
)


class TradingSummaryMetrics(TypedDict):
    """Headline numbers for the Trading page summary cards (DEBT-011).

    Typed return shape for ``build_summary_metrics`` so consumer
    sites pick the right type at each access without ``cast(...)``.
    """

    open_positions: int
    closed_trades: int
    win_rate: float
    realized_pnl: float
    unrealized_pnl: float
    latest_equity: float
    latest_snapshot_at: datetime | None
    quote_currency: str
    proposals_rejected_threshold_count: int


# =============================================================================
# Pure helpers (importable + testable without Streamlit runtime)
# =============================================================================


def build_open_positions_dataframe(trades: list[TradeHistory]) -> pd.DataFrame:
    """Build the open-positions table (FR-029).

    Only ``status == "open"`` trades. Sorted by entry time, most
    recent first, so the operator sees the freshest activity.

    Args:
        trades: Raw trade list (any status); only open trades are kept.

    Returns:
        DataFrame with one row per open position. Empty if nothing is open.
    """
    rows: list[dict[str, object]] = []
    for trade in trades:
        if trade.status != "open":
            continue
        rows.append(
            {
                "Trade ID": trade.id[:8],
                "Symbol": trade.symbol,
                "Side": trade.side.upper(),
                "Quantity": float(trade.entry_quantity),
                "Entry Price": float(trade.entry_price),
                "Leverage": f"{trade.leverage}x",
                "Entry Time": trade.entry_time,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "Trade ID",
                "Symbol",
                "Side",
                "Quantity",
                "Entry Price",
                "Leverage",
                "Entry Time",
            ]
        )
    df = pd.DataFrame(rows).sort_values("Entry Time", ascending=False)
    return df.reset_index(drop=True)


def build_trade_history_dataframe(
    trades: list[TradeHistory],
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> pd.DataFrame:
    """Build the recent-trades table.

    Sorted by close time (closed trades) or entry time (open trades),
    most recent first. Open trades show "—" in the exit columns. Empty
    DataFrames keep their declared columns so the caller can render an
    empty table without conditional schemas.

    Args:
        trades: Raw trade list, any status.
        limit: Max rows returned.

    Returns:
        DataFrame with one row per trade.
    """
    columns = [
        "Trade ID",
        "Symbol",
        "Side",
        "Status",
        "Entry Price",
        "Exit Price",
        "P&L %",
        "Close Reason",
        "When",
    ]
    if not trades:
        return pd.DataFrame(columns=columns)

    def _when(t: TradeHistory) -> datetime:
        return t.exit_time or t.entry_time

    sorted_trades = sorted(trades, key=_when, reverse=True)[:limit]

    rows = []
    for trade in sorted_trades:
        rows.append(
            {
                "Trade ID": trade.id[:8],
                "Symbol": trade.symbol,
                "Side": trade.side.upper(),
                "Status": trade.status,
                "Entry Price": float(trade.entry_price),
                "Exit Price": (
                    float(trade.exit_price) if trade.exit_price is not None else None
                ),
                "P&L %": (
                    round(trade.pnl_percent, 2)
                    if trade.pnl_percent is not None
                    else None
                ),
                "Close Reason": trade.close_reason or "—",
                "When": _when(trade),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def build_equity_curve_dataframe(
    curve: list[tuple[datetime, Decimal]],
) -> pd.DataFrame:
    """Time-indexed equity curve from ``PortfolioTracker.get_equity_curve``.

    Args:
        curve: Raw ``(timestamp, equity)`` tuples.

    Returns:
        DataFrame with ``timestamp`` and ``equity`` columns sorted
        ascending. Empty DataFrame if ``curve`` is empty.
    """
    if not curve:
        return pd.DataFrame(columns=["timestamp", "equity"])
    df = pd.DataFrame([{"timestamp": ts, "equity": float(eq)} for ts, eq in curve])
    return df.sort_values("timestamp").reset_index(drop=True)


def build_comparative_equity_dataframe(
    curves_by_sub_account: dict[str, list[tuple[datetime, Decimal]]],
) -> pd.DataFrame:
    """Build a wide equity table with one column per sub-account."""
    frames: list[pd.DataFrame] = []
    for sub_account_id, curve in curves_by_sub_account.items():
        df = build_equity_curve_dataframe(curve)
        if df.empty:
            continue
        frames.append(
            df.rename(columns={"equity": sub_account_id}).set_index("timestamp")
        )
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index()


def discover_sub_account_ids(data_dir: Path, mode: DashboardMode) -> list[str]:
    """Discover sub-account ids from persisted trade / portfolio paths."""
    found: set[str] = set()
    for base in (
        data_dir / "trades" / mode,
        data_dir / "portfolio" / mode,
    ):
        if not base.exists():
            continue
        found.update(p.name for p in base.iterdir() if p.is_dir())
    ordered = sorted(found - {DEFAULT_SUB_ACCOUNT_ID})
    return [DEFAULT_SUB_ACCOUNT_ID, *ordered]


def build_summary_metrics(
    trades: list[TradeHistory],
    snapshots: list[AssetSnapshot],
    proposal_history: ProposalHistory | None = None,
) -> TradingSummaryMetrics:
    """Aggregate key headline numbers for the summary cards.

    Computed from on-disk state only — no live prices, no exchange
    calls. ``latest_equity`` and ``unrealized_pnl`` reflect the most
    recent recorded snapshot, which may be stale relative to live
    market prices; the summary card warns the operator of this.

    Args:
        trades: All trades for the selected mode.
        snapshots: All asset snapshots for the selected mode.
        proposal_history: Source of proposal records used to count
            threshold-gated rejections (Phase 15.1). Defaults to
            ``ProposalHistory()`` so callers don't need to wire it up.
            An empty / missing directory yields a count of ``0``.

    Returns:
        Dict with keys: ``open_positions``, ``closed_trades``,
        ``win_rate`` (float in [0, 1]), ``realized_pnl``,
        ``unrealized_pnl``, ``latest_equity``, ``latest_snapshot_at``,
        ``proposals_rejected_threshold_count``. Numeric values are
        floats so the dashboard can format them with `:.2f` etc;
        tests assert on the raw numbers.
    """
    open_count = sum(1 for t in trades if t.status == "open")
    closed = [t for t in trades if t.status == "closed"]
    closed_count = len(closed)

    wins = sum(1 for t in closed if t.pnl_percent is not None and t.pnl_percent > 0)
    win_rate = wins / closed_count if closed_count else 0.0

    realized_pnl = sum(
        (float(t.pnl) for t in closed if t.pnl is not None),
        0.0,
    )

    if snapshots:
        latest = max(snapshots, key=lambda s: s.timestamp)
        latest_equity = float(latest.total_equity)
        latest_unrealized = float(latest.unrealized_pnl)
        latest_at: datetime | None = latest.timestamp
        latest_quote = latest.quote_currency
    else:
        latest_equity = 0.0
        latest_unrealized = 0.0
        latest_at = None
        latest_quote = "USDT"

    threshold_rejection_count = _count_threshold_rejections(
        proposal_history if proposal_history is not None else ProposalHistory()
    )

    return {
        "open_positions": open_count,
        "closed_trades": closed_count,
        "win_rate": win_rate,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": latest_unrealized,
        "latest_equity": latest_equity,
        "latest_snapshot_at": latest_at,
        "quote_currency": latest_quote,
        "proposals_rejected_threshold_count": threshold_rejection_count,
    }


def _count_threshold_rejections(history: ProposalHistory) -> int:
    """Count proposal records rejected by the composite-threshold gate.

    Phase 15.1: only the threshold-gate pattern from
    ``RuntimeEngine._auto_decide`` is counted. Cap-rejected records
    (Phase 12.1, reason starts with ``"symbol "``) are a different
    cause and are excluded so the metric stays interpretable.
    """
    try:
        records = history.list_all()
    except Exception:  # pragma: no cover - defensive
        # Backward-compat: a malformed proposals dir must not crash
        # the whole Trading page render.
        logger.warning("Failed to list proposal history; counting 0 rejections")
        return 0

    count = 0
    for record in records:
        if record.decision != "rejected":
            continue
        reason = record.rejection_reason
        if reason is None:
            continue
        if _THRESHOLD_REJECTION_PATTERN.match(reason):
            count += 1
    return count


# =============================================================================
# Streamlit render
# =============================================================================


def render(
    trade_tracker: TradeHistoryTracker | None = None,
    portfolio_tracker: PortfolioTracker | None = None,
    proposal_history: ProposalHistory | None = None,
    sub_account_ids: list[str] | None = None,
) -> None:
    """Render the Trading page.

    Args:
        trade_tracker: Override the trade source. Defaults to
            ``TradeHistoryTracker()``.
        portfolio_tracker: Override the snapshot source. Defaults to
            ``PortfolioTracker()``.
        proposal_history: Override the proposal-history source used
            for the threshold-rejection summary card (Phase 15.1).
            Defaults to ``ProposalHistory()``.
        sub_account_ids: Optional active sub-account ids for tests or
            dashboard wiring. When omitted, ids are discovered from
            persisted trade / portfolio directories.
    """
    st.title("💹 Trading")
    st.caption("Active positions, recent trade history, and equity curve.")

    mode: DashboardMode = st.radio(
        "Mode",
        options=("paper", "live"),
        horizontal=True,
        format_func=lambda v: v.capitalize(),
    )

    ids = sub_account_ids or discover_sub_account_ids(get_settings().data_dir, mode)
    if not ids:
        ids = [DEFAULT_SUB_ACCOUNT_ID]
    options = [AGGREGATE_SUB_ACCOUNT, *ids] if len(ids) > 1 else ids
    selected_sub_account = st.selectbox(
        "Sub-account",
        options=options,
        index=0,
    )

    history_t = proposal_history or ProposalHistory()

    if selected_sub_account == AGGREGATE_SUB_ACCOUNT:
        trades = []
        snapshots = []
        for sub_account_id in ids:
            tracker = TradeHistoryTracker(sub_account_id=sub_account_id)
            portfolio_for_sub = PortfolioTracker(
                trade_tracker=tracker,
                sub_account_id=sub_account_id,
            )
            trades.extend(tracker.load_trades(mode=mode))
            snapshots.extend(portfolio_for_sub.load_snapshots(mode))
        trades_t = TradeHistoryTracker(sub_account_id=DEFAULT_SUB_ACCOUNT_ID)
        portfolio_t = PortfolioTracker(
            trade_tracker=trades_t,
            sub_account_id=DEFAULT_SUB_ACCOUNT_ID,
        )
    else:
        selected_id = str(selected_sub_account)
        trades_t = trade_tracker or TradeHistoryTracker(sub_account_id=selected_id)
        portfolio_t = portfolio_tracker or PortfolioTracker(
            trade_tracker=trades_t,
            sub_account_id=selected_id,
        )
        trades = trades_t.load_trades(mode=mode)
        snapshots = portfolio_t.load_snapshots(mode)
    metrics = build_summary_metrics(trades, snapshots, history_t)

    # ---- Summary cards ----
    st.subheader("Summary")
    latest_at = metrics["latest_snapshot_at"]
    equity_value = metrics["latest_equity"]
    unrealized = metrics["unrealized_pnl"]
    equity_label = (
        f"{equity_value:.2f} {metrics['quote_currency']}"
        if latest_at is not None
        else "—"
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Current Equity",
        equity_label,
        delta=(f"{unrealized:+.2f} unrealized" if latest_at is not None else None),
    )
    c2.metric("Open Positions", metrics["open_positions"])
    c3.metric("Closed Trades", metrics["closed_trades"])
    c4.metric("Win Rate", f"{metrics['win_rate'] * 100:.1f}%")
    c5.metric("Realized P&L", f"{metrics['realized_pnl']:.2f}")

    if latest_at is not None:
        st.caption(f"Snapshot {latest_at.isoformat(timespec='seconds')}")
    else:
        st.caption(
            "No portfolio snapshots recorded yet for this mode. "
            "The trading engine records one at the end of every cycle once "
            "wired with `PortfolioTracker`."
        )

    # ---- Active positions ----
    st.subheader("Active Positions")
    pos_col, rej_col = st.columns([3, 1])
    open_df = build_open_positions_dataframe(trades)
    with pos_col:
        if open_df.empty:
            st.info("No open positions.")
        else:
            st.dataframe(open_df, hide_index=True, use_container_width=True)
    # Phase 15.1: surfaces *why* the table can be empty —
    # threshold-gated rejections are working-as-designed, not a bug.
    rej_col.metric(
        "Proposals rejected (threshold)",
        metrics["proposals_rejected_threshold_count"],
    )

    # ---- Recent trade history ----
    st.subheader("Recent Trade History")
    history_df = build_trade_history_dataframe(trades)
    if history_df.empty:
        st.info("No trade history for this mode yet.")
    else:
        st.dataframe(history_df, hide_index=True, use_container_width=True)

    # ---- Equity curve ----
    st.subheader("Equity Curve")
    if selected_sub_account == AGGREGATE_SUB_ACCOUNT:
        curves = {
            sub_account_id: PortfolioTracker(
                trade_tracker=TradeHistoryTracker(sub_account_id=sub_account_id),
                sub_account_id=sub_account_id,
            ).get_equity_curve(mode)
            for sub_account_id in ids
        }
        curve_df = build_comparative_equity_dataframe(curves)
    else:
        curve = portfolio_t.get_equity_curve(mode)
        curve_df = build_equity_curve_dataframe(curve)
    if curve_df.empty:
        st.info(
            "No equity history yet. Once snapshots accumulate the "
            "curve will populate here."
        )
    else:
        chart_data = (
            curve_df.set_index("timestamp")[["equity"]]
            if "timestamp" in curve_df.columns
            else curve_df
        )
        st.line_chart(chart_data, use_container_width=True)


__all__ = [
    "TradingSummaryMetrics",
    "build_comparative_equity_dataframe",
    "build_equity_curve_dataframe",
    "build_open_positions_dataframe",
    "build_summary_metrics",
    "build_trade_history_dataframe",
    "discover_sub_account_ids",
    "render",
]
