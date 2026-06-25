"""Tests for DEBT-072: paper balance lock/unlock accounting drift repair.

The ledger invariant for paper trading is::

    balance.locked == Σ(open_pos.margin for open trades)

DEBT-072 was a fleet-wide violation of that invariant: a persisted
``balances.json`` snapshot (DEBT-059 path) whose ``locked`` was short some
open margins caused a restart to inherit the drift — ``_open_positions``
carried the full margin (so ``close_position`` tried to ``unlock(margin)``)
but ``locked`` did not, so :meth:`PaperBalance.unlock` raised and the
runtime cycle errored.

These tests pin the fix:

1. Tolerant ``unlock`` for provable tiny float residuals (still raises on a
   structural overshoot beyond EPS).
2. Unconditional restart reconcile of the free/locked split from the
   authoritative ``_open_positions`` margins — in BOTH the snapshot and the
   legacy no-snapshot cases.
3. DEBT-059 (snapshot total preserved) and DEBT-027 (free may go negative)
   are preserved by the reconcile.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.models import Position
from src.runtime.activity_log import ActivityEventType, ActivityLog
from src.strategy.performance import TradeHistoryTracker
from src.trading.paper import (
    EPS,
    PaperBalance,
    PaperTrader,
    PaperTradingError,
)


def _write_balances_snapshot(
    tmp_path: Path,
    *,
    sub_account_id: str = "default",
    balances: dict[str, dict[str, str]],
) -> Path:
    """Write a ``balances.json`` snapshot the way ``_save_balances`` does.

    The snapshot lives at ``<data_dir>/paper/<sub_account_id>/balances.json``
    keyed by currency with ``currency`` / ``free`` / ``locked`` strings.
    """
    balances_dir = tmp_path / "paper" / sub_account_id
    balances_dir.mkdir(parents=True, exist_ok=True)
    path = balances_dir / "balances.json"
    path.write_text(json.dumps(balances, indent=2), encoding="utf-8")
    return path


def _seed_open_trade(
    tmp_path: Path,
    *,
    sub_account_id: str = "default",
    symbol: str = "BTC/USDT",
    side: str = "long",
    entry_price: Decimal = Decimal("50000"),
    quantity: Decimal = Decimal("0.1"),
    leverage: int = 10,
    stop_loss: Decimal | None = Decimal("49000"),
    take_profit: Decimal | None = Decimal("52000"),
) -> str:
    """Persist a single open paper trade row; return its id.

    Goes through ``TradeHistoryTracker`` so the on-disk ``trades.json``
    layout matches production exactly without hand-rolling the schema.
    """
    tracker = TradeHistoryTracker(data_dir=tmp_path, sub_account_id=sub_account_id)
    trade = tracker.open_trade(
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        entry_price=entry_price,
        entry_quantity=quantity,
        mode="paper",
        leverage=leverage,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    return trade.id


# =============================================================================
# Test 1 — tolerant unlock for tiny float residuals
# =============================================================================


class TestTolerantUnlock:
    """DEBT-072 change 1: clamp provable sub-EPS residuals, raise beyond."""

    async def test_unlock_tiny_residual_clamps_without_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """An overshoot within EPS releases all locked and warns."""
        import logging

        locked = Decimal("711.0496810523400424872483206")
        balance = PaperBalance(currency="USDT", free=Decimal("0"), locked=locked)

        # A close recomputes a hair more than was locked (sub-1E-24 tail).
        overshoot_amount = Decimal("711.0496810523400424872483210")
        assert overshoot_amount > locked
        assert overshoot_amount - locked <= EPS

        target_logger = logging.getLogger("crypto_master.trading.paper")
        target_logger.addHandler(caplog.handler)
        target_logger.setLevel(logging.WARNING)
        try:
            balance.unlock(overshoot_amount)
        finally:
            target_logger.removeHandler(caplog.handler)

        assert balance.locked == Decimal("0")
        assert balance.free == locked
        assert any(
            "Tolerating tiny unlock residual" in rec.getMessage()
            for rec in caplog.records
        )

    async def test_unlock_structural_overshoot_still_raises(self) -> None:
        """An overshoot beyond EPS must surface, not be masked."""
        locked = Decimal("711.0496810523400424872483206")
        balance = PaperBalance(currency="USDT", free=Decimal("0"), locked=locked)

        with pytest.raises(PaperTradingError, match="Cannot unlock"):
            balance.unlock(locked + Decimal("0.01"))

        # Balance untouched by the failed unlock.
        assert balance.locked == locked
        assert balance.free == Decimal("0")


# =============================================================================
# Test 2 — DEBT-072 repro: snapshot locked short a full margin
# =============================================================================


class TestRestartReconcileRepro:
    """DEBT-072 change 3: heal a snapshot whose locked is short a margin."""

    async def test_short_snapshot_repaired_on_init_and_closes_clean(
        self, tmp_path: Path
    ) -> None:
        """Snapshot ``locked`` short by a full margin → init repairs it.

        Mirrors the Fly repro: ``_open_positions`` carries the margin but
        the snapshot ``locked`` dropped it, so without the fix the later
        ``close_position`` would raise. After init the invariant holds and
        the close runs clean.
        """
        activity_log = ActivityLog(path=tmp_path / "activity.jsonl")

        # One open trade: notional 50000 * 0.1 = 5000, leverage 10 → margin 500.
        trade_id = _seed_open_trade(tmp_path)

        # Snapshot inherited the drift: total equity is right but ``locked``
        # is short the full 500 margin (it sits at 0 here). total = 10000.
        _write_balances_snapshot(
            tmp_path,
            balances={
                "USDT": {
                    "currency": "USDT",
                    "free": "10000",
                    "locked": "0",
                }
            },
        )

        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
            activity_log=activity_log,
        )

        balance = trader.get_balance("USDT")
        assert balance is not None
        open_pos = trader.get_open_position(trade_id)
        assert open_pos is not None

        # Invariant restored: locked == Σ margin, total preserved.
        assert balance.locked == open_pos.margin == Decimal("500")
        assert balance.free + balance.locked == Decimal("10000")
        assert balance.free == Decimal("9500")

        # Repair event + warning fired.
        events = activity_log.filter(
            event_type=ActivityEventType.RECONCILIATION_REPAIRED_PAPER_BOUNDS
        )
        assert len(events) == 1
        assert events[0].details["currency"] == "USDT"
        assert Decimal(events[0].details["old_locked"]) == Decimal("0")
        assert Decimal(events[0].details["new_locked"]) == Decimal("500")

        # The close that used to crash now runs clean (no raise).
        closed = await trader.close_position(trade_id, Decimal("49000"), "stop_loss")
        assert closed is not None
        assert closed.status == "closed"
        balance_after = trader.get_balance("USDT")
        assert balance_after is not None
        assert balance_after.locked == Decimal("0")

    async def test_repro_matches_weinstein_two_margin_shortfall(
        self, tmp_path: Path
    ) -> None:
        """Two open margins, snapshot locked counts only one → both restored."""
        # Two open trades, each margin 1000 (notional 100000 * 0.2, lev 20).
        id_a = _seed_open_trade(
            tmp_path,
            symbol="ETH/USDT",
            entry_price=Decimal("100000"),
            quantity=Decimal("0.2"),
            leverage=20,
        )
        id_b = _seed_open_trade(
            tmp_path,
            symbol="SOL/USDT",
            entry_price=Decimal("100000"),
            quantity=Decimal("0.2"),
            leverage=20,
        )

        # Snapshot only locked one of the two margins (drift = 1000).
        _write_balances_snapshot(
            tmp_path,
            balances={
                "USDT": {
                    "currency": "USDT",
                    "free": "9000",
                    "locked": "1000",
                }
            },
        )

        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        balance = trader.get_balance("USDT")
        assert balance is not None
        margin_a = trader.get_open_position(id_a)
        margin_b = trader.get_open_position(id_b)
        assert margin_a is not None and margin_b is not None
        expected = margin_a.margin + margin_b.margin
        assert expected == Decimal("2000")
        assert balance.locked == expected
        # total preserved at the snapshot value 9000 + 1000 = 10000.
        assert balance.total == Decimal("10000")
        assert balance.free == Decimal("8000")


# =============================================================================
# Test 3 — stale-high locked releases the excess
# =============================================================================


class TestStaleHighLocked:
    """DEBT-072: snapshot ``locked`` > Σ margins returns the excess."""

    async def test_excess_locked_returns_to_free(self, tmp_path: Path) -> None:
        trade_id = _seed_open_trade(tmp_path)  # margin 500

        # Snapshot over-locked: 1500 locked vs 500 true margin.
        _write_balances_snapshot(
            tmp_path,
            balances={
                "USDT": {
                    "currency": "USDT",
                    "free": "8500",
                    "locked": "1500",
                }
            },
        )

        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )

        balance = trader.get_balance("USDT")
        open_pos = trader.get_open_position(trade_id)
        assert balance is not None and open_pos is not None
        assert balance.locked == open_pos.margin == Decimal("500")
        # Excess 1000 returned to free; total preserved.
        assert balance.free == Decimal("9500")
        assert balance.total == Decimal("10000")

    async def test_no_open_positions_releases_all_locked(self, tmp_path: Path) -> None:
        """Stale ``locked`` with zero open positions drains fully to free."""
        _write_balances_snapshot(
            tmp_path,
            balances={
                "USDT": {
                    "currency": "USDT",
                    "free": "9000",
                    "locked": "1000",
                }
            },
        )

        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.locked == Decimal("0")
        assert balance.free == Decimal("10000")


# =============================================================================
# Test 4 — open → close → re-close is a no-op on locked
# =============================================================================


class TestNoDoubleUnlock:
    """DEBT-072: the reconcile + close path never double-unlocks."""

    async def test_open_close_reclose_no_op_on_locked(self, tmp_path: Path) -> None:
        position = Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        trade = await trader.open_position(position)

        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.locked == Decimal("500")

        closed = await trader.close_position(trade.id, Decimal("49000"), "stop_loss")
        assert closed is not None
        assert balance.locked == Decimal("0")
        free_after_first = balance.free

        # Re-close is a no-op (trade already gone): no raise, no double-unlock,
        # no spurious negative.
        second = await trader.close_position(trade.id, Decimal("48000"), "stop_loss")
        assert second is None
        assert balance.locked == Decimal("0")
        assert balance.free == free_after_first

    async def test_legacy_no_snapshot_reconcile_does_not_double_lock(
        self, tmp_path: Path
    ) -> None:
        """No-snapshot legacy path locks once; the new reconcile is a no-op."""
        trade_id = _seed_open_trade(tmp_path)  # margin 500, no balances.json

        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        balance = trader.get_balance("USDT")
        open_pos = trader.get_open_position(trade_id)
        assert balance is not None and open_pos is not None
        # Legacy reconcile locked margin; the new reconcile saw it already
        # matched and made no further change (no double-lock to 1000).
        assert balance.locked == open_pos.margin == Decimal("500")
        assert balance.free == Decimal("9500")
        assert balance.total == Decimal("10000")


# =============================================================================
# Test 5 — orphan force-close margin handling
# =============================================================================


class TestOrphanForceCloseMargin:
    """DEBT-072 change 4: present → unlock margin; absent → self-heal later."""

    @pytest.fixture
    def long_position(self) -> Position:
        return Position(
            symbol="BTC/USDT",
            side="long",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            leverage=10,
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )

    async def test_force_close_with_position_unlocks_exact_margin(
        self, tmp_path: Path, long_position: Position
    ) -> None:
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        trade = await trader.open_position(long_position)
        balance = trader.get_balance("USDT")
        assert balance is not None
        locked_before = balance.locked  # 500

        await trader.force_close_orphan(trade.id, Decimal("50000"))

        assert trader.get_open_position(trade.id) is None
        assert balance.locked == locked_before - Decimal("500")

    async def test_force_close_without_position_leaves_locked_then_heals(
        self, tmp_path: Path, long_position: Position
    ) -> None:
        """Absent in-memory pos → locked untouched at force-close.

        A later restart's rehydrate reconcile then heals the split (the
        trade is now closed on disk so its margin is no longer expected,
        and the stale ``locked`` drains to ``free``).
        """
        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        trade = await trader.open_position(long_position)
        balance = trader.get_balance("USDT")
        assert balance is not None
        assert balance.locked == Decimal("500")

        # Genuine orphan: drop the in-memory position before force-close.
        trader._open_positions.pop(trade.id, None)
        await trader.force_close_orphan(trade.id, Decimal("50000"))

        # Locked deliberately left as-is (no authoritative margin to unlock).
        assert balance.locked == Decimal("500")

        # A later restart self-heals: the trade is closed on disk so no
        # margin is expected, and the stale 500 locked drains to free.
        restarted = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        restarted_balance = restarted.get_balance("USDT")
        assert restarted_balance is not None
        assert restarted_balance.locked == Decimal("0")


# =============================================================================
# Test 6 — DEBT-027 parity: reconcile may drive free negative
# =============================================================================


class TestDebt027Parity:
    """The reconcile must NOT clamp a negative ``free`` to zero."""

    async def test_reconcile_allows_negative_free(self, tmp_path: Path) -> None:
        """Open margin exceeding equity → free goes negative, not clamped."""
        # Open trade margin 500. Snapshot total is only 200 (an account
        # already under water from a prior liquidation) and locked is short.
        trade_id = _seed_open_trade(tmp_path)
        _write_balances_snapshot(
            tmp_path,
            balances={
                "USDT": {
                    "currency": "USDT",
                    "free": "200",
                    "locked": "0",
                }
            },
        )

        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        balance = trader.get_balance("USDT")
        open_pos = trader.get_open_position(trade_id)
        assert balance is not None and open_pos is not None
        # locked pinned to the margin; free = total(200) - 500 = -300, NOT 0.
        assert balance.locked == Decimal("500")
        assert balance.free == Decimal("-300")
        assert balance.total == Decimal("200")


# =============================================================================
# Test 7 — DEBT-059 parity: snapshot total equity unchanged
# =============================================================================


class TestDebt059Parity:
    """Reconcile moves only the free/locked split; total is preserved."""

    async def test_total_equity_preserved_across_reconcile(
        self, tmp_path: Path
    ) -> None:
        _seed_open_trade(tmp_path)  # margin 500

        # Snapshot total carries realised PnL: 12345.67 total, locked short.
        _write_balances_snapshot(
            tmp_path,
            balances={
                "USDT": {
                    "currency": "USDT",
                    "free": "12345.67",
                    "locked": "0",
                }
            },
        )

        trader = PaperTrader(
            initial_balance={"USDT": Decimal("10000")},
            data_dir=tmp_path,
        )
        balance = trader.get_balance("USDT")
        assert balance is not None
        # total unchanged; only the split moved (locked 0 → 500).
        assert balance.total == Decimal("12345.67")
        assert balance.locked == Decimal("500")
        assert balance.free == Decimal("11845.67")
