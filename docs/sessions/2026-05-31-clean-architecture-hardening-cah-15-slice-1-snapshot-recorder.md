# Session: clean-architecture-hardening CAH-15 Slice 1 — extract `SnapshotRecorder` from `TradingEngine`

Date: 2026-05-31
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-15 (Tier 5 directional epic: `TradingEngine` God-Object decomposition).
Related ADR: `docs/adr/0001-trading-engine-decomposition.md` (CAH-15 design, quant 🟡 → greenlit Slices 1+2, Slice 3 deferred).
Origin finding: ENG-F3 (God-Object / SRP / Divergent-Change in `src/runtime/engine.py`).

> FIRST extraction slice of the CAH-15 epic, after the design ADR (commit 70b7802) landed.
> The ADR gates the epic on CAH-05 (already shipped 2026-05-28) and on a quant-reviewed
> design doc (shipped). Slice 1 is the lowest-coupling collaborator — persistence /
> snapshotting — and is behavior-preserving. Slice 2 (`PositionMonitor`) and the
> conditional Slice 3 (gate-chain, deferred) remain.

## Scope

Extract the engine's persistence concern into a focused, independently-testable
collaborator, with **no behavior change**. Per ADR §"Collaborator 1 — SnapshotRecorder"
the following five methods move:

- `_record_portfolio_snapshot` — end-of-cycle `AssetSnapshot` capture
- `_record_closed_trade` — `POSITION_CLOSED` event + realised-P&L attach-back
- `_save_performance_record` — per-trade `PerformanceRecord` write
- `_classify_close_reason` — close-reason → `TradeOutcome` map
- `_find_proposal_record_for_trade` — proposal-record lookup by trade id

Out of scope (later slices): `PositionMonitor` (`_monitor`/exit/orphan, Slice 2);
the gate chain (Slice 3, deferred).

## What shipped

### New module `src/runtime/snapshot_recorder.py` (306 lines)

`SnapshotRecorder` holds the five methods verbatim (logic byte-identical). It is
**stateless** — quant-confirmed in ADR §2 that none of the five reads any of the six
per-cycle caches; its only shared-state touch is the DEBT-066 mark-price write-through.

Constructor-injected deps: `proposal_history`, `activity_log`, `proposal_engine`
(for `performance_tracker` access), `portfolio_tracker`, `default_exchange` (the old
`self.exchange` per-trade-ticker fallback), `remember_mark_price` callback, `mode`,
`quote_currency`. The trivial `_sub_account_id` resolver is inlined (imports
`DEFAULT_SUB_ACCOUNT_ID`). Public interface preserves the engine signatures:
`async record_portfolio_snapshot(...)`, `record_closed_trade(...)`,
`find_proposal_record_for_trade(...)`; `_save_performance_record` / `_classify_close_reason`
are recorder-private.

### Engine wiring (`src/runtime/engine.py`)

- New `_make_snapshot_recorder()` builds a recorder from the engine's **live**
  `portfolio_tracker` / `mode` / `quote_currency` / `exchange`. Because the recorder
  is stateless it is rebuilt on demand rather than captured in `__init__` — this is the
  load-bearing decision (see Decisions).
- The five method bodies are replaced by four thin delegating wrappers
  (`_record_portfolio_snapshot`, `_record_closed_trade`, `_save_performance_record`,
  `_find_proposal_record_for_trade`) so every call site (run_cycle + the monitor methods
  that stay on the engine in Slice 1) and every existing test pass unchanged.
  `_classify_close_reason` has no external caller and is dropped from the engine.
- Three now-unused imports removed (`PerformanceRecord`, `PerformanceTracker`,
  `TradeOutcome`); `from src.runtime.snapshot_recorder import SnapshotRecorder` added.
- Engine: **5343 → 5196 lines** (−147).

## Decisions

1. **Rebuild the recorder per-access instead of capturing it in `__init__`.** The
   existing tests mutate `engine.portfolio_tracker` / `mode` / `quote_currency` *after*
   `build_engine(...)`. A construct-once recorder would capture the construction-time
   values and silently skip the snapshot / write to the wrong path. Because the recorder
   owns no per-cycle state, rebuilding it from live engine attributes on each delegate
   call is cheap, behavior-identical, and free of any capture-staleness bug. (Slice 2's
   `PositionMonitor` can take the engine's `record_closed_trade` bound delegate, so this
   does not block injecting a recorder reference later.)
2. **ADR CHANGE B — `remember_mark_price` injected directly.** The recorder writes the
   per-trade mark through the engine's `_remember_mark_price` callable passed at
   construction, so the engine-owned `_mark_price_cache` stays the single source of
   truth. The mark write is never chained through another collaborator (which would shift
   *when* the cache is written relative to the cap-blocker read).
3. **Keep thin engine delegates** rather than rewriting every call site. This makes the
   slice minimal and keeps the behavior-preservation proof (existing snapshot /
   closed-trade / mark-price-cache tests untouched).

## Tests / checks

- New `tests/test_snapshot_recorder.py` — 11 tests: tracker-absent early return; the
  **CHANGE-B write-through fires the injected callback** once per open trade with the
  same (symbol, price) as `current_prices`; default-exchange fallback when `exchange=None`;
  closed-trade emits `POSITION_CLOSED` + attaches outcome; unknown-proposal null-id path;
  `_classify_close_reason` parametrized map; `find_proposal_record_for_trade` hit/miss;
  perf-record routed to the trade's sub-account path.
- Existing behavior proof (unchanged, all green): `test_portfolio_snapshot_recorded_each_cycle`,
  `test_portfolio_snapshot_skipped_when_tracker_absent`, `test_close_writes_performance_record_for_dashboard`,
  `test_closed_trade_performance_record_uses_trade_sub_account_path`,
  `test_mark_price_cache_populated_from_asset_snapshot`, the mark-cache fresh/stale suite,
  `test_portfolio_snapshot_balance_failure_does_not_break_cycle`.
- Full suite: **2328 passed** (+11 from the 2317 CAH-14 baseline), 0 failed.
- `black` clean, `ruff check src tests` clean, `mypy src` clean (102 source files).

## Risks

- **Per-access rebuild cost** — negligible (a handful of field assignments, a few times
  per cycle); the recorder is intentionally trivial to construct.
- **Slice 2 dependency direction** — `PositionMonitor` will need to record closed trades
  through the recorder. The engine's `_record_closed_trade` delegate is the stable seam
  for that; CHANGE A (multi-rung single-pass close-count equality) is the mandatory proof
  for Slice 2, not this slice.

## Debt

None added, none resolved. The CAH-15 plan entry + ADR track the epic; this slice is the
audit trail. CAH-15 Slice 2 (`PositionMonitor`) is the next unit; Slice 3 (gate-chain)
stays deferred per the ADR until coupling is re-measured after Slice 2.
