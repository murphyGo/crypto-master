# Cross-Check: DEBT-016/018 Runtime Counter Contract

## Scope

- **Primary Unit**: `proposal-runtime`
- **Related Debt**: DEBT-016, DEBT-018
- **Legacy Phase Context**: Phase 18.1

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-013 User Accept/Reject | Complete | Composite gate acceptance and later post-acceptance rejection are both represented in cycle counters. |
| FR-014 Proposal History Management | Complete | Rejected proposal records remain rewritten with final rejection reasons; this task does not alter persistence behavior. |
| NFR-012 Live Trading Confirmation | Complete | Post-acceptance gates can still block fills after initial accept accounting. |

## Implementation Evidence

- `src/runtime/engine.py`: `CycleResult` docstring now states
  `proposals_accepted` and `proposals_rejected` are non-exclusive stage
  counters.
- `src/runtime/engine.py`: stale-quote gate docstring now explains that the
  composite gate has already incremented accepted before rejection is recorded.
- `tests/test_runtime_engine.py`: post-acceptance rejection tests assert
  `proposals_accepted == 1` alongside rejection and zero-fill assertions.

## Test Evidence

```bash
uv run pytest tests/test_runtime_engine.py -q
uv run ruff check src/runtime/engine.py tests/test_runtime_engine.py
uv run mypy src/runtime/engine.py
```

Result: 40 passed; ruff passed; mypy passed on touched source file.

## Unit and Debt Mapping

- **Primary Unit**: `proposal-runtime`
- **Secondary Units**: None
- **Related Debt**: DEBT-016, DEBT-018
- **Legacy Phase Context**: Phase 18.1

## Gaps and Risks

- DEBT-017 remains open for stale-quote payload key cleanup.
- This task does not redesign cycle summary metrics; it documents and pins the
  existing accounting semantics.

## Recommendations

- Keep future post-acceptance gates aligned with the same counter model.
- If a dashboard summary wants mutually-exclusive final states, derive them from
  proposal records rather than `CycleResult` accepted/rejected counters.
