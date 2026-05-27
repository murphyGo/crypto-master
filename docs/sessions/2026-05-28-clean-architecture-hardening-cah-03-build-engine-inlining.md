# Session: clean-architecture-hardening CAH-03 — build_engine INLINING (BEHAVIOR-PRESERVING REFACTOR)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-03 (Tier 1 quick win; `build_engine` inlining).

> THIRD unit shipped from the `clean-architecture-hardening` plan, the second of the Tier 1 quick wins
> (after the standalone Tier 0 bugfix CAH-01 and CAH-02 order-side helpers). Pure infrastructure wiring —
> no trading math — so it carried a qa-reviewer review only, no quant escalation. CAH-04…CAH-15 remain
> planned.

## Scope

CAH-03 reverses an over-decomposition in `src/main.py`: the `build_engine` factory had been split into 7
single-caller `_build_engine_*_phase` wrappers, each called exactly once from `build_engine` and nowhere
else. The decomposition added indirection without reuse — including a literal no-op
(`_build_engine_exchange_phase` = `del settings; return exchange`) and a 10-parameter pass-through
(`_build_engine_runtime_phase`). This unit inlines the 7 wrappers back into a flat `build_engine` body
(was ~336–517, now ~336–438) while keeping the seams that are genuinely reused.

The discriminating test is reuse, not size: a helper earns its existence when it has more than one caller.
The 7 inlined wrappers had exactly one caller each (`build_engine`); the 3 kept seams —
`_engine_config_from_settings`, `build_trader`, `build_notification_dispatcher` — are each also called
from `run()`, so they stay. This is the AHA / Rule-of-Three discipline the `clean-architecture-hardening`
review locked in: collapse single-caller indirection, preserve real seams.

The refactor is pure inlining: identical artifacts, identical constructor arguments, identical construction
order. The null-coalescing semantics and the order in which objects are built were verified line-by-line
against the pre-refactor body, and the 31 existing `test_main_dispatch.py` tests pass unchanged — the
behavior-preservation proof for the wiring.

## Changes — CAH-03 build_engine inlining

**`src/main.py`** (`build_engine`): the 7 single-caller `_build_engine_*_phase` wrappers inlined into a
flat `build_engine` body —

- including the literal no-op `_build_engine_exchange_phase` (`del settings; return exchange`) and
- the 10-parameter pass-through `_build_engine_runtime_phase`.

**Kept (genuinely reused — each also called from `run()`):**

- `_engine_config_from_settings`
- `build_trader`
- `build_notification_dispatcher`

No dangling `_build_engine_*_phase` references remain; the 3 kept functions retain real callers.

## Process / verdicts

senior-developer implemented → qa-reviewer 🟢. No quant escalation — pure infra wiring, no trading math,
nothing under `src/trading` / `src/backtest` / `src/strategy` touched.

### QA 🟢

qa-reviewer returned 🟢: **2250 passed, no net change** (the inlining adds and removes no tests); ruff +
mypy clean. The null-coalesce semantics and construction order were verified identical line-by-line against
the pre-refactor body. The 31 `test_main_dispatch.py` tests pass unchanged — the behavior-preservation
proof. No dangling `_build_engine_*_phase` references; the 3 kept functions
(`_engine_config_from_settings`, `build_trader`, `build_notification_dispatcher`) have real callers in
`run()`.

## Files Changed

- **Modified**:
  - `src/main.py` — inlined the 7 single-caller `_build_engine_*_phase` wrappers into a flat
    `build_engine` body (was ~336–517, now ~336–438); kept `_engine_config_from_settings`, `build_trader`,
    `build_notification_dispatcher` (each also called from `run()`). Identical artifacts, args,
    construction order.

## Key Decisions

| Decision | Rationale |
|---|---|
| Inline the 7 `_build_engine_*_phase` wrappers | Each had exactly one caller (`build_engine`) — single-caller indirection with no reuse, including a literal no-op (`_build_engine_exchange_phase`) and a 10-param pass-through (`_build_engine_runtime_phase`); collapsing them flattens the factory without losing any seam (AHA / Rule-of-Three). |
| Keep `_engine_config_from_settings` / `build_trader` / `build_notification_dispatcher` | These are genuine seams — each is also called from `run()`, so they have more than one caller and earn their existence; inlining them would create duplication. |
| Treat as behavior-preserving (zero test delta) | Identical artifacts, args, and construction order; null-coalesce semantics verified line-by-line; the 31 `test_main_dispatch.py` tests pass unchanged — no new test needed because no behavior changed. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2250 passed** (no net change from the 2250 CAH-02 baseline — pure inlining adds/removes
  no tests), 0 failed. The 31 `test_main_dispatch.py` tests pass unchanged (behavior-preservation proof
  for the wiring).
- `ruff check`: clean.
- `mypy`: clean.

## Potential Risks

- **A future seam that needs reuse must be re-extracted deliberately.** Inlining trades the named-phase
  structure for a flat factory body; if a later unit (e.g. an alternate engine assembly path) needs to
  reuse one of the inlined steps, it must re-extract a real helper rather than reach for a now-deleted
  wrapper. This is the correct trade — the wrappers had no second caller — but the construction order in
  the flat body is now the single source of truth and must be preserved by any future edit to
  `build_engine`.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-03. A Change-History row dated 2026-05-28
was added to `docs/TECH-DEBT.md` because the refactor is worth the audit trail (de-over-decomposition of a
load-bearing factory).

## Remaining Work

CAH-04…CAH-15 remain planned in `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`.
Next action: **CAH-04 (dead-code / dedup sweep, Tier 1)** — delete `analyzer._sharpe_from_returns`, hoist
`_GLOBAL_CAP_SPECS` + `_pct_of_cap` in dashboard `engine.py`, extract `_load_json_list` in
`reconciliation.py`, and point the inline `Literal["long","short"]` (point 6) at the `TradeSide` alias.

No ADR needed — CAH-03 is a focused Tier 1 quick win that inlines single-caller indirection. It introduces
no new component boundary, locks in no constraint future work must respect, and chooses between no
competing long-term designs (the inline-vs-keep call is the local AHA / Rule-of-Three judgement recorded
in the Key Decisions table). The audit value lives in the session log and the Change-History row, not in an
ADR.
