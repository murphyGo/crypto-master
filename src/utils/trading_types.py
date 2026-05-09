"""Shared trading vocabulary types."""

from __future__ import annotations

from typing import Literal

TradeSide = Literal["long", "short"]
PositionSide = TradeSide
SignalSide = Literal["long", "short", "neutral"]
OrderSide = Literal["buy", "sell"]

__all__ = ["OrderSide", "PositionSide", "SignalSide", "TradeSide"]
