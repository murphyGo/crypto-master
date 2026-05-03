---
name: dev-crypto
description: Continue Crypto Master development using the brownfield AI-DLC unit map.
---

# Crypto Master Development Skill

Develop Crypto Master incrementally using the brownfield AI-DLC overlay.

## Arguments

- `$ARGUMENTS` - Optional target override:
  - empty: choose the next appropriate unit from `aidlc-docs/aidlc-state.md`
  - `<unit>`: work in a specific unit, such as `proposal-runtime`
  - `<unit> <task>`: work in a specific unit with a short task description

## Objective

Plan, implement, test, and document one bounded change at a time. Existing
Phase 1-26 work is considered brownfield-complete; new work is tracked by unit
instead of by extending the legacy chronological plan blindly.

## Required Context

Read these files before choosing or executing work:

1. `AGENTS.md`
2. `aidlc-docs/aidlc-state.md`
3. `aidlc-docs/inception/units/unit-of-work.md`
4. `aidlc-docs/inception/units/legacy-phase-map.md`
5. `aidlc-docs/inception/plans/execution-plan.md`
6. `docs/requirements.md`
7. `docs/TECH-DEBT.md`
8. `DESIGN.md`
9. `CLAUDE.md`

Use `docs/development-plan.md` as historical context. Do not rewrite it unless
the task explicitly updates legacy plan status.

## Execution Steps

### Step 1: Select Unit

If `$ARGUMENTS` names a unit, use it. Otherwise infer the unit from the user's
task and the path ownership table in `unit-of-work.md`.

Present:

```markdown
## Development Target

**Unit**: `<unit>`
**Task**: <short task summary>
**Related Requirements**: FR/NFR IDs if known
**Likely Files**: paths
**Tests**: targeted test list
```

Proceed without asking for confirmation unless the task is ambiguous or risky.

### Step 2: Plan the Change

For behavior or contract changes, create or update a short construction note
under `aidlc-docs/construction/<unit>/`. For narrow code fixes, a session log is
enough.

Check whether the change needs:

- Functional design
- NFR requirement/design notes
- Infrastructure design
- Code/test changes
- Cross-check
- Technical debt update

### Step 3: Implement

- Keep application code in the workspace root, never inside `aidlc-docs/`.
- Preserve existing runtime data and live trading safeguards.
- Prefer existing patterns in `src/`.
- Add or update targeted tests with the change.
- Avoid unrelated refactors.

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

### Step 6: Report

Summarize changed files, tests, documentation, and any remaining risks.

## Brownfield Rules

- Do not delete or migrate `data/` as part of normal development.
- Do not replace Claude CLI integration with API calls unless requirements
  change.
- Keep exchange and live-trading changes conservative and well-tested.
- Keep `docs/development-plan.md` as historical chronology; new planning should
  cite units.
