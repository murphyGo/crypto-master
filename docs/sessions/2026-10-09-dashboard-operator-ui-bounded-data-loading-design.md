# Session: Dashboard Bounded Data Loading Documentation

- **Date:** 2026-10-09
- **Primary unit:** `dashboard-operator-ui`
- **Secondary units:** `dashboard-operator-command-center`, `persistence-data-integrity`, `notifications-ops`
- **Stage:** Functional Design documented; subsequently approved with `진행시켜`
- **Debt:** DEBT-083 (Critical, active)

## Request and Requirement Context

The operator reported unavailable UI/indefinite Trading loading, then requested
improvement work with documentation first: `개선작업 진행해줘, 먼저 문서화부터`.
The development workflow is `.agents/skills/dev-crypto/SKILL.md` with the
Functional Design rule. References: FR-029/031/032/036/042,
NFR-003/007/008/011/012, US-012/014/020/023, and existing command-center rules.

## Evidence and Decisions

- Reused earlier in-session production diagnosis rather than repeatedly
  loading the exhausted VM. The incident artifact preserves machine/release,
  file inventory, metrics, code path, and sampling limitations.
- Guest available memory reached zero after page loading; full raw JSONL
  materialization plus validated event accumulation is the principal trigger.
  No exhausted-state process stack or kernel OOM kill was captured.
- Corrected probe provenance explicitly: the successful partial render was
  Home because the initial hash did not match deployed navigation. A direct
  Trading data render was not verified; its shared reader path is source evidence.
- Inventoried Engine, Ops, Proposal Funnel and Home's nested funnel read so a
  two-page-only repair does not leave the same archive load in another route.
- Separated latest reconciliation/cycle state, existing recent windows, and
  exact historical aggregates. A limited row list cannot replace complete
  historical inputs without preserving each metric's meaning.
- Proposed explicit incomplete/stale UI state, bounded process-wide cache and
  work, cold-start handling, and measurable memory/latency/concurrency targets.
- Numerical targets are review proposals; no performance or recovery result
  is claimed. Functional approval and later NFR/code/qualification remain open.

## Files in This Slice

- New `aidlc-docs/construction/plans/dashboard-operator-ui-bounded-data-loading-functional-design-plan.md`.
- New `aidlc-docs/construction/dashboard-operator-ui/functional-design/bounded-data-loading/`: incident evidence, sanitized metrics excerpt, business logic, rules, entities, frontend behavior.
- New this session log and the corresponding documentation-stage cross-check.
- Narrow updates to `aidlc-docs/aidlc-state.md`,
  `aidlc-docs/inception/units/debt-unit-map.md`, and `docs/TECH-DEBT.md`.

DEBT-082 Dockerfile/runbook artifacts and local Claude settings were already
dirty and changing concurrently. Those changes belong to a separate task;
this slice adds its own entries while preserving that task's current text.
The archived development plan and canonical architecture/requirements are
historical references and were not rewritten.

## Validation

Documentation validation passed: tracked and new-artifact whitespace,
relative-link resolution, sanitized JSON/source-series parity, memory-drop
samples, inventory sums, planned test-path existence, debt statistics and
traceability, and pending-stage consistency. The cross-check records the
source digest and exact values.

No application source, tests, dependency, trading setting, or runtime data
change belongs to this slice. Python tests/resource qualification are queued
for implementation, rather than reusing earlier suite results as acceptance.

## Remaining Work

The subsequent `진행시켜` approved Functional Design and the presented targets.
NFR Requirements were formalized and NFR Design drafted; see
`2026-10-09-dashboard-operator-ui-bounded-data-loading-nfr.md` for the next
checkpoint. Source recheck corrected the Home funnel description: its helper
loads proposals only, not a second activity archive. Next: approve the new NFR
Design, create the code plan, implement and qualify complete-data semantic
parity and shared-VM resource use. Infrastructure recovery/rollout requires
its own concrete action and acceptance evidence. The incident is not marked
resolved by documentation or by a passing shell-health check.
