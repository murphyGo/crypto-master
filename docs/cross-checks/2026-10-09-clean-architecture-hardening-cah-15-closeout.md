# Cross-Check: clean-architecture-hardening CAH-15 Closeout

## Scope

Cross-check of the post-Slices-1/2 coupling re-measurement, explicit Slice 3
NO-GO decision, and CAH-15 terminal-state reconciliation. No application code
was generated for this closeout.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| NFR-001 Python 3.10+ | Complete, unchanged | No executable or dependency change; current pytest and mypy gates pass. |
| FR-011/FR-012 proposal selection | Complete, unchanged | `TradingEngine` retains the existing hardcoded proposal gate order and implementation. |
| FR-026 runtime/validation loop | Complete, unchanged | The proposal-to-execution path and its six-cache cycle reset remain on the engine. |
| NFR-012/CON-003 explicit live intent | Complete, unchanged | No live gate, confirmation, configuration, deployment, or execution behavior changed. |
| AI-DLC governance | Complete | Plan, ADR, decision artifact, state, audit history, session, and cross-check agree on the terminal status. |

## Story Matrix

| Story | Status | Evidence |
|-------|--------|----------|
| US-015 | Complete | The revalidation is routed through `clean-architecture-hardening`, a bounded closeout plan, explicit stage, and verification artifacts. |
| US-016 | Complete | ADR 0001, current code metrics, construction plan, state, session, and cross-check trace the final decision. |

## Implementation Evidence

- Slices 1 and 2 remain shipped as `SnapshotRecorder` and `PositionMonitor`.
- Current `TradingEngine` measurement: 4,787 lines and 64 methods.
- `_handle_proposal`: 388 lines, 19 direct engine calls, and 39 transitively
  reachable engine methods.
- The reachable graph reads 19 non-method dependencies, including six
  per-cycle caches, `_mark_price_cache`, and `_operator_freeze_active`.
- The six-cache reset remains atomic and engine-owned.
- No `ProposalGateChain`, pipeline, registry, `GateContext`, or cache facade was
  introduced.

## Test Evidence

- This closeout is documentation/design-only; no new executable test target was
  created.
- Current working-tree targeted suites: 292 passed.
- Final working-tree full suite: 2,604 passed in 46.50s; independent team
  verification also passed 2,604.
- Black: 222 files clean; Ruff: all checks passed; mypy: 114 source files clean.
- Lock and whitespace checks pass; repository `data/` is unchanged.

## Gaps and Risks

- No blocking implementation gap remains. Slice 3 is a completed NO-GO
  decision, not deferred work.
- `TradingEngine` remains large, but the residual proposal concern is coupled
  by load-bearing order and shared cycle state. Relocation alone would not
  improve that constraint and would increase live-money change risk.
- Reopening is allowed only as a new bounded task with evidence of reduced
  coupling or a concrete correctness/testability benefit.

## Unit and Debt Mapping

- **Primary Unit:** `clean-architecture-hardening`
- **Secondary Units:** `proposal-runtime`, `trading-core`, `quality-governance`
- **Related Debt:** None active; no new debt
- **Legacy Phase Context:** Phase 8 runtime and post-Phase-26 architecture hardening

## Recommendations

**PASS.** Accept ADR Alternative C as the final CAH-15 boundary, mark the epic
complete, and do not implement `ProposalGateChain` under the existing finding.
