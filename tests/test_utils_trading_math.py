"""Unit tests for :mod:`src.utils.trading_math`.

Pins the per-trade PnL convention so that backtester, portfolio, and
paper-trader can all route through a single helper (DEBT-024 / Phase
20.1). Both sign branches are exercised plus the zero-quantity edge
case so that an accidental sign flip is caught at the helper level
before it propagates to the ledger sites.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.utils.trading_math import pnl_for_trade


class TestPnlForTradeLong:
    """Long-side sign and magnitude pinning."""

    def test_long_profit(self) -> None:
        # Entry 100, exit 110, qty 2 -> +20
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=Decimal("2"),
            side="long",
        )
        assert pnl == Decimal("20")

    def test_long_loss(self) -> None:
        # Entry 100, exit 90, qty 2 -> -20
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("90"),
            qty=Decimal("2"),
            side="long",
        )
        assert pnl == Decimal("-20")

    def test_long_no_move(self) -> None:
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("100"),
            qty=Decimal("2"),
            side="long",
        )
        assert pnl == Decimal("0")


class TestPnlForTradeShort:
    """Short-side sign and magnitude pinning."""

    def test_short_profit(self) -> None:
        # Short from 100 to 90, qty 2 -> +20
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("90"),
            qty=Decimal("2"),
            side="short",
        )
        assert pnl == Decimal("20")

    def test_short_loss(self) -> None:
        # Short from 100 to 110, qty 2 -> -20
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=Decimal("2"),
            side="short",
        )
        assert pnl == Decimal("-20")

    def test_short_no_move(self) -> None:
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("100"),
            qty=Decimal("2"),
            side="short",
        )
        assert pnl == Decimal("0")


class TestPnlForTradeEdgeCases:
    """Boundary conditions that must not regress."""

    def test_zero_quantity_long(self) -> None:
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=Decimal("0"),
            side="long",
        )
        assert pnl == Decimal("0")

    def test_zero_quantity_short(self) -> None:
        pnl = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("90"),
            qty=Decimal("0"),
            side="short",
        )
        assert pnl == Decimal("0")

    def test_fractional_decimal_precision(self) -> None:
        # Use values that would lose precision in float math; the
        # Decimal contract is the whole point of the helper.
        pnl = pnl_for_trade(
            entry=Decimal("0.1"),
            exit=Decimal("0.3"),
            qty=Decimal("0.2"),
            side="long",
        )
        assert pnl == Decimal("0.04")

    def test_leverage_is_not_a_parameter(self) -> None:
        # Two callers with different "leverage" assumptions but the
        # same already-levered qty MUST get the same number out.
        # This is the whole point of DEBT-024 / Phase 20.1.
        levered_qty = Decimal("5")  # already includes leverage
        pnl_a = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=levered_qty,
            side="long",
        )
        pnl_b = pnl_for_trade(
            entry=Decimal("100"),
            exit=Decimal("110"),
            qty=levered_qty,
            side="long",
        )
        assert pnl_a == pnl_b == Decimal("50")

    def test_invalid_side_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown trade side"):
            pnl_for_trade(
                entry=Decimal("100"),
                exit=Decimal("110"),
                qty=Decimal("1"),
                side="flat",  # type: ignore[arg-type]
            )
