# Session: DEBT-060 close-out — RSI baseline family R/R coverage

## Unit

- `strategy-framework` (primary — RSI baseline family)
- Secondary unit: `proposal-runtime`

## Related Requirements

- FR-005: Track strategy performance (RSI baseline family throughput / runtime
  R/R gate behaviour). Closest match in
  `aidlc-docs/inception/requirements/requirements.md`.
- FR-006: Calculate risk/reward from trading points (the 2.0 R/R floor
  exercised by the new positive mirror test).

## Scope

Closed DEBT-060 by adding the missing regression coverage for the TP-distance
redesign that already shipped in commit `14ca04c` (2026-05-12), and filed
DEBT-061 as the observability follow-up. Test-only diff today; no production
code touched.

## Changes

- `tests/test_rsi_variants.py`
  - Appended `test_all_rsi_variants_pin_take_profit_pct_at_0_05`: pins
    `strategies.rsi.TAKE_PROFIT_PCT == 0.05` and asserts the two sibling files
    (`rsi_4h.py`, `rsi_15m.py`) do not shadow the constant.
- `tests/test_proposal_engine.py`
  - Appended `test_rsi_variants_clear_rr_floor_under_worst_case_widening`, a
    parametrized triple `(rsi_universal@1h, rsi_4h@4h, rsi_15m@15m)`. Each row
    drives ATR to the worst-plausible widening per
    `src/utils/trading_math.py` SL-widening table (1h→2.4%, 4h→2.25%,
    15m→2.1%) and asserts the proposal is accepted with R/R ≥ 2.0. Mirrors
    the existing negative
    `test_proposal_rejected_when_widening_drags_rr_below_floor` at
    `tests/test_proposal_engine.py:1503`.

## Background

The shipped TP value (`TAKE_PROFIT_PCT` 0.04 → 0.05 across the three RSI
strategy files) already landed in commit `14ca04c` on 2026-05-12. Today's
cycle added the missing regression tests so the value is pinned and the R/R
floor is exercised on every run, then filed the dashboard observability piece
as a scope-split follow-up.

## Quant Ratification

- Worst-case post-widen SL per `src/utils/trading_math.py`: ~2.25% on 4h
  (binding case), ~2.0–2.4% elsewhere.
- TP = 5.0% on all three RSI files → R/R floor = **2.22** on the binding
  4h-alt case (2.25% widened SL vs 5% TP), safely above the 2.0 gate.
- Quant explicitly rejected bumping 4h to 5.5% (would lower hit-rate within
  `max_bars_held=6`); 5% holds the same value across all three RSI variants.

## Verification

- `pytest -q` → 1812 passed (was 1808; net +4).
- `pytest tests/test_rsi_variants.py tests/test_proposal_engine.py -q` → 68
  passed (was 64; net +4).
- `ruff check src tests` → fully clean.
- `mypy src` → 3 pre-existing `src/dashboard/app.py:268,852,865` errors remain
  (out of scope; not introduced by this cycle).

## Risks

- None. Test-only diff; no production code paths changed.

## Reviewer Notes

- quant-trader-expert 🟢 (math: 2.22 R/R floor on the binding 4h-alt case).
- qa-reviewer 🟢 (test quality: positive parametrized mirror cleanly pairs
  with the existing negative widening test; constant pin guards against
  silent reversion).

## Scope-Split Rationale

DEBT-061 (per-strategy proposal-engine fail-closed-rate metric for dashboard
observability) is observability work, not strategy logic — filed separately
rather than gating DEBT-060 closure on dashboard work. The DEBT-060
suggested-resolution's "pair with a fail-closed-rate metric" line is the seed
text for DEBT-061. Surfaced from quant-trader-expert during DEBT-060
close-out review; explicitly *not* a regression of `14ca04c`.
