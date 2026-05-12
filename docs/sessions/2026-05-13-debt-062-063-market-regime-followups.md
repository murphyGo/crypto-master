# Session: DEBT-062 + DEBT-063 market-regime quant follow-up close-out

## Unit

- `proposal-runtime` (primary — gate-sequencing relocation in
  `_handle_proposal`)
- Secondary unit: `consistency-hardening` (classifier rule refinement —
  2-bar confirmation rule in `classify_regime_detailed`, parity preserved
  with `RobustnessGate._classify_regimes`)

## Related Requirements

- FR-045: Market-regime classification — closest match for the
  `classify_regime_detailed` 2-bar confirmation rule change in DEBT-063;
  the contract still emits `bull` / `bear` / `sideways` per the same
  ±2% band but now requires 2 consecutive bars on the new side before
  flipping out of `sideways`.
- FR-029: Proposal gates — closest match for the `_market_regime_gate`
  relocation in DEBT-062; the gate set is unchanged but the ordering
  inside `_handle_proposal` shifts so the actionable correlation-block
  signal surfaces ahead of the non-actionable regime signal when both
  would block.
- NFR-003: Deterministic classification — DEBT-063's 2-bar confirmation
  is a deterministic rule against the existing OHLCV input; the
  `RobustnessGate._classify_regimes` parity (`src/backtest/validator.py:929-959`)
  ensures backtest/live regimes still classify the same way modulo the
  added confirmation latency.

## Scope

Bundled DEBT-062 + DEBT-063 — both filed at the close of the
`market-regime` unit (2026-05-13) from quant-trader-expert review (Q1
and Q4 respectively). Both items independently implemented the quant's
recommended resolution verbatim:

- **DEBT-062 (gate sequencing)** — moved `_market_regime_gate` from
  before `_correlation_gate` to after, in `src/runtime/engine.py::_handle_proposal`.
  New order: `score → correlation → market_regime → strategy_action →
  trend → ...`. When both gates would block (e.g. correlation conflict
  + bear regime against `allowed_regimes=["bull"]`), the operator
  dashboard now surfaces the correlation rejection (with its
  blocking-trade diagnostic — "you already have exposure here") instead
  of the non-actionable regime signal ("this market is in the wrong
  state"). Per-cycle regime cache means the relocation has zero
  OHLCV-fetch cost; the first call per cycle still triggers the
  underlying fetch regardless of order.
- **DEBT-063 (2-bar confirmation)** — `classify_regime_detailed`
  (`src/runtime/market_regime.py`) now requires `close[-1]` AND
  `close[-2]` to BOTH sit on the new side of the ±2% band before
  flipping out of `sideways`. The ±2% threshold itself is unchanged
  (preserves `RobustnessGate._classify_regimes` parity at
  `src/backtest/validator.py:929-959` for backtest/live consistency —
  change the rule, not the number). Defensive
  `len(ohlcv) < 2 → sideways` short-circuit positioned after the
  existing `insufficient_data` / `stale_data` → `unknown` checks so
  data-availability semantics stay above the confirmation rule.

## Changes

- `src/runtime/engine.py` — relocated `_market_regime_gate` call below
  `_correlation_gate` inside `_handle_proposal`. No new fetches; per-cycle
  cache unchanged.
- `src/runtime/market_regime.py` — `classify_regime_detailed` rewrites
  the band-crossing rule to require 2 confirming bars before flipping
  out of `sideways`; defensive `len(ohlcv) < 2` short-circuit added
  after `insufficient_data` / `stale_data` checks.
- `tests/test_market_regime.py` — 8 existing single-bar fixtures
  updated to 2-bar tails; new tests pin two-bar bull confirmation,
  two-bar bear confirmation, one-confirming-bar stays-sideways
  behavior, and both-confirming-bars flip behavior (SMA(200) baseline
  recomputation `100.015 → 100.03` matches `(198×100 + 2×103)/200`).
- `tests/test_runtime_engine.py` — new
  `test_correlation_gate_runs_before_regime_gate` constructs a
  both-blocking fixture (correlation conflict + bear regime against
  `allowed_regimes=["bull"]`) and asserts the correlation event wins.
  Existing tests that exercised the regime classifier through the
  engine had their single-bar tails extended to 2-bar tails.
- `docs/TECH-DEBT.md` — moved DEBT-062 and DEBT-063 from Active to
  Resolved; Statistics Active 8 → 6, Medium 4 → 2, Resolved 58 → 60;
  two Change History rows.
- `aidlc-docs/aidlc-state.md` — appended DEBT-062 + DEBT-063 closeout
  note to the `market-regime` row; Next Action updated to "No
  remaining market-regime follow-ups."

## QA Verdict

🟢 — both items shipped the quant's recommended resolution verbatim,
no scope creep, no unrelated edits. DEBT-062 is a one-call relocation
with a single dedicated pin test; DEBT-063 is a rule refinement
preserving the ±2% threshold for `RobustnessGate` parity (the
quant-emphasised constraint) with an arithmetic-justified fixture
update (`100.015 → 100.03` SMA baseline = `(198×100 + 2×103)/200`).

## Verification

- `pytest -q`
  - Result: 2059 passed (was 2054; net +5, zero regressions).
- `ruff check src tests`
  - Result: fully clean.
- `mypy src/runtime/engine.py src/runtime/market_regime.py`
  - Result: clean.

## Risks

- **2-bar confirmation reduces regime-flap throughput by design** —
  strategies that wanted to enter on a single confirming bar now wait
  one more cycle (one additional 4h bar on the dominant timeframe). The
  band-edge selection bias the quant flagged is the explicit win;
  symmetrically, fast-trending regime entries get a one-bar admission
  delay. Operator impact is captured in the existing `strategy-tuning`
  Slice 2 follow-up (DEBT-069) for threshold calibration after the
  first 2 weeks of paper evidence — the calibration pass will observe
  whether the confirmation latency cleanly clears the "wall of retune"
  expectation or whether `scout.sample_size_max` widening needs to
  accommodate the additional admission delay.
- **Gate-order relocation surfaces correlation signals more often** —
  when both gates would block, dashboards previously dominated by
  `MARKET_REGIME_BLOCKED` events will now surface
  `gate_rejected_correlation` events instead. This is the intended
  operator-experience improvement (correlation rejections are
  directly actionable; regime rejections are not), but the dashboard
  rejection-mix shift is a visible operator change.

## Future Work

- None. Both quant-trader-expert follow-ups against the
  `market-regime` unit (Q1 + Q4) are now closed; the
  `aidlc-state.md` `market-regime` row has no remaining follow-ups.
