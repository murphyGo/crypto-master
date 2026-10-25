# Cross-check: strategy evidence integrity, DEBT-087/088/089

Date: 2026-10-25. Scope: source/tests, not deployment or strategy promotion.

| Unit / debt | Requirement / story | Implementation and actual-path evidence | Verdict |
|-------------|---------------------|-----------------------------------------|---------|
| proposal-runtime / 087 | FR-005/011/036, CON-003; US-005/009 | Explicit account history in all proposal paths and live checks; 14 persisted-history tests including production build_engine and close→next proposal; pending/synthetic excluded | Pass |
| proposal-funnel-audit / 088 | FR-014/036, NFR-007; US-012/023 | Structural monitorability includes supported no-link positions, separate taxonomy; 7 symbol/total cap event controls; actual risk/close logic unchanged | Pass |
| strategy-framework / 089 | FR-005/021, NFR-006/007; US-012/019 | Funding unknown carried from evidence to persistence/UI; legacy basis unspecified; separate input-hashed pure adverse carry CLI; 21 new regression cases | Pass within approved observability scope |
| Runtime-data preservation | NFR-007/008 | Snapshot read-only; no runtime ledger/repair/migration; all cost input hashes unchanged | Pass |
| Source / deployment distinction | CON-003 | Source-only checkpoint complete; user subsequently authorized separate commits/pushes and rollout with fresh operational verification. Applied policy remains unchanged | Rollout pending |

## Verification

- Full suite: **2,865 passed in 52.83s**.
- First full run had 2,864 passes and one `test_timeout_reaps_child_and_grandchild`
  PermissionError failure. Isolated rerun and final full rerun passed; source/test
  in that unrelated module were not changed. Failure is retained in session log.
- Changed 14 Python files: Black/Ruff clean; source mypy: 131 files clean.
- Independent QA: account isolation, default compatibility, no mutable shared
  scope, closed eligibility, and no data mutation accepted.
- Independent quant: carry timing/notional/units and unknown coverage accepted
  after mixed-account and invalid CLI token cases were fixed.
- Fixed proposal replay: MA 0→221, Raschke 0→262, RSI15m 0→224 prior real samples.
- Fixed cost replay: all 12 active accounts, 1,247 closed outcomes; actual funding
  remains unknown. Hypothetical adverse carry is not a funding-adjusted backtest.

## Traceability and remaining boundaries

- Plans: `proposal-runtime-debt-087-plan.md`,
  `proposal-funnel-audit-debt-088-plan.md`, `strategy-framework-debt-089-plan.md`.
- Evidence: `construction/proposal-runtime/code/debt-087-snapshot-replay.json`
  and `construction/strategy-framework/code/debt-089-snapshot-verification.json`
  beneath `aidlc-docs/`.
- Session and recurrence analysis:
  `docs/sessions/2026-10-25-strategy-evidence-integrity-and-recurrence.md`.
- Existing historical repairs, unknown regimes/funding and independent OOS are
  explicit research limitations, not assertions of new runtime bugs. No edge,
  strategy logic, all-cost profitability, or production correction is certified.
