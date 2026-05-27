"""Shared trading vocabulary types."""

from __future__ import annotations

from typing import Literal

TradeSide = Literal["long", "short"]
PositionSide = TradeSide
SignalSide = Literal["long", "short", "neutral"]
OrderSide = Literal["buy", "sell"]


def entry_order_side(side: PositionSide) -> OrderSide:
    """Return the exchange order side that *opens* a position.

    A long position is entered by buying; a short by selling.
    """
    return "buy" if side == "long" else "sell"


def closing_order_side(side: PositionSide) -> OrderSide:
    """Return the exchange order side that *closes* a position.

    Closing is the inverse of entry: a long is closed by selling, a short
    by buying. Centralising this avoids a hand-inlined ternary that, if
    flipped, would submit a wrong-direction order (CAH-02).
    """
    return "sell" if side == "long" else "buy"


__all__ = [
    "OrderSide",
    "PositionSide",
    "SignalSide",
    "TradeSide",
    "closing_order_side",
    "entry_order_side",
]
