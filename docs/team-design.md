# Crypto Master Agent Team Design

> **Runtime constraint (2026-05).** Claude Code blocks subagent nesting — a spawned subagent cannot use the `Agent` tool to spawn siblings, regardless of frontmatter. Therefore the **`team-lead` role is not a subagent**; it is played by the **parent assistant** that received the `/team` invocation. The parent reads `.claude/skills/team/team-lead-algorithm.md`, runs the algorithm, and dispatches the five specialist subagents directly. The diagram below shows the team shape; "team-lead" rows refer to the parent assistant's lead-mode behaviour.
>
> When designing future agents in this repo: **only the parent can fan out to subagents.** Anything that needs to dispatch siblings must live in the parent or in a skill the parent reads.

## Why a team

The project already has a strong, well-documented workflow (`/dev-crypto` skill: plan → research → code → test → review → session log → cross-check). One generalist Claude can run that loop, but it has to switch costume on every step. A specialised team buys three things:

1. **Sharper context** — a quant agent reads a trading PR with hypothesis-driven eyes; a docs agent reads it with audit-trail eyes; the same diff passes through different filters and catches different defects.
2. **Parallelism** — independent sub-tasks (e.g. spec writing + domain validation) can run concurrently instead of serially.
3. **Permission boundaries** — the orchestrator never edits code, the QA agent never invents requirements, the planner never ships untested code. The structure makes "scope creep" structurally hard.

## Team composition (6 agents)

| Agent | Role | Owns | Cannot |
|-------|------|------|--------|
| `team-lead` | Orchestrator. Reads project state and picks the next sub-task. Delegates and integrates. | Coordination, prioritisation, final report | Edit code, write specs |
| `product-planner` | Translates priorities into unit construction specs. Maps FR/NFR. Keeps active construction plans honest. | `aidlc-docs/construction/plans/`, `docs/requirements.md`, ADR drafts | Implement, run tests |
| `quant-trader-expert` | Trading domain expert. Validates hypotheses, robustness gates (OOS / walk-forward / regime / sensitivity), strategy code. Designs new strategies. | `strategies/`, trading correctness review of `src/{trading,backtest,strategy}/`, `docs/baselines.md` | Touch dashboard, runtime, deployment files unless trading correctness is at stake |
| `senior-developer` | Implements features following project conventions (type hints, async where needed, Pydantic, pytest). | `src/`, `tests/`, `pyproject.toml`, `.env.example` | Define product scope, write session logs |
| `qa-reviewer` | Runs `pytest`, `ruff`, `mypy`. Performs `/code-review`-style checks. Validates done-ness. | Test outputs, review verdicts | Land code without dev's involvement; rewrite features |
| `docs-auditor` | Maintains session logs, ADRs, cross-checks, `docs/TECH-DEBT.md`, change history. Performs phase-completion audits. | `docs/sessions/`, `docs/cross-checks/`, `docs/adr/`, `docs/TECH-DEBT.md` | Touch source code |

## Cycle (one sub-task per invocation, mirroring `/dev-crypto`)

```
                ┌─────────────────────────────────┐
                │            team-lead            │
                │  reads construction plans /      │
                │  TECH-DEBT /                     │
                │  cross-checks / git log,        │
                │  picks next sub-task            │
                └────────────────┬────────────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  ▼ (parallel)                  ▼
          ┌──────────────┐               ┌──────────────┐
          │product-planner│              │quant-trader- │
          │   spec it    │               │   expert     │
          │              │               │  domain      │
          │              │               │  validation* │
          └──────┬───────┘               └──────┬───────┘
                 │                              │
                 └──────────────┬───────────────┘
                                ▼
                       ┌────────────────┐
                       │senior-developer│
                       │   implements   │
                       └───────┬────────┘
                               ▼
                       ┌────────────────┐
                       │  qa-reviewer   │
                       │ pytest / ruff  │
                       │ /code-review   │
                       └───────┬────────┘
                               ▼
                       ┌────────────────┐
                       │ docs-auditor   │
                       │ session log,   │
                       │ TECH-DEBT,     │
                       │ ADR if needed, │
                       │ cross-check    │
                       │ on phase done  │
                       └───────┬────────┘
                               ▼
                       ┌────────────────┐
                       │   team-lead    │
                       │ final summary  │
                       └────────────────┘
```

\* `quant-trader-expert` is only invoked when the work touches trading correctness (strategies, backtester, robustness gates, risk params). For pure infra tasks (e.g. log retention, env override) the lead skips it.

## File ownership (who writes what)

```
team-lead          → no writes (delegates)
product-planner    → aidlc-docs/construction/plans/
                     docs/requirements.md (rare; needs explicit approval)
                     docs/adr/NNNN-*.md (drafts; auditor finalises)
quant-trader-expert→ strategies/**.{py,md}
                     docs/baselines.md
                     review-only on src/{trading,backtest,strategy}
senior-developer   → src/**, tests/**, pyproject.toml, .env.example
qa-reviewer        → no writes (verdicts only; surfaces issues for dev to fix)
docs-auditor       → docs/sessions/**, docs/cross-checks/**, docs/TECH-DEBT.md
                     aidlc-docs/construction/plans/ updates
                     docs/adr/**.md (finalisation)
```

When ownership overlaps, the writer of last resort is the agent listed first above. If the lead detects a write outside this map, it surfaces a "scope drift" warning in the final report.

## Communication protocol

Every delegated agent returns a **structured report** to the lead:

```
## <agent-name> report

### What I did
- bullet 1
- bullet 2

### Files changed (or proposed)
- path/to/file — one-line description

### Open questions / blockers
- (or "none")

### Recommended next agent
- (or "back to team-lead")
```

The lead aggregates these into a final user-facing report. The format intentionally mirrors the existing session-log structure so the auditor can lift it almost verbatim.

## Stop conditions

Lead halts the cycle and asks the user when:

- A trading-correctness call has competing valid interpretations (two reasonable hypotheses, can't tell which the user wants).
- A sub-task touches **live trading**, **API keys**, **deployment config**, or **money sizing** — these always need explicit human go-ahead per `NFR-012` and the project's existing safety posture.
- `qa-reviewer` reports red-line failures the dev couldn't resolve in one round-trip.
- A phase is about to complete and the cross-check would surface ≥1 gap — the user decides whether to ship or close gaps first.

## Why six and not four

The user's original ask was 팀장 / 기획자 / 트레이더 전문가 / 개발자 (4). The two additions:

- **`qa-reviewer`** — the existing workflow has a hard quality gate (`/code-review`, full pytest suite, ruff). Folding this into the developer means the developer reviews their own work, which is a known anti-pattern. Pulling it out matches how the project already operates.
- **`docs-auditor`** — session logs, ADRs, cross-checks, TECH-DEBT, change history are all first-class artefacts in this repo (every phase has them). They follow distinct templates and a missed update breaks the `/dev-crypto` health-check. A specialised owner avoids the drift.

If you want a leaner team, `qa-reviewer` could fold into `senior-developer` (worse but tolerable) and `docs-auditor` could fold into `team-lead` (acceptable — the lead already has read access to everything). The 6-agent shape is the recommendation; the 4-agent shape is the fallback.
