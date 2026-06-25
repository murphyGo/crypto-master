# Session: runtime-reconciliation paper balance lock/unlock drift reconcile (DEBT-072)

## Unit

- `runtime-reconciliation`

## Related Requirements

- FR-010, FR-014, FR-029
- NFR-007, NFR-008, NFR-012

## Context

The 2026-06-25 Fly strategy-improvement analysis (snapshot
`/private/tmp/crypto-master-strategy-snapshots/fly-data-20260625-203554`)
found the paper lab's core loop substantially non-functional: **5,627**
`cycle_errored` events of the form `Sub-account <name> cycle failed: Cannot
unlock 1000.000… USDT: only 711.0496810523400424872483206 locked` (latest
`2026-06-25T11:20:42Z`, `weinstein_stage2_filter`). DEBT-072 captured this as a
verified bug, linked to DEBT-071 (orphan opens not rehydrated → monitor cannot
enforce SL/TP; the unlock raise also blocks the orphan force-close path
mid-way, so failed closes leave locks stranded).

The quant-trader-expert root-caused it (review-only, no code) to a violated
ledger invariant: `balance.locked == Σ(open_pos.margin for open trades)` was
not maintained fleet-wide. `_rehydrate_open_positions` only reconciled `locked`
when **no** persisted balance snapshot existed (the gate at old
`paper.py:442`). With a drifted snapshot present, a restart inherited the
drift — `_open_positions` carried the per-trade margin but `locked` did not. The
decisive concrete case: `weinstein_stage2_filter` restored `locked=711.05` while
its open positions dropped two 2026-05-08 margins of 1000 each (drift = exactly
2000), so the next `unlock(1000)` saw `amount > self.locked` and raised
`Cannot unlock … only … locked`. Earlier samples also showed sub-`1E-24`
residuals, implying a Decimal/float round-trip path co-existed with the
structural drift.

The fix had to repair the structural drift on restart **without masking real
drift** (a tolerant unlock that swallowed large overshoots would hide genuine
accounting bugs) and **without violating the standing paper-ledger parity
constraints**: DEBT-059 (`total` is preserved, never reconstructed from
`free + locked`) and DEBT-027 (`free` is allowed to go negative rather than
clamped). The chosen design pins `locked` to the open-position margin sum
unconditionally after rehydration and lets a small `unlock` overshoot
self-clamp to zero, while structural overshoot still raises.

## Changes

All in `src/trading/paper.py` (by senior-developer):

- **Tolerant `PaperBalance.unlock`** — clamps a sub-EPS overshoot
  (`EPS = Decimal("1E-9")`): releases all remaining `locked` → 0 and logs a
  WARNING, but still **RAISES** `PaperTradingError` on structural overshoot
  (`amount - locked > EPS`). Float dust self-heals; real drift stays loud.
- **New `_reconcile_locked_to_open_positions()`**, called
  **unconditionally** after the rehydrate loop (this replaced the old
  line-442 no-snapshot-only gate). Per quote currency it pins
  `locked = Σ(open_pos.margin)` and sets `free = total - expected`,
  **preserving `total`** (DEBT-059) and **allowing `free < 0`** (DEBT-027).
  Emits a `RECONCILIATION_REPAIRED_PAPER_BOUNDS` activity event + a WARNING
  **only on change**. The legacy no-snapshot reconcile still runs first; the
  new reconcile then no-ops (no double-lock). Logs a parity WARNING when a
  currency has open positions but no balance entry.
- **`force_close_orphan` docstring/warning tightened** — drift now self-heals
  on the next rehydrate reconcile, so the stale "operator must rebalance later"
  caveat was removed.

- Added `tests/test_paper_balance_reconcile.py` (new, **12 tests**) covering all
  7 prescribed scenarios, including the DEBT-072 short-snapshot repro (drifted
  `locked` < Σmargin on restart → reconcile repairs, no raise) and the
  structural-overshoot-still-raises guard.

## Verification

- `uv run pytest tests/test_paper_balance_reconcile.py -q`
  - 12 passed (all 7 prescribed scenarios).
- `uv run pytest -q` (full suite)
  - **2362 passed**, 0 failed.
- `ruff check` — clean.
- `uv run mypy src` — clean.
- New test file `black`-clean.
- QA verdict: 🟡 ship (qa-reviewer). Both parity constraints (DEBT-027 `free<0`
  allowed; DEBT-059 `total` preserved) and the `locked == Σmargin` invariant
  verified by QA. The only QA nit was a `black` formatting miss on the new file,
  since fixed.

## Specialist flow

- **quant-trader-expert** (review-only) — root-caused the violated
  `locked == Σmargin` invariant and the no-snapshot-only reconcile gate; wrote
  the design prescription (unconditional reconcile, tolerant-but-bounded unlock,
  parity preservation, 7 test scenarios).
- **senior-developer** — implemented the EPS-tolerant unlock,
  `_reconcile_locked_to_open_positions`, the `force_close_orphan`
  docstring/warning tightening + parity warning, and the 12-test file.
- **qa-reviewer** — 🟡 ship; full suite 2362 passed, ruff + mypy clean, parity +
  invariant verified; flagged the now-fixed `black` nit.

## Parity constraints preserved

- **DEBT-059** — `total` is preserved by the reconcile (`free` is recomputed as
  `total - expected`; `total` is never reconstructed from `free + locked`).
- **DEBT-027** — `free` is permitted to be negative; the reconcile does not
  clamp it.
- **`locked == Σ(open_pos.margin)`** — now pinned unconditionally on every
  rehydrate, so a drifted snapshot can no longer be inherited across restart.

## Risks

- The tolerant `unlock` clamp is deliberately tight (`EPS = 1E-9`): float dust
  self-heals, but any overshoot above EPS still raises, so a genuine
  larger-than-dust accounting bug would surface loudly rather than being masked.
  This is the intended safety property; the trade-off is that a future legitimate
  rounding regime wider than 1E-9 would need a conscious EPS revisit, not a silent
  pass-through.
- The reconcile repairs in-memory state on restart; the persisted snapshot is
  corrected on the next save. A running process with drift is only healed after
  a restart/redeploy picks up the rehydrate path (same restart requirement as the
  proposal-bounds repair tool).
- `RECONCILIATION_REPAIRED_PAPER_BOUNDS` is now emitted by two producers (see
  watch-item below); dashboards that filter on it will see both the
  proposal-linked SL/TP repair and this free/locked split until/unless a
  dedicated event type is added.

## Linked debt (still open)

- **DEBT-071 stays OPEN** (linked, not addressed this cycle). The DEBT-072
  reconcile is the *safety net* that makes DEBT-071's stranded-margin scenario
  self-heal on restart (a failed orphan close no longer leaves the lock ledger
  permanently inconsistent). But DEBT-071's root cause — persisted open paper
  positions are **not** rehydrated into in-memory position state, so the monitor
  mis-flags them as orphans and never reaches the SL/TP check — is unchanged.
  Stops/TPs are still not enforced at their levels until DEBT-071 is fixed.

## Watch-item (follow-up, not filed as debt)

`RECONCILIATION_REPAIRED_PAPER_BOUNDS` is now **dual-producer**: the existing
proposal-linked SL/TP repair tool (`src/tools/repair_paper_trade_bounds_from_proposals.py`,
2026-06-11) and this new free/locked-split reconcile both emit it, distinguishable
only by their `details` keys. A dedicated
`RECONCILIATION_REPAIRED_PAPER_LOCKED_SPLIT` event type would be cleaner for
dashboard filtering. Recorded here as a watch-item rather than a tracked DEBT
item: it is a pure observability nicety with a zero-cost workaround (filter on
`details` keys), the two producers are not in conflict, and no operator decision
or strategy correctness depends on it. If a dashboard pane is ever built that
needs to isolate the locked-split repairs at the event-type level, promote this
to a Low `code-improvement` item then.
