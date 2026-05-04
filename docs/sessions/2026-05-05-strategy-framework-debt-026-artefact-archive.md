# Session Log: 2026-05-05 - strategy-framework - DEBT-026 Artefact Archive

## Overview

- **Date**: 2026-05-05
- **Primary Unit**: `strategy-framework`
- **Secondary Unit**: `ai-feedback-loop`
- **Stage**: Code Generation
- **Task**: Close DEBT-026 by removing the truncated Donchian artefact from runtime strategy discovery and clarifying generated artefact tracking policy.

## Work Summary

The truncated pre-code-type Donchian artefact was moved out of
`strategies/experimental/` and into `docs/archive/strategy-artifacts/` with an
explicit evidence-only warning. `strategies/experimental/` now retains only its
`.gitkeep` placeholder, and `.gitignore` ignores generated `.md` / `.py`
candidate artefacts from future real auto-research runs.

## Files Changed

- Modified: `.gitignore`
- Moved: `strategies/experimental/donchian_turtle_system_2_20260430_002157.md` to `docs/archive/strategy-artifacts/donchian_turtle_system_2_20260430_002157.truncated.md`
- Modified: `docs/TECH-DEBT.md`
- Modified: `aidlc-docs/inception/units/debt-unit-map.md`
- Modified: `aidlc-docs/construction/plans/strategy-framework-code-generation-plan.md`
- Created: `docs/cross-checks/2026-05-05-debt-026-donchian-artefact-archive.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Archive under `docs/archive/strategy-artifacts/` | `discover_strategies(..., include_subdirs=True)` scans `.md` / `.py` under `strategies/`, so `strategies/archive/` would still be loadable. |
| Keep the truncated body as evidence | The file explains the historical failure and remains useful for audit, but is no longer a candidate strategy. |
| Ignore generated experimental `.md` / `.py` files | Auto-research candidates are runtime/operator artefacts; reviewed approval promotes them into tracked active strategies. |

## Verification

- Confirmed `strategies/experimental/` contains only `.gitkeep`.
- Confirmed the archived artefact lives outside `strategies/`.
- `uv run pytest tests/test_strategy_loader.py tests/test_scripts_auto_research_candidates.py -q`

## Code Review Results

| Category | Status |
|----------|--------|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Potential Risks

- Existing historical docs still mention the old path because they record past events. They were left intact; the new archive path and resolved debt entry are the current source for follow-up behavior.

## TECH-DEBT Items

- Resolved: DEBT-026.
