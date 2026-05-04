# Cross-Check: DEBT-026 Donchian Artefact Archive

## Scope

Verify that the truncated Donchian experimental artefact is no longer treated
as a runtime strategy candidate and that generated experimental artefact
tracking policy is explicit.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Remove truncated artefact from runtime discovery | Complete | `strategies/experimental/` now contains only `.gitkeep`; the `.md` artefact moved outside `strategies/`. |
| Preserve historical evidence | Complete | `docs/archive/strategy-artifacts/donchian_turtle_system_2_20260430_002157.truncated.md` retains the body with an evidence-only warning. |
| Clarify future generated-candidate tracking | Complete | `.gitignore` ignores generated `strategies/experimental/*.md` and `*.py` files while keeping the directory placeholder. |
| Update debt source of truth | Complete | `docs/TECH-DEBT.md` moves DEBT-026 to resolved. |
| Refresh AI-DLC debt map | Complete | `aidlc-docs/inception/units/debt-unit-map.md` removes DEBT-026 from active unit mappings. |

## Implementation Evidence

- `.gitignore`
- `docs/archive/strategy-artifacts/donchian_turtle_system_2_20260430_002157.truncated.md`
- `docs/TECH-DEBT.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/construction/plans/strategy-framework-code-generation-plan.md`

## Test Evidence

- `uv run pytest tests/test_strategy_loader.py tests/test_scripts_auto_research_candidates.py -q`
- Result: passing.

## Gaps and Risks

- Historical session logs and cross-checks still mention the old experimental
  path because they describe past runs. They should remain historical unless a
  separate audit task asks to rewrite references.

## Unit and Debt Mapping

- **Primary Unit**: `strategy-framework`
- **Secondary Unit**: `ai-feedback-loop`
- **Related Debt**: DEBT-026 resolved
- **Legacy Phase Context**: Phase 17 auto-research/code-type steering
