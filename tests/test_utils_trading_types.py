"""Unit tests for :mod:`src.utils.trading_types` order-side helpers.

Pins the position-side -> exchange-order-side mapping that was previously
hand-inlined as a ternary at 4 call sites (CAH-02). A flipped closing-side
ternary would submit a wrong-direction live order, so both helpers are
exercised exhaustively across the closed ``long``/``short`` vocabulary to
catch an accidental inversion at the helper level.
"""

from __future__ import annotations

from src.utils.trading_types import closing_order_side, entry_order_side


def test_entry_order_side_long_buys() -> None:
    assert entry_order_side("long") == "buy"


def test_entry_order_side_short_sells() -> None:
    assert entry_order_side("short") == "sell"


def test_closing_order_side_long_sells() -> None:
    assert closing_order_side("long") == "sell"


def test_closing_order_side_short_buys() -> None:
    assert closing_order_side("short") == "buy"


def test_close_is_inverse_of_entry() -> None:
    # Closing must be the exact inverse of entry for every side.
    for side in ("long", "short"):
        assert closing_order_side(side) != entry_order_side(side)
