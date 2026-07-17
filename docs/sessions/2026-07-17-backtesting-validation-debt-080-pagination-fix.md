# Session: DEBT-080 — `fetch_ohlcv_window` pagination hole fix

- **Date**: 2026-07-17
- **Unit**: `backtesting-validation`
- **Task**: Resolve DEBT-080 (silent ~500-bar holes on >1500-bar OHLCV windows)
- **Related Requirements**: FR-025, FR-026, FR-034, NFR-006

## What changed

`scripts/backtest_baselines.py::fetch_ohlcv_window` assumed a
`since`-anchored Binance page returns the full requested count (up to
`BINANCE_MAX_LIMIT = 1500`) and jumped the next `since` by the *requested*
size. Binance serves at most 1000 bars on anchored pages (1500 only on the
no-`since` most-recent page), so every backward page left a ~500-bar hole —
the assembled window still had the requested *count* while calendar coverage
silently shrank (a 270d 1h request was missing ~28% of its span, verified
live during the 2026-07-17 `/strategy-gen` sweep).

Fix:

1. Backward pagination now fills each target span by walking forward from
   the span start by the bars **actually received**, until the span meets the
   data already held. No assumption about per-page counts remains.
2. New `_assert_contiguous` helper raises `ValueError` (symbol, timeframe,
   gap count, first hole) on both the single-page and paginated return
   paths — silently gapped data is now a loud operator error.
3. `tests/test_scripts_auto_research_candidates.py` fakes previously served
   the same 1h-spaced candle list for the "4h" timeframe; the new contiguity
   check correctly rejects that, so the fakes now serve per-timeframe
   spacing via `_make_tf_exchange()`.

## Files changed

- `scripts/backtest_baselines.py` — span-fill pagination + `_assert_contiguous`
- `tests/test_scripts_backtest_baselines.py` — `_SinceCappedBinanceExchange`
  fake (mirrors the real venue's anchored-page cap) + 3 regression tests:
  capped-page contiguity, short-history pass-through, venue-side-hole raise
- `tests/test_scripts_auto_research_candidates.py` — per-timeframe fake candles
- `aidlc-docs/construction/plans/backtesting-validation-code-generation-plan.md`
  — DEBT-080 step block
- `docs/TECH-DEBT.md`, `aidlc-docs/inception/units/debt-unit-map.md` — closeout

## Tests / checks

- `uv run pytest tests/test_scripts_backtest_baselines.py -q` — 21 passed
- `uv run pytest tests/test_run_robustness_gate.py
  tests/test_scripts_backtest_combinations.py
  tests/test_scripts_auto_research_candidates.py
  tests/test_scripts_backtest_baselines.py -q` — 54 passed
- Live verification (read-only public API): `fetch_ohlcv_window(BTC/USDT, 1h,
  2200)` → 2,200 bars, single 3,600,000 ms delta, contiguous — the exact
  request shape that previously produced a 500-bar hole
- Full `uv run pytest` — 2401 passed, 2 failed; both failures
  (`test_runtime_engine.py::test_monitor_multi_rung_single_pass_closes_each_exactly_once`,
  `test_snapshot_recorder.py::test_save_performance_record_routes_to_trade_sub_account`)
  verified failing on the pre-change tree via git-stash check — pre-existing,
  unrelated subsystems, not introduced or fixed here
- `black` / `ruff` clean on touched files
- `mypy scripts/backtest_baselines.py`: 3 pre-existing `Literal` arg-type
  errors, verified present before this change (git-stash check); not
  introduced and not fixed here

## Decisions

- Contiguity violations **raise** rather than warn: no committed snapshot
  exists yet (`data/backtest/snapshots/baselines/` is empty), so nothing
  operational depends on gapped windows; a genuine venue outage should stop
  a gate run, not silently skew it.
- No signature change — all four consumers (`backtest_baselines`,
  `run_robustness_gate`, `backtest_combinations`, `auto_research_candidates`)
  inherit the fix.

## Risks

- If Binance ever serves a genuinely gapped kline range (delisting,
  maintenance), affected fetches now fail loudly and the operator must
  choose a different window — intended behavior, but a visible change.
- Historical `--live` robustness-gate verdicts on >1500-bar 1h/15m windows
  predate this fix and remain unreliable; re-run before trusting them
  (tracked in DEBT-080's resolution notes).

## Debt

- Resolved: DEBT-080.
