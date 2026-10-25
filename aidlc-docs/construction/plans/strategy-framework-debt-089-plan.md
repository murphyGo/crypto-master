# DEBT-089: Funding coverage and carry sensitivity

- Unit: `strategy-framework`; secondary `strategy-tuning`, `dashboard-operator-ui`.
- Stage: approved bounded design clarification, Code Generation / Build and Test.
- Requirements: FR-005, FR-021, NFR-006/007; stories US-012, US-019.
- Legacy context: DEBT-073/084/085, derivatives-data v1 excludes funding accounting.
- Authorization: user approved the three concrete proposed fixes on 2026-10-25.

## Approved functional and NFR contract

The existing net return is fee-net, not funding-adjusted. Carry separate
`funding_coverage=unknown` and fee-net basis through evidence and observations;
legacy records must never deserialize to funded/zero-cost completeness. Current
`economic_complete` retains its fee-net/account/window meaning and existing
recommendation behavior. Present the cost boundary visibly without changing
applied policy, trade amounts, thresholds, or live gates.

Sensitivity is a pure separate result: constant adverse cost per interval times
entry notional and fractional holding intervals, requiring explicit rate and
interval assumptions. It is not historical funding or an exchange settlement
simulation. Count eligible/excluded closed real rows, validate finite positive
notional/times and nonnegative cost rate/positive interval, use actual entry
price, UTC, and exclude synthetic/pending records. Unknown inputs remain
explicit. No implicit fetch, persisted trade rewrite, or cash deduction.

## Steps

- [x] Add coverage metadata and pure carry-sensitivity helper.
- [x] Thread metadata through tuning evidence/persisted observations and report UI.
- [x] Verify old observation compatibility, incomplete inputs, exact units,
      actual fill notional, long/short common adverse scenario, no double fee.
- [x] Run targeted strategy/dashboard tests, Black/Ruff/mypy and shared full suite.
- [x] Quant/QA review and fixed-snapshot read-only sensitivity check.
- [x] Update debt/map/state, session/cross-check and recurrence analysis.

Question: should this model actual historical funding charges?
[Answer]: no; the approved proposal explicitly limits this slice to availability
and a separate reproducible sensitivity. Actual settlement accounting and new
market fetches require separately scoped work.

## Completion evidence

Source/test slice complete on 2026-10-25; not deployed. Full suite: 2,865
passed in 52.83s; changed-file Black/Ruff and 131-file mypy pass. Independent
QA/quant review and fixed-snapshot replay recorded in
`docs/sessions/2026-10-25-strategy-evidence-integrity-and-recurrence.md` and
`docs/cross-checks/2026-10-25-strategy-evidence-integrity.md`.

## Subsequent authorized rollout

The user explicitly requested separate commits/pushes, then deployment and
operational verification. All three corrections are deployed on Fly v63 /
`f0f3e52` (2026-10-26 KST): 177 runtime hashes, health and first engine cycle
pass. Deployed-method read-only checks pass; no new natural proposal/cap event
occurred in the first cycle. Full evidence and coverage limits:
`docs/sessions/2026-10-26-strategy-evidence-production-rollout.md`.
