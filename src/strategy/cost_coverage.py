"""Explicit cost boundaries and a read-only adverse-carry scenario.

This is not a funding settlement model. Actual funding remains unknown;
the caller supplies a constant adverse rate and interval for sensitivity only.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from src.strategy.performance import PerformanceRecord, TradeOutcome
from src.strategy.trade_history import TradeHistory
from src.utils.time import ensure_utc

PnlBasis = Literal["fee_net_excluding_funding", "legacy_unspecified"]
FundingCoverage = Literal["unknown"]


@dataclass(frozen=True)
class CarrySensitivity:
    """Partial sums remain explicitly partial; actual funding is never zeroed."""

    quote_currency: str
    rate_per_interval: Decimal
    interval_hours: Decimal
    closed_real_records: int
    included_trades: int
    excluded_reasons: dict[str, int]
    fee_net_pnl_subtotal: Decimal
    scenario_cost_subtotal: Decimal
    funding_coverage: FundingCoverage = "unknown"
    pnl_basis: PnlBasis = "fee_net_excluding_funding"
    scenario: str = "constant adverse carry; fractional intervals; not actual funding"
    time_basis: str = "executed trade entry_time to exit_time"

    @property
    def complete(self) -> bool:
        """Scenario coverage only; does not certify actual funding coverage."""
        return self.closed_real_records > 0 and not self.excluded_reasons

    @property
    def scenario_pnl(self) -> Decimal | None:
        if not self.complete:
            return None
        return self.fee_net_pnl_subtotal - self.scenario_cost_subtotal


def adverse_carry_sensitivity(
    records: Sequence[PerformanceRecord],
    trades: Mapping[str, TradeHistory],
    *,
    rate_per_interval: Decimal,
    interval_hours: Decimal,
    quote_currency: str,
) -> CarrySensitivity:
    """Join real closed outcomes to actual fills without changing either.

    Each eligible trade pays ``entry_price * quantity * rate * hours/interval``.
    Both sides pay in this deliberately adverse scenario; it is not a claim
    about historical signed funding. Leverage and trading fees are not applied
    again. Mixed accounts/currencies, duplicate links, and missing trade inputs
    invalidate the complete result rather than quietly yielding zero costs.
    """
    if not rate_per_interval.is_finite() or rate_per_interval < 0:
        raise ValueError("rate_per_interval must be finite and nonnegative")
    if not interval_hours.is_finite() or interval_hours <= 0:
        raise ValueError("interval_hours must be finite and positive")
    if not quote_currency:
        raise ValueError("quote_currency must be explicit")

    closed = [
        r for r in records if not r.synthetic and r.outcome != TradeOutcome.PENDING
    ]
    if len({r.sub_account_id for r in closed}) > 1:
        raise ValueError("scenario records must belong to one sub-account")
    link_counts = Counter(r.trade_id for r in closed if r.trade_id)
    excluded: Counter[str] = Counter()
    included = 0
    net = cost = Decimal(0)
    for record in closed:
        if not record.trade_id or record.trade_id not in trades:
            excluded["missing_trade_link"] += 1
            continue
        if link_counts[record.trade_id] != 1:
            excluded["duplicate_trade_link"] += 1
            continue
        trade = trades[record.trade_id]
        if (
            trade.id != record.trade_id
            or trade.sub_account_id != record.sub_account_id
            or trade.symbol != record.symbol
            or trade.side != record.signal
            or trade.mode != record.mode
        ):
            excluded["trade_identity_mismatch"] += 1
            continue
        if trade.symbol.partition("/")[2].partition(":")[0] != quote_currency:
            excluded["quote_currency_mismatch"] += 1
            continue
        if (
            trade.status != "closed"
            or trade.exit_time is None
            or "entry_time" not in trade.model_fields_set
        ):
            excluded["missing_closed_trade_time"] += 1
            continue
        duration = ensure_utc(trade.exit_time) - ensure_utc(trade.entry_time)
        if duration.total_seconds() < 0:
            excluded["exit_before_entry"] += 1
            continue
        if (
            not trade.entry_price.is_finite()
            or not trade.entry_quantity.is_finite()
            or trade.entry_price <= 0
            or trade.entry_quantity <= 0
            or trade.pnl is None
            or not trade.pnl.is_finite()
        ):
            excluded["unknown_trade_economics"] += 1
            continue
        # Decimal microseconds avoid binary float drift in long held positions.
        micros = (
            duration.days * 86400 + duration.seconds
        ) * 1_000_000 + duration.microseconds
        hours = Decimal(micros) / Decimal(3_600_000_000)
        cost += (
            trade.entry_price
            * trade.entry_quantity
            * rate_per_interval
            * hours
            / interval_hours
        )
        net += trade.pnl
        included += 1

    return CarrySensitivity(
        quote_currency=quote_currency,
        rate_per_interval=rate_per_interval,
        interval_hours=interval_hours,
        closed_real_records=len(closed),
        included_trades=included,
        excluded_reasons=dict(sorted(excluded.items())),
        fee_net_pnl_subtotal=net,
        scenario_cost_subtotal=cost,
    )
