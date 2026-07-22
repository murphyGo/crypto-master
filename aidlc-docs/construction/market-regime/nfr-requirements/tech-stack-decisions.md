# Tech Stack Decisions: Funding+OI Crowding Filter

| Concern | Decision | Rationale |
|---|---|---|
| Domain model | Frozen Pydantic models | Matches normalized derivatives and policy contracts |
| Numeric math | `Decimal` | Preserves exact normalized rates/OI values |
| Percentile | Stdlib deterministic nearest-rank | No dependency or interpolation drift |
| Runtime input | Existing `MarketContextProvider` / `MarketContext` | No duplicate fetch/cache path |
| Telemetry | Existing `ActivityEventType` and JSONL log | Operator-visible and already retained |
| Dashboard | Existing pure read-model + pandas pattern | Matches market-regime page architecture |
| Evidence | Existing proposal replay and Snapshot-v2 replay identities | Reuses sealed deterministic surfaces |
| Dependencies | None added | Current stack is sufficient |

No external API, database, queue, cache server, or credential is needed.
