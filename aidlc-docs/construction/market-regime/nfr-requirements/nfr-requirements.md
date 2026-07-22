# NFR Requirements: Funding+OI Crowding Filter

| ID | Requirement |
|---|---|
| CFO-NFR-001 | The filter performs no network or filesystem read on the proposal hot path; it consumes the provided `MarketContext`. |
| CFO-NFR-002 | Pure classification p95 must be <=5ms for 90 Funding and 500 OI points in deterministic local tests. |
| CFO-NFR-003 | Disabled policy adds no event, decision, persistence, order, balance, or position change. |
| CFO-NFR-004 | Shadow mode never changes proposal final state or execution behavior. |
| CFO-NFR-005 | Missing/stale/short/invalid data fails open with stable sanitized skip telemetry. |
| CFO-NFR-006 | All classification inputs are `<= as_of`; predicted Funding is excluded. |
| CFO-NFR-007 | Equal normalized inputs and policy produce byte-equivalent normalized classification/event payloads. |
| CFO-NFR-008 | Telemetry is allowlisted and excludes secrets, raw payloads, URLs, paths, and exception text. |
| CFO-NFR-009 | Evidence qualification requires proposal replay plus one pinned Snapshot-v2 generation, canonical config digest, seed, nonzero samples, and two non-unknown regime buckets. |
| CFO-NFR-010 | Dashboard shadow surfaces explicitly say `SHADOW — NOT ENFORCING` and distinguish skips from would-block decisions. |
| CFO-NFR-011 | No new dependency, service, credential, volume, worker, migration, or deployment process is introduced. |
| CFO-NFR-012 | Unit, contract, integration, security, deterministic, performance, and full repository tests must pass before sealing. |

## Availability and recovery

The OHLCV proposal path remains available during derivatives outages. Recovery
is inherited from `DerivativesContextService`; the filter owns no retry,
circuit breaker, cache, or durable context state.

## Capacity

The approved v1 bounds remain 20 symbols, 90 settled Funding observations for
the default window, and up to 500 OI observations. Event volume is at most one
crowding observation or skip per evaluated shadow proposal.

## Infrastructure applicability

Infrastructure Design is N/A. The feature is in-process, uses existing public
data already refreshed by the runtime, and changes no deployment topology.
