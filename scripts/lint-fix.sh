#!/usr/bin/env bash
# Lint with auto-fix and type-check the project (DEV CONVENIENCE).
#
# Phase 13.1 (DEBT-009): the `--fix` flag rewrites source on lintable
# regressions, which is unsafe for CI gates (silent mutation).
# `scripts/lint.sh` is the report-only counterpart for CI / pre-commit.
# Use this script locally to apply auto-fixes, then re-run
# `scripts/lint.sh` to confirm a clean pass.
set -e
ruff check src tests --fix
mypy src
