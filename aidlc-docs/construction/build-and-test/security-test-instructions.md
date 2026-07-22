# Security Test Instructions: market-regime Funding+OI Crowding Shadow Filter

## Security assertions

- Disabled policy performs zero context work and emits no event.
- The proposal hot path reads only the existing in-memory service cache; it
  performs no exchange/network/filesystem refresh.
- Missing or failed context passes through. Provider exceptions retain only
  `error_type`; raw messages, payloads, paths, URLs, signed query material, and
  credentials are absent.
- Predicted Funding is ignored and every settled record is at or before
  `proposal.created_at` through the sealed `MarketContext` contract.
- No dependency/lock, deployment, infrastructure, credential, migration,
  production configuration, or repository `data/` change exists.

Changed-file Black/Ruff, repository mypy, compile, offline import,
`git diff --check`, and scope scans pass. Repository-wide Black/Ruff reproduces
only existing DEBT-081 (16 Black candidates and 22 Ruff findings), with no
overlap in this slice.

---

# Prior Security Test Instructions: backtesting-validation Derivatives Data Slice 4

## Security assertions

- Snapshot-default promotion imports and runs with socket connection attempts
  forced to fail; no import-time or replay-time network access exists.
- Invalid identity/path/symlink/canonical-file/integrity cases remain covered by
  the 57-test Snapshot v2 suite.
- An unexplained Funding prefix and uncovered derivatives suffix fail closed.
- Runner reports keep only `error_type`; raw exception text, local paths,
  query signatures, credentials, and raw payloads are not serialized.
- Predicted funding has no replay path and cannot satisfy requirements.
- Explicit refresh uses normalized public fields only and was exercised solely
  with a fake exchange and temporary directory.
- Dependency, deployment, credential, migration, duplicate, TODO, and tracked
  `data/` scans are clean for Slice 4.

The literal `apiKey=top-secret` and `/private/tmp/operator/snapshot` strings in
`test_runner_failure_report_does_not_serialize_raw_exception_text` are inert
negative-test sentinels; the test proves neither reaches serialized output.

## Manual checks

```bash
git diff --check
git status --short -- data pyproject.toml uv.lock
uv run black --check <13 Slice 4 Python files>
uv run ruff check <13 Slice 4 Python files>
uv run mypy src
```

Verified result: all Slice 4 checks pass; mypy reports zero issues in 113
source files. Repository-wide Black/Ruff still reproduces unrelated DEBT-081
(19 Black candidates, 22 Ruff findings in four existing scripts).

---

# Prior Security Test Instructions: exchange-integration Derivatives Data Slice 3

## Current command

```bash
uv run pytest \
  tests/test_runtime_derivatives_context.py::test_disabled_service_constructs_no_connection_or_request \
  tests/test_runtime_derivatives_context.py::test_budget_exhaustion_is_non_retryable_and_does_not_leak_raw_error \
  tests/test_runtime_derivatives_context.py::test_events_use_exact_safe_allowlist_and_degrade_once_per_cycle \
  tests/test_main_dispatch.py::test_build_engine_disabled_constructs_no_derivatives_object \
  tests/test_main_dispatch.py::test_build_engine_enabled_uses_dedicated_empty_credential_mainnet_source \
  -q
```

Verified result: 5 passed in 0.97 seconds.

## Security assertions

- Disabled mode constructs no derivatives object, connection, or request.
- Enabled mode creates a separate Binance USD-M mainnet source whose live and
  testnet key/secret fields are all explicitly empty.
- The account trading exchange is never injected into or closed by the
  derivatives service.
- Service events use the exact approved field allowlist and omit exception
  text, credentials, signed query material, URLs, response bodies, and raw ccxt
  payloads.
- Budget/error degradation emits stable safe codes only; the test's injected
  raw error text never leaks.
- Context/prompt serialization is normalized and allowlisted; predicted
  funding is not persisted or replayed.
- Import verification succeeds with all socket connection attempts forced to
  raise, proving no network-at-import path.
- Cache state is process-local and no runtime `data/` path is read or written.

## Manual diff checks

```bash
git diff --check
git diff --name-only -- pyproject.toml uv.lock
git status --short -- data
rg --files | rg '(_new|_modified)\.py$'
```

Verified result: whitespace clean; no dependency/lock change, tracked runtime
data change, or duplicate generated Python file.

---

# Prior Security Test Instructions: backtesting-validation Derivatives Snapshot Schema v2

## Current command

```bash
uv run pytest tests/test_backtest_snapshot_v2.py
```

Verified result: 57 passed, including all path/integrity failure cases.

## Security assertions

- Pinned and `CURRENT` ids reject traversal, absolute, uppercase, short, long,
  and malformed values.
- Generations root, generation directory, generation files, `CURRENT`, and
  dangling symlink variants fail closed.
- Unknown/missing files, invalid UTF-8, noncanonical CSV/JSON, schema mismatch,
  hash/size/count mismatch, and provenance mismatch raise bounded
  `SnapshotValidationError` failures.
- Only the exact normalized allowlist is persisted. The source contains no
  `CurrentFundingRate`, `predicted_rate`, API-key/secret, venue `info`, network,
  or raw-response dependency.
- One test intentionally injects a file named `secret.json` solely to prove the
  allowlist rejects it; it contains no credential material.
- The test suite is offline, uses temporary directories, and performs no live
  order, credential, deployment, or runtime-data action.

## Manual artifact checks

`git diff --check`, new-file whitespace, duplicate-generated-file, dependency,
network-import, sensitive-identifier, and changed-path scans were clean for
Slice 2. User-owned `.claude` changes were preserved.

---

# Prior Security Test Instructions: exchange-integration Derivatives Data Slice 1

## Command

```bash
uv run pytest \
  tests/test_exchange_binance.py::TestBinanceExchangeConnect::test_connect_omits_empty_public_credentials \
  tests/test_exchange_binance.py::TestBinanceDerivativesCurrent::test_derivatives_error_ladder_is_typed_and_sanitized \
  tests/test_exchange_derivatives.py
```

These tests are also included in the canonical 221-test exchange run.

## Security assertions

- A public Binance client omits empty `apiKey` and `secret` configuration keys.
- Existing credentialed/testnet paths retain their historical behavior.
- Raw CCXT `info` payloads do not cross the adapter boundary.
- Exchange exceptions become bounded stable error codes and sanitized messages
  rather than leaking raw venue payloads or credential material.
- Malformed, non-finite, negative-OI, naive-time, wrong-interval, and gapped
  inputs fail closed.
- The Build & Test run uses no real credentials, makes no external network
  request, performs no live order action, and does not mutate runtime data.

## Manual artifact checks

`git diff --check` passed, no duplicate `*_new.py` or `*_modified.py` files
were found, no raw `info` access pattern was found in the generated derivatives
boundary, and the changed-path review found no `data/` or `strategies/` change.
