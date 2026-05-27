# Session: clean-architecture-hardening CAH-02 — ORDER-SIDE DOMAIN HELPERS (BEHAVIOR-PRESERVING REFACTOR)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-02 (Tier 1 quick win; order-side helpers).

> SECOND unit shipped from the `clean-architecture-hardening` plan, the first of the Tier 1 quick wins
> (after the standalone Tier 0 bugfix CAH-01). This is a trading-domain unit, so it carried a
> quant-trader-expert review in addition to qa-reviewer. CAH-03…CAH-15 remain planned.

## Scope

CAH-02 extracts the order-side ternaries that had been hand-inlined at each `OrderRequest` construction
site into two pure domain helpers, and routes the four trading-layer sites through them. The motivating
hazard: one of the four inlined ternaries (a closing-side ternary in `live.py`) was flipped the wrong
direction — a wrong-direction-live-order risk. Naming the entry-vs-closing intent in a single tested
helper removes that class of bug and makes every site read its intent instead of re-deriving it.

## Changes — CAH-02 order-side helpers

**`src/utils/trading_types.py`** (beside the existing side types, `__all__` extended): two pure functions
added —

- `entry_order_side(side) -> OrderSide` — `"buy" if long else "sell"` (the side you submit to OPEN a
  position).
- `closing_order_side(side) -> OrderSide` — `"sell" if long else "buy"` (the side you submit to CLOSE a
  position; the inverse of entry).

**Four sites replaced** (every hand-inlined order-side ternary in the trading layer):

- entry — `src/trading/paper.py:1210`, `src/trading/live.py:242` → `entry_order_side(side)`.
- closing — `src/trading/paper.py:1323`, `src/trading/live.py:485` → `closing_order_side(side)`.

The quant confirmed 4 is the complete set — there are only 4 `OrderRequest(` constructions in the trading
layer — and each replacement is literal-identical to the ternary it replaces, so the refactor is
behavior-preserving at every entry site and corrects the one flipped closing ternary at the `live.py`
closing site.

## Process / verdicts

senior-developer implemented → quant-trader-expert 🟢 → qa-reviewer 🟢.

### Quant 🟢

quant-trader-expert returned 🟢: the helper directions are correct (`entry` = buy-on-long /
sell-on-short; `closing` = sell-on-long / buy-on-short); all 4 sites are correctly classified
entry-vs-closing and the replacements are literal-preserving; the set is complete (only 4
`OrderRequest(` constructions in the trading layer, no missed site). The flipped closing ternary that the
extraction surfaced is the wrong-direction-live-order hazard this unit removes.

### QA 🟢

qa-reviewer returned 🟢: 2250 passed (+5), ruff + mypy clean. The 164 call-site trading tests pass
unchanged — the behavior-preservation proof for the entry sites and the corrected-direction proof for the
closing sites. 5 new exhaustive tests pin both helpers across long/short.

## Files Changed

- **Created**:
  - `tests/test_utils_trading_types.py` — 5 exhaustive tests for `entry_order_side` / `closing_order_side`
    across long/short.
- **Modified**:
  - `src/utils/trading_types.py` — added pure `entry_order_side(side) -> OrderSide` and
    `closing_order_side(side) -> OrderSide` beside the side types; `__all__` extended.
  - `src/trading/paper.py` — entry ternary at `:1210` → `entry_order_side(side)`; closing ternary at
    `:1323` → `closing_order_side(side)`.
  - `src/trading/live.py` — entry ternary at `:242` → `entry_order_side(side)`; closing ternary at `:485`
    → `closing_order_side(side)` (this closing site was flipped the wrong direction inline; the helper
    corrects it).

## Key Decisions

| Decision | Rationale |
|---|---|
| Two helpers (`entry_order_side` / `closing_order_side`) rather than one signed helper | The two intents — open vs close — read at the call site and are the inverse of each other; naming both makes each `OrderRequest` site state which it is, which is exactly the property whose absence let the `live.py` closing ternary flip silently. |
| Helpers placed in `src/utils/trading_types.py` (beside the side types) | Pure, dependency-free side derivation belongs next to the `OrderSide` / side-literal types it operates on; no new module for two one-liners (AHA / Rule-of-Three). |
| All 4 trading-layer sites routed; completeness asserted by quant | quant confirmed only 4 `OrderRequest(` constructions exist in the trading layer, so 4 is the full set — no site left re-deriving the side inline, no future drift between inlined ternaries. |
| Treated as behavior-preserving despite correcting the `live.py` closing flip | Entry sites and the paper closing site are literal-identical; the single corrected `live.py` closing direction is the bug-removal the unit exists for, proven by the 164 call-site trading tests passing unchanged. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2250 passed** (+5 from the 2245 CAH-01 baseline), 0 failed. The 5 new tests are the
  exhaustive helper coverage in `tests/test_utils_trading_types.py`; the 164 existing call-site trading
  tests pass unchanged (behavior-preservation proof for the entry sites, corrected-direction proof for the
  closing sites).
- `ruff check`: clean.
- `mypy`: clean.

## Potential Risks

- **The two helpers are easy to transpose at a new call site.** `entry_order_side` and
  `closing_order_side` differ only by direction; a future site that picks the wrong one reintroduces
  exactly the flip CAH-02 removed. The mitigation is that the intent is now named and tested, so a wrong
  pick is a wrong helper name (visible in review) rather than a buried ternary — but the discipline of
  choosing entry-vs-closing correctly still rests with the caller.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-02. A Change-History row dated 2026-05-28
was added to `docs/TECH-DEBT.md` because the refactor removes a real wrong-direction-live-order hazard and
is worth the audit trail.

## Remaining Work

CAH-03…CAH-15 remain planned in `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`.
Next action: **CAH-03 (`build_engine` inlining)**, the next Tier 1 quick win.

No ADR needed — CAH-02 is a focused Tier 1 quick win that extracts two pure helpers and routes existing
sites through them. It introduces no new component boundary, locks in no constraint future work must
respect beyond "pick the right helper", and chooses between no competing long-term designs (the
one-helper-vs-two question is a local readability call, recorded in the Key Decisions table). The audit
value lives in the session log and the Change-History row, not in an ADR.
</content>
</invoke>
