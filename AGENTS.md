# Crypto Master

Brownfield AI-DLC project overlay for the existing Crypto Master trading system.

## Project Purpose

Crypto Master is an automated crypto trading application with Claude CLI-assisted
strategy generation, backtesting, proposal review, paper/live trading, and
operator dashboard workflows.

This repository predates the AI-DLC overlay. Existing implementation, tests,
session logs, cross-checks, and technical debt records must be treated as source
of truth unless a current task explicitly updates them.

## Quick Commands

| Skill | Purpose | Example |
|-------|---------|---------|
| `/dev-crypto` | Continue unit-oriented development | `/dev-crypto` |
| `/team-lead` | Run the AI-DLC specialist team for one bounded cycle | `/team-lead "resolve DEBT-047"` |
| `/code-review` | Review changed code | `/code-review git` |
| `/tech-debt` | View or promote debt items | `/tech-debt aged` |
| `/cross-check` | Verify implementation vs requirements | `/cross-check proposal-runtime` |

## Key Files

| File | Purpose |
|------|---------|
| `aidlc-docs/aidlc-state.md` | Brownfield AI-DLC state and unit progress |
| `aidlc-docs/inception/requirements/` | Canonical AI-DLC FR/NFR index and verification questions |
| `aidlc-docs/inception/user-stories/` | Personas and AI-DLC story map for future work |
| `aidlc-docs/inception/application-design/` | Canonical component, service, dependency, and story-to-unit design |
| `aidlc-docs/construction/` | Active construction-stage plans and artifacts for new work |
| `aidlc-docs/construction/plans/` | Per-unit construction plan queue |
| `aidlc-docs/inception/units/unit-of-work.md` | Functional unit breakdown of existing and future work |
| `aidlc-docs/inception/units/legacy-phase-map.md` | Mapping from legacy phases/components to AI-DLC units |
| `aidlc-docs/inception/units/debt-unit-map.md` | Mapping from active technical debt to AI-DLC units |
| `aidlc-docs/inception/plans/execution-plan.md` | Construction stage strategy per unit |
| `aidlc-docs/inception/reverse-engineering/` | Reverse-engineered current-system documentation |
| `.agents/agents/` | Codex specialist agent prompts used by `/team-lead` |
| `.agents/skills/team-lead/` | Codex team-lead skill and orchestration algorithm |
| `docs/AGENT-TEAM.md` | Team roster, ownership, and delegation map |
| `docs/requirements.md` | Existing FR/NFR requirements and traceability |
| `docs/development-plan.md` | Pointer to archived legacy plan; not an active queue |
| `docs/legacy/development-plan.md` | Archived chronological development plan |
| `DESIGN.md` | Existing architecture document |
| `CLAUDE.md` | Existing project guide and commands |
| `docs/TECH-DEBT.md` | Active and resolved technical debt registry |
| `docs/sessions/` | Implementation session logs |
| `docs/cross-checks/` | Phase and unit compliance reports |

## Development Workflow

1. Check `aidlc-docs/aidlc-state.md` for current unit status.
2. Use `aidlc-docs/inception/requirements/requirements.md` and
   `aidlc-docs/inception/user-stories/stories.md` to identify the FR/NFR and
   story context for the task.
3. Use `aidlc-docs/inception/application-design/unit-of-work-story-map.md` and
   `aidlc-docs/inception/units/unit-of-work.md` to identify ownership,
   related requirements, legacy phase history, and likely test scope.
4. Use `aidlc-docs/inception/units/legacy-phase-map.md` when a task references
   an old phase, component, session log, or cross-check.
5. Use `aidlc-docs/inception/units/debt-unit-map.md` when a task starts from
   debt, cleanup, risk, or backlog language.
6. Create or resume active work in `aidlc-docs/construction/plans/` and write
   stage artifacts under `aidlc-docs/construction/<unit>/`.
7. Keep `docs/legacy/development-plan.md` as the archived chronological legacy
   plan. Do not flatten or rewrite its history when creating unit-oriented work.
8. For new work, update the relevant unit state, construction plan, tests, session log,
   cross-check, and technical debt record as appropriate.

## Brownfield Constraints

1. Preserve existing runtime behavior unless the task explicitly changes it.
2. Do not overwrite `docs/requirements.md`, `docs/legacy/development-plan.md`,
   `DESIGN.md`, or `CLAUDE.md`; update them intentionally and narrowly.
3. Treat `data/` as runtime/operator data. Do not migrate or delete it during
   AI-DLC overlay work.
4. Keep Claude integration on the CLI path (`claude -p`) unless requirements
   are explicitly changed.
5. Keep exchange credentials and live trading controls conservative. Live mode
   must fail fast for missing credentials and require explicit operator intent.
6. Prefer additive migrations and compatibility shims for existing paper/live
   trading state.

## Quality Bar

- Run targeted tests for any changed unit.
- Run `uv run pytest` for broader changes when practical.
- Run `uv run black` / ruff-compatible formatting for Python changes.
- Record significant decisions in session logs; create ADRs only for durable
  architecture choices.
- Link gaps to `docs/TECH-DEBT.md` instead of leaving untracked TODOs.
