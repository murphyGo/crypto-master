# DEBT-087: Account-scoped proposal performance

- Unit: `proposal-runtime`; secondary `strategy-framework`, `sub-account-capital-segmentation`.
- Stage: Code Generation / Build and Test; corrective existing FR-036 contract.
- Requirements: FR-005, FR-011, FR-036, CON-003; stories US-005, US-009.
- Legacy context: Phase 19 sub-account storage; DEBT-070/084/085.
- Evidence: Fly v62 snapshot `fly-data-20261025T105002Z`, described in TECH-DEBT.
- Authorization: user said "3건 등록하고 수정 진행해줘" on 2026-10-25.

## Approved bounded contract

Historical performance reads must use the requested proposal account, technique,
and version at every selection, scoring, and live cold-start entry point.
Use immutable per-call scope; do not swap a shared mutable tracker account.
Respect injected data roots and default-account callers. Only closed real rows
can qualify live history; synthetic/pending rows cannot. No threshold, strategy,
applied policy, credential, or deployment changes. No write to runtime evidence.
NFR: account isolation, deterministic persisted-fixture replay, no extra remote IO.

## Steps

- [x] Correct scoped reads in `src/proposal/engine.py` and necessary tracker seam.
- [x] Test public proposal paths using persisted opposing account histories,
      versions, synthetic/pending rows, default compatibility, live cold-start.
- [x] Add composition/regression evidence for close-write to next-score-read.
- [x] Replay fixed Fly proposals using only outcomes preceding each decision.
- [x] Run targeted proposal/runtime tests, Black/Ruff, mypy and full suite.
- [x] Independent quant/QA review; record recurrence root-cause evidence.
- [x] Update debt/map/state, session log and cross-check; record not deployed.

## Decisions

Question: may source corrections and the three debt registrations proceed?
[Answer]: explicitly authorized by the user above; no further ambiguity for this
bounded correction. Live activation/deployment remains outside this task.

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
