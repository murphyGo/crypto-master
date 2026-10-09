# Code Summary: DEBT-081 Formatter/Lint Restoration

## Outcome

The repository-wide Python formatting and lint gates are green again. This
slice changed no product contract, trading policy, persistence schema,
dependency, deployment configuration, credential wiring, or runtime data.

## Changes

- Applied the existing Black configuration to the 17 files identified by the
  current baseline under `src/`, `tests/`, and `scripts/`.
- Normalized imports in `goal_baseline.py`, `goal_eval.py`, `goal_gamble.py`,
  and `paper_run_tsmom.py` while keeping logging disabled before project-module
  imports. Narrow per-import E402 waivers record that intentional boundary.
- Replaced the loop-local percentile lambda in `goal_gamble.py` with direct
  p10/p90 calculations using the same sorted-list index formula.
- Did not change Ruff/Black configuration, dependency metadata, or tests to
  weaken the quality gate.

## Verification

- Targeted tests: 292 passed.
- AST comparison: 13/13 formatting-only `src/` and `tests/` files are
  equivalent to `HEAD` with source-location attributes ignored.
- Four script `--help` entry points passed.
- Full suite: 2604 passed.
- Black: 222 files clean.
- Ruff: all checks passed.
- mypy: 114 source files clean.
- `uv lock --check` and `git diff --check`: passed.
- Repository `data/` was unchanged.

## Traceability

- Unit: `quality-governance`
- Debt: DEBT-081
- Requirements/stories: NFR-001, US-015, US-016
- Historical context: Phase 26 Black Sweep and DEBT-042
