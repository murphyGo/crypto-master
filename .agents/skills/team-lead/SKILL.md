---
name: team-lead
description: Run the Crypto Master AI-DLC agent team through one autonomous or directed planning, implementation, QA, and documentation cycle.
---

# Crypto Master Team Lead Skill

Run one bounded team cycle for Crypto Master. The parent assistant is the team
lead and delegates directly to specialist agents under `.agents/agents/`.

## Arguments

- `$ARGUMENTS`
  - empty: autonomous mode; find the next task using the priority order
  - `<task>`: directed mode; decompose and run the requested task
  - `status`: summarize recent team/session state
  - `roster`: show the team roster from `docs/AGENT-TEAM.md`

## Objective

Coordinate specialists without losing the project's AI-DLC traceability:

1. Select exactly one task.
2. Present the task, queue source, delegation plan, expected files, and tests.
3. Proceed unless the task is ambiguous or hits a stop condition.
4. Delegate to specialists, using parallel calls when independent.
5. Integrate reports, surface blockers, and stop after one cycle.

## Required Context

Read before acting:

1. `AGENTS.md`
2. `docs/AGENT-TEAM.md`
3. `.agents/skills/team-lead/team-lead-algorithm.md`
4. `aidlc-docs/aidlc-state.md`
5. `aidlc-docs/inception/requirements/requirements.md`
6. `aidlc-docs/inception/user-stories/stories.md`
7. `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
8. `aidlc-docs/inception/units/unit-of-work.md`
9. `aidlc-docs/inception/units/debt-unit-map.md`
10. `aidlc-docs/inception/plans/execution-plan.md`
11. `aidlc-docs/construction/plans/`
12. `docs/TECH-DEBT.md`
13. `docs/team-priorities.md`

## Modes

### `roster`

Read `docs/AGENT-TEAM.md` and summarize the roster and delegation map.

### `status`

Read `aidlc-docs/aidlc-state.md`, latest session logs, latest cross-checks, and
`git status`. Summarize current team health and any in-flight work.

### Autonomous

Use `team-lead-algorithm.md` to choose the next task. Do not mine
`docs/development-plan.md`; it is only a pointer to legacy history.

### Directed

Map the user's task to a unit, applicable construction stage, and specialist
sequence using the canonical requirements, stories, and unit story map first.
If the task is risky or underspecified, ask a concise question before
delegating.

## Specialist Roster

- `product-planner`
- `quant-trader-expert`
- `senior-developer`
- `qa-reviewer`
- `docs-auditor`

Do not spawn a `team-lead` subagent. The lead role lives in this skill.

## Stop Conditions

Stop and ask the user when work touches live credentials, deployment config,
API keys, mainnet sizing, unresolved QA red findings, or competing trading
interpretations.

## Output

Use the final report format in `team-lead-algorithm.md`.
