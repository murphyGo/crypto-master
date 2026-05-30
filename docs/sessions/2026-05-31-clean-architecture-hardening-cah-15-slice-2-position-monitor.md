# Session: clean-architecture-hardening CAH-15 Slice 2 — extract `PositionMonitor` from `TradingEngine`

Date: 2026-05-31
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-15 (Tier 5 directional epic).
Related ADR: `docs/adr/0001-trading-engine-decomposition.md` — §"Collaborator 2 — PositionMonitor", CHANGE A, CHANGE B, ENG-F6.
Origin findings: ENG-F3 (God-Object), ENG-F6 (extract the inlined orphan branch into `_handle_orphan_trade`).

> SECOND extraction slice of the CAH-15 epic, after Slice 1 (`SnapshotRecorder`).
> The highest-risk slice — it relocates the LIVE-MONEY exit path. Both ADR
> CHANGE A and CHANGE B are folded in, and a mandatory `quant-trader-expert`
> review was run (🟢) alongside `qa-reviewer` (🟢).

## Scope

Extract the monitor/exit concern into a focused collaborator with **no behavior
change**. Moved (verbatim) from `src/runtime/engine.py` into new
`src/runtime/position_monitor.py::PositionMonitor`:

- `_monitor` → `monitor(cycle_id, result, sub_account, trader, exchange=None)`
- `_maybe_time_stop`, `_maybe_stale_age_action`, `_classify_trade_reconciliation`,
  `_resolve_time_stop_window`, `_technique_name_for_trade`, `_missing_position_state`
- NEW `_handle_orphan_trade` — the ENG-F6 extraction of the orphan branch that was
  inlined in `_monitor`.
- The monitor-domain constants `_TIMEFRAME_TO_SECONDS` / `_timeframe_to_seconds`
  (time-stop window math) and `ORPHAN_AUTO_CLOSE_THRESHOLD` (K=5 watchdog).

Out of scope: Slice 3 (`ProposalGateChain`) — deferred per ADR Alternative C; do
not start without a fresh go/no-go after re-measuring coupling.

## Key decisions

1. **Construct-once monitor (NOT rebuilt per call like the Slice-1 recorder).**
   The monitor owns `_orphan_strike_counts`, which is **cross-cycle** state
   (pruned to open trades each pass, **never reset** — it is the watchdog's only
   memory of *consecutive* orphan strikes; resetting it per cycle would defeat
   the Fly 260h BNB force-close). So the engine holds a single
   `self._position_monitor` built once in `__init__`.
2. **`_orphan_strike_counts` exposed as a read-only engine property** proxying to
   `self._position_monitor._orphan_strike_counts`, so the ~8 existing
   `engine._orphan_strike_counts == {...}` watchdog-test assertions resolve
   unchanged while the cache physically lives on the monitor.
3. **CHANGE B — collaborators injected as callables, never chained.**
   `remember_mark_price=self._remember_mark_price` (the engine's, so the
   engine-owned `_mark_price_cache` stays the single source of truth),
   `record_closed_trade=self._record_closed_trade` and
   `find_proposal_record_for_trade=self._find_proposal_record_for_trade` (the
   Slice-1 engine delegates that resolve the live `SnapshotRecorder` each call).
   The mark write fires at the same point in the pass as before (SL/TP ticker
   read precedes the close; orphan path also writes through).
4. **CHANGE A — monitor is the sole owner of `closed_count → result.positions_closed`.**
   The four rungs (SL/TP, time-stop, stale-age, orphan force-close) stay mutually
   exclusive via `continue`, each bumps a single local `closed_count`, and the
   one write to `result.positions_closed` happens at end of pass.
5. **No module-level `engine` import in `position_monitor`** (would be circular).
   `CycleResult` is a `TYPE_CHECKING` annotation; `EngineError` / `ErrorCategory`
   are imported function-locally inside `monitor` / `_handle_orphan_trade` (run
   only at call time, when `engine` is fully loaded). `ORPHAN_AUTO_CLOSE_THRESHOLD`
   is **re-exported** from `engine.py` (redundant-alias form) so existing
   `from src.runtime.engine import ORPHAN_AUTO_CLOSE_THRESHOLD` callers/tests keep
   resolving.

## Files changed

- NEW `src/runtime/position_monitor.py` (≈750 lines incl. docstrings).
- `src/runtime/engine.py`: 7 methods removed; `run_cycle` delegates to
  `self._position_monitor.monitor(...)`; monitor constructed at end of `__init__`;
  `_orphan_strike_counts` property added; `ORPHAN_AUTO_CLOSE_THRESHOLD` re-export;
  unused imports `OpenTradeState` / `default_max_bars_held` dropped. **5196 → 4603
  lines (−593).**
- `tests/test_runtime_engine.py`: one monkeypatch target moved to
  `engine._position_monitor._classify_trade_reconciliation` (the method moved);
  NEW `test_monitor_multi_rung_single_pass_closes_each_exactly_once` (CHANGE-A
  proof). All other hunks are black/ruff line-reflows — no assertion changed.
- `tests/test_import_hygiene.py`: added `src.runtime.position_monitor` to
  `COLD_IMPORT_TARGETS` (pins the no-circular-import contract).

## CHANGE-A behavior proof

`test_monitor_multi_rung_single_pass_closes_each_exactly_once`: one `run_cycle`
with four open trades — A→`stop_loss` (SL/TP), B→`time_stop` (weeks old, past the
48h/1h-default window), C→`stale_age_cap` (30h: past the 24h cap but **inside** the
48h time-stop window, reconciliation MONITORABLE), D→orphan force-close
(pre-seeded to `THRESHOLD-1`). Asserts `positions_closed == 4`, distinct close
reasons `["stale_age_cap","stop_loss","time_stop"]`, `force_close_orphan` awaited
once for D, one canonical event per rung, and `D-orphan` pruned from the counter.
The C-at-30h-inside-48h detail is the load-bearing check that proves the
time-stop-wins-over-stale ordering survives extraction.

## Tests / checks

- Full suite: **2329 passed** (+1 from the 2328 Slice-1 baseline = the new
  CHANGE-A test), 0 failed.
- `ruff check src tests` clean; `mypy src` clean (103 source files); `black` clean.
- Targeted `-k "monitor or orphan or time_stop or stale or force_close"`: 49 passed
  (all existing behavior-preservation tests pass unchanged through `run_cycle`).
- `test_import_hygiene.py`: 6 passed (cold-import of `position_monitor` succeeds).

## Reviews

- **quant-trader-expert 🟢 SHIP** — byte-faithful against `git show main`; CHANGE A
  (single `closed_count`, four mutually-exclusive rungs, single write) and CHANGE B
  (direct `remember_mark_price`, same write point) confirmed; orphan cross-cycle
  prune-not-reset + K=5 intact (Fly-260h guard); reconciliation resolution table
  (auto_close suppressed on DEGRADED/UNRECOVERABLE) preserved; no gate-order/timing
  shift; `account_exchange = exchange or self._default_exchange` capture safe
  (`engine.exchange` never reassigned).
- **qa-reviewer 🟢 Ship** — 2329 passed, ruff + mypy clean; test diff additive only
  (one monkeypatch-target move + the new test); the 7 bodies are pure relocations;
  re-export + function-local import hygiene confirmed; CHANGE-A test sound.

## Risks

- The monitor captures `default_exchange=self.exchange` at construction. Safe today
  (the engine never reassigns `self.exchange`); if a future change makes the
  account exchange mutable post-construction, pass it per-call instead.
- Slice 3 (`ProposalGateChain`) remains the deferred, highest-coupling concern — do
  not extract without re-measuring coupling and a fresh quant go/no-go.

## Debt

None added, none resolved. ENG-F6 (`_handle_orphan_trade` extraction) landed as a
by-product of this slice, as the ADR planned. Two informational follow-ups noted by
qa (non-blocking, NOT filed as DEBT): stale doc-comments in `engine.py` /
`activity_events.py` still say `TradingEngine._monitor` (conceptual references, the
monitor logic now lives on `PositionMonitor`) — candidate for a future doc-tidy
sweep.
