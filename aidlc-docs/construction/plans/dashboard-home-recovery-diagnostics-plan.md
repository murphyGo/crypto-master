# DEBT-083: Home incomplete-result recovery and diagnosis

- Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
- Queue: Critical DEBT-083 and the final v64 qualification cross-check.
- Stage: bounded NFR/functional correction, Code Generation, Build and Test,
  then the already-authorized same-capacity deployment/operations check.
- Baseline: main `5fcad54`, application `dca38fb`, Fly v64.
- Requirements: BDL-NFR-03/04/06/07/08; FR-029/031/032/036/042;
  NFR-003/007/008/011/012; US-012/014/020/023.
- Authority: user `계속 진행` after the explicit next-step report; earlier
  per-item commit/push and deployment/operational verification authorization
  persists. No CPU/cost, credential, live-trading or resource change.
- Isolation: `/private/tmp/crypto-master-home-recovery-20261026`; preserve the
  root's `.claude` changes and other worktree's operational records.

## Scope and design

Reproduce Home's five-query interactions for source-read failure/error caching
and admission saturation. Correct only proven retry gaps: queue saturation is
already retryable in the data service and must retain the existing single page
watcher. Terminal validation/corruption/source-proof failures must remain
explicitly incomplete; do not introduce unlimited automatic rebuilds or claim
the historical two failures have a known cause.

Retain bounded diagnostic events for incomplete reads: allowlisted query kind,
status, stable reason, verification stage, cache age and admitted-job count.
Exclude paths, account/trade/proposal IDs, raw data and exception text. Bound
cardinality/rate, avoid runtime-data files, and leave user-facing explanations
free of implementation detail. Add direct operator retry only if it is needed
to make the existing "Refresh to retry" behavior actionable, with one control
per page and no cache/coverage bypass.

Extend the existing protocol observer to retain alert classification and first
incomplete-shell time, while preserving request/outcome identity, failure
accounting and exact complete-data criteria. Protocol evidence is not native
viewport acceptance. Keep the original cold, native, depleted and 1 GiB gates.

## Work and ownership

- [x] Refresh source/remote/worktree ownership and original acceptance evidence.
- [x] Developer: reproduce failure-cache and queue saturation paths; implement
  the proven recovery correction and bounded diagnostics in dashboard source.
- [x] Lead: retain a reviewable protocol harness with alert/shell observations
  and a bounded same-capacity deployment/rollback recipe.
- [x] QA: independently review source/tests, privacy, retry bounds and coverage;
  targeted tests, full pytest, changed-file Black/Ruff and source mypy.
- [ ] Commit/push the scoped correction with source/test evidence and confirm
  the exact remote SHA, preserving concurrent commits.
- [ ] Deploy that exact validated SHA under the existing authorization, verify
  runtime hashes/health/first natural cycle and the corrected protocol behavior.
- [ ] Docs audit: state, plan, session, cross-check and DEBT-083 status. Preserve
  historical failures and distinguish measured recovery from full acceptance.

## Validation

Target `tests/test_dashboard_availability.py`, `tests/test_dashboard_data_service.py`
and relevant Home/Trading/AppTest tests. Use deterministic event-controlled
builders for saturation/failure transitions, verify one worker/four admissions,
one watcher per page, complete siblings, no unsafe auto-retry for terminal errors,
and sanitized/rate-bounded diagnostics. Run full regression on the final source.
Do not change score math, source-proof validation, quotas or completeness targets.

## Source verification checkpoint

Final source passes 2,989 tests on Python 3.13.0 (224.06s), nine-file
Black/Ruff and 135-file source mypy. Independent QA validates 106 targeted
cases and returns green. All 260 source/test/script hashes are unchanged
during the final full run. Concurrent documentation commit `f1863de` was
fast-forwarded without runtime/test changes. Exact source commit/push and
same-capacity rollout remain next; no production recovery pass yet.
