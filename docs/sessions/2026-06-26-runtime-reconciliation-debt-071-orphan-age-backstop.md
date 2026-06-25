# Session: runtime-reconciliation orphan age-backstop + SL/TP rehydration backfill (DEBT-071)

## Unit

- `runtime-reconciliation`

## Related Requirements

- FR-010, FR-014, FR-029
- NFR-007, NFR-008, NFR-012

## Context

The 2026-06-25 Fly strategy-improvement analysis (snapshot
`/private/tmp/crypto-master-strategy-snapshots/fly-data-20260625-203554`, app
`crypto-master`, machine `6835752b711958`, release 48) found persisted open
paper positions that the monitor could not enforce: **60,003** orphan events,
**0** `POSITION_ORPHAN_FORCE_CLOSED` events ever, the same trade ids recurring
~1,600× — weeks-stale opens were eventually force-closed at stale market prices
and **mislabeled** as SL/TP hits (e.g. SOL `c82add57` closed 62.61 carrying
`close_reason=stop_loss` against a stop of 88.06). DEBT-071 captured this as a
verified runtime/execution defect that contaminates every strategy's loss tape
(§5 gate). The quant-trader-expert root-caused two latent defects (review-only,
no code):

**Defect A — the watchdog never fired across restarts.**
`PositionMonitor._orphan_strike_counts` was an in-memory dict, reset on every
process start. On a Fly host that restarted **38× in 35 days**, no trade ever
accumulated the 5 consecutive strikes the `ORPHAN_AUTO_CLOSE_THRESHOLD`=5
watchdog needs — hence **0** `POSITION_ORPHAN_FORCE_CLOSED` events ever, and all
60,003 orphan events stuck at `strike_count=1`, with the same trade_ids
recurring ~1,600×. The CAH-15 watchdog was structurally correct but unreachable
under the real restart cadence: a counter that resets faster than it can fill is
a counter that never fires.

**Defect B — structurally-unmonitorable opens never entered position state.**
`PaperTrader._rehydrate_open_positions` (`paper.py:396-402`) skipped open trades
lacking **both** SL and TP via a bare `continue`. The 39 orphaned ids were
exactly those rows — classified `state=degraded, missing=[stop_loss,
take_profit]` in the 2026-06-10 reconciliation report — so they never entered
`_open_positions` and became **permanent** orphans. The `dbd9114`
proposal-linked repair tool backfilled bounds once on 2026-06-10; after that the
normal monitor finally fired, but at 34-day-stale prices, producing the
mislabeled closes above. So the two defects compounded: B kept trades
unmonitorable until a one-shot operator tool patched them, and A meant the
watchdog backstop that should have caught them earlier never engaged.

The fix had to make a structurally-unmonitorable open trade self-heal **without
operator intervention and across arbitrary restarts**, while not regressing the
existing fast-path that closes genuinely transient young orphans, and keeping
paper/live parity.

## Changes

By senior-developer; quant-trader-expert root-caused + designed (review-only).

- **`src/runtime/position_monitor.py`** — new
  `ORPHAN_MAX_AGE = timedelta(hours=24)`. In `_handle_orphan_trade` the close
  gate is now `force_close if (strikes >= ORPHAN_AUTO_CLOSE_THRESHOLD) OR
  (trade_age >= ORPHAN_MAX_AGE)`, where `trade_age = now_utc() -
  ensure_utc(trade.entry_time)` — **restart-safe** (wall-clock age survives
  process restarts; the strike counter does not) and **tz-safe** for both naive
  and aware `entry_time`. The age branch force-closes on the **first** qualifying
  cycle via `force_close_orphan` with `close_reason=orphan_force_close` (a
  truthful reason, **not** a phantom SL/TP label). The 5-strike fast-path is
  preserved unchanged for young transient orphans. Orphan events now carry
  `trigger` / `age_hours` / `max_age_hours` so the firing path is observable.
- **`src/strategy/performance.py`** — new
  `resolve_bounds_from_performance_record(...)` helper: a raw-JSON walk that
  fails safe to `None` on a missing file, a malformed record, or null bounds on a
  found record. Lets rehydration recover SL/TP from the linked performance record
  without coupling to the higher-level tracker.
- **`src/trading/paper.py`** + **`src/trading/live.py`** — rehydrate now attempts
  an inline SL/TP backfill from `performance_record_id` (via the new resolver)
  **before** the skip. An unrecoverable row still skips, but now relies on the
  age-backstop rather than becoming a permanent orphan. Paper and live kept at
  parity.
- **`src/runtime/engine.py`** — re-exports `ORPHAN_MAX_AGE`.
- **Tests:**
  - `tests/test_runtime_engine.py` — **4 new tests**; `make_trade` gained an
    optional `entry_time` param, and the **7** existing strike-path tests were
    pinned to a young `entry_time` so the new age branch does not perturb them.
  - `tests/test_paper_trading.py` — **2 new** (rehydrate backfill + unrecoverable
    skip-to-backstop).
  - `tests/test_live_trading.py` — **1 new** (paper/live parity on the rehydrate
    backfill).

## Verification

- `uv run pytest -q` (full suite, qa-reviewer ran independently)
  - **2369 passed**, 0 failed.
- `ruff check` — clean.
- `uv run mypy src` — clean.
- QA verdict: 🟢 ship (qa-reviewer).

## Specialist flow

- **quant-trader-expert** (review-only) — root-caused both latent defects
  (restart-reset strike counter never reaching 5; bare `continue` for
  both-bounds-missing opens making them permanent orphans), traced the
  mislabeled-close consequence to the one-shot `dbd9114` backfill firing the
  normal monitor at stale prices, and designed the age-backstop + inline-backfill
  fix.
- **senior-developer** — implemented `ORPHAN_MAX_AGE` + the OR age gate,
  `resolve_bounds_from_performance_record`, the paper/live rehydrate backfill, the
  `engine.py` re-export, and 7 new tests (plus pinning the 7 strike-path tests
  young).
- **qa-reviewer** — 🟢 ship; full suite **2369 passed**, ruff + mypy clean.

## Restart-safety invariant

The core property this cycle locks in: **a structurally-unmonitorable open trade
is force-closed within a bounded wall-clock age (`ORPHAN_MAX_AGE`, 24h)
regardless of restarts; a transient young orphan is not.** The age comparison is
derived from `entry_time` (persisted, restart-immune), not from the in-memory
strike counter (reset every process start). This is the direct antidote to
Defect A: where the strike watchdog could be starved indefinitely by a frequent
restart cadence, the age backstop fires deterministically on the first cycle past
24h. The fast-path strike close is retained so genuinely transient orphans inside
the 24h window still resolve quickly without waiting out the age window.

## DEBT-072 linkage — both sides now self-heal

DEBT-072 (resolved 2026-06-26) healed the **balance** side: the unconditional
`_reconcile_locked_to_open_positions` reconcile makes a stranded-margin scenario
self-heal on restart so a failed orphan close no longer leaves the lock ledger
permanently inconsistent. DEBT-071 (this cycle) heals the
**position-state-monitoring** side: structurally-unmonitorable opens are now
either backfilled into monitorable state on rehydrate, or force-closed by the
age backstop within 24h regardless of restarts. Together the two reconciles close
the loop — the balance ledger and the position state both self-heal on restart,
so the orphan-recurrence pathology that produced 60,003 events and 0 force-closes
cannot recur.

## Risks

- The age backstop force-closes at the **current** (potentially stale) market
  price for any open that has sat past 24h with no recoverable bounds. This is
  strictly better than the prior behaviour (weeks-stale closes mislabeled as
  SL/TP), and the close is now truthfully labeled `orphan_force_close` rather than
  a phantom `stop_loss`/`take_profit`. But it is a force-close at market, not a
  bounds-respecting exit — the 24h window is the deliberate bound on how stale a
  structurally-unmonitorable open can get, not a guarantee of a good price.
- `ORPHAN_MAX_AGE = 24h` is a fixed constant, not config-driven. It is short
  enough to bound contamination yet long enough to clear a normal restart/redeploy
  cycle without nuking healthy opens that are momentarily mid-rehydrate. A future
  need for per-account tuning would require promoting it to config; recorded here
  rather than pre-built.
- The inline rehydrate backfill recovers SL/TP from `performance_record_id`; rows
  with no perf link still fall through to the age backstop (correct, by design),
  but their bounds are never restored — they are closed at market at 24h rather
  than at their intended levels. The proposal-linked repair tool (`dbd9114`)
  remains the operator path to restore bounds from proposal history for rows that
  have a `ProposalRecord.trade_id` join but no perf link.

## Follow-ups filed

- **DEBT-077 (Low, test/code-improvement)** — `runtime-reconciliation`. Add
  direct unit tests for `resolve_bounds_from_performance_record` fail-safe
  branches (missing file / null-bounds-on-found-record / corrupt JSON → `None`);
  currently only the happy path is covered end-to-end through rehydrate.
- **DEBT-078 (Medium, bug)** — `runtime-reconciliation`. The remaining narrower
  mislabel: a trade whose SL/TP was **backfilled** and then breaches at a stale
  price fires the **normal** SL/TP monitor with `reason="stop_loss"` at a stale
  price rather than `orphan_force_close`. Structural orphans now route correctly
  via the age backstop, so this is the remaining backfilled-monitorable edge.
  Folded in: a tidy-up the dev flagged — three near-identical perf/proposal
  resolution walks now exist (the new `resolve_bounds_from_performance_record` +
  the operator tools' `_PerfIndex` / `_proposal_bounds_index`); consolidating them
  behind one resolver would remove the drift risk.
