# Functional Design Plan: exchange-integration — Derivatives Data Wiring (Funding / OI)

## Task

Wire perpetual-futures derivatives data — funding rate and open interest —
into the platform so strategies, the proposal-layer regime gate, and the
backtester can consume it. This is the alpha path identified by the
2026-07-17 `/strategy-gen` sweep (OHLCV-only edge re-confirmed absent across
3y × 4 symbols; see `docs/sessions/` and memory `no-ohlcv-only-edge`) and by
`docs/research/strategies/00-priority-matrix.md` ranks 1/3 (Funding + OI
Combo Regime Filter, composite 19; Funding Rate Extreme MR, 18).

- **Primary Unit**: `exchange-integration` (owns the first code change:
  `BaseExchange` contract + Binance implementation)
- **Secondary Units**: `strategy-framework` (analyze-contract consumption),
  `backtesting-validation` (historical replay + snapshot reproducibility),
  `proposal-runtime` (regime-gate consumption), `persistence-data-integrity`
  (snapshot schema)
- **Related Requirements**: FR-016..FR-020, NFR-009, NFR-011 (exchange
  scope); NFR-006 (reproducibility). A requirements addendum (new FR for
  derivatives data) should be filed via product-planner before code
  generation.
- **Related Debt/History**: `auto_research_candidates.py` docstring and
  Phase 5.3a policy both defer funding/OI/on-chain techniques to "later
  data wiring" — this design is that wiring.
- **Stage**: Functional Design (behavior + contract change). NFR Design
  will follow for rate-limit/caching behavior; Infrastructure Design N/A
  for v1 (no new external topology if Binance-only).

## Design Constraints (assumed true, from code)

- `BaseExchange` today exposes OHLCV/ticker/balance/order only; ccxt-backed
  (`src/exchange/ccxt_base.py`), Binance (`OHLCV_LIMIT=1500`) + Bybit (200).
- ccxt provides unified `fetch_funding_rate(_history)` and
  `fetch_open_interest(_history)`; Binance USDT-perp serves both from free
  public endpoints (no API key). Funding interval 8h; OI history granularity
  ≥ 5m with venue-side retention limits (~30 days at fine granularity).
- Strategies receive data through `BaseStrategy.analyze(ohlcv, symbol,
  timeframe, *, ohlcv_by_timeframe=None, current_price=None)` — the
  extension point precedent is keyword-only optional inputs.
- Backtest reproducibility is snapshot-pinned (Phase 25): any new data
  stream a backtest consumes must be snapshot-able or the robustness gate
  loses determinism (NFR-006).
- DEBT-080 lesson: any new paginated history fetch must advance by bars
  actually received and assert series contiguity loudly.

## Open Questions (answer inline, then design artifacts are generated)

### Q1 — v1 data-source scope

Binance public API alone covers funding rate (current + full history) and
open interest (current + ~30d history) with zero credentials and zero new
vendors. External freemium vendors (Coinglass etc.) add cross-venue
aggregates, liquidations, and long/short ratios but bring API keys, rate
limits, and ToS surface. Priority-matrix rank 2 (MVRV) needs an on-chain
vendor and is NOT reachable in a Binance-only v1.

Recommendation: **(a) Binance-only v1** — funding + OI, ccxt unified
methods, no new dependencies; vendor integration deferred to a v2 design.

- (a) Binance-only v1 (funding + OI)
- (b) Binance + one freemium vendor (adds liquidations/long-short/MVRV)
- (c) Vendor-first (Coinglass as the primary source)

[Answer]:

### Q2 — strategy consumption contract

How do deterministic strategies receive derivatives data in `analyze()`?

Recommendation: **(a)** a new optional keyword-only `market_context:
MarketContext | None` carrying aligned series (`funding_rates:
list[FundingRate]`, `open_interest: list[OpenInterestPoint]`) plus
convenience latest-value accessors. Backward compatible (strategies that
ignore it keep working), mirrors the `ohlcv_by_timeframe` precedent, and
keeps raw series available so strategies compute their own features
(pre-decision-only, no look-ahead).

- (a) Optional `market_context` object with aligned raw series
- (b) Engine-computed derived features only (e.g. funding z-score, OI
  delta) passed as scalars — smaller surface, less flexible
- (c) Extend `ohlcv_by_timeframe`-style dict with pseudo-timeframe keys
  ("funding", "oi") — no new types but abuses the OHLCV shape

[Answer]:

### Q3 — backtest reproducibility for funding/OI

The robustness gate and backtester must replay derivatives data
deterministically or funding-aware strategies can never be gated (NFR-006).

Recommendation: **(a)** extend the Phase 25 snapshot dataset with
`funding.csv` / `open_interest.csv` per symbol (schema v2, versioned
`metadata.json`), same freshness policy, contiguity-asserted on load; the
backtester slices them by timestamp alongside OHLCV with the same
no-look-ahead guarantee as `slice_multi_tf_by_index`.

- (a) Snapshot schema v2 with funding/OI series (full determinism)
- (b) Live-fetch during backtests, cache per run (faster to ship; breaks
  cross-operator determinism — gate results become non-reproducible)
- (c) v1 runtime-only (no backtest support): strategies can use the data
  live/paper but gated promotion stays OHLCV-only until v2

[Answer]:

### Q4 — first consumer to build after the wiring

Recommendation: **(a)** the proposal-layer Funding+OI regime filter first
(priority-matrix rank 1, composite 19): it upgrades EVERY existing
strategy's entry quality via the existing market-regime gate surface
(`src/runtime/market_regime.py` precedent), needs only latest-value reads,
and produces measurable funnel deltas fast. The Funding-Extreme MR
strategy (rank 3) follows as the first new `strategies/*.py` consumer of
the historical series.

- (a) Proposal-layer Funding+OI regime filter, then Funding-Extreme MR
  strategy
- (b) Funding-Extreme MR strategy first (isolated blast radius, slower
  portfolio-wide benefit)
- (c) Both in one slice (larger, but one review cycle)

[Answer]:

## Plan Steps

- [ ] Q1-Q4 answered; ambiguities resolved (follow-ups if any answer is
      vague).
- [ ] Requirements addendum: file the new derivatives-data FR via
      product-planner flow (`docs/requirements.md` +
      `aidlc-docs/inception/requirements/requirements.md`).
- [ ] Generate `aidlc-docs/construction/exchange-integration/functional-design/`
      artifacts per the AI-DLC rule: `business-logic-model.md`
      (fetch/pagination/alignment flows, DEBT-080-style contiguity rules),
      `domain-entities.md` (`FundingRate`, `OpenInterestPoint`,
      `MarketContext`, snapshot schema v2), `business-rules.md` (freshness
      windows, missing-data semantics = neutral/fail-closed per consumer,
      no-look-ahead alignment rules, venue-retention limits).
- [ ] NFR requirements/design pass: rate-limit budget, caching TTLs,
      backoff, partial-outage behavior (funding available / OI down).
- [ ] Hand off to code generation with a bounded slice list (exchange
      methods → snapshot v2 → market_context plumbing → first consumer per
      Q4).
- [ ] Completion checklist: aidlc-state stage row, session log,
      cross-check on unit completion, debt entries for any deferred edges.
