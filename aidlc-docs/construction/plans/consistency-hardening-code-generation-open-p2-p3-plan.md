# Code Generation Plan: consistency-hardening - CH-11..CH-18 and CH-20..CH-25

## Task

Close the remaining open P2/P3 consistency-hardening backlog items requested
from the functional-design spec.

## Unit / Stage / Slice

- Unit: `consistency-hardening`
- Stage: Code Generation
- Slice IDs: CH-11..CH-18, CH-20..CH-25
- Primary owner units: `ai-feedback-loop`, `proposal-runtime`,
  `persistence-data-integrity`, `backtesting-validation`,
  `exchange-integration`, `dashboard-operator-ui`, `trading-core`

## Related Requirements

- FR-013 Support operator accept/reject decisions
- FR-014 Store proposal history and outcomes
- FR-021 Persist feedback/audit logs durably
- FR-029 Expose dashboard drillthrough workflows
- NFR-006 Maintain testable data integrity boundaries
- NFR-008 Keep runtime persistence append-safe and retention-aware

## Steps

- [x] CH-11: enforce markdown runtime-contract validation even when
      frontmatter claims `technique_type: code`.
- [x] CH-12: make `ProposalHistory.load` sub-account aware and reject
      ambiguous id-only lookups.
- [x] CH-13: make JSONL append/read loss observable and append synchronized
      per rotator instance.
- [x] CH-14: add schema-version fields to activity and audit events.
- [x] CH-15: reuse baseline serialization helpers and atomic writes.
- [x] CH-16: require at least two evaluable regimes for regime validation.
- [x] CH-17: align Binance/Bybit CCXT helper contracts.
- [x] CH-18: preserve dashboard mode/scope through drillthrough links.
- [x] CH-20: centralize dashboard query-param helpers.
- [x] CH-21: add cycle-scoped lookup cache for correlation gate paths.
- [x] CH-22: consolidate duplicated indicator helpers.
- [x] CH-23: apply ClaudeCLI environment allowlist.
- [x] CH-24: remove entry-bar phantom mark from equity curves.
- [x] CH-25: verify the listed anchors are now active runtime contracts after
      CH-06/CH-28 and require no deletion.
- [x] Run targeted tests for changed files.

## Verification

- [x] Targeted tests pass.
- [x] Formatting/lint run for changed source/test files where practical.

## Completion Checklist

- [x] Code shipped under `src/`, `scripts/`, or `strategies/`.
- [x] Tests added or updated.
- [x] Plan steps closed.
- [x] State/spec updated.
- [x] Session log written.
