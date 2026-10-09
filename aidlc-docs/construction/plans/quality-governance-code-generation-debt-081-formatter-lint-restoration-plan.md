# Code Generation Plan: DEBT-081 Formatter/Lint Restoration

## Scope

- **Unit:** `quality-governance`
- **Stage:** Code Generation, followed by Build and Test
- **Task:** Restore the repository-wide Black/Ruff quality gate without
  changing runtime or trading behavior.
- **Related requirements:** NFR-001 and cross-cutting AI-DLC governance
  controls.
- **Related stories:** US-015, US-016.
- **Related legacy/debt:** Phase 26 Black Sweep, DEBT-042, DEBT-081.
- **Functional/NFR/Infrastructure design:** N/A. This is a bounded mechanical
  quality-gate restoration with no public behavior, safety contract,
  persistence, deployment, credential, or topology change.
- **User direction:** `[Answer]:` Proceed with the recommended DEBT-081
  `quality-governance` slice.

## Baseline

- `uv run black --check src tests scripts`: fails on 17 committed files.
- `uv run ruff check src tests scripts`: 22 findings in
  `scripts/goal_baseline.py`, `scripts/goal_eval.py`,
  `scripts/goal_gamble.py`, and `scripts/paper_run_tsmom.py`.
- `uv run mypy src`: passes across 114 source files.
- The pre-existing `.claude/settings.local.json` modification and
  `.claude/scheduled_tasks.lock` untracked file are outside this slice and
  must remain untouched.

## Code Generation Steps

- [x] Apply Black to `src/`, `tests/`, and `scripts/`; confirm only the 17
  baseline candidates change.
- [x] Normalize the four goal/paper-runner import blocks while preserving the
  intentional pre-import logging suppression behavior.
- [x] Replace the loop-capturing percentile lambda in
  `scripts/goal_gamble.py` with behavior-equivalent direct percentile values.
- [x] Run Ruff and Black checks and inspect the full diff for behavioral
  changes or unrelated files.

## Build and Test Steps

- [x] Run targeted tests for the formatted/linted script and module surfaces.
- [x] Run `uv run pytest`.
- [x] Run `uv run black --check src tests scripts`.
- [x] Run `uv run ruff check src tests scripts`.
- [x] Run `uv run mypy src`.
- [x] Run `git diff --check` and verify runtime `data/` is unchanged.

## Completion Checklist

- [x] Add a code-generation summary under
  `aidlc-docs/construction/quality-governance/code/`.
- [x] Create a session log and a unit cross-check.
- [x] Resolve DEBT-081 in `docs/TECH-DEBT.md` and refresh the debt-unit map.
- [x] Update the `quality-governance` row and latest-construction note in
  `aidlc-docs/aidlc-state.md`.
- [x] Record final verification evidence and mark all completed steps `[x]`.

## Final Evidence

- Black reformatted exactly the 17 baseline candidates; the other 205 Python
  files were already compliant.
- Ruff's 22 baseline findings were cleared without configuration changes.
  The four scripts retain logging suppression before project imports, and the
  percentile calculation uses the same sorted-list index formula directly.
- Targeted regression suites: 292 passed in 4.01s.
- AST comparison: all 13 formatting-only `src/` and `tests/` files are
  equivalent to `HEAD` when source-location attributes are ignored.
- Script entry points: all four `--help` invocations passed.
- Complete repository: 2604 passed in 43.42s.
- Black: 222 files clean; Ruff: all checks passed; mypy: 114 source files
  clean; `uv lock --check` and `git diff --check`: passed.
- No dependency, lockfile, deployment, credential, production configuration,
  external trading, or runtime `data/` change was made.
