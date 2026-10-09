# CAH-15 Slice 3 Go/No-Go Revalidation

## Decision

**NO-GO.** Do not extract `ProposalGateChain`. Close CAH-15 with the shipped
`SnapshotRecorder` and `PositionMonitor` slices as its delivered scope.

## Current Evidence

The 2026-10-09 AST-based measurement of `TradingEngine` found:

- 4,787 source lines and 64 methods.
- `_handle_proposal` spans 388 lines.
- `_handle_proposal` makes 19 direct calls through `self`.
- Its in-class transitive call graph reaches 39 methods.
- That graph reads 19 non-method engine dependencies.
- Shared state includes all six atomically reset per-cycle caches,
  cross-cycle `_mark_price_cache`, and `_operator_freeze_active`.

The reset block remains a single engine-owned sequence between the once-per-
cycle operator-freeze read and cycle-start event. This satisfies ADR 0001 and
would become harder, not easier, to audit if the gate path borrowed the same
state through a large collaborator interface.

## Rule Evaluation

| Rule | Result |
|------|--------|
| Does extraction materially narrow the interface? | No; 19 state dependencies and 39 reachable methods remain. |
| Does extraction remove dynamic or configurable ordering complexity? | No; gate order must remain hardcoded. |
| Does it create independent state ownership? | No; six per-cycle caches must remain engine-owned. |
| Does it add a correctness or testability capability? | No demonstrated capability beyond relocation. |
| Is the live-money behavior-change risk proportionate? | No; gate, sizing, execution, event-shape, and cache boundaries all move. |

## Final Boundary

- `TradingEngine` remains the proposal gate-chain owner and cycle orchestrator.
- `SnapshotRecorder` remains the persistence collaborator.
- `PositionMonitor` remains the exit/watchdog collaborator.
- The six per-cycle caches and their atomic reset remain on the engine.
- No pipeline, registry, `GateContext`, or broad cache facade is introduced.
- Future reopening requires a new construction task with evidence of materially
  reduced coupling or a concrete correctness/testability problem.

No application code, behavior, dependency, deployment setting, credential,
production configuration, or runtime `data/` content changes in this closeout.
