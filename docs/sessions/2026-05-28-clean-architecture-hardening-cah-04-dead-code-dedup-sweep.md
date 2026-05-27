# Session: clean-architecture-hardening CAH-04 — DEAD-CODE / DEDUP SWEEP (BEHAVIOR-PRESERVING REFACTOR)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-04 (Tier 1 quick win; dead-code / dedup / type-alias sweep).

> FOURTH unit shipped from the `clean-architecture-hardening` plan, the third of the Tier 1 quick wins
> (after the standalone Tier 0 bugfix CAH-01, CAH-02 order-side helpers, and CAH-03 `build_engine`
> inlining). Four bundled behavior-preserving micro-fixes — no trading math — so it carried a qa-reviewer
> review only, no quant escalation. CAH-05…CAH-15 remain planned.

## Scope

CAH-04 bundles four independent behavior-preserving micro-fixes, each a dead-code deletion, a dedup
extraction, or a type-alias swap. Nothing under a quant surface (no trading math; no PnL / sizing /
gate / signal logic changed) — the changes are structural and type-identical.

1. **BT-F3** — deleted dead `analyzer._sharpe_from_returns` (zero call sites) and fixed the docstring
   reference to point at the live `metrics.sharpe_from_returns`.
2. **DASH-F2** — hoisted a `_GLOBAL_CAP_SPECS` constant and a `_pct_of_cap(details, total_key, limit_key)`
   helper in `dashboard/pages/engine.py`; rewired `build_portfolio_cap_utilization` and
   `_closest_global_cap` through them. The subtle drop-vs-keep-vs-None row semantics were preserved at the
   call site (not folded into the helper).
3. **RECON-F4** — extracted `_load_json_list(path, *, context) -> list` in `reconciliation.py`; rewired the
   3 fail-soft list readers through it. Distinct warning messages preserved via the `context` label;
   `_load_balance_locked` (a dict reader, not a list reader) deliberately left untouched.
4. **CAH-04b** — replaced 6 inline `Literal["long", "short"]` annotations with the existing `TradeSide`
   alias (`backtest/engine.py:235,868`; `risk_sizing.py:92`; `trade_autopsy.py:47`;
   `performance.py:824,948`) — type-identical. The `Literal["long", "short", "neutral"]` superset at
   `performance.py:87` is a genuinely wider type and was correctly left alone.

## Changes — CAH-04 dead-code / dedup sweep

**`src/backtest/analyzer.py`** (BT-F3) — deleted dead `_sharpe_from_returns` (zero call sites); docstring
ref fixed to `metrics.sharpe_from_returns`.

**`src/dashboard/pages/engine.py`** (DASH-F2) — hoisted `_GLOBAL_CAP_SPECS` constant +
`_pct_of_cap(details, total_key, limit_key)` helper; `build_portfolio_cap_utilization` +
`_closest_global_cap` rewired through them; drop-vs-keep-vs-None row semantics preserved at the call site.

**`src/runtime/reconciliation.py`** (RECON-F4) — extracted `_load_json_list(path, *, context) -> list`; 3
fail-soft readers rewired; distinct warnings preserved via `context`; `_load_balance_locked` (dict) left
untouched.

**`src/backtest/engine.py`, `src/trading/risk_sizing.py`, `src/strategy/trade_autopsy.py`,
`src/strategy/performance.py`** (CAH-04b) — 6 inline `Literal["long", "short"]` swapped to `TradeSide`
(`backtest/engine.py:235,868`; `risk_sizing.py:92`; `trade_autopsy.py:47`; `performance.py:824,948`);
type-identical; the `Literal["long", "short", "neutral"]` superset at `performance.py:87` left alone.

## Process / verdicts

senior-developer implemented → qa-reviewer 🟢. No quant escalation — no trading math; dead-code /
dedup / type-alias only.

### QA 🟢

qa-reviewer returned 🟢: **2254 passed (+4)**; ruff + mypy clean. The `TradeSide` swap confirmed
type-identical (mypy clean across the 6 sites). All 6 cap drop/keep/None cases reproduced exactly after the
DASH-F2 helper extraction. 4 new `_load_json_list` branch tests added in
`tests/test_runtime_reconciliation.py`. Scope clean.

## Files Changed

- **Modified**:
  - `src/backtest/analyzer.py` — deleted dead `_sharpe_from_returns`; docstring ref fixed to
    `metrics.sharpe_from_returns` (BT-F3).
  - `src/dashboard/pages/engine.py` — hoisted `_GLOBAL_CAP_SPECS` + `_pct_of_cap` helper; rewired
    `build_portfolio_cap_utilization` + `_closest_global_cap`; preserved drop/keep/None row semantics at
    the call site (DASH-F2).
  - `src/runtime/reconciliation.py` — extracted `_load_json_list(path, *, context) -> list`; rewired 3
    fail-soft readers; distinct warnings preserved via `context`; `_load_balance_locked` left untouched
    (RECON-F4).
  - `src/backtest/engine.py` — `Literal["long", "short"]` → `TradeSide` at lines 235, 868 (CAH-04b).
  - `src/trading/risk_sizing.py` — `Literal["long", "short"]` → `TradeSide` at line 92 (CAH-04b).
  - `src/strategy/trade_autopsy.py` — `Literal["long", "short"]` → `TradeSide` at line 47 (CAH-04b).
  - `src/strategy/performance.py` — `Literal["long", "short"]` → `TradeSide` at lines 824, 948;
    `Literal["long", "short", "neutral"]` at line 87 left alone (CAH-04b).
  - `tests/test_runtime_reconciliation.py` — 4 new `_load_json_list` branch tests.

## Key Decisions

| Decision | Rationale |
|---|---|
| Delete `analyzer._sharpe_from_returns` rather than wire it up | Zero call sites; the live implementation is `metrics.sharpe_from_returns`. Dead code with a stale docstring ref — delete and re-point the docstring. |
| Keep the drop-vs-keep-vs-None row semantics at the DASH-F2 call site, not in `_pct_of_cap` | The helper computes a percentage; the row-inclusion decision (drop / keep / emit None) is call-site policy and folding it into the helper would couple presentation logic to the math. All 6 cases reproduced exactly. |
| Leave `_load_balance_locked` out of the RECON-F4 extraction | It reads a dict, not a list — `_load_json_list` is list-shaped only. Distinct warning text preserved across the 3 list readers via the `context` parameter. |
| Swap only the exact `Literal["long", "short"]` pairs to `TradeSide`; leave the `["long","short","neutral"]` superset | The 6 swapped sites are byte-for-type-identical to the alias; the `performance.py:87` superset is a genuinely wider type and must not be narrowed. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2254 passed (+4 from the 2250 CAH-03 baseline)**, 0 failed. The +4 are the new
  `_load_json_list` branch tests in `tests/test_runtime_reconciliation.py`.
- `ruff check`: clean.
- `mypy`: clean (confirms the 6 `TradeSide` swaps are type-identical).

## Potential Risks

- **The DASH-F2 helper extraction must keep the drop/keep/None semantics at the call site.** The
  percentage math now lives in `_pct_of_cap`, but the row-inclusion policy stayed at the call site
  deliberately. A future edit that pushes that policy into the helper would change which rows the dashboard
  emits — the 6 reproduced cases are the regression boundary to respect.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-04. A Change-History row dated 2026-05-28
was added to `docs/TECH-DEBT.md` for the audit trail (a four-item dead-code / dedup / type-alias sweep
across backtest / dashboard / runtime / strategy).

## Remaining Work

CAH-05…CAH-15 remain planned in `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`.
Next action: **CAH-05 (`engine._handle_proposal` finalize helpers, Tier 2)** — method extraction in the
trading domain, so it gets a quant-trader-expert review. Watch the asymmetric `events` /
`events + outcome.events` concatenation at `engine.py` ~L1247 during the extraction.

No ADR needed — CAH-04 is a focused Tier 1 quick win bundling dead-code deletion, dedup extraction, and a
type-alias swap. It introduces no new component boundary, locks in no constraint future work must respect,
and chooses between no competing long-term designs (the keep-semantics-at-the-call-site and
leave-the-superset-alone calls are local judgements recorded in the Key Decisions table). The audit value
lives in the session log and the Change-History row, not in an ADR.
