# Logical Components: Bounded Dashboard Data Loading

**Status:** NFR Design approved 2026-10-09. Names below describe design
responsibilities; implementation details and remaining gaps are recorded under
`code/bounded-data-loading/`.

## Ownership and Contracts

| Component / likely location | Responsibility |
|-----------------------------|----------------|
| Query/result contracts, `src/dashboard/read_models.py` | Frozen query identity, source/window evaluation, per-section completeness/freshness and immutable projections. |
| Process service, `src/dashboard/data_service.py` | Locked singleton factory, one worker, global cache/reducer/manifest budgets, admission/coalescing, cancellation and test reset/close seam. |
| Bounded source readers, persistence utilities / additive runtime IO primitives | Bounded JSONL/JSON-object/JSON-array iteration and readonly path discovery; preserve existing full-history public APIs for non-UI consumers. |
| Activity reducers, dashboard read-side code | Latest reconciliation/cycle, recent safety/risk/regime, cycle/lifetime counters and bounded timeline/detail. |
| History reducers, dashboard read-side code | Proposal funnel/threshold, ledger/open positions/trade summary, latest snapshots/equity/curve and candidate/audit detail needed by Home. |
| Page adapters and availability rendering, `src/dashboard/pages/` | Preserve controls, pure builder meaning, scoped data and independently valid sections; explicit stale/partial/unavailable presentation. |

Source lookup uses the same legacy/default/account compatibility as current
trackers, but excludes their mkdir/write side effects from render. Do not
move all IO into a page or bypass persistence seams used by tests.

## Query Identity and Publication

Identity includes resolved data root, query kind/projection version, mode,
account scope, selected period, ordering/detail options and an explicitly
supplied evaluation time where relevant. Normal page requests share the
currently valid result's recorded evaluation epoch (at most 2s), rather than
creating a new cache key for every timestamp/millisecond. Tests/replay with
an explicit time use that exact time.

The service returns a result with data, requested/captured source coverage,
evaluation time, actual source timestamps and a stable reason. Capture is a
bounded per-file view, not a transactional whole-engine snapshot. Publication
checks relevant generations and owned budgets; only valid complete results
enter the complete cache. Partial progress and stale fallback have separate
status and cannot silently overwrite complete state.

### Consumer-Specific Semantics to Preserve

| Field/consumer | Current source contract |
|----------------|-------------------------|
| Trading threshold rejection count | Global eligible proposal history; currently not filtered by selected mode/account. |
| Home 24h funnel caption | Global proposal-only summary; no activity read or selected mode/account argument. |
| Trading reconciliation banner | Whole-runtime health report, displayed before account selection. |
| Home safety/incident rows | Current selected-account/global inclusion and existing safety helper rules. |
| Home actionable-events card | Existing unscoped `count_actionable_events(events)` counts the displayed incident slice, capped at 10; it is not an uncapped total. |
| Home aggregate equity | Sum latest snapshot per selected account. |
| Trading aggregate summary | Existing `build_summary_metrics()` chooses a single latest snapshot from combined inputs; it does not currently sum account equities. |

These are explicit parity boundaries, not claims that every inherited metric
is ideal. Global fields must not accidentally acquire an account filter, and
display-limited counters must not silently become new totals. Any financial
or scope correction needs its own approved semantic change; complete and
incomplete coverage must not be confused with changing metric meaning.

## Activity Reduction and Ordering

1. Enumerate the current effective retained paths, including legacy sources,
   without altering archives. Canonical file rank matches the legacy reader's
   path order; each record has a file/line ordinal.
2. Read captured prefixes in bounded blocks. Handle UTF-8 across boundaries,
   the partial final append, corrupt rows and oversized lines explicitly.
3. Normalize/validate one relevant event at a time using existing UTC/model
   behavior. Latest selection uses maximum UTC timestamp and the earliest
   original source ordinal on equal timestamps, matching current stable
   ordering/`max()` behavior. Do not sort all raw events.
4. Reconciliation retains the latest report/failure candidate and required
   detail within its budget, independently of safety-window membership.
5. Cycle reducers store compact state: earliest start, earliest terminal
   event, any-error flag, totals and relevant companion-rejection identity
   state. The current terminal/error rules are preserved even when event
   order is interleaved. Recent cycle rows do not replace lifetime counters.
6. Preserve genuine-rejection rules within each cycle: advisory handling,
   all non-advisory rejected events, and companion suppression when a sibling
   `PROPOSAL_REJECTED` shares the id. Recent safety has its own existing
   account/cycle/gate/reason deduplication; do not reuse the wrong dedup scope.
7. Keep exact recent-window descriptors and latest-per-type/account risk,
   regime and Ops diagnostic fields within bounded cardinality/byte state.
   The current 24h cutoff behavior and global/account inclusion remain the
   parity reference. Every independent reducer reports coverage if its keys
   or required payload cannot fit.

## Proposal, Ledger and Snapshot Reduction

- Iterate eligible proposal files with bounded discovery/metadata rather
  than `ProposalHistory._iter_record_paths()` returning all paths and rich
  `list_all()` records. Match legacy/account lookup and archive exclusion.
- Validate one proposal at a time; use the current funnel classification and
  `decision_at`/`created_at` inclusive-window semantics. Total/by-strategy/
  by-account counts and Trading's exact threshold-pattern count have bounded
  reducers. Same-id replacement invalidates aggregates instead of adding a
  duplicate. DEBT-086 classification changes are not part of this algorithm.
- Stream trade/snapshot JSON arrays using a bounded incremental parser;
  reject invalid separators/trailing content and cap a single object's bytes.
  A full JSON array decoded first and filtered afterward is disallowed.
- Trade reducers keep complete open-position data, exact financial summary
  fields under their existing definitions, and the newest 25 history rows.
  If valid open positions exceed the cap, disclose incomplete coverage and
  never claim no positions. Required source values keep Decimal semantics.
- Snapshot reducers select latest UTC timestamp per account and preserve
  each consumer's existing equity, source freshness and mark selection. Reuse the same
  snapshot read for metrics/curve. At most 4096 curve points may be displayed;
  if reduced, retain per-bucket extrema and first/latest points in timestamp
  order, label the curve sampled, and never use it to compute exact totals.
- Bound Home candidate/evidence and Feedback audit drilldowns under the same
  query principles; a candidate-specific filter after full audit materialization
  is not an acceptable hidden fallback for qualified page readiness.

## Integration and Compatibility

| Page | Projections |
|------|-------------|
| Trading | Latest reconciliation + ledger summary/open positions + threshold count + latest/account snapshots + history/curve. |
| Home | Latest cycle + 24h safety/incident inputs + exposure/latest equity + bounded candidate summary + proposal-only 24h funnel. |
| Engine | Exact cycle/summary counters, recent cycles/durations/timeline, latest reconciliation and required risk/regime projections. |
| Ops | Path/freshness checks plus latest applicable derivative-health events; optional health URL retains its existing bounded check, outside new worker rendering. |
| Standalone Funnel | Windowed/lifetime proposal rollups and bounded activity gate samples. |

Existing pure helpers stay callable with complete fixture inputs; equivalent
reducers must pass parity tests. Adapt IO/render tests through an explicit
service/result seam; production defaults cannot quietly fall back to legacy
full-history calls when a new reader fails. Preserve existing operator action
controls and their intent gates; the read service itself is read-only.
