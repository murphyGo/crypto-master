"""Trade autopsy dashboard page.

Surfaces closed-trade autopsy evidence from persisted paper/live trade history.

Related Requirements:
- FR-041: Trade quality autopsy
- FR-032 / NFR-003: Streamlit dashboard
"""

from __future__ import annotations

from typing import Literal

import pandas as pd
import streamlit as st

from src.config import get_settings
from src.dashboard.pages.trading import AGGREGATE_SUB_ACCOUNT, discover_sub_account_ids
from src.strategy.performance import TradeHistory, TradeHistoryTracker
from src.strategy.trade_autopsy import TradeAutopsy, TradeAutopsyError
from src.trading.sub_account_registry import DEFAULT_SUB_ACCOUNT_ID

DashboardMode = Literal["paper", "live"]


def build_trade_autopsies(trades: list[TradeHistory]) -> list[TradeAutopsy]:
    """Build autopsy records for closed trades with complete exit evidence."""
    autopsies: list[TradeAutopsy] = []
    for trade in trades:
        try:
            autopsies.append(TradeAutopsy.from_trade_history(trade))
        except TradeAutopsyError:
            continue
    autopsies.sort(key=lambda autopsy: autopsy.exit_time, reverse=True)
    return autopsies


def build_autopsy_dataframe(autopsies: list[TradeAutopsy]) -> pd.DataFrame:
    """Build the trade autopsy summary table."""
    columns = [
        "Trade ID",
        "Symbol",
        "Side",
        "Outcome",
        "P&L",
        "P&L %",
        "Close Reason",
        "Hold (min)",
        "MFE %",
        "MAE %",
        "Sub-account",
        "Exited",
    ]
    if not autopsies:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "Trade ID": autopsy.trade_id[:8],
                "Symbol": autopsy.symbol,
                "Side": autopsy.side.upper(),
                "Outcome": autopsy.outcome.value,
                "P&L": float(autopsy.pnl),
                "P&L %": (
                    round(autopsy.pnl_percent, 4)
                    if autopsy.pnl_percent is not None
                    else None
                ),
                "Close Reason": autopsy.close_reason,
                "Hold (min)": round(autopsy.holding_seconds / 60, 2),
                "MFE %": (
                    round(autopsy.max_favorable_excursion_percent, 4)
                    if autopsy.max_favorable_excursion_percent is not None
                    else None
                ),
                "MAE %": (
                    round(autopsy.max_adverse_excursion_percent, 4)
                    if autopsy.max_adverse_excursion_percent is not None
                    else None
                ),
                "Sub-account": autopsy.sub_account_id,
                "Exited": autopsy.exit_time.isoformat(timespec="seconds"),
            }
            for autopsy in autopsies
        ],
        columns=columns,
    )


def render(
    sub_account_ids: list[str] | None = None,
) -> None:
    """Render the Trade Autopsy page."""
    st.title("Trade Autopsy")
    st.caption("Closed-trade evidence for improvement and operator review.")

    mode_options: tuple[DashboardMode, DashboardMode] = ("paper", "live")
    requested_mode = _query_param_first("mode")
    mode_index = (
        mode_options.index(requested_mode) if requested_mode in mode_options else 0
    )
    mode: DashboardMode = st.radio(
        "Mode",
        options=mode_options,
        index=mode_index,
        horizontal=True,
        format_func=lambda value: value.capitalize(),
    )

    ids = sub_account_ids or discover_sub_account_ids(get_settings().data_dir, mode)
    if not ids:
        ids = [DEFAULT_SUB_ACCOUNT_ID]
    options = [AGGREGATE_SUB_ACCOUNT, *ids] if len(ids) > 1 else ids
    requested_sub_account = _query_param_first("sub_account")
    selected_index = (
        options.index(requested_sub_account) if requested_sub_account in options else 0
    )
    selected_sub_account = st.selectbox(
        "Sub-account",
        options=options,
        index=selected_index,
    )

    trades = _load_trades(
        mode=mode,
        selected_sub_account=str(selected_sub_account),
        sub_account_ids=ids,
    )
    autopsies = build_trade_autopsies(trades)
    requested_symbol = _query_param_first("symbol")
    if requested_symbol:
        autopsies = [
            autopsy for autopsy in autopsies if autopsy.symbol == requested_symbol
        ]

    st.subheader("Closed Trade Autopsies")
    autopsy_df = build_autopsy_dataframe(autopsies)
    if autopsy_df.empty:
        st.info("No closed trade autopsies match the selected scope.")
        return
    st.dataframe(autopsy_df, hide_index=True, use_container_width=True)

    st.subheader("Autopsy Detail")
    options_by_id = {autopsy.trade_id: autopsy for autopsy in autopsies}
    selected_trade_id = st.selectbox(
        "Trade",
        options=list(options_by_id),
        format_func=lambda trade_id: (
            f"{trade_id[:8]} "
            f"({options_by_id[trade_id].symbol} "
            f"{options_by_id[trade_id].outcome.value})"
        ),
    )
    autopsy = options_by_id[selected_trade_id]
    st.markdown(f"**Trade ID:** `{autopsy.trade_id}`")
    st.markdown(f"**Outcome:** {autopsy.outcome.value}")
    st.markdown(f"**Close reason:** {autopsy.close_reason}")
    st.markdown(f"**Evidence:** {'; '.join(autopsy.evidence)}")


def _load_trades(
    *,
    mode: DashboardMode,
    selected_sub_account: str,
    sub_account_ids: list[str],
) -> list[TradeHistory]:
    if selected_sub_account == AGGREGATE_SUB_ACCOUNT:
        trades: list[TradeHistory] = []
        for sub_account_id in sub_account_ids:
            trades.extend(
                TradeHistoryTracker(sub_account_id=sub_account_id).load_trades(
                    mode=mode
                )
            )
        return trades
    return TradeHistoryTracker(sub_account_id=selected_sub_account).load_trades(
        mode=mode
    )


def _query_param_first(name: str) -> str | None:
    raw = st.query_params.get(name)
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


__all__ = [
    "build_autopsy_dataframe",
    "build_trade_autopsies",
    "render",
]
