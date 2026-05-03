# Crypto Master Agent Team

## Runtime Model

`/team-lead` is a skill, not a subagent. The parent assistant reads
`.agents/skills/team-lead/SKILL.md`, acts as the lead, and delegates directly to
the specialist agents in `.agents/agents/`.

## Roster

| Agent | Role | Primary Responsibility | Writes |
|-------|------|------------------------|--------|
| `team-lead` | Orchestrator skill | Select one task, delegate, integrate, stop after one cycle | No direct writes unless acting outside strict lead mode for a user-approved correction |
| `product-planner` | Planner | Turn fuzzy work into a unit construction task | `aidlc-docs/construction/plans/`, design notes |
| `quant-trader-expert` | Trading domain expert | Validate strategies, backtests, robustness, risk, paper/live semantics | `strategies/`, trading docs when delegated |
| `senior-developer` | Implementer | Implement approved code/test/script/config changes | `src/`, `tests/`, `scripts/`, config examples |
| `qa-reviewer` | Independent verifier | Test, lint, type-check, review the diff | None |
| `docs-auditor` | Audit trail owner | Session logs, cross-checks, TECH-DEBT, AI-DLC state | `docs/sessions/`, `docs/cross-checks/`, `docs/TECH-DEBT.md`, `aidlc-docs/` |

## Delegation Map

| Task Signal | Specialists |
|-------------|-------------|
| Ambiguous request or missing construction plan | `product-planner` |
| Strategy, backtest, robustness, risk, PnL, leverage, paper/live semantics | `quant-trader-expert` |
| Source/test/script/config implementation | `senior-developer` |
| Implementation completed | `qa-reviewer` |
| Cycle completed or debt/cross-check/session update needed | `docs-auditor` |

## Operating Rules

- One `/team-lead` invocation handles one bounded task.
- New work uses AI-DLC units and `aidlc-docs/construction/plans/`.
- `docs/development-plan.md` is not an active queue.
- The team stops for live credentials, deployment config, API keys, mainnet
  money sizing, QA red findings, and unresolved trading interpretation choices.
- The user decides whether to commit, push, deploy, or run another cycle.
