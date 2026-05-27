# Session: clean-architecture-hardening CAH-05 — `_handle_proposal` FINALIZE-HELPER + CAP-GATE EXTRACTION (BEHAVIOR-PRESERVING REFACTOR)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-05 (first Tier 2 method extraction; `engine._handle_proposal` finalize helpers).

> FIFTH unit shipped from the `clean-architecture-hardening` plan, and the FIRST of the Tier 2 method
> extractions (after the standalone Tier 0 bugfix CAH-01, and the three Tier 1 quick wins CAH-02 order-side
> helpers, CAH-03 `build_engine` inlining, CAH-04 dead-code/dedup sweep). This unit touches the trading
> domain (`engine._handle_proposal`'s reject path + cap gates), so it carried a quant-trader-expert review
> in addition to qa-reviewer. CAH-06…CAH-15 remain planned.

## Scope

CAH-05 extracts the duplicated invariant tail of `engine._handle_proposal`'s rejection path into a single
`_finalize_rejection` helper, and lifts the two inline cap gates into named methods matching the existing
`_account_aggregate_cap_gate` sibling contract. Behavior-preserving — no trading math, no PnL / sizing /
signal change; the gate evaluation order, the reason strings, the terminal event constants, and the
`proposals_rejected` accounting are all preserved byte-for-byte.

1. **Finalize-helper extraction** — added
   `_finalize_rejection(*, final_record, replay_events, result)` capturing the invariant rejection tail
   only: `proposals_rejected += 1`; `proposal_history.save`; replay-event emission. Crucially the helper
   does **NO concatenation** — callers own the list shape, so the asymmetric **Shape A** (`outcome.events`)
   vs **Shape B** (`events + gate.events`) call shapes are preserved at the call sites. All **15 reject call
   sites** were routed through it.
2. **Cap-gate extraction** — the two inline cap gates were lifted into `_total_cap_gate` /
   `_symbol_cap_gate`, matching the contract of the existing `_account_aggregate_cap_gate` sibling. The gate
   evaluation order (total-cap before symbol-cap, same slot in the pipeline) is preserved exactly.

A count note carried over from the brief: an earlier framing said "16" reject call sites; qa confirmed the
true count is **15 call sites + 1 helper definition**.

## Changes — CAH-05 finalize-helper + cap-gate extraction

**`src/runtime/engine.py`** — added `_finalize_rejection(*, final_record, replay_events, result)`: the
invariant rejection tail only (`proposals_rejected += 1`; `proposal_history.save`; replay-event emission);
**no concatenation** — callers own the list shape, so the asymmetric Shape A (`outcome.events`) vs Shape B
(`events + gate.events`) is preserved. Routed all 15 reject call sites through the helper. Extracted the two
inline cap gates into `_total_cap_gate` / `_symbol_cap_gate`, matching the `_account_aggregate_cap_gate`
sibling contract; total-cap-before-symbol-cap order preserved, same pipeline slot.

**`tests/test_runtime_engine.py`** — 2 new guard tests pinning ordered event identity + `proposals_rejected
== 1` for Shape A (total-cap) and Shape B (regime). No existing test modified.

## Process / verdicts

senior-developer implemented → quant-trader-expert 🟢 → qa-reviewer 🟢. Trading-domain unit, so it carried
the quant review in addition to qa.

### Quant 🟢

quant-trader-expert returned 🟢: the gate ORDER is byte-for-byte preserved (total-cap before symbol-cap,
same slot); the cap-gate reason strings, the `GATE_REJECTED_TOTAL_CAP` + `GATE_REJECTED_SYMBOL_CAP`
terminals, the `gate_reason`, and the `blocking_trades` payloads are all character-identical; the double
`get_open_trades()` is provably safe — they are pure reads with no position opens between the two gates;
`proposals_rejected` increments exactly once per rejection; the Shape A + Shape B spot-checks match.

### QA 🟢

qa-reviewer returned 🟢: **2256 passed (+2)**; ruff + mypy clean. `git diff -- tests/` shows ONLY the 2 new
tests + a constant, no existing test modified = behavior-preservation proof. The 2 guard tests genuinely pin
ordered event identity + `proposals_rejected == 1` for Shape A (total-cap) and Shape B (regime). The old
inline cap code is fully removed with no other caller.

## Files Changed

- **Modified**:
  - `src/runtime/engine.py` — added `_finalize_rejection(*, final_record, replay_events, result)` (invariant
    rejection tail only: `proposals_rejected += 1`; `proposal_history.save`; replay events — NO
    concatenation, callers own the list shape, preserving asymmetric Shape A `outcome.events` vs Shape B
    `events + gate.events`); routed all 15 reject call sites through it; extracted the two inline cap gates
    into `_total_cap_gate` / `_symbol_cap_gate` matching the `_account_aggregate_cap_gate` sibling contract
    (total-cap-before-symbol-cap order + same slot preserved).
  - `tests/test_runtime_engine.py` — 2 new guard tests pinning ordered event identity + `proposals_rejected
    == 1` for Shape A (total-cap) and Shape B (regime).

## Key Decisions

| Decision | Rationale |
|---|---|
| `_finalize_rejection` does NO concatenation — callers pass the already-shaped `replay_events` list | The rejection tail is asymmetric: Shape A call sites emit `outcome.events`, Shape B sites emit `events + gate.events`. Folding the concatenation into the helper would force one shape on both and silently change which events get emitted. Callers own the list shape; the helper only owns the invariant tail (`proposals_rejected += 1`; `proposal_history.save`; replay emission). |
| Extract `_total_cap_gate` / `_symbol_cap_gate` to match the `_account_aggregate_cap_gate` sibling contract | The third cap gate was already a named method; lifting the two inline gates to the same contract makes the cap-gate trio symmetric without changing evaluation order. Total-cap-before-symbol-cap and the pipeline slot are preserved exactly. |
| Keep the double `get_open_trades()` across the two cap gates | Quant confirmed both calls are pure reads with no position opens between them, so de-duplicating was unnecessary and would have changed the call structure under a quant surface for no behavioral gain. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2256 passed (+2 from the 2254 CAH-04 baseline)**, 0 failed. The +2 are the Shape A
  (total-cap) and Shape B (regime) guard tests in `tests/test_runtime_engine.py`.
- `ruff check`: clean.
- `mypy`: clean.
- `git diff -- tests/` shows ONLY the 2 new tests + a constant, no existing test modified =
  behavior-preservation proof.

## Potential Risks

- **The asymmetric Shape A / Shape B list shape lives at the call sites, not in `_finalize_rejection`.** A
  future edit that pushes the `events + gate.events` concatenation into the helper would change which events
  the Shape A sites emit (and vice versa). The 2 guard tests (ordered event identity + `proposals_rejected
  == 1` for each shape) are the regression boundary to respect.
- **The cap-gate evaluation order (total-cap before symbol-cap) is load-bearing.** The two extracted gates
  share the same pipeline slot and the same double `get_open_trades()` reads; the quant audit confirmed the
  order and the pure-read safety. A reordering or a merged single read would need a fresh quant pass.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-05. A Change-History row dated 2026-05-28 was
added to `docs/TECH-DEBT.md` for the audit trail (the first Tier 2 method extraction: `_handle_proposal`
finalize-helper + cap-gate extraction, behavior-preserving, no trading math).

## Remaining Work

CAH-06…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-06 (long-function splits, Tier 2)** — `paper.close_position` (TRAD-F4) +
`proposal._build_proposal_for_strategy` (PROP-F5); trading-domain so quant-reviewed. Watch the **TRAD-F4
unlock-before-read ordering crux** during the `close_position` split.

No ADR needed — CAH-05 is a focused Tier 2 method extraction. It introduces no new component boundary, locks
in no constraint future work must respect, and chooses between no competing long-term designs (the
no-concatenation-in-the-helper call and the keep-the-double-read call are local judgements recorded in the
Key Decisions table). The audit value lives in this session log and the Change-History row, not in an ADR.
