# Session: clean-architecture-hardening CAH-06 — `close_position` + `_build_proposal_for_strategy` LONG-FUNCTION SPLITS (BEHAVIOR-PRESERVING REFACTOR)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-06 (Tier 2 long-function splits; `paper.close_position` TRAD-F4 + `proposal._build_proposal_for_strategy` PROP-F5).

> SIXTH unit shipped from the `clean-architecture-hardening` plan, and the SECOND of the Tier 2 method
> extractions (after the standalone Tier 0 bugfix CAH-01, the three Tier 1 quick wins CAH-02 order-side
> helpers / CAH-03 `build_engine` inlining / CAH-04 dead-code-dedup sweep, and the first Tier 2 extraction
> CAH-05 `_handle_proposal` finalize helpers). This unit touches the trading domain (`paper.close_position`'s
> liquidation-clamp balance math + the proposal sizing/SL-floor path), so it carried a quant-trader-expert
> review in addition to qa-reviewer. CAH-07…CAH-15 remain planned.

## Scope

CAH-06 is two independent behavior-preserving long-function extractions, both pure code-moves with no
trading math, no PnL / sizing / signal change, no statement reorder, and no changed branch.

### Part A (TRAD-F4) — `src/trading/paper.py`: `close_position` split

`close_position` was split by extracting two helpers:

- `_apply_close_to_balance` — the liquidation-clamp balance-mutation block. It preserves the load-bearing
  `unlock(margin) → read balance.free → projected_free → liquidated → clamp → balance_after` statement order
  **byte-identically**. This ordering is the crux of the unit: the margin must be unlocked back into
  `balance.free` BEFORE the free balance is read for the projected-free predicate, or the liquidation
  decision is computed against the wrong free balance.
- `_emit_liquidation_event` — the `LIQUIDATED` event emission, still gated on
  `liquidated and activity_log is not None` exactly as before.

### Part B (PROP-F5) — `src/proposal/engine.py`: `_build_proposal_for_strategy` split

`_build_proposal_for_strategy` was split by extracting two helpers:

- `_apply_sl_floor` — the ATR + `enforce_sl_floor` + conditional `model_copy` block (the stop a trade gets).
- `_size_position` — the `create_position` try/except fail-closed path.

The multi-TF `analyze()` branch was left **untouched**. `Position` was added to the `src/proposal/engine.py`
imports for the `_size_position` return annotation.

## Process / verdicts

senior-developer implemented → quant-trader-expert 🟢 → qa-reviewer 🟢. Trading-domain unit, so it carried
the quant review in addition to qa.

### Quant 🟢

quant-trader-expert returned 🟢 across both parts:

- **Part A** — the balance math is byte-identical: the unlock-before-read order is preserved; the clamp
  branch plus `balance_before` / `balance_after` plus the PnL / fee enter identically; the return tuple is
  consumed correctly at the call site; the `LIQUIDATED` event is gated as before
  (`liquidated and activity_log is not None`).
- **Part B** — the SL-floor extraction preserves the stop a trade gets; the sizing fail-closed path is
  intact; the multi-TF `analyze()` branch is genuinely untouched.
- No statement reorder, no changed branch, no numeric drift across either part.

### QA 🟢

qa-reviewer returned 🟢: **2256 passed, no net change**; ruff + mypy clean. `git diff -- tests/` is **EMPTY**
= no test modified. `test_under_water_close_emits_liquidated_event` plus the paper-close suites plus the
proposal SL-floor / sizing suites all pass unchanged = behavior-preservation proof. Pure-move verified
line-by-line.

## Files Changed

- **Modified**:
  - `src/trading/paper.py` — `close_position` split: extracted `_apply_close_to_balance` (the
    liquidation-clamp balance-mutation block; preserves the load-bearing
    `unlock(margin) → read balance.free → projected_free → liquidated → clamp → balance_after` statement
    order byte-identically) + `_emit_liquidation_event` (the `LIQUIDATED` event, still gated on
    `liquidated and activity_log is not None`).
  - `src/proposal/engine.py` — `_build_proposal_for_strategy` split: extracted `_apply_sl_floor` (ATR +
    `enforce_sl_floor` + conditional `model_copy`) + `_size_position` (`create_position` try/except
    fail-closed). The multi-TF `analyze()` branch left untouched. `Position` added to the imports for the
    `_size_position` return annotation.

No test files changed — the existing money / order suites are the behavior-preservation proof
(`git diff -- tests/` EMPTY).

## Key Decisions

| Decision | Rationale |
|---|---|
| `_apply_close_to_balance` preserves the `unlock(margin) → read balance.free → projected_free → liquidated → clamp → balance_after` order byte-identically | The margin must be unlocked back into `balance.free` BEFORE the free balance is read for the projected-free liquidation predicate; reordering would compute the liquidation decision against the wrong free balance. This is the TRAD-F4 unlock-before-read crux the brief flagged. The quant confirmed the order is preserved and the clamp branch / `balance_before` / `balance_after` / PnL / fee enter identically. |
| `_emit_liquidation_event` keeps the `liquidated and activity_log is not None` gate | The `LIQUIDATED` event was conditional in the original; moving it into a helper does not change the gate, so the event fires under exactly the same conditions as before. |
| Leave the multi-TF `analyze()` branch in `_build_proposal_for_strategy` untouched | Only the SL-floor and sizing tails were the long-function targets. The multi-TF branch is a separate concern; touching it would widen the quant surface for no behavioral gain. Quant confirmed it is genuinely untouched. |
| Add `Position` to `src/proposal/engine.py` imports | Needed only for the `_size_position` return annotation; a pure-typing import, no behavior change. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2256 passed (no net change from the 2256 CAH-05 baseline)**, 0 failed. Pure code-moves add
  no tests; the existing money / order suites are the proof.
- `ruff check`: clean.
- `mypy`: clean.
- `git diff -- tests/`: **EMPTY** — no test modified, so the unchanged passing money / order suites
  (`test_under_water_close_emits_liquidated_event` + paper close + proposal SL-floor / sizing) prove
  behavior preservation.

## Potential Risks

- **The TRAD-F4 unlock-before-read ordering inside `_apply_close_to_balance` is load-bearing.** The helper
  preserves `unlock(margin) → read balance.free → projected_free → liquidated → clamp → balance_after`
  byte-identically. A future edit that reads `balance.free` before unlocking the margin — or that reorders
  the clamp relative to the projected-free predicate — would compute the liquidation decision against the
  wrong free balance and silently change clamp behavior. `test_under_water_close_emits_liquidated_event` plus
  the paper-close suites are the regression boundary to respect.
- **The `LIQUIDATED` event gate (`liquidated and activity_log is not None`) lives in
  `_emit_liquidation_event`.** Dropping the `activity_log is not None` half would crash when no activity log
  is wired; dropping the `liquidated` half would over-emit. The gate must stay paired.
- **The multi-TF `analyze()` branch in `_build_proposal_for_strategy` was deliberately left out of scope.**
  It was not part of this split and was not quant-reviewed in this cycle; future SL-floor / sizing edits
  should not assume the multi-TF branch shares the extracted helpers.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-06. A Change-History row dated 2026-05-28 was
added to `docs/TECH-DEBT.md` for the audit trail (the second Tier 2 method extraction: two behavior-preserving
long-function splits in the trading domain, 0 test delta).

## Remaining Work

CAH-07…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-07 (LSP: uniform `analyze()` signatures, Tier 2)** — add the 2 ignored kwargs to the 6 truncated
strategies so the `analyze()` signatures are uniform; trading-domain so quant-reviewed.

No ADR needed — CAH-06 is two focused Tier 2 method extractions. It introduces no new component boundary,
locks in no constraint future work must respect, and chooses between no competing long-term designs (the
preserve-the-unlock-before-read-order call and the leave-the-multi-TF-branch-untouched call are local
behavior-preservation judgements recorded in the Key Decisions table). The audit value lives in this session
log and the Change-History row, not in an ADR.
