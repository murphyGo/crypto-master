#!/usr/bin/env bash
# Lint and type-check the project (CI / pre-commit safe — no rewrites).
#
# Phase 13.1 (DEBT-009) split this from the prior `--fix` script:
#   * `scripts/lint.sh`     — report-only, safe for CI gates
#   * `scripts/lint-fix.sh` — `ruff check --fix` for dev convenience
#
# Phase 11.1 baseline contract: `ruff check src tests && mypy src`
# should pass clean for the in-scope module set. Run from the project
# root.
set -e
ruff check src tests
mypy src
