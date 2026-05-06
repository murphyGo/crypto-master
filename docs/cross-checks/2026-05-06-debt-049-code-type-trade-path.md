# Cross-Check: DEBT-049 Code-Type Trade Path

## Scope

Verify that code-type auto-research integration coverage now exercises a real
trade-producing backtest path, not only strategy load and neutral analysis.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Code-type fixture emits a trade-producing signal | Complete | `TRADE_PRODUCING_PYTHON_STRATEGY` returns one `long` signal with valid SL/TP. |
| Real Backtester opens/closes a trade | Complete | `test_code_type_pick_produces_backtest_trade_without_claude_analyze` captures the baseline `BacktestResult` and asserts `total_trades >= 1`. |
| Generated strategy remains reloadable | Complete | The test reloads the saved `.py` file through `load_strategy`. |
| Per-bar Claude hot path remains bypassed | Complete | The test asserts `ClaudeCLI.analyze.call_count == 0`. |
| Update debt and AI-DLC maps | Complete | `docs/TECH-DEBT.md` resolves DEBT-049; `aidlc-docs/inception/units/debt-unit-map.md` removes it from active debt. |

## Implementation Evidence

- `tests/test_scripts_auto_research_candidates.py`
- `docs/TECH-DEBT.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/construction/plans/ai-feedback-loop-code-generation-plan.md`
- `aidlc-docs/construction/plans/backtesting-validation-code-generation-plan.md`

## Test Evidence

- `uv run pytest tests/test_scripts_auto_research_candidates.py -q`
- Result: passing.

## Gaps and Risks

- The robustness gate is stubbed in this integration test to keep scope on the
  code-type trade path. Robustness gate behavior remains covered by
  `tests/test_backtest_validator.py`.

## Unit and Debt Mapping

- **Primary Unit**: `ai-feedback-loop`
- **Secondary Unit**: `backtesting-validation`
- **Related Debt**: DEBT-049 resolved
- **Legacy Phase Context**: Phase 17.5 code-type steering
