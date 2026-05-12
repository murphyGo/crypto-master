# Session: four units functional-design milestone

## Unit

- `runtime-reconciliation` (primary)
- `proposal-funnel-audit` (primary)
- `cross-account-risk-policy` (primary)
- `strategy-tuning` (primary)
- Secondary units: none — design-only cycle, no implementation surface touched.

## Related Requirements

Rolled up across the four specs (per the functional-design-plan headers; the
spec bodies inherit the same coverage):

- `runtime-reconciliation`: FR-010, FR-014, FR-029, FR-036, NFR-007, NFR-008,
  NFR-012.
- `proposal-funnel-audit`: FR-011, FR-012, FR-013, FR-014, FR-015, FR-029,
  FR-043, NFR-007, NFR-012.
- `cross-account-risk-policy`: FR-036, FR-037, FR-038, FR-044, NFR-007,
  NFR-008, NFR-012.
- `strategy-tuning`: FR-001, FR-002, FR-005, FR-013, FR-027, FR-034, FR-036,
  FR-039, NFR-006, NFR-007.

No new FR or NFR entries required; every reference resolves into the existing
inception requirement index.

## Scope

Design-only milestone. Four functional-design specs landed in one cycle, each
paired with a code-generation plan that is staged but explicitly blocked on
open-decision resolution before implementation. The four functional-design
plans were ticked through completion of the design steps. No `src/` code, no
tests, no runtime artefacts touched. Commit handled by the lead.

## Output

Twelve files written or modified, grouped by deliverable:

- **Functional-design specs (NEW)** — `aidlc-docs/construction/<unit>/functional-design/spec.md`:
  - `aidlc-docs/construction/runtime-reconciliation/functional-design/spec.md`
  - `aidlc-docs/construction/proposal-funnel-audit/functional-design/spec.md`
  - `aidlc-docs/construction/cross-account-risk-policy/functional-design/spec.md`
  - `aidlc-docs/construction/strategy-tuning/functional-design/spec.md`
- **Code-generation plans (NEW, awaiting decision resolution)**:
  - `aidlc-docs/construction/plans/runtime-reconciliation-code-generation-plan.md`
  - `aidlc-docs/construction/plans/proposal-funnel-audit-code-generation-plan.md`
  - `aidlc-docs/construction/plans/cross-account-risk-policy-code-generation-plan.md`
  - `aidlc-docs/construction/plans/strategy-tuning-code-generation-plan.md`
- **Functional-design plans (ticked through design completion)**:
  - `aidlc-docs/construction/plans/runtime-reconciliation-functional-design-plan.md`
  - `aidlc-docs/construction/plans/proposal-funnel-audit-functional-design-plan.md`
  - `aidlc-docs/construction/plans/cross-account-risk-policy-functional-design-plan.md`
  - `aidlc-docs/construction/plans/strategy-tuning-functional-design-plan.md`

## Cross-unit dependencies

The four specs surfaced the following dependency map, captured here so the
next implementation cycle does not collide with already-shipped contracts:

- `runtime-reconciliation` ↔ `trading-core` (paper-trade ledger schema),
  `persistence-data-integrity` (atomic writes / `balances.json` snapshots),
  `proposal-runtime` (`performance_record_id` linkage), `notifications-ops`
  (degraded-runtime activity surface), `dashboard-operator-command-center`
  (health signal blocking silent cash-only reporting).
- `proposal-funnel-audit` ↔ `proposal-runtime` (final-state field on proposal
  records; per-gate cap diagnostics), `runtime-safety-score` (gate-pass
  accounting feeds the safety score inputs), `dashboard-operator-command-center`
  (funnel drill-down on Home), DEBT-061's `FailClosedMetricsTracker`
  (per-strategy fail-closed counts already wired; funnel reuses the tracker
  rather than duplicating).
- `cross-account-risk-policy` ↔ `sub-account-capital-segmentation` (policy
  attaches to `SubAccount`), `strategy-correlation-governor` (global symbol/side
  caps compose with correlation gating), `runtime-safety-score` (kill switches
  read safety score), `market-regime` (regime-block precedence vs. cross-account
  caps — sequencing decision is one of the seven open items).
- `strategy-tuning` ↔ `strategy-promotion-lab` (scores feed action
  recommendation), `proposal-runtime` (applied action gates emit/open),
  `sub-account-experiment-marketplace` (template can pre-declare initial
  action), `dashboard-operator-command-center` (Strategies-page surface for
  recommendation + apply).

## Open decisions inventory

Twenty-three open decisions across the four specs, breakdown per the planner
reports:

- `runtime-reconciliation`: 5 open decisions.
- `proposal-funnel-audit`: 5 open decisions.
- `cross-account-risk-policy`: 7 open decisions.
- `strategy-tuning`: 6 open decisions.

Total: 23. Implementation in the next cycle requires resolving these. The lead
may either resolve as reasonable defaults (and capture the resolution as
ratified-as-shipped in the next cycle's session log) or escalate to the user
for a decision pass before code-generation begins. The code-generation plans
are staged but explicitly blocked until that resolution lands.

## Risks

None — design-only cycle. No runtime, persistence, or test surface touched.
The risks for each unit are surfaced in the respective specs and will be
re-stated in the implementation-cycle session logs.

## Reviewer notes

- quant-trader-expert: not engaged. Spec-correctness review at design stage is
  premature; the binding behaviour lands at code-generation. Quant review will
  run per-unit at the implementation cycle when concrete thresholds, gate
  sequencing, and risk-policy math are wired.
- qa-reviewer: not engaged for the same reason. QA review attaches to code +
  tests, not to design prose.

## Next-step pointer

Lead's choice between two paths:

1. **Decision pass with the user** on the 23 open decisions — surfaces the
   highest-impact items (cross-account cap precedence, strategy-tuning evidence
   thresholds, funnel `final_state` schema) for explicit ratification before
   any code lands.
2. **Pre-resolve defaults** for the 23 open decisions using the planner-
   suggested defaults already noted in each spec, queue four sequential
   code-generation cycles (one per unit), and treat each ratification as
   resolved-as-shipped in the implementation session log.

Either path is defensible. The lead picks based on user availability and the
relative reversibility of each open item.
