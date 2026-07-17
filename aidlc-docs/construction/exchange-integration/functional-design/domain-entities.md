# Domain Entities: Derivatives Data Wiring (Funding / OI) — v1

Decisions locked 2026-07-17 (plan Q1-Q4): Binance-only source;
`market_context` object contract; snapshot schema v2; regime-filter first
consumer.

## FundingRate

One settled funding interval for a perpetual symbol.

| Field | Type | Semantics |
|-------|------|-----------|
| `symbol` | str | Trading pair, e.g. `"BTC/USDT"` (perp) |
| `timestamp` | datetime (UTC) | Funding settlement time (8h grid: 00/08/16 UTC on Binance) |
| `rate` | Decimal | Settled funding rate for the interval (signed; +ve = longs pay) |

- Only **settled** intervals are represented; the in-progress predicted
  rate is a separate scalar (`predicted_rate` on the current-state read),
  never mixed into the history series.
- Series contract: chronologically ascending, contiguous on the venue's
  8h grid (DEBT-080-style loud contiguity assertion).

## OpenInterestPoint

One open-interest observation for a perpetual symbol.

| Field | Type | Semantics |
|-------|------|-----------|
| `symbol` | str | Trading pair |
| `timestamp` | datetime (UTC) | Observation close time (granularity grid) |
| `open_interest` | Decimal | Contracts/base-asset units outstanding |
| `open_interest_value` | Decimal \| None | Quote-currency notional when the venue provides it |

- v1 canonical granularity: **1h** (coarse enough for rate limits, fine
  enough for the regime filter and a 4h/1h strategy family).
- Venue retention: Binance serves fine-granularity OI history ~30 days
  back. The series carries `truncated_at_venue_retention: bool` metadata —
  a shorter-than-requested OI window is explicit, never silent.

## MarketContext

The per-decision derivatives bundle passed to strategies and gates.

| Field | Type | Semantics |
|-------|------|-----------|
| `symbol` | str | Trading pair the context describes |
| `as_of` | datetime (UTC) | Decision-bar close time; **no element in any series may be newer** |
| `funding_rates` | list[FundingRate] | Ascending, settled intervals ≤ `as_of` |
| `open_interest` | list[OpenInterestPoint] | Ascending, observations ≤ `as_of` |
| `predicted_funding_rate` | Decimal \| None | Venue's current predicted rate (live/paper only; None in backtests — see business rules) |

Convenience accessors (read-only, computed from the series):

- `latest_funding_rate -> FundingRate | None`
- `latest_open_interest -> OpenInterestPoint | None`

No derived analytics (z-scores, deltas) live on the entity — consumers
compute their own features from the raw series (Q2 decision), and every
derived feature inherits the `as_of` no-look-ahead bound.

## Consumption contract

`BaseStrategy.analyze(..., *, market_context: MarketContext | None = None)`
— keyword-only, optional, default `None`. Strategies that ignore it are
unchanged. `TechniqueInfo` gains `requires_market_context: bool = False`
(mirrors `requires_multi_timeframe`): when True and `market_context is
None`, the strategy returns neutral (strategy path) / the gate records
`INSUFFICIENT_DATA` (gate path) rather than guessing.

## Exchange contract additions (`BaseExchange`)

| Method | Returns | Notes |
|--------|---------|-------|
| `get_funding_rate(symbol)` | current + predicted scalar view | live/paper cycle reads |
| `get_funding_rate_history(symbol, since, limit)` | list[FundingRate] | paginated per business-logic rules |
| `get_open_interest(symbol)` | OpenInterestPoint | current observation |
| `get_open_interest_history(symbol, timeframe, since, limit)` | list[OpenInterestPoint] | 1h default granularity |
| `supports_derivatives_data` | bool (class attr) | Binance `True`; Bybit `False` in v1 (methods raise a typed NotSupported error) |

## Snapshot schema v2 (`persistence-data-integrity` spillover)

Per snapshot symbol directory (alongside `ohlcv.csv` + `metadata.json`):

- `funding.csv` — `timestamp,rate`
- `open_interest.csv` — `timestamp,open_interest,open_interest_value`
- `metadata.json` gains `schema_version: 2`, per-series `fetched_at`,
  `since`/`until`, `granularity`, `truncated_at_venue_retention`.

Backward compatibility: `schema_version` absent → v1 → derivatives series
absent → loaders produce `market_context=None`; `requires_market_context`
strategies then gate as `INSUFFICIENT_DATA` (never a vacuous pass).
