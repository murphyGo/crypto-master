"""Portfolio management and P&L aggregation.

Provides a mode-separated view of account state by combining caller-
supplied balances with trade history from ``TradeHistoryTracker``.
Snapshots are persisted under ``data/portfolio/{mode}/snapshots.json``
so the dashboard can render equity curves per mode.

Related Requirements:
- FR-009: Live Trading Mode
- FR-010: Paper Trading Mode
- NFR-007: Trading History Storage
- NFR-008: Asset/PnL History (mode separation)
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.config import get_settings
from src.logger import get_logger
from src.strategy.performance import TradeHistoryTracker

logger = get_logger("crypto_master.trading.portfolio")


Mode = Literal["backtest", "paper", "live"]

DEFAULT_PORTFOLIO_DIR = Path("data/portfolio")


def _coerce_decimal(value: str | int | float | Decimal) -> Decimal:
    """Convert a numeric or string value to Decimal."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class AssetSnapshot(BaseModel):
    """Point-in-time snapshot of portfolio state for a mode.

    A snapshot captures what the account looked like at a specific
    moment: balances held, cumulative realized P&L, and unrealized
    P&L from open positions at that moment's prices.

    Attributes:
        timestamp: When the snapshot was taken.
        mode: Trading mode (backtest/paper/live).
        quote_currency: The currency used as the equity denomination.
        balances: Currency -> total amount held.
        realized_pnl: Cumulative realized P&L up to ``timestamp``
            (sum of closed-trade P&L in this mode).
        unrealized_pnl: Unrealized P&L of open positions at the
            snapshot's reference prices.
    """

    timestamp: datetime = Field(default_factory=datetime.now)
    mode: Mode
    quote_currency: str
    balances: dict[str, Decimal] = Field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")

    model_config = {"validate_assignment": True}

    @field_validator("balances", mode="before")
    @classmethod
    def coerce_balances(
        cls, v: dict[str, str | int | float | Decimal] | None
    ) -> dict[str, Decimal]:
        """Coerce balance values to Decimal."""
        if v is None:
            return {}
        return {k: _coerce_decimal(val) for k, val in v.items()}

    @field_validator("realized_pnl", "unrealized_pnl", mode="before")
    @classmethod
    def coerce_pnl(cls, v: str | int | float | Decimal) -> Decimal:
        """Coerce P&L values to Decimal."""
        return _coerce_decimal(v)

    @property
    def quote_balance(self) -> Decimal:
        """Balance held in the quote currency."""
        return self.balances.get(self.quote_currency, Decimal("0"))

    @property
    def total_equity(self) -> Decimal:
        """Quote balance plus unrealized P&L from open positions."""
        return self.quote_balance + self.unrealized_pnl

    @property
    def total_pnl(self) -> Decimal:
        """Realized + unrealized P&L."""
        return self.realized_pnl + self.unrealized_pnl


class Portfolio(BaseModel):
    """Live view of portfolio state for a mode (not persisted).

    Returned by :meth:`PortfolioTracker.get_portfolio` as a snapshot
    computed from caller-supplied balances and current prices,
    enriched with position counts from the trade tracker.

    Attributes:
        mode: Trading mode.
        quote_currency: Currency used for equity denomination.
        balances: Currency -> total amount held.
        realized_pnl: Cumulative realized P&L from closed trades.
        unrealized_pnl: P&L of open positions at current prices.
        open_positions_count: Number of open trades in this mode.
        closed_trades_count: Number of closed trades in this mode.
    """

    mode: Mode
    quote_currency: str
    balances: dict[str, Decimal]
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    open_positions_count: int
    closed_trades_count: int

    @property
    def quote_balance(self) -> Decimal:
        """Balance held in the quote currency."""
        return self.balances.get(self.quote_currency, Decimal("0"))

    @property
    def total_equity(self) -> Decimal:
        """Quote balance plus unrealized P&L from open positions."""
        return self.quote_balance + self.unrealized_pnl

    @property
    def total_pnl(self) -> Decimal:
        """Realized + unrealized P&L."""
        return self.realized_pnl + self.unrealized_pnl


class PortfolioTracker:
    """Aggregates balances and trade-derived P&L per mode, with persistence.

    PortfolioTracker is stateless with respect to balances — the
    caller supplies them on every call. This keeps the tracker
    decoupled from both ``PaperTrader`` and ``LiveTrader`` while
    still letting it own the snapshot history (``data/portfolio/``)
    and P&L roll-ups (via ``TradeHistoryTracker``).

    Related Requirements:
    - NFR-007: Trading History Storage (reads from TradeHistoryTracker)
    - NFR-008: Asset/PnL History (mode-separated snapshots)

    Attributes:
        data_dir: Directory for portfolio snapshot storage.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        trade_tracker: TradeHistoryTracker | None = None,
    ) -> None:
        """Initialize PortfolioTracker.

        Args:
            data_dir: Root directory for snapshot storage. Defaults to
                ``data/portfolio/`` resolved via ``get_settings()``.
            trade_tracker: Optional TradeHistoryTracker for P&L
                calculation. If omitted, one is constructed using
                the same settings-derived data root.
        """
        if data_dir is None:
            settings = get_settings()
            self.data_dir = settings.data_dir / "portfolio"
        else:
            self.data_dir = data_dir

        self._trade_tracker = trade_tracker or TradeHistoryTracker()

    def _get_mode_dir(self, mode: Mode) -> Path:
        """Get (and create) the directory for a mode's snapshots."""
        mode_dir = self.data_dir / mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        return mode_dir

    def _get_snapshots_path(self, mode: Mode) -> Path:
        """Path to the snapshots file for a mode."""
        return self._get_mode_dir(mode) / "snapshots.json"

    def calculate_realized_pnl(self, mode: Mode) -> Decimal:
        """Sum realized P&L across all closed trades in a mode.

        Args:
            mode: Trading mode filter.

        Returns:
            Cumulative realized P&L as Decimal (0 if no trades).
        """
        trades = self._trade_tracker.load_trades(mode=mode)
        total = Decimal("0")
        for trade in trades:
            if trade.status == "closed" and trade.pnl is not None:
                total += trade.pnl
        return total

    def calculate_unrealized_pnl(
        self,
        mode: Mode,
        current_prices: dict[str, Decimal],
    ) -> Decimal:
        """Sum unrealized P&L for open trades at given prices.

        Open trades whose symbol is not in ``current_prices`` are
        skipped (treated as having zero mark-to-market contribution)
        so a stale price feed doesn't zero out the entire portfolio.

        Args:
            mode: Trading mode filter.
            current_prices: symbol -> current price map.

        Returns:
            Total unrealized P&L (leverage-adjusted, fees not
            subtracted since fees are charged on close).
        """
        open_trades = self._trade_tracker.get_open_trades(mode=mode)
        total = Decimal("0")

        for trade in open_trades:
            price = current_prices.get(trade.symbol)
            if price is None:
                continue

            entry = trade.entry_price
            qty = trade.entry_quantity
            leverage = Decimal(trade.leverage)

            if trade.side == "long":
                total += (price - entry) * qty * leverage
            else:
                total += (entry - price) * qty * leverage

        return total

    def get_portfolio(
        self,
        mode: Mode,
        quote_currency: str,
        balances: dict[str, Decimal],
        current_prices: dict[str, Decimal] | None = None,
    ) -> Portfolio:
        """Build a live Portfolio view for a mode.

        Args:
            mode: Trading mode.
            quote_currency: Currency used for equity denomination.
            balances: Current balances supplied by the caller.
            current_prices: Optional symbol -> price map for
                unrealized P&L. If None, unrealized P&L is 0.

        Returns:
            A Portfolio populated with P&L aggregates and counts.
        """
        prices = current_prices or {}
        realized = self.calculate_realized_pnl(mode)
        unrealized = self.calculate_unrealized_pnl(mode, prices)

        trades = self._trade_tracker.load_trades(mode=mode)
        open_count = sum(1 for t in trades if t.status == "open")
        closed_count = sum(1 for t in trades if t.status == "closed")

        return Portfolio(
            mode=mode,
            quote_currency=quote_currency,
            balances=dict(balances),
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            open_positions_count=open_count,
            closed_trades_count=closed_count,
        )

    def record_snapshot(
        self,
        mode: Mode,
        quote_currency: str,
        balances: dict[str, Decimal],
        current_prices: dict[str, Decimal] | None = None,
    ) -> AssetSnapshot:
        """Build a snapshot, persist it, and return it.

        Args:
            mode: Trading mode.
            quote_currency: Currency used for equity denomination.
            balances: Balances to record.
            current_prices: Optional prices for unrealized P&L.

        Returns:
            The persisted AssetSnapshot.
        """
        prices = current_prices or {}
        realized = self.calculate_realized_pnl(mode)
        unrealized = self.calculate_unrealized_pnl(mode, prices)

        snapshot = AssetSnapshot(
            mode=mode,
            quote_currency=quote_currency,
            balances=dict(balances),
            realized_pnl=realized,
            unrealized_pnl=unrealized,
        )

        snapshots = self.load_snapshots(mode)
        snapshots.append(snapshot)
        self._save_snapshots(mode, snapshots)

        logger.info(
            f"Recorded {mode} snapshot @ {snapshot.timestamp.isoformat()}: "
            f"equity={snapshot.total_equity} {quote_currency}, "
            f"realized={realized}, unrealized={unrealized}"
        )
        return snapshot

    def load_snapshots(
        self,
        mode: Mode,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[AssetSnapshot]:
        """Load snapshots for a mode, optionally filtered by date.

        Args:
            mode: Trading mode.
            start: Inclusive lower bound on snapshot timestamp.
            end: Inclusive upper bound on snapshot timestamp.

        Returns:
            List of AssetSnapshots sorted by storage order.
        """
        snapshots_path = self._get_snapshots_path(mode)
        if not snapshots_path.exists():
            return []

        try:
            with open(snapshots_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                f"Failed to load snapshots from {snapshots_path}: {e}"
            )
            return []

        snapshots = [AssetSnapshot(**item) for item in data]

        if start is not None or end is not None:
            snapshots = [
                s
                for s in snapshots
                if (start is None or s.timestamp >= start)
                and (end is None or s.timestamp <= end)
            ]

        return snapshots

    def _save_snapshots(
        self, mode: Mode, snapshots: list[AssetSnapshot]
    ) -> None:
        """Write snapshots to the mode's storage file."""
        snapshots_path = self._get_snapshots_path(mode)
        data = [self._snapshot_to_dict(s) for s in snapshots]
        with open(snapshots_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def _snapshot_to_dict(snapshot: AssetSnapshot) -> dict:
        """Convert a snapshot to a JSON-serializable dict.

        Converts Decimals to strings and datetime to ISO format for
        stable round-trip serialization.
        """
        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "mode": snapshot.mode,
            "quote_currency": snapshot.quote_currency,
            "balances": {k: str(v) for k, v in snapshot.balances.items()},
            "realized_pnl": str(snapshot.realized_pnl),
            "unrealized_pnl": str(snapshot.unrealized_pnl),
        }

    def get_equity_curve(
        self,
        mode: Mode,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[tuple[datetime, Decimal]]:
        """Return (timestamp, total_equity) points for a mode.

        Args:
            mode: Trading mode.
            start: Optional inclusive start filter.
            end: Optional inclusive end filter.

        Returns:
            List of (timestamp, equity) tuples in storage order.
        """
        snapshots = self.load_snapshots(mode, start, end)
        return [(s.timestamp, s.total_equity) for s in snapshots]

    def delete_snapshots(self, mode: Mode) -> bool:
        """Delete all snapshots for a mode.

        Args:
            mode: Trading mode.

        Returns:
            True if a directory was removed, False if nothing existed.
        """
        mode_dir = self.data_dir / mode
        if not mode_dir.exists():
            return False
        shutil.rmtree(mode_dir)
        logger.info(f"Deleted portfolio snapshots for mode: {mode}")
        return True
