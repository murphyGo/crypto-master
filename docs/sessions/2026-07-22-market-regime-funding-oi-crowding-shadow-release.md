# Session: Funding+OI Crowding Shadow Release

**Date:** 2026-07-22

**Primary unit:** `market-regime`

**Secondary units:** `proposal-runtime`, `exchange-integration`,
`dashboard-operator-ui`, `quality-governance`

**Stages:** NFR Requirements, NFR Design, Code Generation, Build and Test,
cross-check

**Status:** Complete; shadow release sealed; Operations N/A

## Operator direction

Exact response: `내 허락 묻지말고 계속 작`

The direction was applied as authorization to continue through the remaining
bounded construction stages with the already selected recommended options,
without repeated approval pauses. It did not authorize live trading,
deployment, credentials, production configuration, or runtime-data mutation.

## Delivered

- Deterministic settled-Funding p95/p05 plus rising-24h-OI classifier.
- Side-aware, per-sub-account, disabled-by-default shadow policy.
- Proposal-layer cached-context observation after existing earlier gates.
- Sanitized observed/skipped activity events and an honest dashboard surface.
- Fail-closed dual-lane evidence qualifier and a schema-level veto barrier.
- Functional/NFR/code/build plans, cross-check, state, and audit traceability.

## Verification

- 317 focused tests passed; classifier module coverage 91%.
- Classifier p95 0.000064s at 90 Funding/500 OI, target <=0.005s.
- 2604 complete repository tests passed in 45.09s.
- Black/Ruff pass on the 12 changed Python files.
- `mypy src` passes 114 files; lock, compile, offline import, diff, dependency,
  deployment, credential, and runtime-data scope checks pass.
- Global Black/Ruff reproduces only DEBT-081 (16/22), outside this slice.

## Decisions and boundaries

- Shadow `would_block` is telemetry, never a rejection.
- Missing/stale/short/error context fails open.
- Predicted Funding is excluded; raw payloads and error messages are never
  serialized.
- No live request, order, strategy threshold, deployment, migration,
  credential, production refresh, or repository `data/` mutation occurred.
- Infrastructure Design and Operations are N/A for this in-process slice.

## Debt

No new debt. Actual dual-lane evidence cannot exist before the shadow observer
runs; evidence accumulation and a possible veto are the next hypothesis stage,
not an incomplete part of this release.
