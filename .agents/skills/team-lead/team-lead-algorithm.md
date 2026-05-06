# Team Lead Algorithm

The parent assistant that receives `/team-lead` acts as the team lead. Do not
spawn a `team-lead` subagent. The lead reads project state, chooses one bounded
task, delegates to specialists, integrates their reports, and stops.

## Survey Order

Read in parallel where practical:

- `AGENTS.md`
- `docs/team-priorities.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/requirements/requirements.md`
- `aidlc-docs/inception/user-stories/stories.md`
- `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- `aidlc-docs/inception/units/unit-of-work.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/inception/plans/execution-plan.md`
- `aidlc-docs/construction/plans/`
- `docs/TECH-DEBT.md`
- latest `docs/sessions/`
- latest `docs/cross-checks/`
- `git status`

## Priority Order

Pick exactly one sub-task:

1. Critical TECH-DEBT.
2. First unchecked item in `docs/team-priorities.md`.
3. Blocking gap from the latest cross-check.
4. First unchecked step in `aidlc-docs/construction/plans/`.
5. Follow-up item from the latest session log.
6. If none exist, report no actionable team task.

Always state which queue produced the task.

## Specialist Selection

| Task shape | Invoke |
|------------|--------|
| Scope is missing or ambiguous | `product-planner` |
| Trading correctness, strategy, backtest, robustness, risk, live/paper semantics | `quant-trader-expert` |
| Any code/test/script/config change | `senior-developer` |
| Any implementation landed | `qa-reviewer` |
| Any completed team cycle | `docs-auditor` |

Use independent parallel delegation when two specialists can work without
overlapping writes. Keep write ownership disjoint.

## Stop Conditions

Ask the user before proceeding when:

- The task touches live trading credentials, deployment config, API keys, or
  mainnet money sizing.
- A specialist reports a blocker.
- QA returns a red verdict that was not fixed in one handoff.
- Two valid trading interpretations compete.
- A completion cross-check surfaces a gap that needs a ship/defer decision.

## Final Report

```markdown
## Team Cycle Report

**Task picked**: <summary>
**Queue**: priorities | tech-debt | cross-check | construction-plan | session-follow-up
**Why this one**: <short rationale>
**Specialists invoked**: <roles and one-line outcomes>

### Outcome
- ...

### Files touched
- path - by <role>

### Tests
- command - result

### Open questions
- none

### Next cycle preview
<one line>
```
