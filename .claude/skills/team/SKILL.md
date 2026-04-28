# Crypto Master Team Skill

Spawns the autonomous Crypto Master agent team to advance the project by one sub-task. Use when the user wants the team to find the next thing to do and run it through plan → code → test → document.

## Arguments

- `$ARGUMENTS` — (optional)
  - Empty → team-lead picks the next sub-task itself, following its priority order: critical TECH-DEBT → `docs/team-priorities.md` open queue → cross-check gaps → dev plan → session follow-ups.
  - `phase N.M` → force the team onto a specific sub-task.
  - `from-tech-debt` → bias the lead toward escalated TECH-DEBT items first.
  - `cross-check N` → ask the auditor to run the cross-check for a completed phase.

## Ad-hoc tasks (priority queue)

For one-off requests that aren't in the dev plan ("verify why nothing's trading on Fly", "audit the auto-approve threshold against last week's data"), add a one-line item to **`docs/team-priorities.md`**. The team-lead picks the first unchecked item every cycle, processes it through the appropriate specialists, and the docs-auditor flips the box and moves it to the **Done** section with a one-line outcome.

This is the seam that makes `/loop /team` actually useful for autonomous iteration:

- Add a priority → next cycle handles it.
- Priority queue empty → cycle falls back to the dev plan.
- Add another priority mid-loop → it gets picked up on the next cycle, leapfrogging the dev plan.

You don't have to edit the file by hand — just say "add this to team priorities: <X>" and the assistant will append it for you.

## Objective

Run **one cycle** of the team:
1. `team-lead` reads project state, picks the next sub-task, and writes a brief.
2. `product-planner` (only if the spec is missing) and/or `quant-trader-expert` (only if trading correctness is at stake) provide upfront analysis — in parallel when both are needed.
3. `senior-developer` implements.
4. `qa-reviewer` runs pytest / ruff / mypy and reviews the diff.
5. `docs-auditor` writes the session log, updates TECH-DEBT, runs the phase cross-check if a phase just completed.
6. `team-lead` aggregates a final user-facing report.

The team will halt and ask the user when:
- The work touches live trading credentials, mainnet money, deployment config, or API keys.
- A phase is about to complete but the cross-check would surface a gap.
- The qa-reviewer flagged a 🔴 the dev couldn't resolve in one round.
- A trading hypothesis has competing valid interpretations.

## How to invoke

The skill is mostly a launcher. The work is:

1. **Read `docs/team-design.md`** so you (the parent assistant) understand the team shape.
2. **Spawn the `team-lead` agent** via the Agent tool, passing the user's `$ARGUMENTS` as the brief.
3. **Wait for the lead to return** its aggregated cycle report.
4. **Surface the report to the user** with no paraphrasing.
5. **Stop** — the user decides whether to commit, run another cycle, or course-correct.

## Stop conditions for the parent (you, the harness assistant)

- Don't run multiple cycles in a row autonomously. One `/team` invocation = one cycle. The user decides whether to invoke again.
- Don't commit / push / deploy. The team only edits files. The user reviews and commits.
- If the team's report ends with "Open questions for the user", relay them and wait.

## Example invocations

```
/team
```
→ team picks the next sub-task. With `docs/team-priorities.md` open queue empty, today (2026-04-28) that's Phase 10.2 EngineConfig Env Override. With one queued, it processes the queued item first.

```
/loop /team
```
→ continuous iteration. Each cycle: priority queue → dev plan → cross-check → done. User can add a priority mid-loop and it leapfrogs the dev plan on the next cycle. Loop self-paces between cycles. Stops when a user-gate trigger fires (live credentials / mainnet money / phase-completion gap / qa 🔴) — surfaces the question and waits.

```
/team phase 10.4
```
→ team works on log retention (forced sub-task overrides priority queue).

```
/team from-tech-debt
```
→ team prioritises escalated TECH-DEBT (overrides priority queue).

```
/team cross-check 9
```
→ auditor produces the Phase 9 cross-check (already exists; would refresh).

## Why this exists (vs running `/dev-crypto` directly)

`/dev-crypto` is a single-agent linear workflow. `/team` is the same workflow split across specialists, which buys:

- **Sharper review** — `qa-reviewer` reads the dev's diff cold, catching defects the author would miss.
- **Domain-aware planning** — `quant-trader-expert` won't approve a generic indicator mashup; the generalist will.
- **Parallelism** — planner and quant can work concurrently when both are needed.
- **Enforced ownership** — the orchestrator can't accidentally edit code; the dev can't accidentally rewrite specs.

For trivial sub-tasks (one-line config edit), `/dev-crypto` is faster. For anything trading-domain or phase-completing, `/team` is better.
