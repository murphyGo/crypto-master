---
name: dev-crypto
description: Execute Crypto Master brownfield AI-DLC construction work by unit.
---

# Crypto Master Development Skill

Execute Crypto Master construction work using the brownfield AI-DLC overlay.

## Arguments

- `$ARGUMENTS` - Optional target override:
  - empty: choose the next construction target from AI-DLC unit state and debt
  - `<unit>`: work in a specific unit, such as `proposal-runtime`
  - `<unit> <stage>`: work in a specific construction stage
  - `<unit> <task>`: start a new construction task for that unit

## Objective

Plan, implement, test, and document one bounded construction step at a time.
Existing Phase 1-26 work is brownfield-complete historical context. New work is
tracked under `aidlc-docs/construction/` by unit and stage.

## Required Context

Read these files before choosing or executing work:

1. `AGENTS.md`
2. `aidlc-docs/aidlc-state.md`
3. `aidlc-docs/inception/requirements/requirements.md`
4. `aidlc-docs/inception/requirements/requirement-verification-questions.md`
5. `aidlc-docs/inception/user-stories/stories.md`
6. `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
7. `aidlc-docs/inception/application-design/components.md`
8. `aidlc-docs/inception/units/unit-of-work.md`
9. `aidlc-docs/inception/units/legacy-phase-map.md`
10. `aidlc-docs/inception/units/debt-unit-map.md`
11. `aidlc-docs/inception/plans/execution-plan.md`
12. `aidlc-docs/construction/README.md`
13. `docs/requirements.md`
14. `docs/TECH-DEBT.md`
15. `DESIGN.md`
16. `CLAUDE.md`

Use `docs/legacy/development-plan.md` only as historical chronology when a task
mentions an old phase. Do not use `docs/development-plan.md` as the queue for
new work, and do not extend the archived plan with new phases unless the user
explicitly asks for legacy-plan maintenance.

## Execution Steps

### Step 1: Select Construction Target

If `$ARGUMENTS` names a unit, use it. Otherwise infer the unit from the user's
task, the canonical requirements/story map, active `docs/TECH-DEBT.md` entries,
and the path ownership table in `unit-of-work.md`. If there is no clear task,
report that no construction target is currently selected rather than mining
`docs/legacy/development-plan.md` for old phase work.

Determine the current construction stage:

1. Functional Design, if behavior, contracts, workflows, or operator semantics
   change.
2. NFR Requirements / NFR Design, if reliability, safety, data integrity,
   security, observability, latency, or runtime resilience changes.
3. Infrastructure Design, if Fly.io, credentials, processes, deployment, or
   external topology changes.
4. Code Generation, for source/test/script changes.
5. Build and Test, after code changes and before sealing the unit task.

Use `aidlc-docs/inception/plans/execution-plan.md` to decide which conditional
stages apply.

Present:

```markdown
## Development Target

**Unit**: `<unit>`
**Stage**: `<construction stage>`
**Task**: <short task summary>
**Related Requirements**: FR/NFR IDs if known
**Related Stories**: US IDs if known
**Likely Files**: paths
**Tests**: targeted test list
**Construction Plan**: `aidlc-docs/construction/plans/<unit>-<stage>-plan.md`
```

Proceed without asking for confirmation unless the task is ambiguous or risky.

### Step 2: Enter or Resume the Construction Stage

Look for the matching plan file under `aidlc-docs/construction/plans/`.

- If it does not exist, create it before touching application code.
- If it exists, resume the first unchecked `[ ]` step.
- If all steps are checked, mark the stage complete in
  `aidlc-docs/aidlc-state.md` and move to the next applicable stage.

Plan files must include:

- Unit, stage, task, related requirements, and related legacy phase/debt IDs.
- Related user stories when the work maps to a story in
  `aidlc-docs/inception/user-stories/stories.md`.
- Explicit `[ ]` steps with target files and verification commands.
- Any user questions with `[Answer]:` tags.
- A completion checklist for docs, tests, debt, cross-check, and state updates.

For design stages, load and follow the matching rule file from
`aidlc-workflows/aidlc-rules/aws-aidlc-rule-details/construction/` and write
artifacts under `aidlc-docs/construction/<unit>/<stage>/`.

For code generation, write application code in the workspace root and write
only summaries or implementation notes under
`aidlc-docs/construction/<unit>/code/`.

### Step 3: Implement

- Keep application code in the workspace root, never inside `aidlc-docs/`.
- Preserve existing runtime data and live trading safeguards.
- Prefer existing patterns in `src/`.
- Add or update targeted tests with the change.
- Avoid unrelated refactors.
- Mark a plan step `[x]` only after the implementation and targeted
  verification for that step are complete.

### Step 4: Verify

Run targeted tests first. Use broader checks when the blast radius is larger:

```bash
uv run pytest <targeted tests>
uv run pytest
uv run black src tests scripts
uv run ruff check src tests scripts
uv run mypy src
```

Record any checks not run and why.

### Step 5: Document

Create or update the relevant construction artifacts:

- `aidlc-docs/construction/plans/<unit>-<stage>-plan.md`
- `aidlc-docs/construction/<unit>/<stage>/...` for design artifacts or code
  summaries
- `aidlc-docs/aidlc-state.md` for stage/unit progress

Create a session log under `docs/sessions/YYYY-MM-DD-<unit>-<task>.md` for
substantial changes. Include:

- Unit
- Related requirements
- Files changed
- Tests/checks run
- Decisions
- Risks
- Debt added/resolved

For completed unit-level changes, create or update a cross-check under
`docs/cross-checks/`.

Do not use `docs/development-plan.md` as the progress tracker for new work.
`docs/legacy/development-plan.md` may be cited as legacy context only.

### Step 6: Report

Summarize changed files, tests, documentation, and any remaining risks.

## Brownfield Rules

- Do not delete or migrate `data/` as part of normal development.
- Do not replace Claude CLI integration with API calls unless requirements
  change.
- Keep exchange and live-trading changes conservative and well-tested.
- Keep `docs/legacy/development-plan.md` as historical chronology; new planning
  must cite units and construction plan files.
