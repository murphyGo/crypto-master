# Session Log: 2026-05-03 - DEBT-013 - Auto-Research Runtime Wiring

## Overview

- **Date**: 2026-05-03
- **Scope**: DEBT-013
- **Status**: ✅ Resolved

## Work Summary

Resolved the auto-research script's implicit runtime construction at
the CLI entrypoint. `main()` now builds the `FeedbackLoop` and Binance
exchange explicitly via `build_loop()` / `build_exchange()` and passes
both into `run_async()`.

## Files Changed

- Modified: `scripts/auto_research_candidates.py`
- Modified: `tests/test_scripts_auto_research_candidates.py`
- Modified: `docs/TECH-DEBT.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep `run_picks()` compatible with optional dependencies | Existing tests and lower-level callers already use that injection seam directly. |
| Make `run_async()` require caller-built dependencies | The script entrypoint no longer hides `FeedbackLoop` / exchange construction, closing DEBT-013 at the production wiring layer. |
| Add `owns_exchange` lifecycle flag | CLI still owns connect/disconnect, while future shared-runtime callers can pass a pre-connected exchange with `owns_exchange=False`. |
| Use a dynamic `fetch_ohlcv_window` proxy | Keeps changed-file mypy from following pre-existing type debt in `scripts/backtest_baselines.py`. |

## Validation

- `uv run pytest tests/test_scripts_auto_research_candidates.py -q` — 17 passed
- `uv run ruff check scripts/auto_research_candidates.py tests/test_scripts_auto_research_candidates.py`
- `uv run mypy scripts/auto_research_candidates.py`
- `uv run pytest -q` — 1415 passed

## TECH-DEBT

- DEBT-013 moved to Resolved.
- Active debt count: 12 → 11.
