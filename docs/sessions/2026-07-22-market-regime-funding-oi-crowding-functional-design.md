# Session: Funding+OI Crowding Filter Functional Design

**Date:** 2026-07-22

**Primary unit:** `market-regime`

**Secondary units:** `proposal-runtime`, `exchange-integration`,
`dashboard-operator-ui`, `proposal-replay-simulator`, `quality-governance`

**Stage:** Functional Design

**Status:** Complete; later stages closed in the shadow-release session

## Decisions

- Shadow-first; no initial veto.
- Settled Funding at the trailing 30-day nearest-rank p95/p05 extreme plus OI
  strictly above its 24-hour reference.
- Side-aware per-sub-account policy using `proposal.symbol`; disabled by
  default.
- Missing/short/stale context fails open with stable skip telemetry.
- Veto requires both proposal-history replay and pinned Snapshot-v2 backtest
  evidence, non-negative expectancy delta in both, nonzero crowding samples,
  and at least two non-unknown OHLCV regime buckets.
- Predicted Funding, raw exchange payloads, credentials, request URLs, and raw
  exception text are excluded.

## Artifacts

- `aidlc-docs/construction/market-regime/functional-design/spec.md`
- `business-logic-model.md`
- `business-rules.md`
- `domain-entities.md`
- `frontend-components.md`
- `aidlc-docs/construction/plans/market-regime-functional-design-plan.md`

## Verification

Targeted documentation consistency and traceability checks. No application,
deployment, credential, or runtime `data/` change in this stage.

## Debt

No new debt. DEBT-081 remains unrelated.

## Lifecycle continuation

NFR Requirements, NFR Design, Code Generation, Build & Test, and cross-check
continued under the operator's autonomous-continuation direction. Final
evidence is recorded in
`docs/sessions/2026-07-22-market-regime-funding-oi-crowding-shadow-release.md`.
