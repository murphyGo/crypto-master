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

from src.models import OHLCV
from src.utils.trading_types import TradeSide

# =============================================================================
# Stop-loss floor enforcement (P1 items F + G)
# =============================================================================
#
# Calibrated against the Fly 12-day paper run: 35 stop_loss vs 6 take_profit
# exits across 41 closed trades, with 7/10 strategies shipping median SL
# distance < 1× typical 1h ATR. The proposal layer now intercepts the
# strategy-declared SL and widens it outward to whichever floor is
# stricter (i.e. wider stop): the ATR-scaled floor or the per-timeframe
# minimum percentage. The floor never tightens an existing stop.
#
# Per-timeframe minimum SL distance as a fraction of entry price.
# Calibrated to ~1× typical realized ATR on liquid majors so a single
# candle's noise can't take the stop out.
TF_MIN_SL_PCT: dict[str, Decimal] = {
    "5m": Decimal("0.003"),
    "15m": Decimal("0.004"),
    "30m": Decimal("0.006"),
    "1h": Decimal("0.008"),
    "2h": Decimal("0.012"),
    "4h": Decimal("0.015"),
    "8h": Decimal("0.020"),
    "12h": Decimal("0.022"),
    "1d": Decimal("0.025"),
    "1w": Decimal("0.040"),
}
DEFAULT_TF_MIN_SL_PCT = Decimal("0.008")  # fallback for unknown TFs

ATR_FLOOR_MULTIPLIER = Decimal("1.5")  # SL >= 1.5 x ATR(14)


def compute_atr(ohlcv: list[OHLCV], period: int = 14) -> Decimal | None:
    """Wilder's Average True Range.

    Returns ``None`` when there are fewer than ``period + 1`` candles
    (one extra is needed because the first true range references the
    previous close). All math runs in :class:`~decimal.Decimal` to
    match the rest of the trading-math module.

    True Range per bar is::

        max(high - low,
            abs(high - prev_close),
            abs(low - prev_close))

    The first ATR is the simple mean of the first ``period`` true
    ranges; subsequent bars apply Wilder's smoothing::

        ATR_t = (ATR_{t-1} × (period - 1) + TR_t) / period

    Args:
        ohlcv: Chronologically-ordered candle series.
        period: Lookback window. 14 is the canonical Wilder default.

    Returns:
        The Wilder-smoothed ATR at the latest bar, or ``None`` when
        ``len(ohlcv) < period + 1``.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if len(ohlcv) < period + 1:
        return None

    true_ranges: list[Decimal] = []
    for i in range(1, len(ohlcv)):
        high = ohlcv[i].high
        low = ohlcv[i].low
        prev_close = ohlcv[i - 1].close
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        true_ranges.append(tr)

    # First ATR: simple mean of the first ``period`` TRs.
    atr_value = sum(true_ranges[:period], Decimal("0")) / Decimal(period)
    # Wilder smoothing for every subsequent TR.
    period_dec = Decimal(period)
    for tr in true_ranges[period:]:
        atr_value = (atr_value * (period_dec - Decimal("1")) + tr) / period_dec
    return atr_value


def enforce_sl_floor(
    *,
    side: TradeSide,
    entry_price: Decimal,
    stop_loss: Decimal,
    timeframe: str,
    atr: Decimal | None,
) -> Decimal:
    """Widen ``stop_loss`` outward to satisfy the SL floor.

    The floor is the wider of two distances:

    * **ATR floor** — ``ATR_FLOOR_MULTIPLIER × atr`` (skipped when
      ``atr is None``).
    * **TF % floor** — ``entry_price × TF_MIN_SL_PCT[timeframe]``
      (or :data:`DEFAULT_TF_MIN_SL_PCT` when ``timeframe`` is not a
      known key).

    The returned SL is the *wider* of the original ``stop_loss`` and
    the floor — this function never tightens an existing stop. For
    longs the SL sits below entry, so widening means moving the SL
    further DOWN; for shorts it sits above entry, so widening means
    moving it further UP.

    Args:
        side: ``"long"`` or ``"short"``.
        entry_price: Strategy-declared entry price. Must be positive
            in practice (callers validate via Pydantic models).
        stop_loss: Strategy-declared stop loss.
        timeframe: Primary timeframe key (e.g. ``"1h"``, ``"4h"``).
            Unknown values fall back to :data:`DEFAULT_TF_MIN_SL_PCT`.
        atr: Wilder ATR(14) on the primary timeframe, or ``None``
            when there is insufficient data.

    Returns:
        A SL that is at least the floor distance from ``entry_price``
        on the correct side. If the strategy already declared a wider
        SL than both floors, ``stop_loss`` is returned unchanged.

    Raises:
        ValueError: If ``side`` is not ``"long"`` or ``"short"``.
    """
    if side not in ("long", "short"):
        raise ValueError(f"Unknown trade side: {side!r}")

    tf_pct = TF_MIN_SL_PCT.get(timeframe, DEFAULT_TF_MIN_SL_PCT)
    tf_floor_distance = entry_price * tf_pct
    atr_floor_distance = atr * ATR_FLOOR_MULTIPLIER if atr is not None else Decimal("0")
    # Whichever floor is stricter wins (i.e. demands the wider stop).
    floor_distance = max(tf_floor_distance, atr_floor_distance)

    current_distance = abs(entry_price - stop_loss)
    if current_distance >= floor_distance:
        return stop_loss

    # Widen outward — never tighten. Long → SL further down; short → up.
    if side == "long":
        return entry_price - floor_distance
    return entry_price + floor_distance


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
