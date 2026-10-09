# Domain Entities: Bounded Dashboard Data Loading

**Status:** Operator-approved conceptual contracts (`진행시켜`, 2026-10-09); not committed Python API names.

| Entity | Fields / responsibility |
|--------|-------------------------|
| DashboardQuery | Query kind, resolved data root, mode, account scope, time window, ordering, display limit, projection version; declares the business meaning of the read. |
| ReadCoverage | Requested scope/window, checked source generations, complete/partial/unavailable status, scanned/retained counts and bytes, skipped records, termination reason. |
| DashboardReadResult | Compact projection, ReadCoverage, latest source timestamp, read time, optional stale prior complete projection; separates completeness from freshness. |
| LatestRuntimeState | Independently obtained latest reconciliation result and latest cycle projection, with source time and coverage per field. |
| WindowAggregate | Exact counters/deduplication state for a declared period, bounded visible detail, completeness; a row limit never changes the counter's period. |
| HistoricalAggregate | Lifetime/selected-period totals, source coverage/checkpoint provenance, completeness; may be unavailable during bounded bootstrap. |
| ReaderBudget | Limits on total scan work, per-record bytes, retained payload bytes/rows, elapsed work and simultaneous rebuilds; numeric limits belong to NFR Design. |
| SourceGeneration | File identity and relevant mutation/version metadata; distinguishes append, replacement, truncation and month rollover. |
| DashboardCache | Process-level ownership of bounded projections; capped bytes/entries, invalidation, eviction, and per-query rebuild coordination. No session owns a second full archive. |

One query produces one result whose data and coverage must be consumed
together. Cache refresh time cannot replace source freshness. The renderer
does not infer a complete result from an empty list.

Existing `ActivityEvent`, `TradeHistory`, `AssetSnapshot`, reconciliation
banner, and safety-score entities remain source contracts. Latest-state
projections may retain the relevant existing validated event so the current
pure builders continue to make the same decisions.

A future persistent projection is optional and requires its own additive,
versioned, atomic, restart-compatible design. No new store or runtime writer
is implemented or approved by this artifact.
