# Cross-Check: Quality Governance Inception Canonicalization

## Scope

Verify that the brownfield AI-DLC overlay now exposes standard inception
requirements, user-stories, and application-design paths while preserving
existing reverse-engineering, unit maps, and legacy references.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| All FR/NFR IDs remain discoverable | Complete | `aidlc-docs/inception/requirements/requirements.md` indexes FR-001 - FR-038 and NFR-001 - NFR-012. |
| AI-DLC planning can start from standard inception paths | Complete | `aidlc-docs/inception/requirements/`, `user-stories/`, and `application-design/` now exist. |
| Brownfield source evidence remains available | Complete | `aidlc-docs/inception/reverse-engineering/`, `aidlc-docs/inception/units/`, `docs/requirements.md`, and legacy plan references remain in place. |
| New work routes through unit construction plans | Complete | `AGENTS.md`, `/dev-crypto`, `/team-lead`, and `/cross-check` now prioritize canonical inception paths and unit maps. |

## Story Matrix

| Story | Status | Evidence |
|-------|--------|----------|
| US-015 | Complete | Workflow docs require identifying story/unit/stage before implementation. |
| US-016 | Complete | Requirement, story, unit, component, and verification paths are linked through `unit-of-work-story-map.md`. |

## Implementation Evidence

- `aidlc-docs/inception/requirements/requirements.md` provides the FR/NFR and
  constraint index.
- `aidlc-docs/inception/requirements/requirement-verification-questions.md`
  provides review questions for trading safety, strategy quality, runtime,
  persistence, operations, dashboard, and governance.
- `aidlc-docs/inception/user-stories/stories.md` maps operator, strategy,
  trading-risk, operations, and governance stories to requirements and units.
- `aidlc-docs/inception/application-design/` provides component, service,
  dependency, method, and unit-story design views.
- `aidlc-docs/aidlc-state.md` records these artifacts as complete and defines
  canonical inception read order.
- `.agents/skills/` and `.claude/skills/` now read the canonical paths before
  legacy detailed documents.

## Test Evidence

- No application tests were run because no application code changed.
- Documentation validation was limited to path inspection and consistency
  review.

## Gaps and Risks

- Drift risk remains between the detailed `docs/requirements.md` text and the
  AI-DLC requirement index. Future requirement edits should update both when
  IDs, ownership, or scope change.

## Unit and Debt Mapping

- **Primary Unit**: `quality-governance`
- **Secondary Units**: all units, via requirement and story maps
- **Related Debt**: none
- **Legacy Phase Context**: Phase 23 / Phase 26 AI-DLC hygiene and
  documentation governance

## Recommendations

- Treat `aidlc-docs/inception/requirements/requirements.md` as the first-read
  index for agents.
- Treat `docs/requirements.md` as the detailed historical text until a future
  intentional migration makes the AI-DLC requirements file fully standalone.
