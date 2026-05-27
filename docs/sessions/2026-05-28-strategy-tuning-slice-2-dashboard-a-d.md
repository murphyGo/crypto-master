# Session: strategy-tuning Slice 2 — DASHBOARD APPLIED/RECOMMENDED VIEW + STRATEGY_ACTION_APPLIED EMITTER (DEBT-069(a) + (d))

Date: 2026-05-28
Units: `strategy-tuning` / `proposal-runtime` / `dashboard-operator-ui`
Stage: Code Generation
Related debt: DEBT-069(a) — dashboard view + YAML clipboard helper; DEBT-069(d) — `STRATEGY_ACTION_APPLIED` startup diff emitter.
Related requirements: FR-036, FR-037, FR-038, NFR-007, NFR-008

> Sibling to the `strategy-tuning` Slice 1 (2026-05-13) and Slice 2(e) true-profit-factor
> (2026-05-24) logs. Slice 1 shipped the state machine + recommender + runtime gate; (e)
> replaced the `_infer_profit_factor` approximation with true `gross_win_pct / gross_loss_pct`.
> This log ships the operator-facing dashboard pass — the read-only Applied/Recommended view
> with a clipboard YAML diff — plus the `STRATEGY_ACTION_APPLIED` startup diff emitter that was
> reserved as an enum value in Slice 1 but never emitted. Both sub-tasks are RENDER-ONLY /
> OBSERVABILITY-ONLY; no recommender or gate math was touched. Uncommitted on `main` at the time
> of writing; committed immediately after.

## Scope

DEBT-069(a) wires the dashboard surface (functional-design Step 4): a per-(sub-account, strategy)
table with Applied / Recommended columns + evidence summary, plus a clipboard YAML diff for the
operator-apply workflow. The write-back path is explicitly OUT OF SCOPE (resolved Open Decision) —
the operator copies the YAML diff and applies it by hand + restart. DEBT-069(d) adds the
`STRATEGY_ACTION_APPLIED` startup-time diff emitter that fires one event per prior-action → new-action
transition detected at config-reload.

This was a full team cycle: senior-developer implemented both sub-tasks; qa-reviewer returned 🟡 on a
single defect (a stale enum docstring on `STRATEGY_ACTION_APPLIED` that sketched a speculative payload
shape and cited a nonexistent test); senior-developer fixed the docstring (comment-only); the defect
resolved, leaving the cycle effectively 🟢.

## Changes — DEBT-069(a) dashboard Applied/Recommended view + YAML clipboard diff (RENDER-ONLY)

All in `src/dashboard/pages/strategies.py`:

- Pure builders `build_strategy_tuning_rows` / `build_strategy_tuning_yaml_diff` /
  `build_strategy_tuning_dataframe`, plus a `StrategyTuningRow` model and an
  `INSUFFICIENT_EVIDENCE` sentinel, plus a thin `render_strategy_tuning`.
- Wired into `render()` via optional `tuning_policy` / `tuning_sub_account_id` args (default
  disabled policy — existing callers are unaffected).
- Applied column = `policy.applied_action_for(name)`; Recommended column =
  `recommend_action(evidence, policy.thresholds_for(name))`, rendering `"—"` when the recommender
  returns `None`.
- Write-back path explicitly OUT OF SCOPE (resolved Open Decision) — the operator copies the YAML
  diff and applies by hand + restart.
- Placement decision: extended `strategies.py` (NOT a new page) because it already holds the
  `PerformanceTracker` / `FailClosedMetricsTracker` inputs the recommender needs.

## Changes — DEBT-069(d) STRATEGY_ACTION_APPLIED startup diff emitter

New module `src/runtime/strategy_action_snapshot.py`:

- `load_snapshot` (fail-soft), pure `diff_snapshots`, `save_snapshot` (via the canonical
  `src.utils.io.atomic_write_text`).

In `src/runtime/engine.py`:

- Once-per-process `_maybe_emit_strategy_action_transitions` hooked into `run_cycle` (guarded by
  `_strategy_action_diff_done`).
- `_current_applied_state_map` unions registered strategies @ the default `keep` with override keys,
  so removed-override transitions are detected.
- New `EngineConfig.strategy_action_snapshot_path` (default `data/runtime/strategy_action_snapshot.json`).
- First run with NO prior snapshot SEEDS silently (no event storm on deploy); thereafter emits one
  event per changed `(sub_account, strategy)` with details `{sub_account, strategy, prior_action,
  new_action}`.
- The emitter is wrapped fail-soft so a snapshot IO failure never crashes the cycle.

## Review

### QA 🟡 → resolved — the stale enum docstring (the docstring-contract decision)

qa-reviewer returned 🟡 on a single defect: the `STRATEGY_ACTION_APPLIED` enum docstring at
`src/runtime/activity_log.py:297-306` sketched a DIFFERENT / speculative payload
(`sub_account_id` / `prior_state` / `new_state` / `applied_by` / `evidence_snapshot`) and cited a
nonexistent test (`test_strategy_action_applied_event_payload`).

**Lead decision (the FINAL contract):** the shipped 4-key shape
`{sub_account, strategy, prior_action, new_action}` is the FINAL contract — it follows the
DEBT-069(d) spec text verbatim. The speculative `applied_by` / `evidence_snapshot` fields belong to
DEBT-069(c) (the observation store), NOT to the (d) emitter. The docstring was rewritten to match the
emitted contract and to cite the real emitter + the real test. This was a COMMENT-ONLY fix — no
behavior changed. It was fixed THIS cycle, not deferred; it is NOT filed as new open debt.

### QA — independently confirmed

qa-reviewer independently confirmed the test deltas (see Verification) and the pure/thin split on
both surfaces.

### No quant escalation

No `src/trading` / `src/backtest` / `src/strategy` math was touched — both sub-tasks read the existing
recommender / policy API only (reads, no math). No quant-trader-expert escalation required.

## Files Changed

- **Created**:
  - `src/runtime/strategy_action_snapshot.py` — `load_snapshot` (fail-soft) / pure `diff_snapshots` /
    `save_snapshot` (via canonical `atomic_write_text`) for the (d) emitter.
  - `tests/test_strategy_action_snapshot.py` — 11 snapshot tests.
- **Modified**:
  - `src/dashboard/pages/strategies.py` — (a) `build_strategy_tuning_rows` /
    `build_strategy_tuning_yaml_diff` / `build_strategy_tuning_dataframe` + `StrategyTuningRow` +
    `INSUFFICIENT_EVIDENCE` sentinel + thin `render_strategy_tuning`, wired into `render()` via
    optional `tuning_policy` / `tuning_sub_account_id`.
  - `src/runtime/engine.py` — (d) `_maybe_emit_strategy_action_transitions` (guarded by
    `_strategy_action_diff_done`) hooked into `run_cycle`, `_current_applied_state_map`, new
    `EngineConfig.strategy_action_snapshot_path`.
  - `src/runtime/activity_log.py` — comment-only: `STRATEGY_ACTION_APPLIED` enum docstring rewritten
    to the FINAL 4-key contract `{sub_account, strategy, prior_action, new_action}` + real
    emitter/test citation (the QA 🟡 fix).
  - `tests/test_dashboard_strategies.py` — 7 (a) dashboard tests.
  - `tests/test_runtime_engine.py` — 4 (d) engine tests.

## Key Decisions

| Decision | Rationale |
|---|---|
| Write-back path OUT OF SCOPE for (a) | Resolved Open Decision — operator copies the YAML diff and applies by hand + restart; (a) is render-only. |
| Extend `strategies.py`, not a new page | It already holds the `PerformanceTracker` / `FailClosedMetricsTracker` inputs the recommender needs. |
| Recommended column renders `"—"` when `recommend_action` returns `None` | Keeps the table honest about insufficient evidence rather than fabricating an action. |
| `STRATEGY_ACTION_APPLIED` FINAL contract = 4 keys `{sub_account, strategy, prior_action, new_action}` | Follows the DEBT-069(d) spec verbatim; speculative `applied_by` / `evidence_snapshot` belong to DEBT-069(c) observation store, not the (d) emitter. |
| First run with no prior snapshot SEEDS silently | Avoids an event storm on deploy — only genuine transitions emit thereafter. |
| `_current_applied_state_map` unions registered strategies @ default `keep` with override keys | So removed-override transitions are detected (a strategy reverting to default still emits). |
| Emitter wrapped fail-soft | A snapshot IO failure must never crash the cycle. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2217 passed**, 0 failed (was 2195; net **+22** = 7 (a) dashboard tests in
  `tests/test_dashboard_strategies.py` + 11 snapshot tests in `tests/test_strategy_action_snapshot.py`
  + 4 (d) engine tests in `tests/test_runtime_engine.py`).
- `ruff check src tests`: clean.
- `mypy src`: clean (90 source files).
- No `src/trading` / `src/backtest` / `src/strategy` math touched (reads of existing recommender /
  policy API only) → no quant-trader-expert escalation.

## Potential Risks

- **The dashboard view is read-only by design; the apply path is manual.** Because the write-back is
  out of scope (resolved Open Decision), an operator who reads a Recommended action and forgets to
  copy/apply the YAML diff + restart leaves Applied diverged from Recommended. This is intentional
  (the operator stays in the loop), but it means the dashboard's value depends on the operator
  acting on it — the table observes drift, it does not close it.

- **The `STRATEGY_ACTION_APPLIED` emitter is once-per-process and seeds silently on first run.** A
  deploy that loses or relocates `data/runtime/strategy_action_snapshot.json` re-seeds silently
  (no transitions emitted that cycle), so a genuine action change that coincides with a snapshot-file
  loss would not emit. The fail-soft wrapping makes this safe (never crashes), but the audit trail
  has a one-cycle blind spot across a snapshot reset. Bounded and acceptable for an observability
  signal.

## TECH-DEBT Items

DEBT-069(a) and (d) marked **SHIPPED 2026-05-28**. No NEW debt filed. The stale-docstring defect
surfaced by QA was FIXED this cycle (comment-only), NOT deferred — it is explicitly NOT filed as new
open debt. After this cycle the DEBT-069 umbrella has (b), (c), (f), (g), (i) remaining open; (e) and
the (h)-comment half already shipped (2026-05-24).

## Remaining Work

DEBT-069 umbrella remains Active for (b) initial-action seeding, (c) observation store, (f) pause-reason
split, (g) threshold calibration, and (i) funnel unit-test coverage gaps. Suggested next cycle: (b)
initial-action seeding bundles naturally with the now-shipped (a) dashboard view (it populates the
Recommended column on day one); (c) observation store would let the dashboard render trends without
re-running the recommender at every page load.

No ADR needed — both sub-tasks are render-only / observability-only. (a) extends an existing dashboard
page and reads the already-decided recommender / policy API; (d) emits an already-reserved enum value
on a transition. Neither introduces a new component boundary, chooses between competing long-term
approaches, nor locks in a constraint future work must respect. The one contract clarification (the
`STRATEGY_ACTION_APPLIED` 4-key shape) is recorded above in Key Decisions — the session log is its right
home.
