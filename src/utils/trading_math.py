"""Trading-math primitives — single source of truth for per-trade PnL.

This module exists to close DEBT-024 (leverage applied twice in
backtester / portfolio / persistence PnL math). The convention
captured here is:

- The PnL on a price move is ``(Δp) × qty``. Leverage does *not*
  enter the per-trade PnL formula because ``qty`` was sized off the
  price-distance to the stop, not off margin. See
  :meth:`src.trading.strategy.RiskManager.calculate_position_size`
  (``src/trading/strategy.py:330-407``): ``quantity = risk_amount /
  abs(entry - stop)`` is leverage-independent — leverage only
  influences the *margin cap* check at the bottom of that method,
  never the quantity that closes the trade. So the same ``qty``
  delivers ``risk_amount`` at the stop regardless of leverage, and
  ``(Δp) × qty`` is therefore already the correct PnL figure for
  any leverage setting.
- Concretely: ``(exit - entry) * qty`` for longs and ``(entry -
  exit) * qty`` for shorts. ``leverage`` is *not* a parameter of
  :func:`pnl_for_trade` and callers must not multiply by it again.
- Fees, funding, and slippage are accounted for *outside* this
  helper — the helper returns the gross price-move PnL only.

The reference implementation that already followed this shape is
``PaperTrader.close_position`` (via ``Position.calculate_pnl``).
Phase 20.1 routes the backtester realised-PnL site, the portfolio
unrealised-PnL site, the paper-trader realised-PnL site, and the
persistence-layer ``TradeHistory.calculate_pnl`` site through this
single helper so the convention is enforced by construction.

Related Requirements:
- FR-006: Risk/Reward Calculation (correctness boundary on the
  per-trade PnL math).
- FR-025: Backtesting Execution (backtester PnL must match operator
  expectations and paper-trader ledgers).
- NFR-001: Operational maturity (single source of truth for a
  trading-math primitive).
"""

from __future__ import annotations

from decimal import Decimal

from src.utils.trading_types import TradeSide


def pnl_for_trade(
    entry: Decimal,
    exit: Decimal,
    qty: Decimal,
    side: TradeSide,
) -> Decimal:
    """Compute gross per-trade PnL from a price move.

    Returns ``(exit - entry) * qty`` for longs and
    ``(entry - exit) * qty`` for shorts. Leverage is intentionally
    not a parameter: the per-trade PnL on a price move is ``(Δp) ×
    qty``, and leverage does not enter because ``qty`` was sized off
    the price-distance to the stop (see
    :meth:`src.trading.strategy.RiskManager.calculate_position_size`,
    ``src/trading/strategy.py:330-407`` — ``quantity = risk_amount /
    abs(entry - stop)`` is leverage-independent; leverage only
    relaxes the margin cap further down). Multiplying by ``leverage``
    again at PnL time double-applies it.

    Fees / funding / slippage are accounted for by the caller; this
    helper returns only the price-move component.

    All math is in :class:`~decimal.Decimal` to avoid float drift; do
    not coerce inputs to ``float``.

    Args:
        entry: Entry fill price. Must be > 0 in practice; the helper
            does not validate (callers already constrain via Pydantic
            models such as :class:`src.models.Position`).
        exit: Exit fill price. Same validation contract as ``entry``.
        qty: Position quantity, sized off the entry-to-stop
            price-distance per the invariant above. Must be > 0;
            negative quantities are not the convention this codebase
            uses to encode shorts (``side`` does that instead).
        side: ``"long"`` or ``"short"``.

    Returns:
        Gross PnL as a :class:`~decimal.Decimal`. Sign follows the
        usual convention: positive = profit, negative = loss, zero
        for a no-move close or a zero-quantity trade.

    Raises:
        ValueError: If ``side`` is not ``"long"`` or ``"short"``.
    """
    if side == "long":
        return (exit - entry) * qty
    if side == "short":
        return (entry - exit) * qty
    raise ValueError(f"Unknown trade side: {side!r}")
