# Session: clean-architecture-hardening CAH-09 — TIER 3 DASHBOARD DECOMPOSITION (PURE MODULE MOVES + BACK-COMPAT RE-EXPORTS, NO LOGIC CHANGE)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-09 (Tier 3 dashboard module decomposition: split `dashboard/pages/engine.py` into sibling panel modules [DASH-F1]; move `app.py` Home command-center to `pages/home.py` [DASH-F6]).

> NINTH unit shipped from the `clean-architecture-hardening` plan, and the SECOND of the Tier 3 module
> splits (after CAH-08 split `performance.py` / relocated replay logic). It follows the standalone Tier 0
> bugfix CAH-01, the three Tier 1 quick wins (CAH-02 order-side helpers / CAH-03 `build_engine` inlining /
> CAH-04 dead-code-dedup sweep) and the three Tier 2 method extractions (CAH-05 `_handle_proposal` finalize
> helpers / CAH-06 long-function splits / CAH-07 LSP uniform `analyze()` signatures). Like CAH-08 this unit
> is a pure Tier-3 relocation — verbatim cluster moves, zero logic change — so it carried no quant review;
> qa-reviewer alone (dashboard UI, no trading math). CAH-10…CAH-15 remain planned.

## Scope

CAH-09 is a behavior-preserving dashboard module decomposition: it splits two oversized dashboard modules
along their natural seams, moving symbol clusters verbatim and preserving every old import path via
back-compat re-exports. No logic changed; the moved bodies are byte-identical to their pre-move form
(with one documented exception in Part B — see below).

### Part A — DASH-F1: split `src/dashboard/pages/engine.py` (1864 → 705 lines)

Three cohesive panel clusters were moved **verbatim** out of `engine.py` into three NEW sibling modules:

- `src/dashboard/pages/engine_reconciliation.py`
- `src/dashboard/pages/engine_market_regime.py`
- `src/dashboard/pages/engine_cross_account_risk.py`

`engine.py` retains the cycle-aggregation / summary / sub-account-metrics helpers plus the master `render`,
and re-exports all moved public symbols. The `__all__` preserves the FULL 34-symbol public surface, so the
3 reconciliation symbols that `src/dashboard/pages/trading.py:36-40` imports from `engine.py` still resolve
from `engine.py` unchanged. The new siblings import only from `runtime/activity_log` — a one-directional
dependency, so no import cycle is introduced.

### Part B — DASH-F6: move the Home command-center to `pages/home.py`

The Home command-center (~900 lines) was moved out of `src/dashboard/app.py` (1176 → 225 lines) into a NEW
`src/dashboard/pages/home.py`. `app.py` is now a pure chassis that re-exports the Home surface (including
`ActivityLog`, which the `tests/test_dashboard_app.py` monkeypatch targets via `dashboard_app.ActivityLog`).
The one home→app back-edge — `render_command_center_links` needs `page_for_key` from `app.py` — is broken
with a **function-local lazy import**, so the module-level import graph stays acyclic. This is the single
documented byte-difference in the moved code: every other moved symbol is byte-identical, and
`render_command_center_links` differs only by exactly that lazy import.

## Process / verdicts

senior-developer implemented → qa-reviewer 🟢. No quant escalation: this is a pure Tier-3 dashboard-UI
relocation with byte-identical moved bodies (one documented lazy-import exception) and zero logic change —
no trading math, no signal / gate / sizing path touched.

### QA 🟢

qa-reviewer returned 🟢: **2258 passed, unchanged** (0 test delta — pure relocation, the existing suites
are the behavior-preservation proof); ruff + mypy clean across 95 source files. AST-compared all moved
symbols — **Part A 0 mismatches**, **Part B only `render_command_center_links` differs by exactly the
documented lazy import**. All old `engine.py` (34) + `app.py` (28) public symbols resolve via re-export.
`trading.py`'s 3 reconciliation imports + the `dashboard_app.ActivityLog` monkeypatch are intact. No import
cycle. `render_home` is registered as before.

## Files Changed

- **Created**:
  - `src/dashboard/pages/home.py` — NEW module holding the verbatim Home command-center (~900 lines) moved
    out of `app.py`; the home→app back-edge (`render_command_center_links` → `page_for_key`) is a
    function-local lazy import.
  - `src/dashboard/pages/engine_reconciliation.py` — NEW sibling holding the verbatim reconciliation panel
    cluster; imports only from `runtime/activity_log`.
  - `src/dashboard/pages/engine_market_regime.py` — NEW sibling holding the verbatim market-regime panel
    cluster; imports only from `runtime/activity_log`.
  - `src/dashboard/pages/engine_cross_account_risk.py` — NEW sibling holding the verbatim cross-account-risk
    panel cluster; imports only from `runtime/activity_log`.
- **Modified**:
  - `src/dashboard/pages/engine.py` — three panel clusters removed (now live in the three new siblings);
    keeps cycle-agg / summary / sub-account-metrics + the master `render`; re-exports all moved public
    symbols; `__all__` preserves the full 34-symbol public surface (so `trading.py:36-40`'s 3 reconciliation
    imports still resolve from here).
  - `src/dashboard/app.py` — Home command-center (~900 lines) removed (now lives in `pages/home.py`); pure
    chassis + re-exports the Home surface (incl. `ActivityLog` for the `test_dashboard_app.py` monkeypatch);
    `render_home` registered as before.

No `src/` LOGIC was touched — only the relocations + re-exports (and the single documented lazy import in
`render_command_center_links`).

## Key Decisions

| Decision | Rationale |
|---|---|
| Split `engine.py` into 3 sibling panel modules rather than one big `engine_panels.py` | The three clusters (reconciliation, market-regime, cross-account-risk) are cohesive panels with distinct concerns and distinct dependency footprints; separate siblings keep each focused and importing only `runtime/activity_log`. `engine.py` keeps the cycle-agg / summary / sub-account-metrics + master `render`. |
| Preserve the full 34-symbol public surface via `__all__` re-export from `engine.py` | `trading.py:36-40` imports 3 reconciliation symbols from `engine.py`. Re-exporting the moved symbols keeps every old import path resolving from `engine.py`, so zero importer edits were needed — the split is invisible to callers. |
| New siblings import only from `runtime/activity_log` (one-directional) | Keeps the dependency one-directional (siblings → activity_log), so no import cycle is introduced by the split. |
| `app.py` becomes a pure chassis + re-exports the Home surface (incl. `ActivityLog`) | The `tests/test_dashboard_app.py` monkeypatch targets `dashboard_app.ActivityLog`; re-exporting `ActivityLog` from `app.py` keeps that monkeypatch working and avoids touching the test. |
| Break the home→app back-edge with a function-local lazy import in `render_command_center_links` | `render_command_center_links` needs `page_for_key` from `app.py`, but `app.py` imports the Home surface from `home.py` — a module-level import would form a cycle. A function-local lazy import inside `render_command_center_links` breaks the cycle while keeping the module-level graph acyclic. This is the single documented byte-difference in the moved code. |
| Verbatim cluster moves — byte-identical bodies (one documented exception) | The whole point of a Tier-3 split is relocation without behavioral risk. Keeping the bodies byte-identical (except the documented lazy import) lets the existing suites stand as the behavior-preservation proof and keeps this out of quant scope. The qa AST compare confirmed Part A 0 mismatches, Part B only the lazy-import diff. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2258 passed (no net change from the 2258 CAH-08 baseline)**, 0 failed.
- `ruff check`: clean.
- `mypy`: clean — 95 source files.
- AST compare of all moved symbols: Part A **0 mismatches**; Part B only `render_command_center_links`
  differs, by exactly the documented function-local lazy import.
- Public-surface check: all old `engine.py` (34) + `app.py` (28) public symbols resolve via re-export;
  `trading.py`'s 3 reconciliation imports + the `dashboard_app.ActivityLog` monkeypatch intact.
- Import-graph: no import cycle (siblings import only `runtime/activity_log`; the home→app back-edge is a
  function-local lazy import). `render_home` registered as before.

## Potential Risks

- **The back-compat re-exports are the contract that keeps old import paths alive.** Dropping the
  `engine.py` re-export of any moved panel symbol would silently break callers that still import from
  `engine.py` — most concretely `trading.py:36-40`'s 3 reconciliation imports. The full 34-symbol surface
  is preserved today via the `__all__` re-export; a future cleanup that thins it must first migrate every
  importer to the canonical sibling-module path.
- **The function-local lazy import in `render_command_center_links` is load-bearing for the acyclic graph.**
  If a later edit hoists that `page_for_key` import to module level (or adds another module-level
  `app` ↔ `home` reference), it would reintroduce the home→app cycle the lazy import exists to break. The
  reason it is function-local is recorded here so a later reader understands it is deliberate, not accidental.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-09. A Change-History row dated 2026-05-28
was added to `docs/TECH-DEBT.md` for the audit trail (the second Tier 3 module split: pure verbatim cluster
moves + back-compat re-exports, byte-identical bodies modulo one documented lazy import, 0 test delta).

## Watch-items (NOT filed as DEBT)

- **`engine_cross_account_risk._latest_by` is confirmed dead code.** It is pre-existing (it was dead before
  CAH-09 and was moved verbatim with its cluster — CAH-09 introduced no new dead code). It is a candidate
  for removal in a separate cleanup sweep. Deliberately NOT filed as a DEBT item per the cycle brief —
  recorded here as a session-log watch-item only so a later reader picks it up if a dead-code sweep revisits
  the dashboard pages.

## Remaining Work

CAH-10…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-10 (Tier 4: LLMClient port + `ai/exceptions` decoupling + `prompts.py` extraction + `_run_cycle`
param object)** — the AI / feedback DIP cluster. It is trading-domain-adjacent but carries no trading math,
so quant review is optional; the lead will decide.

No ADR needed — CAH-09 is a focused Tier 3 dashboard module decomposition. It introduces no new component
boundary in the architectural sense (the moved symbols keep their existing contracts via verbatim
relocation + back-compat re-exports; callers are unaffected), locks in no new constraint future work must
respect beyond the pre-existing public symbol surface, and chooses between no competing long-term designs
(the sibling-split granularity, the `__all__` re-export, and the lazy-import cycle break are local cohesion /
back-compat judgements recorded in the Key Decisions table). The audit value lives in this session log and
the Change-History row, not in an ADR.
