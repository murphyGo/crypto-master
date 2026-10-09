# Business Logic Model: Bounded Dashboard Data Loading

**Status:** Operator-approved Functional Design (`진행시켜`, 2026-10-09); DEBT-083.

**Goal:** Show usable trading and runtime state without making page loading
proportional to all accumulated event payloads.

## Existing Behavior to Preserve

Paper/live mode and aggregate/sub-account selection remain explicit. Position,
equity, PnL, safety-score thresholds, incident windows, reconciliation decisions,
and proposal rejection definitions keep their current meanings. Rendering
uses persisted operator data and does not call exchanges or execute trades.

## Query Classes

| Query | Result needed | Coverage contract |
|-------|---------------|-------------------|
| Latest reconciliation | Latest successful health report or later health-check failure; matching detail rows | Search retained sources independently of the incident window. Preserve current UTC timestamp selection and stable equal-timestamp handling. |
| Latest cycle | Most recent cycle state, start time, and required terminal/summary events | Preserve cycle grouping, including a cycle beginning before the recent window. |
| Recent safety/incidents | Existing 24-hour safety inputs and bounded incident display rows | Preserve event counts and deduplication over the declared window; limit display rows separately from aggregate correctness. |
| Recent history/detail | Existing selected window and visible page/detail limits | Explicit ordering, paging, scope, and completeness; truncating rows cannot silently truncate totals. |
| Historical aggregates | Lifetime threshold rejection count, trade/PnL totals, or a selected funnel aggregate | Preserve metric period and exactness; use bounded aggregate state rather than storing every rich record. |
| Portfolio state/curve | Latest snapshot per account and selected historical equity view | Home aggregate equity sums the latest snapshot per account; preserve each existing consumer's summary contract. Curve limits/downsampling must be disclosed. |

## Read Flow

1. Determine page, mode, account scope, query class, selected time window, and
   required fields before loading payloads.
2. Consult a bounded shared read cache and its source coverage. A cache hit
   is reusable only for the same query meaning and valid source generation.
3. Obtain the required projection within a reader work budget. Select and
   validate relevant payloads before allocating rich event/history models.
4. Return the data with coverage, source freshness, and any read limitation.
5. Reuse current pure business builders for complete results, or equivalent
   projection builders verified against them.
6. Render incomplete results explicitly. Independently available trades and
   snapshots can render even if runtime activity is unavailable.

A limited input list passed to an existing full-history builder does not
automatically preserve its meaning. NFR Design must account for each field
the builder depends on, including lifetime counts and latest-state events.

## Page Integration Inventory

| Consumer | Required integration |
|----------|----------------------|
| Trading | Latest reconciliation and detail first; independent trade/snapshot state; exact historical summary and threshold metric; no repeated snapshot parsing for the curve. |
| Home | Latest cycle, existing recent safety/incident rollups, current exposure/snapshots, and a reused 24-hour funnel projection. |
| Engine | Latest cycle, bounded cycle/timeline display, reconciliation, regime/risk state, and correctly labeled aggregate coverage. |
| Ops | Existing diagnostic windows and latest relevant failure/state projections. |
| Proposal Funnel | Windowed/lifetime proposal rollups plus bounded gate detail; the standalone page reads activity, while Home's caption reads proposals only and must not enumerate all rich proposal models. |

Legacy non-dashboard consumers can retain the full-history API. New dashboard
queries must not implement their budget by calling that API first.

## Error and Recovery Flow

Budget exhaustion, oversized input, or a read error returns a partial or
unavailable result. A prior complete cached result may be displayed as stale
with its source time and coverage; it must not replace the failing source with
fresh-looking values. A cold restart has no such prior cache, so its bounded
bootstrap and degraded-state behavior must be specified before code generation.

Infrastructure recovery is a separate work item: changing memory or restarting
the shared VM affects the engine. A successful health GET proves shell health,
not full Home/Trading data readiness or debt closure.
