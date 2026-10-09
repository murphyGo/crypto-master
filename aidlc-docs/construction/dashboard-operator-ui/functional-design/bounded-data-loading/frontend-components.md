# Frontend Components: Bounded Dashboard Data Loading

**Status:** Operator-approved Functional Design (`진행시켜`, 2026-10-09). Existing Streamlit navigation and
paper/live/account controls remain the user flow.

## Component Responsibilities

| Component | Inputs | Visible behavior |
|-----------|--------|------------------|
| Page shell / selection controls | Existing page, mode, account and window | Appears promptly; no new trading action or configuration flow. |
| Data availability notice | ReadCoverage, source time, optional prior complete data | Identifies which section is unavailable, partial, or showing older data; gives a meaningful retry action without exposing reader internals. |
| Trading reconciliation | LatestRuntimeState | Same complete-result banner/detail semantics; older known adverse state is visibly stale; incomplete lookup never implies a healthy no-report state. |
| Trading positions and summary | Independently loaded ledger/snapshots and aggregates | Available positions continue rendering even if activity fails. Unknown metrics show an unavailable value rather than a fabricated zero. |
| Home runtime status | Latest cycle and recent complete safety rollup | Same scores/thresholds for complete inputs; incomplete evidence is explicitly unavailable rather than a fresh SAFE status. |
| Incident/timeline/funnel/history views | WindowAggregate, selected scope and visible detail | Retain selected period and ordering; disclose partial coverage or downsampling where relevant. |
| Equity display | Latest per-account snapshots and historical curve | Preserve aggregate account totals and source freshness; do not imply an exchange price refresh. |

## Interaction and State

- A selection change creates the correctly scoped query and cannot reuse
  another mode/account's result.
- Retry invalidates only the relevant bounded projection; concurrent users
  cannot trigger duplicate unbounded rebuilds.
- Complete, partial, unavailable, and stale data states remain separate from
  safety severity. A stale red report remains adverse and stale.
- Each failed section identifies the affected information. Avoid raw exception
  dumps, scan budgets, file paths, cache keys, or operational implementation
  details in the normal user flow.
- Existing page links, selected-account context, reconciliation drilldown,
  raw detail access, and paper/live labels remain available where source
  coverage permits. Form/trading validation rules are unchanged.

## UI Validation Scenarios

1. Healthy complete inputs preserve current Home/Trading metrics and banners.
2. Latest adverse reconciliation lies outside the incident window.
3. Truncated/corrupt/oversized activity input with a valid open-trade ledger.
4. Cold cache, expired cache, and a last-known adverse result during failure.
5. Paper/live, aggregate/account, and source-root switching under four sessions.
6. New monthly archive, file replacement, and a concurrent partial final append.
7. Historical aggregate unavailable while positions and latest equity remain
   available; no lifetime value is replaced by a recent sample.

This is a read-only persisted-data interface. There is no new exchange/API
integration or live execution control.
