# Business Rules: Derivatives Data Wiring (Funding / OI) — v1

## R1 — No look-ahead (hard invariant)

Every `MarketContext` is bound to `as_of`; no series element may carry
`timestamp > as_of`. Derived features computed by consumers inherit the
bound: any feature used to judge or modify entry logic must be computable
from elements `<= as_of`. Backtests must produce the identical context a
live cycle at that bar would have seen (minus `predicted_funding_rate`,
which is always `None` in replay).

## R2 — Contiguity and explicit truncation

- Funding series: contiguous on the venue 8h grid or the fetch raises
  (DEBT-080 precedent — no silently gapped series ever reaches a
  consumer).
- OI series: contiguous on the granularity grid within the venue
  retention horizon; retention-shortened windows are explicit
  (`truncated_at_venue_retention=True`) and logged, never silent.
- Pagination advances by records actually received, never by requested
  page size.

## R3 — Missing-data semantics (per consumer)

| Consumer | Behavior when `market_context is None` / series empty |
|----------|------------------------------------------------------|
| Strategy with `requires_market_context=True` | Return neutral (same convention as `InsufficientDataError` → neutral) |
| Strategy with `requires_market_context=False` | Unaffected — must not assume presence |
| Proposal-layer regime filter | **Fail-open** (skip the filter) + `gate_skipped_missing_market_context` telemetry |
| Robustness gate on a `requires_market_context` strategy | `INSUFFICIENT_DATA` outcome — **never a vacuous pass** |

Fail-open rationale for the filter: absence of derivatives data restores
today's OHLCV-only behavior; the filter is an enhancement layer, and
fail-closing it would halt the entire proposal pool on a data outage.
The skip telemetry keeps the degradation measurable and alertable.

## R4 — Determinism for promotion decisions (NFR-006)

Any run that feeds a promotion/gate decision consumes snapshot v2 data
only. Live-fetched derivatives data is for runtime cycles and exploratory
research; a gate report must record the snapshot identity it replayed.
`predicted_funding_rate` (not reproducible) is excluded from gated logic
by construction — it is absent in replay, so strategies depending on it
fail honest (neutral) in the gate rather than diverging live-vs-backtest.

## R5 — Source scope and capability flags (Q1)

v1 source is Binance public endpoints only (no credentials, no external
vendors). `supports_derivatives_data=False` venues (Bybit v1) raise a
typed NotSupported error from the derivatives methods; engine context
build treats that venue's symbols as `market_context=None` (R3) rather
than erroring the cycle. Vendor integration (liquidations, long/short,
MVRV) is a separate v2 design with its own NFR pass.

## R6 — Rate-limit posture (detailed in the NFR pass)

Design ceilings the NFR stage must verify: ≤3 funding-history fetches per
symbol per day (8h boundary refresh), ≤1 OI append-fetch per symbol per
cycle at 1h granularity, current-state scalar reads once per cycle. All
reads are public-endpoint weight; no credentialed quota consumed.

## R7 — Hypothesis-first consumers (Phase 5.3a unchanged)

The wiring ships data, not signals. Every consumer (regime filter
thresholds, Funding-Extreme MR strategy) still requires its own
predeclared hypothesis, falsifiability statement, and replay/backtest
evidence on snapshot v2 data before it can veto proposals or trade.
