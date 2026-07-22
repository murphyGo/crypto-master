# Session: exchange-integration Derivatives Runtime Context

**Date:** 2026-07-19

**Primary unit:** `exchange-integration`

**Secondary units:** `strategy-framework`, `proposal-runtime`,
`dashboard-operator-ui`, `quality-governance`

**Stage:** Code Generation Part 2

**Status:** Generated; explicit code review pending before Build & Test

## Scope

Executed the approved ten-step Derivatives Data Slice 3 plan: immutable runtime
context/state contracts, a pure no-look-ahead builder, a bounded engine-scoped
public-data service, optional strategy/proposal plumbing, engine prefetch and
shutdown, safe health events, and the existing Ops Diagnostics projection.

Excluded proposal filtering, Funding-Extreme MR, replay/backtest consumption,
Snapshot v2 writes, `data/`, deployment, dependencies, credentials, and every
order/risk path.

## Decisions implemented

- Keep the feature disabled by default and construct no object in that state.
- When enabled, use one dedicated Binance USD-M mainnet public client with all
  credential fields empty; never reuse an account exchange.
- Cache normalized immutable values in memory only. Use per-series atomic
  replacement so a partial/invalid response cannot overwrite good records.
- Keep current Funding/OI reads per cycle while scheduling Funding history on
  its 8h grid and OI history with an independent 1h cursor.
- Bound work with four-way concurrency, 5s/15s deadlines, 300s rolling budgets,
  at most two transient retries, and per-symbol/per-series circuit state.
- Resolve proposal context at the final primary candle timestamp and share one
  provider read across all techniques at that decision boundary.
- Preserve legacy strategy signatures through inspection before invocation,
  never by catching and retrying `TypeError`.
- Make derivatives degradation additive and fail-open for existing OHLCV
  scanning; explicit strategy requirements alone can return neutral before
  analysis.
- Persist only safe health activity events. The runtime context cache itself is
  intentionally disposable and not hydrated on restart.

## Files changed

Application/config:

- `.env.example`
- `src/config.py`
- `src/exchange/derivatives.py`
- `src/runtime/derivatives_context.py`
- `src/strategy/market_context.py`
- `src/strategy/base.py`
- `src/strategy/loader.py`
- `src/proposal/engine.py`
- `src/runtime/activity_events.py`
- `src/runtime/engine.py`
- `src/main.py`
- `src/dashboard/pages/ops.py`

Tests:

- `tests/test_exchange_derivatives.py`
- `tests/test_strategy_market_context.py`
- `tests/test_runtime_derivatives_context.py`
- `tests/test_strategy_base.py`
- `tests/test_strategy_loader.py`
- `tests/test_proposal_engine.py`
- `tests/test_config.py`
- `tests/test_runtime_engine.py`
- `tests/test_main_dispatch.py`
- `tests/test_runtime_activity_log.py`
- `tests/test_dashboard_ops.py`

AI-DLC artifacts:

- `aidlc-docs/construction/plans/exchange-integration-code-generation-plan.md`
- `aidlc-docs/construction/exchange-integration/code/derivatives-runtime-context-summary.md`
- `aidlc-docs/audit.md`
- `aidlc-docs/aidlc-state.md`
- this session log

## Validation

- Approval-time baseline: 523 passed in 4.84s.
- Domain/builder: 31 passed.
- Service: 12 passed in 1.52s with fake clock/random/source and no network.
- Modified component group: 560 passed in 5.34s.
- Full repository: 2555 passed in 42.06s.
- Black passed on the 22 touched Python files.
- Ruff passed on the same 22 files.
- `uv run mypy src`: 111 source files, zero issues.
- `git diff --check`: passed.
- No duplicate generated Python file, unsafe raw payload/credential event,
  network-at-import behavior, leaked owned task, context look-ahead, tracked
  `data/` mutation, dependency, migration, or deployment change was found.

## Risks and mitigations

- Venue degradation is expected and does not fail the OHLCV cycle; safe events,
  cached/stale status, per-series circuits, and Ops rows surface it.
- Runtime cache loss on restart is intentional. The first enabled cycle
  reconnects and bootstraps bounded recent normalized history.
- Required-context techniques can be neutral while data is unavailable. This
  is explicit metadata behavior and does not affect existing strategies.
- Historical parity is not claimed in this slice. Snapshot-only replay remains
  the next bounded implementation slice.

## Debt and remaining sequence

No new debt was added. Existing unrelated DEBT-081 formatting drift was not
absorbed.

1. Explicitly review and approve this generated Slice 3 code.
2. Run the separate Build & Test stage after approval.
3. Cross-check and close Slice 3 if Build & Test passes.
4. Implement Slice 4 Snapshot-only replay/robustness integration.
5. Separately design the proposal Funding+OI filter, then Funding-Extreme MR.

FR-046 and US-025 remain Partial until Slice 4 deterministic replay ships.
