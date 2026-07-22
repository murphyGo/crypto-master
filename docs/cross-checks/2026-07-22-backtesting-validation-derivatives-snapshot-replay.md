# Cross-Check: backtesting-validation Derivatives Snapshot Replay

## Scope

Independent Construction Build & Test cross-check for Derivatives Data Slice 4
LC-11. The review covers pinned Snapshot v1/v2 replay, per-primary-bar
Funding/OI context, backtest/harness/robustness propagation, deterministic
provenance, explicit snapshot refresh, offline/no-fallback behavior, and the
promotion-blocking insufficient-evidence contract.

The cross-check reads Slice 4 together with the already sealed Slice 1 public
acquisition, Slice 2 immutable Snapshot v2 persistence, and Slice 3 runtime
context evidence when deciding FR-046 and US-025 completion.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-025 Backtesting Execution | Complete | `Backtester` accepts an optional pinned context provider and evaluates it at each primary candle; focused and complete regressions pass. |
| FR-026 Automated Feedback Loop | Complete | `RobustnessGate.evaluate_snapshot` propagates the same replay into baseline, OOS, walk-forward, and sensitivity sub-runs. |
| FR-027 Technique Adoption | Complete | Context-required evidence cannot promote from an unpinned, v1, missing, short, or gapped replay; operator adoption controls remain unchanged. |
| FR-034 Robustness Validation Gate | Complete | `INSUFFICIENT_DATA` is distinct from `SKIPPED` and blocks `overall_passed`; all four existing gates remain represented. |
| FR-046 Perpetual Derivatives Market Context | Complete | Slice 1 acquisition + Slice 2 versioned persistence + Slice 3 runtime context + Slice 4 deterministic replay now cover the full requirement. |
| NFR-006 Structured Backtest Results | Complete | Backtest/report artifacts serialize replay identity, canonical configuration digest, seed, and context coverage. |
| DD-NFR-008 Snapshot integrity/compatibility | Complete | Exact generation pinning, schema-v1 unavailability, v2 integrity, OI retention, unexplained Funding-prefix rejection, and suffix/gap failures are covered. |
| DD-NFR-009 Determinism/no look-ahead | Complete | All context timestamps are bounded by primary `as_of`, predicted funding is absent, repeated exact generation/config/seed reports are identical, and snapshot runs are offline. |
| DD-NFR-011 Public-data security | Complete | Reports sanitize raw exception messages; normalized public snapshot values only; no credentials, signed query material, path, or raw payload is serialized. |
| DD-NFR-012 Maintainability/isolation | Complete | Focused optional seams, no new dependency, deterministic fakes/tmp paths, scoped Black/Ruff, repository mypy, and full pytest pass. |

## Story Matrix

| Story | Status | Evidence |
|-------|--------|----------|
| US-002 Historical technique evaluation | Complete | Pinned replay produces structured deterministic backtest and robustness evidence tied to strategy/config/snapshot/seed. |
| US-003 Robustness before promotion | Complete | OOS, walk-forward, regime, and sensitivity gates remain visible; failed or insufficient evidence blocks promotion while compatible skips remain explicit. |
| US-025 Runtime and historical derivatives context | Complete | Runtime uses the sealed shared builder, replay delegates to that same builder, future values are excluded, v1/missing data is explicit, and v2 replay is deterministic. |

## Implementation Evidence

- `src/backtest/reproducibility.py:22` — immutable replay identity;
  `:45` — canonical configuration digest.
- `src/backtest/snapshot_replay.py:40` — pinned source; `:121` — per-bar
  context; `:144` — coverage; `:273` — unexplained prefix fail-closed repair.
- `src/backtest/engine.py:494` / `:576` / `:701` — optional single,
  multi-timeframe, and dispatcher seams; `:847` — primary-candle context lookup;
  `:335` — structured provenance fields.
- `src/backtest/validator.py:94` — `INSUFFICIENT_DATA`; `:416` — blocking
  aggregation; `:439` — pinned snapshot evaluation.
- `src/backtest/harness.py:172` — same replay propagated to account backtests;
  mixed generations are rejected during combination.
- `scripts/run_robustness_gate.py:335` — explicit collector-to-v2 refresh;
  `:651` — snapshot-only runner; `:705` — sanitized runner failure report.

## Test Evidence

- Focused v1/v2/replay/engine/gate/harness/CLI: 210 passed in 11.69s.
- Generated-path coverage: 183 passed in 17.80s; 92% combined across six
  measured modules (`snapshot_v2` 85%, `reproducibility` 82%,
  `snapshot_replay` 95%, `engine` 98%, `validator` 97%, `harness` 94%).
- Shared live/replay builder and proposal/runtime compatibility: 103 passed in
  4.59s.
- Existing backtest script consumers: 46 passed in 17.77s.
- Hermetic fake refresh -> exact generation reload -> replay -> report twice:
  1 passed in 1.27s with identical normalized reports.
- Complete repository: 2585 passed in 46.89s.
- Black/Ruff pass on all 13 Slice 4 files; `mypy src` passes 113 files; lock,
  compile, offline import, diff, duplicate, TODO, dependency, deployment, and
  tracked `data/` checks pass.

New Build & Test regressions pin the previously missing boundaries:

- `tests/test_backtest_snapshot_replay.py:273` — unexplained Funding prefix.
- `tests/test_backtest_snapshot_replay.py:303` — symbol mismatch.
- `tests/test_backtest_validator.py:355` — repeated report determinism.
- `tests/test_run_robustness_gate.py:433` — exact generation forwarding.
- `tests/test_run_robustness_gate.py:542` — hermetic full E2E.
- `tests/test_run_robustness_gate.py:629` — raw exception/path/query exclusion.

## Gaps and Risks

- No blocking LC-11/FR-046/US-025 gap remains.
- Live Binance smoke was not run. It is explicitly opt-in and not a normal CI
  or deterministic promotion prerequisite.
- No production replay performance threshold exists; recorded test runtimes
  are observations only.
- Proposal-layer Funding+OI filtering and Funding-Extreme MR remain separate
  hypothesis/evidence-gated product slices. Their absence is not a gap in the
  optional context acquisition/runtime/replay requirement.
- Repository-wide Black/Ruff remains red only for existing DEBT-081: 19 Black
  candidates and 22 Ruff findings in four pre-existing scripts. No Slice 4
  file overlaps.

## Unit and Debt Mapping

- **Primary Unit:** `backtesting-validation`
- **Secondary Units:** `exchange-integration`, `strategy-framework`,
  `persistence-data-integrity`, `quality-governance`
- **Related Debt:** DEBT-043 and DEBT-080 resolved precedents; DEBT-081 active
  and unrelated. No new debt.
- **Legacy Phase Context:** Phases 5, 9, 19, 24, and 25.

## Recommendations

**PASS.** Operator approval was recorded on 2026-07-22; LC-11 and
FR-046/US-025 are sealed Complete across Slices 1-4. Operations is N/A unless a
later, separate approval explicitly authorizes production snapshot refresh or
deployment. Plan the proposal Funding+OI regime filter as a separate next
slice; do not fold it into this completed replay boundary.
