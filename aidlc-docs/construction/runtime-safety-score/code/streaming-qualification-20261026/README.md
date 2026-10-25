# Runtime safety streaming evidence

Baseline oracle: `4b714fdc4c4da8d76be79000dc3b385a0c5cb6a1`.
`source-validation.json` records 3,008 passing tests, Black/Ruff, 132-file mypy
and exact source/test hashes. `independent_review_result.json` records the final
independent review and its matching hashes.

- `oracle_manifest.json` pins the old helper/log/engine source hashes. The saved
  `/private/tmp` paths describe the independent evaluator's local workspace;
  the same old files can be recovered with `git show BASELINE:SOURCE`.
- `parity_result.json` records fixed-time old-code comparisons, including scalar,
  NaN, advisory, fallback, recency, duplication and score-factor behavior.
- `legacy_compat_result.json` records the final independent helper-scope check:
  public helpers retain the uncapped legacy hashable-key behavior, while the
  runtime accumulator keeps its hard limits. The review finding was fixed before
  deployment; no dashboard consumer inherits a new runtime cap.
- `reducer_million_result.json` records a generated million-event lifetime and
  state check. `source_million_result.json` adds real JSONL IO, worker/deadline
  behavior and event-loop heartbeat. Single local runs are not p95 results.
- `source_compat_result.json` records legacy line/parser/source-set cases.
- `incident_archive_result.json` records seven archived Fly files with 229,677
  canonical rows, captured 2026-10-25T10:50:02Z, and unchanged hashes. It is a
  historical fixture, not a fresh inventory or the earlier 214,686-row incident.
- `predeploy.json` pins v63 source, dependencies, health, resources and current
  cycle evidence before this runtime deployment. Error scope starts at v63 boot.

The independent harness ran from
`/private/tmp/crypto-master-safety-quant-20261026/quant_harness.py` using the frozen
baseline modules. No production strategy analysis, exchange action, data repair
or new order was triggered by these checks. Deterministic regression equivalents
are in `tests/test_runtime_safety_{score,streaming,inputs,integration}.py`.

Resource figures distinguish logical reader state, whole-process high-water RSS
and actual guest memory. They cannot certify original cold/warm page, native
browser, depleted-CPU, four-session or declared 1 GiB guest acceptance. DEBT-083
stays Critical/active; dashboard checkpoint implementation is separate.

See the [session](../../../../../docs/sessions/2026-10-26-runtime-safety-streaming.md)
and [cross-check](../../../../../docs/cross-checks/2026-10-26-runtime-safety-streaming.md).
