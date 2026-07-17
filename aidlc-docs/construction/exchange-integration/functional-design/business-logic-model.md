# Business Logic Model: Derivatives Data Wiring (Funding / OI) — v1

Flows for fetching, aligning, persisting, and serving funding/OI data.
Entities in `domain-entities.md`; rules in `business-rules.md`.

## Flow 1 — History fetch (funding, OI)

1. Resolve the request window (`since`, `until`/count) on the series grid
   (funding: 8h; OI: 1h v1 granularity).
2. Page through venue history **advancing by records actually received**
   — never by the requested page size (DEBT-080 rule). Binance funding
   history pages max 1000; OI history max 500 per call.
3. De-duplicate by timestamp, sort ascending.
4. Assert grid contiguity for the covered span. Funding: every 8h tick
   present. OI: every granularity tick present *within the venue
   retention horizon*; a request extending past retention returns the
   available suffix with `truncated_at_venue_retention=True` (explicit,
   logged, never silent).
5. On any page-level API failure after retries: raise; callers decide
   fallback per the missing-data rules — no partially-stitched silent
   result.

## Flow 2 — Runtime cycle context build (engine, live/paper)

1. Per scan cycle, per symbol in the scan universe: refresh cached series.
   - Funding history: refresh only when a new 8h boundary has settled
     since the cached tail (at most 3 fetches/day/symbol).
   - OI: append-fetch since cached tail each cycle (1h grid → at most one
     new point per hour); current-OI scalar read is per-cycle.
   - Predicted funding: per-cycle scalar read, cache TTL = cycle.
2. Build `MarketContext(symbol, as_of=decision_bar_close)` from cached
   series filtered to `timestamp <= as_of`.
3. Pass to every strategy `analyze()` call (keyword-only optional) and to
   the proposal-layer regime filter.
4. Fetch failure degrades to `market_context=None` for that cycle —
   OHLCV-only behavior, plus a telemetry event (see business rules); it
   never blocks the cycle.

## Flow 3 — Backtest / robustness-gate replay

1. Gate and backtester consume **snapshot v2 only** (Q3 decision): no
   live derivatives fetch inside a promotion-relevant run.
2. Loader validates schema version, series contiguity, and that the
   derivatives span covers the OHLCV span being replayed (funding span
   may start later only if flagged; the uncovered prefix replays with
   `market_context=None`).
3. Per simulated bar `t`: slice funding/OI series to `timestamp <=
   close_time(t)` — the exact multi-TF alignment guarantee
   (`slice_multi_tf_by_index` precedent) extended to derivatives series.
   `predicted_funding_rate` is always `None` in replay (not reproducible;
   strategies must not depend on it for gated logic).
4. Funding **cost** modeling stays where it is today (fee/funding drag in
   the backtest engine is out of scope for this unit's v1; this unit only
   supplies the *signal* series).

## Flow 4 — First consumer: proposal-layer Funding+OI regime filter (Q4)

Contract only (thresholds are the consumer slice's hypothesis-first work,
priority-matrix rank 1):

1. Input: `MarketContext` for the proposal's symbol at proposal build
   time.
2. The filter classifies crowding state from latest funding + OI trend
   (e.g. crowded-long / crowded-short / neutral) and can veto or
   down-weight proposals whose side trades *with* the crowd at extremes.
3. Emits the standard gate-reason telemetry (`src/runtime/gate_reason.py`
   precedent) with the observed funding/OI values, so funnel deltas are
   measurable from day one.
4. Missing context → filter is **skipped** with
   `gate_skipped_missing_market_context` telemetry (fail-open; rules
   doc has the rationale).

## Sequencing for code generation (bounded slices)

1. `exchange-integration`: entities + `BaseExchange` methods + Binance
   implementation + contiguity/pagination logic + tests (fake venue with
   capped pages, retention truncation, grid gaps).
2. `persistence-data-integrity` spillover: snapshot v2 write/read +
   version negotiation + tests.
3. `strategy-framework`: `market_context` plumbing through engine +
   `requires_market_context` + neutral-on-missing semantics + tests.
4. `backtesting-validation`: replay slicing + gate INSUFFICIENT_DATA
   outcome + tests.
5. `proposal-runtime`: regime-filter consumer (own hypothesis + replay
   evidence per Phase 5.3a before any veto goes live).
