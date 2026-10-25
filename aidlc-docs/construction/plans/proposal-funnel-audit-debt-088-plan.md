# DEBT-088: Cap-blocker monitorability semantics

- Unit: `proposal-funnel-audit`; secondary `runtime-reconciliation`.
- Stage: Code Generation / Build and Test; corrective existing operator contract.
- Requirements: FR-014, FR-036, NFR-007; stories US-012, US-023.
- Legacy context: DEBT-064/066/078; proposal-funnel cap-blocker payload.
- Authorization: "3건 등록하고 수정 진행해줘", 2026-10-25.

## Approved bounded contract

The boolean reports structural SL/TP monitorability, not completeness of the
optional forward performance link and not a guarantee of exchange availability.
Both `monitorable` and `legacy_no_perf_link` support normal monitoring;
degraded/unrecoverable remain false. Add explicit reconciliation state so
provenance is retained. Do not change caps, close behavior, history or repair data.
NFR: additive payload, no new IO, missing-data behavior remains conservative.

## Steps

- [x] Correct `_build_cap_blocker_payload` in `src/runtime/engine.py`.
- [x] Exercise normal no-link positions through real cap-rejection events and
      degraded/unrecoverable controls in focused runtime tests.
- [x] Check consumers/docs for the prior misleading boolean meaning.
- [x] Run targeted tests and formatting/type checks, then shared full regression.
- [x] Independent review and exact snapshot counterexample verification.
- [x] Update debt/map/state, session and cross-check; deployment not included.

## Completion evidence

Source/test slice complete on 2026-10-25; not deployed. Full suite: 2,865
passed in 52.83s; changed-file Black/Ruff and 131-file mypy pass. Independent
QA/quant review and fixed-snapshot replay recorded in
`docs/sessions/2026-10-25-strategy-evidence-integrity-and-recurrence.md` and
`docs/cross-checks/2026-10-25-strategy-evidence-integrity.md`.
