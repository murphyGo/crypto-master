# Phase 17 Cross-Check: Strategy Evolution Operator Workflow

**Date**: 2026-04-29
**Phase**: 17 - Strategy Evolution Operator Workflow
**Status**: All one sub-task complete (17.1)

## Scope

The strategy-evolution stack (`StrategyImprover` → `Backtester` →
`PerformanceAnalyzer` → `RobustnessGate` →
`FeedbackLoop._run_cycle` → `CandidateRecord`) shipped with Phase
5.5 in 2026-04-25 and has been unit-tested in isolation since, but
no caller has ever exercised the full chain on Fly —
`/data/feedback/state/` and `/data/audit/` were empty in
production, and `src/main.py` only carried a FR-026 placeholder
comment. At the same time the operator built a research catalog
under `docs/research/strategies/` (priority matrix +
per-strategy briefs covering ICT/SMC, chart patterns,
breakout-range, mean-reversion, trend indicators, and crypto-specific
techniques) that the existing `StrategyImprover._build_new_idea_prompt`
didn't see, so Claude regenerated from-scratch ideas every time
instead of picking from the curated OHLCV-only first-wave list.
Phase 17 is a one-sub-task closure phase: 17.1 closes both gaps
without introducing scheduling or auto-promotion. (a) Catalog
injection: `_build_new_idea_prompt` reads
`docs/research/strategies/00-priority-matrix.md` and injects it
under a `## Reference Catalog` section so Claude has the full
taxonomy in context. (b) Operator entry point:
`scripts/auto_research_candidates.py` reads the priority matrix's
first-wave OHLCV-only Top-N picks, dispatches each through
`improver.generate_idea` → `loop.propose_new`, and lands every
robustness-gate-passing result in `AWAITING_APPROVAL` for explicit
operator approval per CON-003. Promotion stays manual; nightly
auto-execution is deferred to a later phase.

The phase added **no new functional or non-functional requirements**;
the development plan's Requirements Mapping table records Phase 17
against requirements that were originally introduced in earlier
phases — Phase 17 either extends them (FR-023 catalog awareness, FR-026
end-to-end exercise) or operationalises them (FR-034 robustness
gate as part of the operator-driven candidate path, CON-003 explicit
operator approval preserved):

- **FR-023** — New Technique Idea Generation. 17.1 makes
  `StrategyImprover.generate_idea` catalog-aware: the new-idea path
  reads the priority matrix and injects it under a `## Reference
  Catalog` section so Claude picks from the curated OHLCV-only
  taxonomy instead of regenerating from scratch.
- **FR-026** — Automated Feedback Loop. 17.1 is the first end-to-end
  exercise of the loop on a real (operator-driven) trigger:
  `improver.generate_idea` → `loop.propose_new` →
  `RobustnessGate` → `CandidateRecord` writes to
  `/data/feedback/state/` and `/data/audit/`. Nightly automation is
  deferred; the operator entry point closes the gap that the loop
  has shipped but never been exercised.
- **FR-034** — Robustness Validation Gate. 17.1 routes every Phase 17
  candidate through the existing `RobustnessGate` (OOS / walk-forward
  / regime / sensitivity). Note: sensitivity gate `SKIPPED` for every
  Phase 17.1 candidate because `loop.propose_new` is called without
  a `param_grid` — recorded as DEBT-014 (Medium); the OOS /
  walk-forward / regime gates run normally and the per-tf candle
  defaults (1h: 4380, 15m: 8760 per quant Issue 1) ensure the
  regime gate sees both bull and bear instead of a single-direction
  tape.
- **CON-003** — User Approval Required. 17.1 deliberately stops at
  `AWAITING_APPROVAL`; promotion to `active` requires the operator
  to call `FeedbackLoop.approve()` separately (or use the existing
  Phase 7.4 dashboard feedback page). No auto-promotion logic in
  17.1.

17.1 was added based on the operator-curated catalog under
`docs/research/strategies/` (created out-of-cycle as a planning
artefact) and the standing observation that Phase 5.5's
`FeedbackLoop` had shipped but `/data/feedback/state/` was empty in
production. The phase is bounded to the operator-driven entry point
and the catalog-awareness extension; nightly scheduling, dashboard
trigger UX, and auto-promotion all explicitly deferred. Phase 17 is
a compact one-sub-task phase that closes the operator-driven path
end-to-end and seals in this cycle.

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 17.1 | Auto-Research Operator Workflow + Catalog-Aware Improver (FR-023, FR-026, FR-034, CON-003) | `scripts/auto_research_candidates.py` (new, 561 lines — argparse entry point with `--picks N` (default 5) and `--dry-run` flags. Reads `docs/research/strategies/00-priority-matrix.md`'s first-wave OHLCV-only Top-N picks (declared as `TOP_PICKS: list[Pick]`), dispatches each through `improver.generate_idea(context=<pick description>)` → `loop.propose_new(...)`, persists `data/research_runs/run_{ts}.json` snapshot, prints operator-facing summary with per-pick `decision_reason` + `robustness_summary` continuation lines. `--dry-run` short-circuits before the loop call and routes generated experimental files under `strategies/experimental/dry_runs/`. Per-tf candle defaults: 1h=4380, 15m=8760 per quant Issue 1. `run_async(...)` accepts `loop=None` / `exchange=None` (constructs its own when absent — DEBT-013). Per-pick try/except boundary so one pick failing does NOT abort the batch.). `src/ai/improver.py` (extended — `__init__` accepts `catalog_path: Path \| None = None` defaulting to `docs/research/strategies/00-priority-matrix.md`; new `_load_catalog` helper reads the file at most once per improver lifetime, fail-softs on missing path with `logger.info(...)` + empty string; new `_catalog_section` wrapper; `_build_new_idea_prompt` injects catalog under `## Reference Catalog` section; `_build_user_idea_prompt` and `_build_improvement_prompt` deliberately skip injection per quant Issue 4 + the original "improvement is failure-mode analysis" principle). | `tests/test_ai_improver.py` (extended — new `TestCatalogInjection` class: `test_catalog_injected_in_new_idea` / `test_catalog_not_in_user_idea_prompt` (regression guard for the Issue-4 deviation) / `test_catalog_absent_graceful` (missing path → INFO log + empty section + prompt still builds) / `test_catalog_not_in_improvement_prompt` (regression guard). Existing-test churn for the new `catalog_path` constructor kwarg.) `tests/test_scripts_auto_research_candidates.py` (new, 403 lines — full mocked Binance + Claude CLI coverage: end-to-end happy path with N=2 picks both reaching `AWAITING_APPROVAL` (run snapshot written + stdout summary correct); `--dry-run` generates strategy files but skips `_run_cycle`; one pick raises and the other completes (batch does NOT abort, errored pick recorded in snapshot)). State-file / audit-log persistence under `/data/feedback/state/` and `/data/audit/` is owned by `src/feedback/loop.py` + `src/feedback/audit.py` and pinned by those modules' own test suites. — total +19 net (1170 → 1189) |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-023 | New Technique Idea Generation | ✅ Complete (extended) | 17.1 makes `StrategyImprover.generate_idea` catalog-aware. New `_load_catalog` helper reads `docs/research/strategies/00-priority-matrix.md` at most once per improver lifetime; new `_catalog_section` wrapper frames the content with `## Reference Catalog` headings; `_build_new_idea_prompt` injects the wrapped section into the prompt. `_build_user_idea_prompt` deliberately skips injection (the user has described their idea — injecting the catalog would redirect Claude away from the user's intent; deviation from original spec wording per quant-trader-expert review Issue 4, locked by `test_catalog_not_in_user_idea_prompt`). `_build_improvement_prompt` also skips (improvement is failure-mode analysis on an existing strategy, not a fresh-idea exercise). Fail-soft on missing catalog: `logger.info(...)` + empty string + prompt still builds. |
| FR-026 | Automated Feedback Loop | ✅ Complete (operationalised) | 17.1 is the first end-to-end exercise of the loop. `scripts/auto_research_candidates.py` dispatches each Top-N pick through `improver.generate_idea(context=<pick description>)` → `loop.propose_new(...)`, which runs backtest → `RobustnessGate` → state persistence → audit log. Nightly automation is deferred to a later sub-task; the operator entry point closes the previously-empty `/data/feedback/state/` and `/data/audit/` gap on Fly. Run-level snapshot written to `data/research_runs/run_{ts}.json` with per-pick `{slug, status, candidate_id, error?}`. |
| FR-034 | Robustness Validation Gate | ✅ Complete (operationalised — partial verdict) | Every Phase 17.1 candidate routes through the existing `RobustnessGate` (OOS / walk-forward / regime / sensitivity). The OOS / walk-forward / regime gates run normally; the per-tf candle defaults (1h=4380, 15m=8760 per quant Issue 1) ensure the regime gate sees both bull and bear instead of single-direction tape. ⚠️ The sensitivity gate `SKIPPED`s for every Phase 17.1 candidate because `loop.propose_new` is called without a `param_grid` — the gate's design correctly skips when no grid is supplied. Recorded as DEBT-014 (Medium); the partial-robustness-verdict consequence is a known limitation, not a blocker. The fix needs `Pick`-level parameter-grid declaration or a strategy-introspection helper. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-003 | User Approval Required | ✅ Complete (preserved) | 17.1 deliberately stops at `AWAITING_APPROVAL`; promotion to `active` requires the operator to call `FeedbackLoop.approve()` separately (or use the existing Phase 7.4 dashboard feedback page). No auto-promotion logic in 17.1. The operator entry point's stdout summary surfaces `decision_reason` + `robustness_summary` per pick so the operator has the information they need to make the approval decision without opening the JSON. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-001 / FR-002 / FR-003 | Strategy framework input contract | ✅ Complete (preserved) | The catalog-aware path operates entirely inside `StrategyImprover._build_new_idea_prompt`; the `BaseStrategy` / `ClaudeCLI` / `Backtester` boundaries are unchanged. Generated experimental strategy files comply with the existing `BaseStrategy` contract (the improver's existing prompt + Claude CLI emit a fully-formed strategy file). |
| FR-022 | Technique Improvement Suggestion (Claude) | ✅ Complete (preserved) | `_build_improvement_prompt` is left bytewise unchanged on 17.1's principle that the catalog menu is off-topic for failure-mode analysis. Phase 16.1's chasulang parse + wedge mitigation, Phase 14.1's per-strategy timeout override, and Phase 12.3's retry-on-timeout all carry through unchanged — `StrategyImprover` calls `ClaudeCLI` via `ClaudeClient` per the existing contract. |
| FR-025 / FR-027 | Backtest + Performance Analysis | ✅ Complete (preserved) | `loop.propose_new` invokes `Backtester` + `PerformanceAnalyzer` per the existing contract. Phase 9.3's multi-timeframe backtester support carries through; the improver-generated strategies use whichever timeframe their generated frontmatter declares. |

## Test Summary

- **Phase 17 tests at phase completion**:
  - 17.1: +19 net new across `tests/test_ai_improver.py` and the
    new `tests/test_scripts_auto_research_candidates.py`. Improver
    suite gains the `TestCatalogInjection` class
    (catalog-injected-in-new-idea / catalog-NOT-in-user-idea
    regression guard / catalog-absent-graceful / catalog-NOT-in-improvement
    regression guard) plus existing-test churn for the new
    `catalog_path` constructor kwarg. Script suite covers happy-path
    2-pick run / dry-run / one-pick-raises with batch continuing.
- **Full suite at phase completion**: **1189 passing, 0 failing**.
- **Lint/format**: `ruff check` clean across all Phase 17 source.
  `mypy src` clean (53 source files — preserved from Phase 12.2's
  29 → 0 baseline; no regression introduced; `scripts/` is not in
  mypy scope per spec, so the new
  `scripts/auto_research_candidates.py` typing is best-effort but
  follows the established style).

## Gaps

None blocking. The single sub-task shipped with passing tests and
clean lint/type baselines on touched files.

Three soft items worth flagging — none is a gap against the
requirements mapping table, all three are intentional choices
documented in the session log:

1. **Operator Fly verification still owed** — the script + improver
   changes are unit-tested with mocked Binance + Claude CLI, but no
   real-world run has ever exercised the full chain on Fly. The
   operator needs to invoke `flyctl ssh console --app crypto-master
   -C "python -m scripts.auto_research_candidates --picks 2"` and
   confirm: (a) at least one `CandidateRecord` lands under
   `/data/feedback/state/`, (b) at least one audit entry lands under
   `/data/audit/`, (c) the run snapshot under
   `/data/research_runs/run_{ts}.json` matches the operator-facing
   stdout summary, (d) the run snapshot's per-pick `candidate_id`
   fields cross-reference to `*.json` filenames under
   `/data/feedback/state/`. Without this, Phase 17.1 is unproven
   against the production environment it targets. Highest-priority
   operator action for the next cycle.
2. **Sensitivity gate `SKIPPED` for every Phase 17.1 candidate**
   (DEBT-014) — `loop.propose_new` is called without a
   `param_grid`, so the fourth robustness gate is `SKIPPED` per the
   gate's design. The OOS / walk-forward / regime gates still run
   and the per-tf candle defaults (1h=4380, 15m=8760) ensure the
   regime gate sees both bull and bear, but the robustness verdict
   is partial — a candidate that passes the three running gates may
   be parameter-fragile in a way that goes undetected. Surface in
   this cross-check rather than the session log because it's a
   phase-completion-relevant note about whether "passes the gate"
   means "robust": it doesn't fully, until DEBT-014 is closed.
3. **`run_async` constructs its own `FeedbackLoop` /
   `BinanceExchange`** (DEBT-013) — currently fine because `main`
   is the only caller. Cheap fix when a second caller (dashboard
   hook, scheduled job, etc.) materialises. Low-priority because no
   second caller is on the near-term roadmap.

## Risks Carried Forward

1. **Operator Fly verification of 17.1 still owed** — the operator
   needs to redeploy Fly and confirm that the script populates
   `/data/feedback/state/` + `/data/audit/` end-to-end. Highest-priority
   operator action for the next cycle.
2. **Sensitivity gate SKIP makes the robustness verdict partial**
   (DEBT-014, 17.1 introduced) — until `Pick`-level parameter-grid
   declaration (or a strategy-introspection helper) lands, every
   Phase 17.1 candidate's robustness verdict is missing the
   parameter-fragility check. Mitigated short-term by the per-tf
   candle defaults from quant Issue 1 (longer windows + bull+bear
   coverage reduce, but don't eliminate, the blind spot).
3. **`run_async` self-constructs its dependencies** (DEBT-013, 17.1
   introduced) — fine for the single-caller `main` today. Open
   when a second caller materialises.
4. **Live verification of 16.1 chasulang parse + wedge mitigation
   still owed** (16.1 carry) — the operator needs to redeploy Fly
   and confirm the `KeyError: 'signal'` log line stops appearing on
   every chasulang cycle, and any subsequent timeout terminates
   within 5s of the per-attempt timeout instead of wedging. With
   Phase 17.1 also requiring an operator Fly run, both
   verifications can be paired in a single redeploy.
5. **Live verification of Phase 14.1 chasulang 240s override still
   owed** (14.1 carry).
6. **`ENGINE_AUTO_APPROVE_THRESHOLD=0.30` Fly secret action still
   owed** (15.1 + 16.1 carry) — Phase 17.1 is orthogonal (operates
   on the candidate approval path, not the proposal execution
   path), so this carry remains outstanding regardless of 17.1.
7. **No live-engine smoke run in production yet** (10.1
   carry-forward) — the live wiring landed but the operator still
   needs to redeploy with live-mode env vars and walk the 9-step
   checklist in `docs/deployment.md` with a $100 balance before
   flipping production to live mode at real sizing.
8. **3-channel push test trade — operator action** (12.4 + 13.4
   + 14.2 carry).
9. **Per-TF RSI baselines deployed but not measured** — Phase 9.4
   shipped `rsi_4h` + `rsi_15m` but their relative performance vs
   `rsi_universal` has not been measured. Operator-runnable now via
   `scripts.backtest_baselines`.

## DEBT Closure Summary

- **Phase 17 introduced two TECH-DEBT items** (DEBT-013 Low,
  DEBT-014 Medium) and resolved none (none were active prior to the
  phase). The TECH-DEBT tracker climbs from 0 active to 2 active
  for the first time since Phase 14.2 sealed DEBT-012 on
  2026-04-28. Both are 17.1 self-disclosures from quant-trader-expert
  review Issues 3 + 5; neither blocks shipping.

Net DEBT: 0 resolved, 2 added. **Active count rises 0 → 2.**

## Recommendations for Phase 18 (or follow-up)

With two new DEBT items active and Phase 17 sealed in a single
sub-task, the next phase's shaping is driven by the session-log
"Follow-up Work" section, this cross-check's "Risks Carried
Forward", and any new operator-observed defects from the upcoming
Fly run. Candidates:

1. **Operator: run `python -m scripts.auto_research_candidates
   --picks 2` on Fly** — the primary verification action for Phase
   17.1. Watch for: (a) ≥1 `CandidateRecord` under
   `/data/feedback/state/`, (b) ≥1 audit entry under
   `/data/audit/`, (c) run snapshot under
   `/data/research_runs/run_{ts}.json` matches stdout, (d) every
   pick's robustness verdict shows sensitivity gate `SKIPPED`
   (confirms DEBT-014 in production), (e) at least one pick reaches
   `AWAITING_APPROVAL` (confirms the chain works end-to-end). If
   every pick goes `DISCARDED`, the operator should open the run
   snapshot and check `decision_reason` per pick — the reasons will
   surface whether the gate is rejecting on quality or the
   prompt/idea is the issue. Pair with the 16.1 chasulang
   verification to cut down on Fly redeploy round-trips.
2. **DEBT-014 fix (Medium priority)** — `Pick`-level parameter-grid
   declaration or a strategy-introspection helper to pass a
   `param_grid` into `loop.propose_new`. The right shape depends on
   whether the param grid lives with the pick (strategy-agnostic,
   declared in the operator's matrix) or with the strategy
   (introspection — the strategy class declares its tunable params
   and the loop reads them). Recommend the introspection approach:
   it keeps the pick declarations small and lets each strategy
   own its sensitivity surface. Trigger to pick this up: the first
   operator-driven `--picks` run that produces all-`SKIPPED`
   sensitivity verdicts (which will be every run until this is
   fixed).
3. **Operator: set `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` via Fly
   secrets** (15.1 + 16.1 carry, still standing) — orthogonal to
   17.1 but should be done in the same operator session if 16.1's
   verification is also pending.
4. **Operator: redeploy Fly to verify Phase 14.1 chasulang 240s
   override eliminates timeouts** (14.1 carry, still standing) —
   Phase 16.1's wedge mitigation is the *fallback*; reducing how
   often timeouts happen is still the better lever and lives in
   the prompt.
5. **Operator runs (still standing)**:
   - `python -m scripts.backtest_baselines` (Phase 10.3 leftover —
     fills `docs/baselines.md` reference numbers).
   - `python -m src.tools.purge_proposals` (Phase 11.4 — manual
     lever for ad-hoc retention windows).
6. **3-channel push test trade — operator action** (Phase 14.2
   carry).
7. **Per-TF RSI baseline measurement (Phase 9.4 follow-up)** —
   operator-runnable now via `scripts.backtest_baselines`.
8. **Live-mode smoke checklist execution** (10.1 carry-forward) —
   walk the 9-step checklist in `docs/deployment.md` with a $100
   balance before flipping production to live mode at real sizing.
9. **DEBT-013 fix (Low priority)** — open when a second caller of
   `run_async` materialises. Cheap fix; the signature is already
   in place to accept `loop=None` / `exchange=None`.
10. **Nightly auto-execution wiring (deferred from Phase 17.1)** —
    the operator-driven path is the floor; a scheduled
    `auto_research_candidates` invocation (cron / fly scheduled
    machine / `main.py` background task) would close the second
    half of the FR-026 "Automated" interpretation. Out of scope
    for 17.1 by design; right next step once the operator-driven
    path has been exercised on Fly enough times to trust the
    output volume.

## Cross-Check Result

- ✅ Complete: 7 requirements (3 FR + 1 CON + 3 phase-adjacent
  preserved)
- ⚠️ Partial: 0 requirements (FR-034 sensitivity-gate-SKIP is
  a known DEBT-014 limitation, not a partial cross-check verdict —
  the gate runs as designed when given a grid; 17.1 just doesn't
  supply one)
- ❌ Gap: 0 requirements

**Phase 17 closes. The development plan's Current Status table now
shows the Phase 17 row as ✅ Complete. The mainline has no
non-deferred unchecked items. Carried-forward deferrals: 7.5 Tapbit
(longstanding); nightly auto-execution wiring (deferred from 17.1
by design). The TECH-DEBT tracker climbs to 2 active items
(DEBT-013 Low, DEBT-014 Medium) — first non-empty state since
Phase 14.2's DEBT-012 closure. Recommended Phase 18 shaping above
the line: operator Fly run of the Phase 17.1 script (the
highest-value verification the project has open right now — the
chain is unproven on Fly); DEBT-014 fix to restore full
robustness-gate coverage; pair the 17.1 verification with the
standing 16.1 chasulang verification + the threshold-secret
operator action to cut Fly redeploy round-trips; the standing
operator-run set (baselines, purge tooling, 3-channel push test,
per-TF RSI measurement, live-mode smoke checklist) which remains
broadly applicable.**
