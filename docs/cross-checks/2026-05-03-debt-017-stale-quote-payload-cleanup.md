# Cross-Check: DEBT-017 Stale-Quote Payload Cleanup

## Scope

- **Primary Unit**: `proposal-runtime`
- **Related Debt**: DEBT-017
- **Legacy Phase Context**: Phase 18.1

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-014 Proposal History Management | Complete | Persistence behavior remains unchanged; only activity payload redundancy changed. |
| FR-015 Proposal Notification / Operator Visibility | Complete | Rejection activity events still include entry, stop, live price, and drift fields needed for post-mortem visibility. |

## Implementation Evidence

- `src/runtime/engine.py`: stale-quote rejection details no longer add
  `proposal_entry`; `_proposal_summary` continues to provide `entry_price`.
- `src/runtime/engine.py`: no-live-data rejection details follow the same
  cleanup.
- `tests/test_runtime_engine.py`: stale-quote rejection test asserts
  `entry_price` is present and `proposal_entry` is absent.

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
- **Related Debt**: DEBT-017
- **Legacy Phase Context**: Phase 18.1

## Gaps and Risks

- External consumers, if any, should use `entry_price` instead of
  `proposal_entry`.

## Recommendations

- Keep `_proposal_summary` as the source of common proposal event fields.
