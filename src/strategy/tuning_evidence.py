"""Pure rolling evidence with explicit account-capital and quote units."""

from datetime import datetime
from decimal import Decimal

from src.strategy.performance import (
    PerformanceRecord,
    TradeOutcome,
    net_return_for_record,
)
from src.strategy.tuning_recommender import RecommenderEvidence
from src.utils.time import ensure_utc


def evidence_from_records(
    records: list[PerformanceRecord],
    *,
    window_closed_trades: int,
    initial_balance: Decimal | None,
    fail_closed_rate: float,
    quote_currency: str = "USDT",
) -> RecommenderEvidence:
    """Use the latest N closed real trades, never lifetime notional sums.

    Unknown timestamps invalidate the window; unknown amounts within the
    selected window invalidate economic conclusions. No rows are guessed away.
    Account/strategy/version isolation belongs to the calling tracker.
    """
    if window_closed_trades < 1:
        raise ValueError("window_closed_trades must be positive")
    closed = [
        r for r in records if not r.synthetic and r.outcome != TradeOutcome.PENDING
    ]
    dated = [r for r in closed if r.exit_timestamp is not None]
    dated.sort(key=_exit_order)
    window = dated[-window_closed_trades:]
    problems: list[str] = []
    if len(dated) != len(closed):
        problems.append("missing exit time")
    capital_valid = (
        initial_balance is not None
        and initial_balance.is_finite()
        and initial_balance > 0
    )
    if not capital_valid:
        problems.append("missing positive account capital")
    amounts: list[Decimal] = []
    for record in window:
        quote = record.symbol.partition("/")[2].partition(":")[0]
        if quote != quote_currency:
            problems.append("mixed or unknown quote currency")
            continue
        net_return = net_return_for_record(record)
        entry = (
            record.actual_entry_price
            if record.actual_entry_price is not None
            else record.entry_price
        )
        quantity = record.quantity
        if (
            net_return is None
            or quantity is None
            or not quantity.is_finite()
            or not entry.is_finite()
            or quantity <= 0
            or entry <= 0
        ):
            problems.append("unknown net trade amount")
            continue
        amounts.append(net_return * entry * quantity / 100)
    complete = not problems
    net_total = sum(amounts, Decimal(0))
    gains = sum((amount for amount in amounts if amount > 0), Decimal(0))
    losses = -sum((amount for amount in amounts if amount < 0), Decimal(0))
    pnl_pct = drawdown = Decimal(0)
    if complete:
        assert initial_balance is not None
        pnl_pct = net_total / initial_balance * 100
        equity = peak = initial_balance
        for amount in amounts:
            equity += amount
            peak = max(peak, equity)
            drawdown = max(drawdown, (peak - equity) / peak * 100)
    return RecommenderEvidence(
        closed_trades=len(window),
        win_rate=(
            sum(amount > 0 for amount in amounts) / len(amounts)
            if amounts and complete
            else 0.0
        ),
        profit_factor=float(gains / losses) if losses and complete else None,
        closed_pnl_pct=float(pnl_pct),
        max_drawdown_pct=float(drawdown),
        fail_closed_rate=fail_closed_rate,
        economic_complete=complete,
        quote_currency=quote_currency,
        coverage_note="; ".join(dict.fromkeys(problems)),
        window_closed_trades=window_closed_trades,
        capital_base=(
            float(initial_balance)
            if capital_valid and initial_balance is not None
            else None
        ),
    )


def _exit_order(record: PerformanceRecord) -> tuple[datetime, str]:
    assert record.exit_timestamp is not None
    return ensure_utc(record.exit_timestamp), record.id
