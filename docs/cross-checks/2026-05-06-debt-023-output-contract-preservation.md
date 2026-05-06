# Cross-Check: DEBT-023 Output Contract Preservation

## Scope

Verify that strategy improvement generation cannot silently drop an existing
prompt runtime `## Output Contract`.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Preserve existing Output Contract heading | Complete | `StrategyImprover._validate_improvement_preserves_output_contract` requires the heading when the original source contains it. |
| Preserve runtime trade keys | Complete | The guard checks keys present in the original contract: `signal`, `entry_price`, `stop_loss`, `take_profit`, `take_profit_1`, and `take_profit_2`. |
| Prevent invalid generated files | Complete | `suggest_improvement` validates before saving; invalid generated content raises `GeneratedTechniqueError`. |
| Regression tests cover positive and negative paths | Complete | `TestImprovementOutputContract` covers preserved contract, dropped contract, and missing key cases. |
| Update debt and AI-DLC maps | Complete | `docs/TECH-DEBT.md` resolves DEBT-023; `aidlc-docs/inception/units/debt-unit-map.md` removes it from active debt. |

## Implementation Evidence

- `src/ai/improver.py`
- `tests/test_ai_improver.py`
- `docs/TECH-DEBT.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/construction/plans/ai-feedback-loop-code-generation-plan.md`
- `aidlc-docs/construction/plans/strategy-framework-code-generation-plan.md`

## Test Evidence

- `uv run pytest tests/test_ai_improver.py -q`
- Result: passing.

## Gaps and Risks

- This guard preserves the current schema. A future intentional schema migration
  should be planned explicitly so it can update parser expectations and tests in
  the same cycle.

## Unit and Debt Mapping

- **Primary Unit**: `ai-feedback-loop`
- **Secondary Unit**: `strategy-framework`
- **Related Debt**: DEBT-023 resolved
- **Legacy Phase Context**: Phase 17 auto-research workflow unblock
