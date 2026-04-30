# Phase 21 Cross-Check: Time / Timezone Hardening

**Date**: 2026-05-01
**Phase**: 21 - Time / Timezone Hardening
**Status**: All three sub-tasks complete (21.1 ✅, 21.2 ✅, 21.3 ✅)

## Scope

The 3-agent comprehensive audit on 2026-04-30 surfaced DEBT-025
(High): exchange adapters (`src/exchange/binance.py`,
`src/exchange/bybit.py`) constructed OHLCV / ticker / order
timestamps via `datetime.fromtimestamp(ms / 1000)` with no `tz=`
argument — host-local tz interpretation. `JsonlRotator`
(`src/runtime/jsonl_rotator.py`) used `datetime.now()` (also
tz-naive local) to derive the active month token. Phase 18.1's
stale-quote payload mixed both tz-naive sources. Production on
Fly (UTC host) hid the bug; local development on KST hosts
surfaced it as silent 9-hour shifts. A future region change
(e.g. `fly regions add nrt`) would silently activate the bug in
production.

Phase 21 closes DEBT-025 across three sub-tasks:

- **21.1 — UTC-Aware Timestamp Helper + Adapter Migration**
  (sealed 2026-05-01). New `src/utils/time.py` module
  (`from_unix_ms(ms) -> datetime` with `tz=UTC`; `now_utc() ->
  datetime` wrapping `datetime.now(tz=UTC)`); 8 adapter call-site
  swaps (4 in Binance, 4 in Bybit) routing every
  `datetime.fromtimestamp(ms / 1000)` through the helper;
  `JsonlRotator._coerce_timestamp` (read-side) UTC-normalised; 16
  new tests including KST-host invariance via
  `time_machine.travel(..., tz_offset=9)`. Reviewers both 🟢.

- **21.2 — `JsonlRotator` UTC Month Boundary (expanded — write-
  side sweep)** (sealed 2026-05-01). The 21.1 compatibility-
  sweep findings expanded the spec scope from rotator-only to
  the full engine-side write half: 12+ `datetime.now()` write-
  sites swept to `now_utc()` across `runtime/` / `feedback/` /
  `proposal/` / `strategy/` / `ai/` / `models.py` /
  `trading/portfolio.py`; new `ensure_utc(value)` helper added
  to `src/utils/time.py` (3-function module now); Pydantic
  `field_validator(mode="after")` UTC-coerce hooks added on 7
  models (9 timestamp fields: `ActivityEvent`, `AuditEvent`,
  `Proposal`, `CandidateRecord`, `AssetSnapshot`,
  `PerformanceRecord` ×2, `TradeHistory` ×2); reader-boundary
  naive-tolerance shims at 5 sites (`PortfolioTracker.load_
  snapshots`, `TradeHistoryTracker.get_trades_by_date_range`,
  `PerformanceTracker.get_records_by_date_range`,
  `ProposalHistory.purge_old`, `ProposalHistory.list_all` sort
  key). 13 pre-existing tests updated; 12 new regression tests
  added (KST-host invariance on fresh writes + legacy-naive read
  tolerance). Reviewers both 🟢.

- **21.3 — Stale-Quote Payload Timestamp Coherence** (sealed
  2026-05-01). Verification + type-tightening, no behaviour
  change. `_record_stale_quote_rejection` docstring extended
  with formal "Timestamp coherence contract" section naming the
  five timestamp sources flowing into the rejection payload (all
  UTC-aware post-21.1 + 21.2). 3 new regression tests pinning
  aware-on-write coherence, cross-source aware math, and legacy-
  naive read tolerance. Function body byte-identical below the
  new docstring section. Quant 🟢; qa 🟡 with recorded out-of-
  scope linter-reformat note (not actioned per lead's standing
  guidance).

The phase added **no new functional or non-functional
requirements**; the development plan's Requirements Mapping
table records Phase 21 against requirements introduced in
earlier phases — Phase 21 extends them along the
correctness-boundary axis:

- **FR-020** — Historical Chart Data Query. 21.1 makes the
  OHLCV timestamp returned by `BinanceExchange.get_ohlcv` and
  `BybitExchange.get_ohlcv` UTC-aware via `from_unix_ms(ms)`
  rather than host-local tz-naive.
- **NFR-007** — Trading History Storage. 21.1 + 21.2 make every
  timestamp written into the trade ledger UTC-aware: write-side
  via `now_utc()` swap, model-boundary via Pydantic `mode=
  "after"` validators, read-side via `ensure_utc(...)` shim on
  legacy on-disk records.
- **NFR-008** — Asset/PnL History. 21.2's `JsonlRotator` write-
  side `datetime.now()` → `now_utc()` swap fixes the active-
  month boundary so a record written near UTC midnight on a
  non-UTC host lands in the UTC-month file expected by readers.
- **FR-008** — Entry/Take-Profit/Stop-Loss Setting. 21.3 pins
  the stale-quote rejection payload's timestamp coherence: the
  fill-boundary correctness surface that decides whether to
  reject a proposal as stale.
- **NFR-012** — Live Trading Confirmation. 21.3 same — the
  stale-quote gate is the last barrier before a live fill.

Phase 21 is a mechanical TZ migration; no architectural seam
shift. No ADR.

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 21.1 | UTC-Aware Timestamp Helper + Adapter Migration (FR-020, NFR-007) | `src/utils/time.py` (new — `from_unix_ms` / `now_utc`); `src/exchange/binance.py` (4 site swaps ~lines 233, 273, 504, 506 + import); `src/exchange/bybit.py` (4 site swaps ~lines 165, 202, 433-435 + import); `src/runtime/jsonl_rotator.py::_coerce_timestamp` (read-side UTC-normalised) | `tests/test_utils_time.py` (new, 10 cases pinning UTC tzinfo + non-UTC host invariance via `time_machine.travel(..., tz_offset=9)`); `tests/test_exchange_binance.py` + `tests/test_exchange_bybit.py` (3 cases each — KST-host invariance test pinning `tzinfo=UTC` regardless of host TZ) |
| 21.2 | `JsonlRotator` UTC Month Boundary (expanded — write-side sweep) (FR-020, NFR-007, NFR-008) | `src/utils/time.py` (added `ensure_utc(value)` helper — 3-function module); `src/runtime/jsonl_rotator.py:103` (the original 21.2 spec target); `src/runtime/engine.py` (multiple write-sites); `src/runtime/activity_log.py`; `src/feedback/loop.py` (~6 sites); `src/feedback/audit.py`; `src/proposal/interaction.py` (~3 sites); `src/proposal/engine.py`; `src/proposal/notification.py`; `src/strategy/performance.py` (~6 sites incl. field defaults); `src/strategy/base.py`; `src/ai/improver.py:334`; `src/models.py`; `src/trading/portfolio.py`. Pydantic `field_validator(mode="after")` UTC-coerce on 7 models (9 fields): `ActivityEvent`, `AuditEvent`, `Proposal`, `CandidateRecord`, `AssetSnapshot`, `PerformanceRecord` (`analysis_timestamp` + `exit_timestamp`), `TradeHistory` (`entry_time` + `exit_time`). Reader-boundary shims at 5 sites: `PortfolioTracker.load_snapshots`, `TradeHistoryTracker.get_trades_by_date_range`, `PerformanceTracker.get_records_by_date_range`, `ProposalHistory.purge_old`, `ProposalHistory.list_all` (sort key). | KST-host write-side invariance test in `tests/test_runtime_jsonl_rotator.py` (active-month token = `2026-04` UTC, not `2026-05` local, when frozen at `2026-04-30T23:30:00+09:00`). 13 pre-existing tests updated for new UTC-aware return shape; 12 new regression tests across the touched modules covering KST-host invariance on fresh writes + legacy-naive read tolerance through the 5 reader shims. |
| 21.3 | Stale-Quote Payload Timestamp Coherence (FR-008, NFR-012) | `src/runtime/engine.py::_record_stale_quote_rejection` (docstring extended with "Timestamp coherence contract (DEBT-025 / Phase 21.3)" section formally documenting the UTC-aware contract for every timestamp source — body byte-identical below the new docstring section). | 3 new tests in `tests/test_runtime_engine.py`: `test_stale_quote_rejection_payload_timestamps_are_utc_aware` (line 992 — coherence: every timestamp field on the rejection event carries `tzinfo=UTC` under non-UTC host); `test_stale_quote_rejection_decision_at_minus_candle_ts_is_aware_math` (line 1033 — cross-source aware math: `decision_at - candle_ts` succeeds without `TypeError` and the resulting `timedelta` is correct); `test_stale_quote_rejection_tolerates_legacy_naive_record_on_disk` (line 1082 — legacy tolerance: pre-21.2 naive on-disk record flowing back through the read-side shim is silently UTC-coerced). |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-020 | Historical Chart Data Query | ✅ Complete (extended) | 21.1 makes the OHLCV timestamp returned by `BinanceExchange.get_ohlcv` and `BybitExchange.get_ohlcv` UTC-aware via `from_unix_ms(ms)`. The four `datetime.fromtimestamp(ms / 1000)` call-sites in each adapter (8 total) now route through the helper, returning `datetime` with `tzinfo=UTC` regardless of host TZ. Locked by 3 KST-host invariance tests in each of `tests/test_exchange_binance.py` and `tests/test_exchange_bybit.py`. |
| FR-008 | Entry/Take-Profit/Stop-Loss Setting | ✅ Complete (preserved + pinned) | 21.3 pins the stale-quote rejection payload's timestamp coherence at the fill-boundary correctness surface. Five timestamp sources (engine wall-clock, ticker candle, proposal entry, live price, persisted record) all UTC-aware post-21.1+21.2+21.3; locked by 3 regression tests asserting tzinfo on every payload field, cross-source aware math, and legacy-naive read tolerance. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-007 | Trading History Storage | ✅ Complete (extended) | 21.1 + 21.2 + 21.3 make every timestamp written into the trade ledger UTC-aware: write-side via `now_utc()` swap (12+ sites in 21.2), model-boundary via Pydantic `field_validator(mode="after")` UTC-coerce on 7 models / 9 fields (21.2), read-side via `ensure_utc(...)` shim on legacy on-disk records at 5 reader boundaries (21.2). Stale-quote rejection records (the trading-history adjacent surface most likely to mix tz-naive and tz-aware sources) pinned by 21.3's contract docstring + 3 regression tests. |
| NFR-008 | Asset/PnL History | ✅ Complete (extended) | 21.2's `JsonlRotator:103` `datetime.now()` → `now_utc()` swap fixes the active-month boundary: a record written at `2026-04-30T23:30:00+09:00` (KST) now lands in the `2026-04` UTC-month file expected by readers, not the `2026-05` local-month file. Locked by `tests/test_runtime_jsonl_rotator.py` KST-host invariance test. |
| NFR-012 | Live Trading Confirmation | ✅ Complete (preserved + pinned) | 21.3 pins the stale-quote rejection gate's timestamp coherence — the last barrier before a live fill. The gate now consumes UTC-aware timestamps from every source (engine, adapter, proposal, live price, persisted record) and the rejection payload carries UTC tzinfo on every field. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-001 / FR-002 / FR-003 | Strategy framework input contract | ✅ Complete (preserved) | The TZ migration is invisible to the `BaseStrategy` contract — strategies receive `pd.DataFrame` input where the index `datetime` values are now UTC-aware rather than naive, but pandas operations on the index are unchanged. No strategy-side code modification needed. |
| FR-006 / FR-025 | Trading Strategy / Backtest | ✅ Complete (preserved) | `Backtester` and `PaperTrader` consume the same UTC-aware timestamps; PnL math (closed by Phase 20.1 / 20.2) is timestamp-orthogonal. No regression. |
| FR-026 | Automated Feedback Loop | ✅ Complete (preserved) | `FeedbackLoop` write-sites swept in 21.2 (~6 sites in `loop.py` + `audit.py`); audit events now carry UTC tzinfo via the Pydantic `mode="after"` validator on `AuditEvent`. |
| Phase 18.1 stale-quote gate | (no FR/NFR — operational surface) | ✅ Complete (preserved + pinned) | The stale-quote gate landed in Phase 18.1 with a then-undocumented mix of tz-naive and tz-aware sources. 21.3's contract docstring + 3 regression tests close the gap; the gate itself is unchanged in behaviour. |

## Test Summary

- **Phase 21 tests at phase completion**:
  - 21.1: +16 net new across `tests/test_utils_time.py` (10),
    `tests/test_exchange_binance.py` (3), `tests/test_exchange_bybit.py`
    (3). Helper unit tests pin UTC tzinfo on `from_unix_ms` /
    `now_utc`; KST-host invariance via `time_machine.travel(...,
    tz_offset=9)`. Adapter regression tests assert
    `tzinfo=UTC` on returned timestamps regardless of host TZ.
    Plus the `JsonlRotator` KST-host UTC-month-boundary test.
  - 21.2: 13 pre-existing tests updated for new UTC-aware
    return shape (no count change); +12 new regression tests
    across the swept modules covering KST-host invariance on
    fresh writes + legacy-naive read tolerance through the 5
    reader shims.
  - 21.3: +3 regression tests in `tests/test_runtime_engine.py`
    (lines 992 / 1033 / 1082) pinning the rejection-payload
    contract.
- **Full suite at phase completion**: **1265 passing, 0
  failing.** (1231 → 1247 → 1262 → 1265 across 21.1 / 21.2 /
  21.3.)
- **Lint/format**: `ruff check` clean across all Phase 21
  source. `mypy src` clean. `black --check` clean.

## Gates

| Gate | Result |
|---|---|
| pytest | 1265 passed |
| ruff check | clean |
| mypy src | clean |
| black --check | clean |

## Verdict

**PASS.**

## Gaps

**None.** Every UTC-naive surface flagged in the 2026-04-30
3-agent comprehensive audit is now closed:

- Adapter read-side (8 sites in `binance.py` + `bybit.py`) — closed
  by 21.1.
- `JsonlRotator` read-side (`_coerce_timestamp`) — closed by 21.1.
- `JsonlRotator` write-side (`:103` and friends) — closed by 21.2.
- 12+ engine / feedback / proposal / strategy / ai / models /
  portfolio write-sites — closed by 21.2.
- Pydantic model boundary (7 models, 9 fields) — closed by 21.2.
- Reader-boundary tolerance for legacy on-disk records (5 sites) —
  closed by 21.2.
- Stale-quote rejection payload contract — closed by 21.3.

No new debt surfaced during Phase 21.

## DEBT Closure Summary

- **DEBT-025 fully resolved.** Closed across the three-cycle
  chain: 21.1 (adapter read-side, 8 sites + helper module), 21.2
  (write-side sweep, 12+ sites + 7 Pydantic UTC-coerce
  validators + 5 reader-boundary naive-tolerance shims), and
  21.3 (stale-quote payload coherence — formal contract
  docstring + 3 regression tests).
- **No new debt added** during Phase 21.

Net DEBT: 1 resolved, 0 added. **Active count drops 27 → 26;
Resolved count rises 16 → 17.**

## Recommendations for Phase 22 (or follow-up)

Phase 21 sealed cleanly with no carry-forward gaps. The next
phase's shaping is driven by the existing `docs/development-
plan.md` Current Status table and `docs/team-priorities.md`:

1. **Phase 19 — Sub-Account / Capital Segmentation** is on deck
   per the recent plan-add commit `14b692a`. Five sub-tasks
   ready (19.1 Foundation through 19.5 Strategy-Combination A/B
   Backtest Harness). Worth noting: **Phase 19.2 will introduce
   N concurrent writers per cycle against the same persistence
   files** — Phase 22.1 (Atomic JSON Persistence Helper, closes
   DEBT-028 Medium) should land *before* 19.2 to avoid race-
   condition tear-write artefacts under sub-account fan-out. The
   ordering recommendation: 22 before 19, even though the
   Current Status table has 19 listed first.
2. **Phase 22 — Persistence Atomicity & Liquidation Visibility**
   — closes DEBT-028 (atomic JSON helper for `TradeHistoryTracker`
   / `PortfolioTracker` / `ProposalHistory` / `_record_stale_quote_
   rejection`) and DEBT-027 (paper trader liquidation
   visibility). The atomic-JSON fix is the precondition for
   sub-account fan-out per recommendation 1.
3. **Standing operator action set** (carries forward from Phase
   17 cross-check):
   - Operator Fly run of `python -m scripts.auto_research_
     candidates --picks 2` (highest-priority verification
     outstanding).
   - Operator: set `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` via Fly
     secrets.
   - Operator: redeploy Fly to verify Phase 14.1 chasulang 240s
     override.
   - 3-channel push test trade.
   - Per-TF RSI baseline measurement via
     `scripts.backtest_baselines` (note: pending Phase 25's
     snapshot-pinned reproducible baselines per DEBT-043).
   - Live-mode smoke checklist execution.
4. **Linter-reformat hygiene at `engine.py:436-440`** — recorded
   in the 21.3 session log as out-of-scope, not actioned per
   lead's standing guidance. No follow-up needed; the note
   exists for audit-trail completeness only.

## Cross-Check Result

- ✅ Complete: 5 requirements (2 FR + 3 NFR) + 4 phase-adjacent
  preserved
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 21 closes. The development plan's Current Status table
now shows all three Phase 21 rows as ✅ Complete. DEBT-025
resolves to **Resolved** as the headline TECH-DEBT outcome of
the cycle. The trading-engine timestamp surface is UTC-aware
end-to-end (write-side via `now_utc()`, adapter read-side via
`from_unix_ms(...)`, model boundary via Pydantic `mode="after"`
validators, reader-boundary via `ensure_utc(...)` shim on legacy
on-disk records, stale-quote payload contract pinned via
docstring + 3 regression tests). No new debt surfaced. 1265
tests passing; ruff / mypy / black all clean. Recommended Phase
22 above the line: atomic JSON persistence helper before Phase
19 sub-account fan-out introduces N concurrent writers per
cycle.**
