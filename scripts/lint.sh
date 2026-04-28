#!/usr/bin/env bash
# Lint and type-check the project. Phase 11.1 baseline contract:
# `ruff check src tests && mypy src` should pass clean for the
# in-scope module set. Run this from the project root.
set -e
ruff check src tests --fix
mypy src
