# Phase 25 Cross-Check: Snapshot-Pinned Reproducible Baselines

- **Date**: 2026-05-01
- **Phase**: Phase 25 — Snapshot-Pinned Reproducible Baselines
- **Verdict**: ✅ PASS (partial seal — infrastructure complete; one
  operator follow-up action documented and non-gating)
- **Cross-check author**: docs-auditor (lead-orchestrated, due to
  upstream rate-limit)

## Scope

Phase 25 closed DEBT-043 (Medium) — the reproducibility debt
re-scoped out of DEBT-029 when Phase 20.3 was deferred. Original
problem: `scripts/backtest_baselines.py` called live Binance with no
snapshot mode; re-runs were non-deterministic across operators / days.

## Sub-task Status

| Sub-task | Status | Closure |
|----------|--------|---------|
| 25.1 Snapshot Dataset + Format | ✅ Complete | Format spec + loader + 27 tests |
| 25.2 `--snapshot` CLI Flag + Script Changes | ✅ Complete | 4 CLI flags + SnapshotExchange + 10 tests |
| 25.3 Part A Operator Runbook + Doc Restructure | ✅ Complete | Runbook + freshness policy + reproducibility note |
| 25.3 Part B First Run + Populate Numbers | ⏸ Operator (post-seal) | One-time live Binance fetch — operator action only |

## Implementation Map

### 25.1 — Format spec + loader

- `src/backtest/snapshot.py` (new): `SnapshotMetadata` Pydantic model
  with UTC-coerce field validator (Phase 21.2 pattern); `Snapshot`
  bundling metadata + `list[OHLCV]`; `SnapshotValidationError`;
  `load_snapshot` + `save_snapshot` (atomic via Phase 22.1
  `atomic_write_text`); `is_snapshot_fresh` (90-day default, `now=`
  injectable); `baseline_directory` helper.
- Format: CSV (`ohlcv.csv`) + JSON sidecar (`metadata.json`).
  Decimal-as-string round-trip. ISO-8601 UTC timestamps.
- Layout: `data/backtest/snapshots/baselines/<SYMBOL>__<timeframe>/`.
- `.gitignore` `data/` → `data/*` with carve-backs for snapshot subtree.
- 27 tests (round-trip, schema breach × 8, UTC contract, freshness
  boundary).

### 25.2 — CLI flags + SnapshotExchange

- 4 new CLI flags on `scripts/backtest_baselines.py`:
  `--snapshot [PATH]` (opt-in reproducible mode),
  `--refresh-snapshot` (operator-gated mainnet entry),
  `--max-snapshot-age-days INT` (default 30 — quant-recommended
  active-use window), `--snapshot-root PATH`. `--snapshot` and
  `--refresh-snapshot` mutually exclusive.
- `SnapshotExchange` class in `src/backtest/snapshot.py` —
  free-standing, follows the `_FakeBinanceExchange` injection pattern.
- Slice-bounds enforcement (quant carry-over from 25.1):
  `clamped_limit = min(limit, len(rows))`; `if since > last_ts_ms:
  return []`. Pinned by 2 tests.
- `refresh_snapshots` async — sole mainnet entry; two operator-visible
  warnings (logger + stdout).
- `Settings.engine_baseline_max_snapshot_age_days = 30` env-overridable.
- `rsi_universal` reconciliation: KEEP (verified against
  `strategies/rsi.py:11-18` "universal-cadence fallback").
- 10 tests including `test_cross_operator_determinism_byte_identical`
  (UUID scrubbing approved by quant — operator-trace IDs not strategy
  state).

### 25.3 Part A — Operator runbook + freshness guidance

- `docs/baselines.md` restructured:
  - Operator runbook (5-step first-fetch procedure).
  - Snapshot freshness policy (30-day active vs 90-day absolute).
  - Reproducibility note (cross-operator byte-equality contract).
  - Reference numbers intro rewritten to explain placeholder semantics.
- All 5 baselines enumerated (`rsi_universal`, `rsi_4h`, `rsi_15m`,
  `bollinger_band_reversion`, `ma_crossover`).
- Spec deviations documented:
  - 9-column table → kept at 6 (rewriter pattern hard-wired); DEBT-048.
  - `_AWAITING_OPERATOR_FIRST_RUN_` token → kept `_TBD_` (existing
    tests assert literal); bundled in DEBT-048.

## Tests

| Phase | Count | Cumulative pytest |
|-------|-------|-------------------|
| 25.1 | +27 | 1338 |
| 25.2 | +10 | 1348 |
| 25.3 Part A | 0 (docs-only) | 1348 |

ruff / mypy / black clean throughout. Reviewers 🟢🟢 on all sub-tasks.

## DEBT Closures

- **DEBT-043** ✅ Resolved (infrastructure level; operator follow-up
  documented + non-gating).

## DEBT Residue

- **DEBT-048 (Low, NEW)**: `docs/baselines.md` table widening +
  `_TBD_` → `_AWAITING_OPERATOR_FIRST_RUN_` rename. Bundle small
  docs-polish sub-task updating header regex + `render_table` + 3
  affected tests in lockstep.
- **(Informational, not a DEBT yet)**: `BacktestResult.run_id` /
  `Trade.trade_id` UUID determinism — surfaced in 25.2; future
  `--deterministic-ids` flag could land truly byte-identical
  artefacts. Not blocking; the determinism test scrubs UUIDs.

## Compliance Matrix

| Requirement | Status |
|-------------|--------|
| FR-025 Backtesting Execution — snapshot-pinned reproducibility | ✅ Complete (infra; operator action remaining for first numbers) |
| NFR-006 Backtesting Result Storage | ✅ Complete (atomic via Phase 22.1) |
| NFR-007 Trading History Storage (UTC contract) | ✅ Complete (Phase 21.2 contract preserved) |

0 ⚠️ Partial (Part B operator follow-up does not partial-flag the
infrastructure). 0 ❌ Gap.

## Verdict

**✅ PASS (partial seal)**. The reproducibility infrastructure is
autonomous-complete:
- Format spec committable + version-controlled (CSV + JSON sidecar).
- Loader / saver atomic (Phase 22.1).
- CLI flags wired (`--snapshot`, `--refresh-snapshot`,
  `--max-snapshot-age-days`).
- Slice-bounds enforced; freshness gate active.
- Operator runbook documented.
- Cross-operator determinism contract pinned by test.

The remaining work (Part B — first-run population) is a one-time
operator action requiring live Binance read-only credentials. It does
not gate further phases. Phase 25 seals here; Part B can land any time
the operator has 5 minutes.

## Open Items

None blocking. DEBT-048 (table widening polish) is a Low follow-up
that does not block any other phase.
