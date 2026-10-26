# Dashboard Home recovery and diagnostics — 2026-10-26 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
DEBT-083 remains Critical / active. This bounded correction follows the user's
`계속 진행` authorization. The isolated worktree starts from `5fcad54`; the
deployed application baseline is `dca38fb` / Fly v64. Root-owned `.claude` work
and the other worktree's operational evidence are preserved. Concurrent
documentation commit `f1863de` is integrated as the parent without changing
the verified runtime source.

**Source checkpoint passed:** final regression, static checks and independent
QA are complete. Commit/push, rollout and post-deployment observation are next;
no production recovery result is claimed from this source gate.

## Proven defects and historical uncertainty

The earlier v64 run retains 349 matched request starts/outcomes, 347 complete
and two incomplete Home responses. Those two responses have no recorded alert
reason or first-shell timestamp. Their overlap with a natural engine cycle
does not establish CPU contention, source churn, or either defect below as the
historical cause. The failed run remains a failed readiness measurement.

Two recovery gaps are reproduced deterministically in current source/tests:

1. The service already treats `queue_full` as retryable, but the availability
   layer did not retain its page watcher for that result. A page whose last
   unresolved section was queue-saturated could finish incomplete without a
   continuing recovery check. Both unavailable and stale queue-full results
   now participate in the existing single page watcher.
2. Terminal failures told the operator to refresh, but supplied no actionable
   page control. A plain rerun within the two-second cached-error interval
   would reuse the failure. One `Refresh data` control now invokes optional,
   generation-scoped retry callbacks for terminal sections before a normal
   rerun. A callback clears only its own captured error object under the service
   lock; it cannot erase a later error, another query, valid cached data or
   active work. The next request uses the normal validation/coalescing path.

Terminal validation, corruption and source-proof failures remain incomplete.
They do not acquire an automatic rebuild loop. Verified sibling sections keep
their payload and original evaluation/freshness timestamps. Tests exercise
Home's five-query interaction, queue release, concurrent explicit retries and
an older callback presented after a newer failure.

## Bounded diagnostics and observation

`read_diagnostics.py` retains only allowlisted query kind, status, reason and
verification stage, plus sanitized numeric cache age/admitted count. Unknown
labels become `unknown`. Paths, account/trade/proposal identifiers, payloads
and exception text are excluded. The standalone console logger has no ancestor
or file handlers; it creates no runtime-data file.

The production shared recorder retains at most 64 records and 64 rate keys,
with burst 8, refill 2 events/second and a five-second identical-key cooldown.
A single process-wide daemon delivers through a nonblocking 64-slot queue;
one additional event can be active. A blocked sink does not spawn a replacement
worker or block the reader/service close. Queue overflow drops delivery;
sink failures are counted and cannot change read results. These are bounded,
best-effort diagnostics, not a lossless incident stream.

Reader limits remain one worker/four admitted jobs, 2 MiB result, 16 MiB cache,
64 cache entries, 16 MiB reducer state, 4 MiB manifest, 50,000 identities,
128 accounts, 256 strategies, two roots and the existing four-second foreground
wait. Source-proof and metric calculations are unchanged. No CPU, memory,
dependency, credential, paper/live or engine-cadence change is included.

`scripts/observe_dashboard_protocol.py` makes the existing four-session observer
reusable with a fresh required output directory, descriptor path and phase.
It preserves the production endpoint/machine defaults, admission/drain rules,
health/memory sampling, warm-up records and complete natural-cycle requirement.
It adds allowlisted alert classifications and first incomplete receipt/
script-finish offsets, without retaining alert bodies. Complete results require
the exact Home/Trading metric labels, nonplaceholder values and element counts;
this is a protocol-shape check, not independent table-cell or native validation.

Every admitted request retains its outcome, including cancellation, timeout,
exception or incomplete finish. Starts/outcomes are reconciled by identity.
Nearest-rank p95 uses `ceil(0.95 * n)`; any incomplete result prevents an aggregate
readiness pass. An errored engine cycle remains recorded and fails continuity;
the observer does not discard it in favor of a later clean cycle. Independent
QA identified an observation-window gap: full-cycle qualification now requires
`window start <= cycle start <= cycle completion <= window end`, including
the live stop check. Future, inverted and pre-window cycles cannot qualify;
their in-window error events remain failure evidence.

## Verification checkpoint

| Check | Evidence / status |
|---|---|
| Reproduced defects | Before edits, the three unavailable/stale queue-full and terminal-control cases fail; the identical selection passes all three after correction. Exact commands/results are retained in `source-red-green.json` / `.txt`. |
| Developer-focused recovery/diagnostics tests | 48 passed in 4.69 s on Python 3.11.13: `uv run pytest tests/test_dashboard_availability.py tests/test_dashboard_data_service.py tests/test_dashboard_read_diagnostics.py -q`; four changed source files also pass mypy. |
| Protocol observer focused tests | 48 passed in 0.23 s after the QA observation-window correction; `python -m pytest -q tests/test_dashboard_protocol_observer.py -p no:cacheprovider --basetemp=/private/tmp/crypto-master-home-recovery-observer-tests-window` using the existing root `.venv` interpreter. |
| Observer formatting/static checks | `python -m black --check scripts/observe_dashboard_protocol.py tests/test_dashboard_protocol_observer.py` and corresponding `python -m ruff check` passed. |
| Observer import/CLI behavior | Import-safety test and `python scripts/observe_dashboard_protocol.py --help` passed without observation/network/Fly calls. |
| Historical offline replay | All 349 saved outcomes reproduce 347 complete / 2 incomplete with zero classification mismatch and a bijective request ledger. Home 172/174, successful p95 0.760711 s; Trading 175/175, p95 0.724168 s. Aggregate readiness remains false. Remote sampler literal matches the committed observer. |
| Independent QA | Green across 106 distinct targeted cases (initial 101 plus five observation-window cases). Final exact observer files independently pass all 48 tests in 0.18 s. |
| Final full pytest | 2,989 passed in 224.06 s on Python 3.13.0 using `/Users/user/Desktop/Projects/crypto-master/.venv/bin/python -m pytest -q`. All 260 `src`/`tests`/`scripts` hashes remain unchanged during this run. |
| Earlier full pytest | 2,984 passed in 61.06 s on Python 3.11.13 before the five observer boundary tests; this earlier result does not replace the final exact-source gate. |
| Final static gate | Black/Ruff pass for nine changed Python files; mypy passes 135 source files. |
| Exact remote commit and rollout | Pending; no deployment of this correction yet. |
| Post-rollout hashes/health/natural cycle and enhanced protocol observation | Pending; no inferred pass from local tests. |

Durable source evidence under
`aidlc-docs/construction/dashboard-operator-ui/code/home-recovery-20261026/`:
`source-qualification.json`, `source-input-sha256.json`,
`full-pytest-final.txt`, `independent-qa.json` and `source-red-green.json` / `.txt`.
Independent QA confirms the corrected observer hashes and no remaining source
or harness blocker. This evidence establishes the local source gate only.

## Unchanged acceptance boundaries

This correction does not close DEBT-083. The original complete Home/Trading
cold p95 <=5 s and warm p95 <=2 s still require at least 20 observations per
page/scenario, with every failure retained. Cacheless construction and process
restart are separate; seeded reuse does not certify either cold case. The
incomplete-shell <=5 s target is separate from complete readiness.

Four-session observation must cover at least ten minutes and a full natural
engine cycle with every health response <5 s. Dashboard RSS growth <=256 MiB
and guest use <=768 MiB on the declared 1024 MiB allocation remain the original
memory requirements. A numeric pass on the unchanged current 2048 MiB machine
does not qualify the original allocation. Native Browser and depleted-CPU
qualification remain open; protocol results and positive CPU-credit samples
cannot substitute. The performance-CPU/cost proposal remains deferred.

Plan: `aidlc-docs/construction/plans/dashboard-home-recovery-diagnostics-plan.md`.
Design and deployment recipe:
`aidlc-docs/construction/dashboard-operator-ui/code/home-recovery-20261026/`.
Cross-check: `docs/cross-checks/2026-10-26-dashboard-home-recovery-diagnostics.md`.
