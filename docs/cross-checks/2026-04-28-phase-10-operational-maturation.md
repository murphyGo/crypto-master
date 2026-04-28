# Phase 10 Cross-Check: Operational Maturation

**Date**: 2026-04-28
**Phase**: 10 - Operational Maturation
**Status**: All six sub-tasks complete (10.1, 10.2, 10.3, 10.4, 10.5, 10.6)

## Scope

Phase 10 takes the system from "feature-complete + deployable" (the
exit state of Phase 8.3 + Phase 9) to "operable in production". Every
sub-task closes a specific operational gap surfaced in prior-phase
session logs and risk lists. No new framework abstractions —
production wiring of existing components plus operator tooling.

The phase added **no new functional or non-functional requirements**;
the development plan's Requirements Mapping table records Phase 10
against requirements that were originally introduced in earlier
phases — Phase 10 wires them into the runtime / extends them to the
deployed footprint:

- **FR-009 / FR-010 / NFR-012** — Live + paper trading mode were
  shipped in Phase 4 and exposed through `src/main.py` as paper-only
  in Phase 8.3. 10.1 closed the live wiring.
- **NFR-004** — Env-driven configuration was Phase 1's principle;
  10.2 extended it to the engine tunables that had been hardcoded in
  `src/main.py`.
- **FR-025** — Backtesting Execution shipped in Phase 5.1 and was
  extended for multi-TF in Phase 9.3. 10.3 added the operator script
  that populates `docs/baselines.md`'s reference numbers using the
  existing engine.
- **NFR-008** — Mode-separated storage was Phase 3.5's contract.
  10.4 extends it to retention (monthly rotation + retention-bounded
  reads + age-based purge); 10.5 fixes the volume-mount path defect
  Cycle 1's runtime verification surfaced.
- **FR-005 / FR-012** — Performance tracking + altcoin proposals
  shipped in Phase 6.1. 10.6 closed the single-strategy lockout
  Cycle 1 diagnosed: the proposal engine now iterates every
  applicable technique per symbol with per-symbol dedup.

10.6 was added to the plan during Phase 10 itself (Cycle 2 added it
based on Cycle 1's runtime verification of the zero-trades issue
on the live Fly deployment). 10.5 was likewise added to the plan
mid-phase based on the same diagnosis. The other four sub-tasks
(10.1–10.4) were planned at the start of the phase from the
accumulated risk lists.

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 10.1 | Live Trading Wiring | `src/trading/base.py` (`Trader` Protocol), `src/main.py` (`build_exchange`, `build_trader`), `src/trading/live.py` (signature alignment), `src/runtime/engine.py` (`trader: Trader`), `docs/deployment.md` (9-step live checklist) | `tests/test_main_dispatch.py`, `tests/test_runtime_engine.py` (refactored to mock `Trader`), `tests/test_paper_trading.py` (async conversion), `tests/test_live_trading.py` |
| 10.2 | EngineConfig Env Override | `src/config.py` (`Settings.engine_*` fields + `_parse_engine_symbols`), `src/main.py` (`build_engine`) | `tests/test_config.py::TestEngineSettings`, `tests/test_main_dispatch.py::TestBuildEngineEnvOverride` |
| 10.3 | Baseline Reference Numbers | `scripts/backtest_baselines.py`, `docs/baselines.md` (operator instructions + period labels; metric cells `_TBD_`) | `tests/test_scripts_backtest_baselines.py` (6 smoke tests) |
| 10.4 | Log Retention Policy | `src/runtime/jsonl_rotator.py` (`JsonlRotator`), `src/feedback/audit.py` (composes rotator), `src/runtime/activity_log.py` (composes rotator), `src/proposal/interaction.py` (`ProposalHistory.purge_old`), `src/config.py` (`log_retention_months`) | `tests/test_jsonl_rotator.py`, `tests/test_feedback_audit.py` (rotator integration), `tests/test_runtime_activity_log.py` (rotator integration), `tests/test_proposal_interaction.py` (7 `purge_old` tests), `tests/test_config.py::TestLogRetentionSettings` |
| 10.5 | Volume-Aware Default Paths | `src/runtime/activity_log.py`, `src/feedback/audit.py`, `src/feedback/loop.py`, `src/proposal/interaction.py`, `src/proposal/notification.py`, `src/trading/portfolio.py` (latter already correct) | `tests/test_runtime_activity_log.py`, `tests/test_feedback_audit.py`, `tests/test_feedback_loop.py`, `tests/test_proposal_interaction.py`, `tests/test_proposal_notification.py`, `tests/test_portfolio.py` (one "respects `Settings.data_dir`" case each) |
| 10.6 | Multi-Technique Per-Symbol Scan | `src/proposal/engine.py` (`_propose_all_for_symbol`, `_dedup_by_symbol`, `_select_all_techniques`, `multi_technique_per_symbol` flag) | `tests/test_proposal_engine_multi_technique.py` (7 tests) |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-005 | Analysis Technique Performance Tracking | ✅ Complete (extended) | 10.6's multi-technique scan means every applicable technique now gets a chance to surface trades on every cycle, so `PerformanceTracker` accumulates samples for every loaded strategy rather than only `bollinger_band_reversion`. The dedup path drops losers per symbol but the *winning* technique still records its outcome — diversification of feeders, not diversification of trades. `tests/test_proposal_engine_multi_technique.py` pins the dedup-by-symbol contract. |
| FR-009 | Live Trading Mode | ✅ Complete (extended) | 10.1 wires `LiveTrader` into the runtime: `src/main.py::build_exchange` switches on `Settings.trading_mode` (testnet for paper, mainnet for live with a friendly error if live keys are missing), `build_trader` returns `PaperTrader` or `LiveTrader` to satisfy the new `Trader` protocol, and the engine consumes `trader: Trader` mode-agnostically. `tests/test_main_dispatch.py` covers the dispatch on every mode permutation. The 9-step live checklist in `docs/deployment.md` documents key rotation, threshold tuning, sizing, notifications, start-small advice, confirmation policy, exit policy, monitoring, and rollback. |
| FR-010 | Paper Trading Mode | ✅ Complete (extended) | Same 10.1 dispatch path; the paper branch is the unchanged Phase 4 implementation now reached via `build_trader`. PaperTrader's `open_position` / `close_position` were converted to async to satisfy the unified `Trader` protocol — covered by ~50 PaperTrader call-site conversions in `tests/test_paper_trading.py` and friends. |
| FR-012 | Altcoin Trading Proposal | ✅ Complete (extended) | 10.6's `propose_altcoins` aggregation order is **dedup-by-symbol first, then top-K** — so with `top_k=3` the result is the three best symbols (FR-012's diversification semantic), not three slots that could be eaten by the same symbol. `tests/test_proposal_engine_multi_technique.py::test_top_k_after_dedup_preserves_diversification` pins this. |
| FR-025 | Backtesting Execution | ✅ Complete (consumed) | 10.3's `scripts/backtest_baselines.py` is operator tooling on top of the existing `Backtester.run_for_strategy` (Phase 5.1 + 9.3). The script fetches Binance public OHLCV with pagination, runs the engine + `PerformanceAnalyzer` per baseline, and persists artefacts under `data/backtest/baselines/<strategy>/`. No engine change. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-004 | Environment Variable Management | ✅ Complete (extended) | 10.2 promotes 4 `EngineConfig` fields (`engine_cycle_interval`, `engine_auto_approve_threshold`, `engine_symbols`, `engine_balance`) to env vars; defaults are bytewise-equal to the pre-10.2 hardcoded values so existing deployments don't change behaviour without an explicit env setting. `engine_symbols` uses `Annotated[list[str], NoDecode]` + `field_validator(mode="before")` for comma-separated env parsing (operationally natural over JSON literals). 10.4 adds `log_retention_months: int = 12` with the same env-loadable shape. `tests/test_config.py::TestEngineSettings` + `TestLogRetentionSettings` + `tests/test_main_dispatch.py::TestBuildEngineEnvOverride` cover the propagation. 4 remaining `EngineConfig` fields deferred as DEBT-003 (Low). |
| NFR-008 | Asset/PnL History (storage / retention) | ✅ Complete (extended) | Two complementary fixes. **10.5** routes the runtime / audit / feedback / proposal / notification / portfolio defaults through `Settings.data_dir` so writes land on the persistent volume mount (`/data` on Fly), not the ephemeral container root (`/app/data`) — closing the Cycle-1-diagnosed defect that wiped logs on every machine recycle. **10.4** adds time-based monthly rotation (`<base>.YYYY-MM.jsonl`) for the audit + activity logs and an age-based archive (`<data_dir>/proposals/archive/<YYYY-MM>/`) for the per-proposal JSON files, so the volume doesn't grow unbounded. Six "respects `Settings.data_dir`" tests + 25 retention tests pin both behaviours. |
| NFR-012 | Live Trading Confirmation | ✅ Complete (extended) | 10.1's `_engine_auto_confirmation` shim auto-approves the engine's already-threshold-gated proposals — the engine's auto-approve threshold has already authorized the trade by the time the trader is asked. Interactive sessions can still swap in `default_confirmation` for stdin prompts. Auto-exit reasons (`stop_loss` / `take_profit`) skip the confirmation callback because the user pre-authorized those bounds at open time. `tests/test_main_dispatch.py` and `tests/test_live_trading.py` cover both branches. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-003 | User approval for technique adoption | ✅ Complete (preserved) | No Phase 10 sub-task touches the technique-promotion path. `FeedbackLoop.approve` / `reject` continue to be the only way `experimental/` strategies move to `active`. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-011 | Bitcoin Trading Proposal | ✅ Complete (consumed) | 10.6's `propose_bitcoin` returns the single highest-scoring candidate from the BTC set after multi-technique dedup. Existing single-proposal contract preserved. |
| FR-013 | User Accept/Reject | ✅ Complete (preserved) | Live wiring (10.1) leaves the proposal accept/reject path intact — confirmation callbacks layer on top, they don't replace it. |
| FR-014 | Proposal History Management | ✅ Complete (extended) | 10.4 adds `ProposalHistory.purge_old`; 10.5 routes the default `data_dir` through `Settings`. The history-listing API is unchanged — `purge_old` archives into a subdirectory the top-level glob ignores, so `list_all` doesn't surface archived records. |
| FR-026 | Automated Feedback Loop | ✅ Complete (consumed) | 10.5 gives `FeedbackLoop` a `data_dir` kwarg so the loop state directory lands on the volume. No loop-logic change. |

## Test Summary

- **Phase 10 tests at phase completion**:
  - 10.1: 11 new dispatch tests in `tests/test_main_dispatch.py`;
    refactored `tests/test_runtime_engine.py` to mock the `Trader`
    protocol; ~50 PaperTrader call sites converted to async across
    `tests/test_paper_trading*.py`.
  - 10.2: 12 new tests across `tests/test_config.py::TestEngineSettings`
    + `tests/test_main_dispatch.py::TestBuildEngineEnvOverride`.
  - 10.3: 6 smoke tests in `tests/test_scripts_backtest_baselines.py`.
  - 10.4: 25 new tests across `tests/test_jsonl_rotator.py` (the
    rotator's behaviour proper) + `tests/test_feedback_audit.py`
    (rotator integration) + `tests/test_runtime_activity_log.py`
    (same) + `tests/test_proposal_interaction.py` (7 `purge_old`
    tests) + `tests/test_config.py::TestLogRetentionSettings`.
  - 10.5: 6 new "respects `Settings.data_dir`" tests across the six
    touched components.
  - 10.6: 7 new tests in
    `tests/test_proposal_engine_multi_technique.py`.
- **Full suite at phase completion**: **1083 passing, 0 failing**.
- **Lint/format**: `ruff check` clean across all Phase 10 source.
  `mypy` clean on touched files (pre-existing transitive errors in
  unrelated modules tracked as DEBT-001, not new debt).

## Gaps

None blocking. All six sub-tasks shipped with passing tests and clean
lint/type baselines on touched files.

Two soft items worth flagging — neither is a gap against the
requirements mapping table, both are intentional deferrals documented
in their respective session logs and (where worth tracking) recorded
as TECH-DEBT:

1. **`docs/baselines.md` metric cells remain `_TBD_`** —
   10.3 shipped the script that populates the table but did not run
   it (no synthesised numbers — the operator runs the script when
   they want fresh numbers). This was the explicit decision recorded
   in the 10.3 session log; it's an operator follow-up, not a gap.
2. **`ProposalHistory.purge_old` has no startup hook** — the method
   ships and is tested, but no runtime path invokes it. Operators
   have to call it manually (or wire a CLI / scheduled cron). Phase
   10.4's session log explicitly defers the wiring to a separate
   sub-task; until then archive volume on disk is bounded only by
   retention reads, not by file count.

## Risks Carried Forward

1. **Calendar approximation in `purge_old`** — uses
   `30 * retention_months` days for the cutoff rather than
   `relativedelta(months=retention_months)`. ~5-day approximation at
   the 12-month default. QA flagged "acceptable but sharper with
   `relativedelta`". Auditor judged not worth tracking. (10.4)
2. **Legacy un-rotated files stay on disk forever** — the rotator
   reads them as the oldest archive but never writes them and never
   deletes them. An operator has to clean them up by hand once the
   monthly files are accumulating. Acceptable today because today's
   volumes are tiny. (10.4)
3. **OHLCV refetch per technique in multi-technique scan** — Phase
   10.6's dedup runs N×M `get_ohlcv` calls per symbol per cycle.
   Current envelope (5 symbols × 5 strategies × 4 timeframes = 100
   calls/cycle) is fine for Binance public rate limits; will start
   to bite once a second multi-TF strategy lands or the symbol list
   grows. Tracked as DEBT-002 (Low). (10.6)
4. **4 `EngineConfig` fields not env-overridable** —
   `monitor_interval_seconds`, `bitcoin_symbol`, `altcoin_top_k`,
   `actor` remain hardcoded in `build_engine`. Operators wanting to
   tune those still need a code edit + redeploy. Tracked as DEBT-003
   (Low) — will repeat the 10.2 pattern only when an operator
   request lands. (10.2)
5. **Pre-existing lint/type sweep needed** — 18 ruff + 24 mypy
   errors across `src/ai`, `src/strategy`, `src/feedback`,
   `src/trading`, tests. Pre-existing this phase (not introduced by
   any 10.x sub-task) but surfaced during the touch-and-verify of
   10.5. Tracked as DEBT-001 (Medium). One focused sweep cycle would
   clear it and unblock a future ruff/mypy CI gate. (10.5)
6. **`_client` reach-around in `scripts/backtest_baselines.py`** —
   the script paginates by accessing `BinanceExchange._client`
   directly because `BaseExchange.get_ohlcv` doesn't accept a
   `since` parameter. Operationally fine (operator-invoked, not on
   any production path) but a soft coupling. Tracked as DEBT-004
   (Low) along with a one-line mypy nit. (10.3)
7. **No live-engine smoke run in production yet** — the live wiring
   landed (10.1) but the operator still needs to redeploy Fly to
   exercise it. The 9-step checklist in `docs/deployment.md` should
   be walked with a $100 balance before flipping to live mode at
   real sizing. (10.1)
8. **`_select_best_technique` retained as live code under
   `multi_technique_per_symbol=False`** — kept for op-emergency
   rollback. Should be retired once the multi-technique path has
   accumulated production miles and the rollback flag has not been
   exercised. (10.6)

## Recommendations for Phase 11 (or follow-up)

Based on accumulated TECH-DEBT (DEBT-001 through DEBT-004), the
session-log "Follow-up Work" sections, and the cross-check itself,
the next phase shaping should consider:

1. **Pre-existing lint/type sweep (DEBT-001, Medium)** — one focused
   cycle to clear the 18 ruff + 24 mypy errors, add `types-PyYAML`
   to dev extras, and add a CI gate so future regressions are
   blocked at PR time. The most surface-area item; gating future
   touches on a clean baseline pays for itself quickly.
2. **OHLCV cache for multi-technique scan (DEBT-002, Low)** — hoist
   the OHLCV fetch above the technique loop in
   `_propose_all_for_symbol`, or cache per `(symbol, timeframe)` for
   the duration of one `propose_*` call. Closes the temporal-drift
   item (different techniques seeing different candle T's) and the
   call-count compound problem. Cheap to implement.
3. **`BaseExchange.get_ohlcv` extension with `since` parameter
   (DEBT-004, Low)** — would let `scripts/backtest_baselines.py`
   drop the `_client` reach-around, and is a clean framework
   improvement that future strategies will want anyway. Don't ship
   speculatively; wait until at least one second use case appears.
4. **`ProposalHistory.purge_old` startup hook or CLI** — the method
   is tested and ready but unwired. Wiring it to a CLI command
   (`python -m src.tools.purge_proposals`) or a startup hook would
   close the "method exists but nothing calls it" loop. One-day
   sub-task.
5. **Live-mode smoke checklist execution** — operator action, not a
   sub-task. Walk the 9-step checklist in `docs/deployment.md` with
   a $100 balance before flipping production to live mode at real
   sizing. The Phase 10.1 session log explicitly flags this.
6. **Notification redundancy for live mode** — current backends are
   Console + File. Live mode benefits from at least one push-style
   backend (Slack / Telegram / email) so the operator gets paged
   when the engine is unattended. Phase 10.1's session log carried
   this as a clear next-after-Phase-10 item. Recommend scoping into
   a Phase 11 sub-task.
7. **Populate `docs/baselines.md` reference numbers** — operator
   action: invoke `scripts/backtest_baselines.py` standalone (no
   live trading needed; only Binance public OHLCV). Updates the
   metric cells in place. Cheap, unblocks "is the LLM beating the
   baselines?" measurement.
8. **Retire `_select_best_technique` (10.6 follow-up)** — once the
   multi-technique path has accumulated production miles and the
   `multi_technique_per_symbol=False` rollback flag has not been
   exercised, drop the legacy single-selection code. Cleanup, not
   urgent.
9. **EngineConfig remaining-fields env override (DEBT-003, Low)** —
   repeat the 10.2 pattern for whichever of the four remaining
   fields actually needs operator-tunability in practice. Don't
   ship all four speculatively; wait until at least one operator
   request lands.

## Cross-Check Result

- ✅ Complete: 13 requirements (5 FR + 3 NFR + 1 CON + 4 phase-adjacent
  consumed)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 10 closes. The development plan's Current Status table now
shows every Phase 10 row as ✅ Complete. The mainline has no
non-deferred unchecked items. Carried-forward deferrals: 7.5 Tapbit
(longstanding) and the soft items above (none blocking). Recommended
Phase 11 shaping above the line: lint/type sweep + OHLCV cache +
notification push backend + baselines population.**
