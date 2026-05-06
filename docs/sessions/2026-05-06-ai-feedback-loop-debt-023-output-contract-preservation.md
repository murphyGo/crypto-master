# Session Log: 2026-05-06 - ai-feedback-loop - DEBT-023 Output Contract Preservation

## Overview

- **Date**: 2026-05-06
- **Primary Unit**: `ai-feedback-loop`
- **Secondary Unit**: `strategy-framework`
- **Stage**: Code Generation
- **Task**: Close DEBT-023 by preventing improvement generations from dropping an existing runtime Output Contract.

## Work Summary

`StrategyImprover.suggest_improvement` now validates generated improvement
content before saving it. If the original strategy source contains a
`## Output Contract` block, the generated improvement must preserve that
heading and the runtime trade keys present in the original contract. Dropped
contracts or missing keys raise `GeneratedTechniqueError`, preventing invalid
prompt strategies from landing in `strategies/experimental/`.

## Files Changed

- Modified: `src/ai/improver.py`
- Modified: `tests/test_ai_improver.py`
- Modified: `docs/TECH-DEBT.md`
- Modified: `aidlc-docs/inception/units/debt-unit-map.md`
- Modified: `aidlc-docs/construction/plans/ai-feedback-loop-code-generation-plan.md`
- Modified: `aidlc-docs/construction/plans/strategy-framework-code-generation-plan.md`
- Created: `docs/cross-checks/2026-05-06-debt-023-output-contract-preservation.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Validate after parsing but before saving | The generated body needs to parse first, but invalid improvements should not be written to the experimental directory. |
| Preserve keys present in the original contract | Supports both generic `take_profit` and Chasulang-style `take_profit_1` / `take_profit_2` contracts without hard-coding one schema. |
| Raise `GeneratedTechniqueError` on violation | The improvement generation is invalid; surfacing a hard failure is safer than accepting an unparseable prompt strategy. |

## Verification

- `uv run pytest tests/test_ai_improver.py -q`

## Code Review Results

| Category | Status |
|----------|--------|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Potential Risks

- Improvements that intentionally redesign a prompt strategy's runtime schema must retain the old keys or be handled through a separate explicit migration path.

## TECH-DEBT Items

- Resolved: DEBT-023.
