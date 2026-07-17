# Technical Debt Unit Map

## Purpose

This document maps active `docs/TECH-DEBT.md` items to AI-DLC units. It is a
planning index, not the debt source of truth. Update `docs/TECH-DEBT.md` first
when debt is added or resolved, then refresh this map.

## Active Debt by Unit

| Unit | Active Debt | Priority Mix | Notes |
|------|-------------|--------------|-------|
| `backtesting-validation` | DEBT-080 | 1 High | `fetch_ohlcv_window` pagination drops ~500 bars/page on >1500-bar windows; robustness-gate `--live` runs and baseline snapshot refreshes on 1h/15m inherit silent holes. |

## Debt Details

| Debt | Priority | Primary Unit | Secondary Unit | Suggested Next Action |
|------|----------|--------------|----------------|-----------------------|
| DEBT-080 | High | `backtesting-validation` | — | Fix backward pagination in `scripts/backtest_baselines.py::fetch_ohlcv_window` to advance by bars actually received (or clamp `since` pages to 1000), add a loud contiguity assertion + regression test, then re-run `run_robustness_gate --live` for >1500-bar 1h/15m windows and refresh the baseline snapshot. |

## Promotion Candidates

No additional promotion candidates.

## Update Rules

- If `docs/TECH-DEBT.md` moves an item to resolved, remove it here in the same
  change.
- If a new debt item references a legacy phase, map it through
  `legacy-phase-map.md` before assigning a unit.
- If a debt item spans multiple units, choose the unit that owns the first code
  change as primary and list the other as secondary.
