# Phase 22 Cross-Check: Persistence Atomicity & Liquidation Visibility

**Date**: 2026-05-01
**Phase**: 22 - Persistence Atomicity & Liquidation Visibility
**Status**: Both sub-tasks complete (22.1 ✅, 22.2 ✅)

## Scope

Phase 22 closes two related correctness boundaries surfaced by
the 2026-04-30 3-agent comprehensive audit:

- **DEBT-028 (Medium)** — non-atomic JSON persistence across
  `TradeHistoryTracker` / `PortfolioTracker` / `ProposalHistory`
  / Phase 18.1 stale-quote rewrite. All four call sites used a
  load → mutate → `Path.write_text(json.dumps(...))` shape;
  concurrent writers raced; mid-write crashes truncated.
- **DEBT-027 (Medium)** — paper trader silently zeroed balance
  on under-water close instead of emitting a structured
  liquidation event. Operators using paper-mode to forecast live
  behaviour saw a softer drawdown profile than reality.

Phase 22 closes both across two sub-tasks:

- **22.1 — Atomic JSON Persistence Helper** (sealed 2026-05-01).
  New `src/utils/io.py::atomic_write_text(path: Path, text: str)
  -> None` writing to a uuid-suffixed `.tmp` (concurrent-writer-
  tolerant on the tmp side) then `os.replace`-ing into the
  destination, with cleanup-on-exception so a raise mid-write
  leaves no orphan tmp file. Migrated 5 named load → mutate →
  save sites: `PerformanceTracker._save_records` (`src/strategy/
  performance.py:439`), `PerformanceTracker._update_summary`
  (`:494`), `TradeHistoryTracker._save_trades` (`:1077`),
  `PortfolioTracker._save_snapshots` (`src/trading/portfolio.py:
  407`), `ProposalHistory.save` (`src/proposal/interaction.py:
  245`). `_record_stale_quote_rejection` covered transitively
  via `ProposalHistory.save`; doc comment at the call-site names
  the transitive coverage. Reviewers both 🟢. Plan-text correction
  applied in-place (`src/proposal/history.py` →
  `src/proposal/interaction.py`).

- **22.2 — Paper Trader Liquidation Visibility** (sealed
  2026-05-01). `ActivityEventType.LIQUIDATED` enum member added
  with structured payload contract (`symbol`, `side`, `entry`,
  `exit`, `qty`, `realized_pnl`, `balance_before`,
  `balance_after`). `PaperTrader.close_position` rewritten:
  detection via `projected_free = balance.free + (pnl -
  exit_fee) < 0` predicate; default branch records true negative
  equity AND emits LIQUIDATED; opt-out `auto_deposit_on_
  liquidation=True` reverts to legacy clamp-to-zero (still emits
  LIQUIDATED). `PaperBalance.free` Pydantic constraint relaxed
  (lock / deduct / reserve paths still enforce overdraw
  protection). `PaperTrader.__init__` got `activity_log` and
  `auto_deposit_on_liquidation` kwargs; `EngineConfig` /
  `Settings` mirror the flag (env-overridable
  `PAPER_AUTO_DEPOSIT_ON_LIQUIDATION`); `build_engine` plumbs
  through. Reviewers both 🟢.

The phase added **no new functional or non-functional
requirements**; the development plan's Requirements Mapping
table records Phase 22 against existing requirements:

- **FR-010** — Paper Trading Mode. 22.2 closes the paper-vs-live
  divergence at the under-water close boundary (paper now
  reflects the liquidation event live exchanges emit).
- **NFR-006** — Backtesting Result Storage. 22.1's
  `atomic_write_text` helper is the storage-correctness boundary
  (durability guarantee that destination is either fully old or
  fully new, never partial).
- **NFR-007** — Trading History Storage. 22.1 covers the trade-
  ledger persistence boundary (`TradeHistoryTracker._save_
  trades`, `PerformanceTracker._save_records` / `_update_
  summary`); 22.2 ensures liquidation persists as a structured
  event in the activity log + trade ledger.
- **NFR-008** — Asset/PnL History. 22.1 covers `PortfolioTracker.
  _save_snapshots`; 22.2 ensures the asset / PnL history reflects
  true negative equity post-liquidation (rather than a
  silently-clamped zero).

Phase 22 is mechanical persistence + visibility additions. No
architectural seam shift. No ADR.

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 22.1 | Atomic JSON Persistence Helper (FR-010, NFR-006, NFR-007, NFR-008) | `src/utils/io.py` (new — `atomic_write_text`); `src/strategy/performance.py` (3 sites — `_save_records:439`, `_update_summary:494`, `_save_trades:1077`); `src/trading/portfolio.py` (1 site — `_save_snapshots:407`); `src/proposal/interaction.py` (1 site — `ProposalHistory.save:245`); `src/runtime/engine.py::_record_stale_quote_rejection` (transitive coverage via `ProposalHistory.save`; doc comment at call-site, no body change) | `tests/test_utils_io.py` (new, 15 helper unit tests — happy path, tmp file present after crash, last-writer-wins under threads, cleanup-on-exception, uuid-tmp non-collision); `tests/test_strategy_performance.py` (+2 site regression — `_save_records` crash-mid-write, `_save_trades` threaded last-writer-wins); `tests/test_portfolio.py` (+1 — `_save_snapshots` crash-mid-write); `tests/test_proposal_interaction.py` (+1 — `ProposalHistory.save` crash-mid-write) |
| 22.2 | Paper Trader Liquidation Visibility (FR-010, NFR-007, NFR-008) | `src/runtime/activity_log.py::ActivityEventType.LIQUIDATED` (new enum member, structured payload contract); `src/trading/paper.py::PaperTrader.close_position` (under-water branch rewrite — projected-free predicate, negative-equity default + LIQUIDATED event, opt-out clamp behind flag); `src/trading/paper.py::PaperBalance.free` (`ge=0` constraint relaxed); `src/trading/paper.py::PaperTrader.__init__` (+2 kwargs `activity_log`, `auto_deposit_on_liquidation`); `src/main.py::build_engine` (plumbs `ActivityLog` + flag); `src/config.py` (`EngineConfig.paper_auto_deposit_on_liquidation`, `Settings.paper_auto_deposit_on_liquidation`); `.env.example` (`PAPER_AUTO_DEPOSIT_ON_LIQUIDATION=false` documented) | `tests/test_paper_trading.py` (+6 — `test_under_water_close_emits_liquidated_event`, `test_under_water_close_records_negative_equity`, `test_under_water_close_with_auto_deposit_clamps`, `test_exit_fee_only_shortfall_emits_liquidated_event`, `test_normal_close_does_not_emit_liquidated_event`, flag-on payload parity) |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-010 | Paper Trading Mode | ✅ Complete (extended) | 22.2 closes the paper-vs-live divergence at the under-water close boundary. Default behaviour records true negative equity and emits a structured `LIQUIDATED` activity event matching what live exchanges emit; opt-out flag `auto_deposit_on_liquidation` preserves legacy clamp behaviour for testing scenarios. Locked by 6 regression tests in `tests/test_paper_trading.py` covering both branches, fee-only shortfall, and happy-path silence. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-006 | Backtesting Result Storage | ✅ Complete (preserved) | 22.1's `atomic_write_text` helper exists as the storage-correctness primitive available to backtest result writers. (Note: `Backtester._save_result` itself is not yet routed through the helper — registered as DEBT-045 Low; the primitive is ready, the routing is a one-line follow-up.) |
| NFR-007 | Trading History Storage | ✅ Complete (extended) | 22.1 routes the trade-ledger persistence boundary through `atomic_write_text` (`TradeHistoryTracker._save_trades`, `PerformanceTracker._save_records` / `_update_summary`). Crash-mid-write cannot leave the trade ledger in a torn state. 22.2 ensures liquidation persists as a structured `LIQUIDATED` activity event with full payload (`symbol` / `side` / `entry` / `exit` / `qty` / `realized_pnl` / `balance_before` / `balance_after`) and a true-negative-equity record on the closed-trade row. |
| NFR-008 | Asset/PnL History | ✅ Complete (extended) | 22.1 routes `PortfolioTracker._save_snapshots` through `atomic_write_text` — asset / PnL snapshots are atomic on disk. 22.2 ensures the asset / PnL history reflects true negative equity post-liquidation rather than a silently-clamped zero, so equity-curve consumers see the same drawdown profile they'd see live. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-009 | Live Trading Mode | ✅ Complete (preserved) | Live trading is unaffected — the LIQUIDATED event already exists in the live path via the exchange's own liquidation reporting. Phase 22.2 adds the paper-mode parity. |
| Phase 18.1 stale-quote gate | (no FR/NFR — operational surface) | ✅ Complete (preserved) | `_record_stale_quote_rejection` covered transitively via `ProposalHistory.save` (now atomic). Doc comment at call-site names the transitive coverage so a future refactor doesn't lose the guarantee. |

## Test Summary

- **Phase 22 tests at phase completion**:
  - 22.1: +19 net new across `tests/test_utils_io.py` (15
    helper unit tests — happy path, tmp file present after crash,
    last-writer-wins under threads, cleanup-on-exception,
    uuid-tmp non-collision, `os.replace` semantics) and 4 site
    regression tests (`tests/test_strategy_performance.py` +2,
    `tests/test_portfolio.py` +1, `tests/test_proposal_
    interaction.py` +1).
  - 22.2: +6 in `tests/test_paper_trading.py` pinning the
    LIQUIDATED contract on both branches, fee-only shortfall,
    and happy-path silence.
- **Full suite at phase completion**: **1290 passing, 0
  failing.** (1265 → 1284 → 1290 across 22.1 / 22.2 = +25 net
  new across the phase: 15 atomic-helper + 4 site regression +
  6 liquidation.)
- **Lint/format**: `ruff check` clean. `mypy src` clean. `black
  --check` clean.

## Gates

| Gate | Result |
|---|---|
| pytest | 1290 passed |
| ruff check | clean |
| mypy src | clean |
| black --check | clean |

## Verdict

**PASS.**

## Gaps

**None blocking phase seal.** The two correctness boundaries
Phase 22 was scoped to close (DEBT-028 atomic persistence,
DEBT-027 paper liquidation visibility) are closed.

DEBT residue carrying forward (none of which gates Phase 22's
seal):

- **DEBT-044** (Low) — `FeedbackLoop.save_state` not migrated to
  `atomic_write_text`. Same shape as the 5 migrated sites, out
  of Phase 22.1 named scope. Mechanical one-line fix.
- **DEBT-045** (Low) — `Backtester._save_result` single-write
  not atomic. Single-write (no load → mutate cycle) but benefits
  from atomicity if the backtest run crashes during persistence.
  Helper exists, one-line route.
- **DEBT-046** (Medium, **hard prereq for Phase 19.2**) —
  Atomic write does not protect against concurrent-mutation
  loss. Single-engine deployment is safe today; Phase 19.2's
  sub-account fan-out introduces parallel workers and requires
  per-file locking (e.g. `fcntl.flock`) or per-account file
  partitioning. **Phase 19.2 cannot ship without addressing
  DEBT-046**; Prerequisites line on the 19.2 spec page cites it
  explicitly.
- **DEBT-047** (Medium, NEW from Phase 22.2 quant review) —
  Backtester has no leverage-liquidation modeling.
  `src/backtest/engine.py:371,396` does `balance += pnl_delta`
  with no margin lock / clamp / event — asymmetric with
  PaperTrader post-22.2. Resolution shapes: `BacktestConfig.
  liquidation_threshold` emitting structural marker on
  `BacktestTrade` / `BacktestResult`, OR conservative clamp +
  log at threshold. Follow-up; not blocking.

## DEBT Closure Summary

- **DEBT-028 fully resolved** (Phase 22.1). Closed by helper +
  5-site migration + transitive coverage of
  `_record_stale_quote_rejection` via `ProposalHistory.save`.
- **DEBT-027 fully resolved** (Phase 22.2). Closed by
  projected-free under-water predicate + structured LIQUIDATED
  event + negative-equity round-trip + opt-out flag for legacy
  clamp behaviour + 6 regression tests.
- **3 follow-up debts surfaced during Phase 22.1**: DEBT-044
  (Low), DEBT-045 (Low), DEBT-046 (Medium — Phase 19.2 prereq).
- **1 follow-up debt surfaced during Phase 22.2**: DEBT-047
  (Medium — backtester liquidation parity).

Net DEBT across the phase: 2 resolved (DEBT-027, DEBT-028), 4
added (DEBT-044, DEBT-045, DEBT-046, DEBT-047). Active count net
+2 across Phase 22; Resolved count rises 17 → 19 (DEBT-028 +
DEBT-027).

## Recommendations for Phase 19 (or follow-up)

Phase 22 sealed cleanly. The next phase's shaping is driven by
the existing `docs/development-plan.md` Current Status table:

1. **Phase 19 — Sub-Account / Capital Segmentation** is on deck
   per commit `14b692a`. **Phase 19.2 cannot ship without
   addressing DEBT-046** (concurrent-mutation loss under parallel
   workers). The Prerequisites line on the 19.2 spec page cites
   it explicitly; planner picks the resolution shape (per-file
   `fcntl.flock` lock OR per-account file partitioning aligned
   with the `{sub_account_id}` path layout) before 19.2 starts.
2. **DEBT-047 (backtester liquidation parity)** is the obvious
   next-pass for backtest-fidelity work. Two resolution shapes
   sketched. Consider folding into Phase 24 (strategy robustness
   polish — already scoped against DEBT-030/031/032/033/034) or
   a dedicated backtester-fidelity cycle.
3. **DEBT-044 / DEBT-045** are mechanical one-line fixes.
   Either fold into a hygiene cycle or pick up opportunistically
   when adjacent code is touched.
4. **Standing operator action set** carries forward unchanged
   from the Phase 21 cross-check (Fly auto-research run,
   `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` secret, redeploy for
   chasulang 240s override, 3-channel push test trade, per-TF
   RSI baseline measurement pending Phase 25, live-mode smoke
   checklist).

## Cross-Check Result

- ✅ Complete: 4 requirements (1 FR + 3 NFR) + 2 phase-adjacent
  preserved
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 22 closes. The development plan's Current Status table
now shows both Phase 22 rows (Atomic JSON Persistence Helper,
Paper Trader Liquidation Visibility) as ✅ Complete. DEBT-028
and DEBT-027 resolve as the headline TECH-DEBT outcomes of the
phase. The persistence layer is crash-safe (atomic writes
across 5 named sites + 1 transitive); the paper trader's
liquidation surface matches live-exchange semantics (structured
LIQUIDATED event + true-negative-equity round-trip + opt-out
flag for legacy testing scenarios). Four follow-up debts
registered (DEBT-044/045 Low atomic follow-ups, DEBT-046 Medium
Phase 19.2 prereq, DEBT-047 Medium backtester parity). 1290
tests passing; ruff / mypy / black all clean. Open: DEBT-046
must land before Phase 19.2.**
