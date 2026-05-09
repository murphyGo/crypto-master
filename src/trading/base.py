"""Trader protocol — the runtime interface PaperTrader and LiveTrader share.

The runtime engine (``src/runtime/engine.py``) drives both modes through
this protocol so ``main.py`` can select the implementation based on
``Settings.trading_mode`` without the engine knowing or caring which
one it talks to.

State-mutating calls (``open_position`` / ``close_position``) are
async because the live path performs network I/O against an exchange.
The paper path's underlying logic is synchronous; its protocol-conformant
methods just wrap that logic in a trivial ``async def``. Read-only
helpers (``get_open_trades`` / ``check_exit_conditions``) stay
synchronous — they query in-memory state and never touch the network.

Related Requirements:
- FR-009 / FR-010: paper / live mode switching
- NFR-007: Trading history storage (consumed via the protocol)
- NFR-012: Live confirmation (handled internally by ``LiveTrader``)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

from src.models import Position
from src.strategy.performance import TradeHistory

ExitReason = Literal["stop_loss", "take_profit"]


def exit_reason_for_position(
    position: Position,
    current_price: Decimal,
) -> ExitReason | None:
    """Return the SL/TP exit reason for ``position`` at ``current_price``."""
    if position.stop_loss is not None:
        if position.side == "long" and current_price <= position.stop_loss:
            return "stop_loss"
        if position.side == "short" and current_price >= position.stop_loss:
            return "stop_loss"

    if position.take_profit is not None:
        if position.side == "long" and current_price >= position.take_profit:
            return "take_profit"
        if position.side == "short" and current_price <= position.take_profit:
            return "take_profit"

    return None


def exit_condition_for_position(
    position: Position,
    current_price: Decimal,
) -> tuple[bool, ExitReason | None]:
    """Return the shared trader exit-condition tuple."""
    reason = exit_reason_for_position(position, current_price)
    return (reason is not None, reason)


@runtime_checkable
class Trader(Protocol):
    """The trader-side surface ``TradingEngine`` consumes.

    Both ``PaperTrader`` and ``LiveTrader`` implement this protocol.
    The engine never imports either concrete class — only this
    protocol — so swapping implementations at runtime is just a
    constructor argument change in ``src/main.py``.

    Notes on the async/sync split:

    * ``open_position`` / ``close_position`` are ``async`` because the
      live path submits orders over the network and may also call the
      live confirmation callback. The paper path implements them as
      ``async`` wrappers around its existing synchronous logic — there
      is no real I/O cost in paper mode.
    * ``get_open_trades`` / ``check_exit_conditions`` are synchronous
      because both implementations answer them from in-memory state.
      Making them async would be a paper-tax for no live benefit.
    """

    async def open_position(
        self,
        position: Position,
        performance_record_id: str | None = None,
    ) -> TradeHistory:
        """Open a position. Returns the persisted ``TradeHistory``.

        ``LiveTrader`` calls its confirmation callback before the
        order is submitted; ``PaperTrader`` records the simulated
        fill immediately.
        """
        ...

    async def close_position(
        self,
        trade_id: str,
        exit_price: Decimal,
        reason: str = "manual",
    ) -> TradeHistory | None:
        """Close an open position.

        Returns ``None`` if no position with ``trade_id`` is open.
        ``reason`` is stored on the trade record verbatim — common
        values are ``"manual"``, ``"stop_loss"``, ``"take_profit"``.
        """
        ...

    def get_open_trades(self) -> list[TradeHistory]:
        """Return every currently-open trade in this trader's state."""
        ...

    def check_exit_conditions(
        self,
        trade_id: str,
        current_price: Decimal,
    ) -> tuple[bool, str | None]:
        """Decide whether a trade should exit at ``current_price``.

        Returns ``(should_exit, reason)``. ``reason`` is one of
        ``"stop_loss"``, ``"take_profit"``, or ``None`` (when
        ``should_exit`` is False).
        """
        ...

    async def get_balances(self) -> dict[str, Decimal]:
        """Return current per-currency total balances.

        Used by the engine's portfolio-snapshot recorder so the
        dashboard's Trading page can display the current equity. The
        paper path reads its in-memory ledger; the live path queries
        the exchange (network I/O — hence async).
        """
        ...


__all__ = [
    "ExitReason",
    "Trader",
    "exit_condition_for_position",
    "exit_reason_for_position",
]
