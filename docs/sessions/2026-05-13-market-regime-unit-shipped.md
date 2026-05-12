# Session: market-regime unit shipped

## Unit

- `market-regime` (primary)
- Secondary units: `proposal-runtime`, `dashboard-operator-ui`, `consistency-hardening`

## Related Requirements

- FR-045
- FR-036
- FR-029
- FR-031
- NFR-003
- NFR-007
- NFR-008

## Scope

Shipped the `market-regime` unit end-to-end: pure-math classifier, per-sub-account `MarketRegimePolicy`, runtime gating in `_handle_proposal`, per-cycle classification cache, structured activity events for both block and fail-open-degraded paths, dashboard surface, and full test coverage. Combined deliverable across R1 (initial) + R2 (post-quant-review fix for Q3 🔴).

## Changes

- `src/runtime/market_regime.py` (NEW) — pure-math classifier: `classify_regime(...)` + `classify_regime_detailed(...)` + `RegimeClassification` Pydantic model + `timeframe_to_seconds(...)` helper. Decimal arithmetic via `Decimal(str(band))` lift; rules `close > SMA(200) * 1.02 → bull`; `close < SMA(200) * 0.98 → bear`; else `sideways`; insufficient candles OR stale (last candle older than `2 × timeframe`) → `unknown`.
- `src/trading/sub_account.py` — `MarketRegimePolicy` (frozen Pydantic) attached to `SubAccount.market_regime`; defaults `enabled=False, reference_symbol="BTC/USDT", timeframe="4h"`; empty `allowed_regimes` and unknown regime labels rejected at Pydantic-time.
- `src/runtime/engine.py` — `_market_regime_gate` wired into `_handle_proposal` after `PROPOSAL_ACCEPTED` and before `_correlation_gate`; per-cycle `_market_regime_cache` invalidated at `run_cycle` top alongside `_htf_trend_cache`; one OHLCV fetch per (symbol, timeframe) per cycle; `unknown` blocks by default; explicit `allowed_regimes: [..., "unknown"]` opts in; emits `MARKET_REGIME_BLOCKED` on block with `record.rejection_reason = "market_regime_blocked_<regime>"`; OHLCV fetch failure emits `MARKET_REGIME_DEGRADED` then fail-opens (returns None) — fail-open semantics match `_trend_filter_gate` precedent. One new `# type: ignore[arg-type]` at `:1692` matches the precedent at `src/proposal/engine.py:855`.
- `src/runtime/activity_log.py` — new `MARKET_REGIME_BLOCKED` event (payload: `symbol`, `timeframe`, `regime`, `baseline`, `close`, `policy_decision`, `sub_account_id`) and new `MARKET_REGIME_DEGRADED` event (payload: `symbol`, `timeframe`, `error_type`, `sub_account_id`, `policy_decision: "pass_through_degraded"`).
- `src/dashboard/pages/engine.py` — 6 new helpers (status rows + status DF + account rows + account DF + blocked-events DF + degraded-events DF), 2 dataclasses, new "Market Regime" section in `render()`.
- `aidlc-docs/construction/market-regime/functional-design/spec.md` — §4 end gained Q5 codification: a gate earns its own `ActivityEventType` *iff it represents a persistent market or portfolio condition the dashboard will chart over time*.
- `tests/test_market_regime.py` (NEW) — 13 tests covering bull/bear/sideways/unknown rule branches, insufficient/stale guards, `timeframe_to_seconds`, and the Decimal lift.
- `tests/test_trading_sub_account.py` — +5 tests covering `MarketRegimePolicy` parsing/validation (empty allowed_regimes rejection, unknown-label rejection).
- `tests/test_runtime_engine.py::TestMarketRegimeGate` — +12 tests covering gate behavior, 4-case parametrized integration (bull/bear/sideways/unknown), and the degraded-event payload.
- `tests/test_dashboard_engine.py` — +9 tests covering the helpers and the degraded surface.

## Quant adjudications (Q1-Q5)

- **Q1** (gate sequencing — regime before correlation): deferred to **DEBT-062**. Operator-priority: correlation signal is directly fixable, regime signal is non-actionable; current ordering buries the actionable one. Filed for follow-up rather than shipping the reorder in this cycle.
- **Q2** (BTC/USDT default reference): ratified-as-shipped. Multi-reference / per-symbol reference is a future extension if/when an asset class needs its own anchor.
- **Q3** (OHLCV fetch silent-disable): 🔴 caught after R1. Initial R1 cut had the gate silent-pass on fetch error with no operator-visible signal — quant's verdict: "silent-disable on a money-handling gate is the DEBT-061 anti-pattern." Fixed in R2 by adding the `MARKET_REGIME_DEGRADED` activity event with payload contract `{symbol, timeframe, error_type, sub_account_id, policy_decision: "pass_through_degraded"}` before the fail-open. R2 then 🟢 from QA on the final diff.
- **Q4** (single-candle band-crossing hysteresis): deferred to **DEBT-063**. Chop near the ±2% band flips the label every cycle; suggested fix is two-bar confirmation, keeping the ±2% threshold for backtest/live consistency with `RobustnessGate._classify_regimes`.
- **Q5** (when a gate earns its own `ActivityEventType`): ratified — codified in spec §4 as "iff it represents a persistent market or portfolio condition the dashboard will chart over time."

## 🔴-and-fix

R1 left `_market_regime_gate` silent on OHLCV fetch failure — gate returned None but emitted nothing, so operators would see proposals pass through during an outage with no breadcrumbs. Quant-trader-expert caught this as a recurrence of the DEBT-061 silent-collapse pattern: a money-handling gate must produce an operator-visible signal even on its own degraded path. R2 added the `MARKET_REGIME_DEGRADED` activity event emission immediately before the fail-open return, with the full payload contract above. Quant 🟢 on the R2 diff; QA 🟢.

## Verification

- `pytest -q` — **1882 passed** (was 1843; net +39, zero regressions).
- `ruff check src tests` — fully clean.
- `mypy` on changed files — clean; one new `# type: ignore[arg-type]` at `src/runtime/engine.py:1692` mirrors the precedent at `src/proposal/engine.py:855`.

## Risks

- Fail-open semantics on OHLCV fetch error are intentional and match `_trend_filter_gate` precedent, but now operator-visible via `MARKET_REGIME_DEGRADED` so a sustained outage will not silently widen exposure.
- Live-mode `unknown`-override (operator escape hatch to admit during low-confidence classification) is deferred per spec §6 — current behavior is "unknown blocks by default; opt-in via `allowed_regimes: [..., \"unknown\"]`".
- Gate sequencing (DEBT-062) means cap-bound accounts may see regime-block events dominate over correlation-block events on the dashboard until the reorder ships.
- Classifier flapping (DEBT-063) at the ±2% band on chop will produce noisy admit/block alternation until the two-bar confirmation lands.

## Reviewer notes

- quant-trader-expert: 🟢 on R2 final diff after Q3 fix.
- qa-reviewer: 🟢 on R2 final diff.

## Open decisions resolved-as-shipped

- Reference symbol: BTC/USDT only (default, not multi-reference).
- Operating mode: gate-only (block proposals), not rank/score.
- `unknown`-override in live mode: deferred per spec §6.
