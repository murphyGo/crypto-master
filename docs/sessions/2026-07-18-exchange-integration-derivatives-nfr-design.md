# Session: exchange-integration Derivatives NFR Design

**Date:** 2026-07-18

**Unit:** `exchange-integration`

**Stage:** NFR Design

**Status:** Approved; NFR Design complete

## Scope

Converted the approved FR-046 / US-025 NFR requirements into implementation
patterns and logical components for public Binance funding/OI collection,
runtime context caching, deterministic snapshot-v2 replay, and health
observability.

## Operator decisions

The operator answered **all recommended**, selecting option (a) for Q1-Q10:

- one engine-scoped shared public context service;
- explicit per-series availability plus typed consumer requirements;
- isolated per-symbol/series circuit state;
- cycle-start batch refresh under 5s/15s deadline;
- one collector process per deployment and local 50% request budgets;
- immutable snapshot generations selected by atomic `CURRENT`;
- typed unsupported handling for non-8h funding;
- service-owned degraded/recovered transition events;
- a credential-free dedicated Binance public client and sanitized output;
- collection default off, proposal filter `off -> observe -> enforce`.

## Artifacts

- `aidlc-docs/construction/plans/exchange-integration-nfr-design-plan.md`
- `aidlc-docs/construction/exchange-integration/nfr-design/nfr-design-patterns.md`
- `aidlc-docs/construction/exchange-integration/nfr-design/logical-components.md`

## Key decisions

- Runtime last-known-good data is process-local memory only; no restart
  hydration from replay snapshots.
- `MarketContext` is reconstructed from normalized series for each `as_of`; the
  context object itself is not durably stored.
- Durable data uses immutable normalized schema-v2 generations and an atomic
  pointer. Raw Binance responses and predicted funding are never persisted.
- Data collection, proposal observation, and proposal enforcement have
  separate activation boundaries.
- Infrastructure Design remains N/A; no external component or new production
  dependency is introduced.

## Validation

- Structural checks cover ten explicit answers, ten NFR design patterns,
  thirteen logical components, DD-NFR/FR/story traceability, and required
  artifact paths.
- Markdown/whitespace validation uses `git diff --check` plus explicit checks
  for the untracked design artifacts.
- No application tests were run because this stage changes documentation only.
- No technical debt was added; excluded capabilities have explicit safe v1
  behavior and future-design boundaries.
- Cross-check remains deferred until implementation evidence exists.

## Next step

The operator approved the NFR Design with `승인, 다음단계 진행` at
2026-07-18T05:45:11+09:00. The approval audit, AI-DLC state, and parent plan
were updated; proceed to Code Generation planning for Slice 1.
