# NFR Requirements Plan: Funding+OI Crowding Filter

## Context

- Unit: `market-regime`
- Stage: NFR Requirements
- Requirements: FR-045, FR-046, NFR-003, NFR-006, NFR-007, NFR-011
- Stories: US-024, US-025, US-026
- Debt: DEBT-081 unrelated

## Questions and approved recommendations

### Q1 — Runtime cost

Reuse the already-prefetched immutable `MarketContext`, perform no filter-owned
network call, and keep classification p95 below 5ms for a 90 Funding/500 OI
context. [Answer]: Approved recommended option under the 2026-07-22 autonomous
continuation directive.

### Q2 — Failure posture

Missing, stale, short, or failed context must fail open and emit one sanitized
skip event per evaluated proposal. [Answer]: Approved recommended option.

### Q3 — Security boundary

Persist only derived allowlisted values; exclude predicted Funding, raw
payloads, URLs, credentials, and exception text. [Answer]: Approved recommended
option.

### Q4 — Enforcement safety

Shadow must be behaviorally inert. Veto remains impossible without a validated
dual-lane evidence result. [Answer]: Approved recommended option.

### Q5 — Determinism

Use Decimal inputs, nearest-rank percentiles, UTC timestamps, pinned snapshot
identity, canonical config digest, and explicit seed. [Answer]: Approved
recommended option.

## Steps

- [x] Assess performance, availability, reliability, security, usability, and
  maintainability.
- [x] Record measurable requirements and tech-stack decisions.
- [x] Confirm no infrastructure or dependency change.
- [x] Hand off to NFR Design.
