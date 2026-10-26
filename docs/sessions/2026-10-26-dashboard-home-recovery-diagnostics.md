# Dashboard Home recovery and diagnostics — 2026-10-26 KST

Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
DEBT-083 remains Critical / active. This bounded correction follows the user's
`계속 진행` authorization. The isolated worktree starts from `5fcad54`; the
previous application baseline is `dca38fb` / Fly v64. Root-owned `.claude` work
and the other worktree's operational evidence are preserved. Concurrent
documentation commit `f1863de` is integrated as the parent without changing
the verified runtime source.

**Bounded correction deployed:** source `382c26b` is on remote main and Fly v65.
Final regression, static checks, independent QA and deployed-source checks pass.
The final four-session observation **fails complete readiness**: 116/120
requests complete and four time out. Health, full natural-cycle and observed
memory checks pass within the current 2048 MiB envelope. DEBT-083 stays open.

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
| Exact remote commit and rollout | `382c26b1290c4b1a7cc843f28686fc9e2e4f2323` is pushed to remote main and deployed as Fly v65 on the existing machine/configuration. |
| Post-rollout source/health/engine | At 04:55:19 UTC, all 182 runtime hashes match; public/internal health is 200/ok. Activity since 02:28 UTC contains five completed cycles, 60 monitor passes and zero recorded errors. This is a later check, not an immediate post-deploy sample. |
| Enhanced protocol observation | Final audit `FAIL_SAMPLE`: 04:56:43.681997–05:06:50.782715 UTC (607.100718 s), 120 matched starts/outcomes, 116 complete and four timeouts. No duplicates/orphans or recomputed summary differences. |

Durable source evidence under
`aidlc-docs/construction/dashboard-operator-ui/code/home-recovery-20261026/`:
`source-qualification.json`, `source-input-sha256.json`,
`full-pytest-final.txt`, `independent-qa.json` and `source-red-green.json` / `.txt`.
Independent QA confirms the corrected observer hashes and no remaining source
or harness blocker. This evidence establishes the local source gate only.

## Deployment and operational coverage

The exact source-labelled image is
`sha256:6a621b4d7ee3427c47251a4d833c0754679a0b73bba7b9f388e3c7cdfae42200`.
It overlays the five verified runtime files on the existing v64 base, retaining
installed dependencies. Machine `6835752b711958`, shared CPU 1 / 2048 MiB,
the existing `/data` volume, paper/Codex settings and 1800-second engine cadence
are unchanged. The runtime restarted around 02:29 UTC; the 04:55:19 UTC check
occurs later. `operations/candidate.json`, `postdeploy.json`, rollout output
and `delivery-manifest.json` retain the source/image/configuration evidence.

The captured activity has 13 generated and 13 accepted proposal events,
12 rejected events, one opened position and one closed position. Acceptance
is an earlier proposal stage; it does not mean thirteen executions. The helper
checks thirteen distinct persisted proposals, with no proposal parse failure:

| Account / strategy version | Proposals | Prior closed sample | Expected-value comparison |
|---|---:|---:|---|
| `ma_crossover` / `1.0.0` | 4 | 226 | All match -0.3710364625 |
| `rsi_15m` / `1.1.0` | 5 | 227 | All match 0.3073767841 |
| `vwap_mean_reversion` / `1.1.1` | 4 | 190 | All match 0.2922324503 |

All thirteen sample sizes and expected values match their prior-close basis.
Final states are twelve `gate_rejected_symbol_cap` and one `trade_opened`.
This checks these two score fields for these three account/version pairs, not
all strategy score fields, all accounts or trading profitability.

The twelve emitted cap comparison rows cover six distinct trades. Every row
agrees on `legacy_no_perf_link` and `monitorable=true`. All twelve account fields
are null and proposal IDs are absent in this captured subset, so it cannot
establish proposal-by-proposal cap attribution or all-account event coverage.

Separate pure deployed-method replay covers eighteen account/version score
rows across twelve accounts and eleven cap trade rows. All score comparisons
match, the shared tracker's account remains unchanged, and the twenty-four
input hashes match before/after this replay. That does not assert canonical
inputs stayed static during normal engine operation. Replay uses current
persisted data, fixed confidence 1, omitted proposal joins and unknown market
marks; it is distinct from actual emitted decisions. VWAP's current replay
sample is 191, whereas its earlier proposals correctly used 190 prior closes.

The funding smoke retains `fee_net_excluding_funding`, unknown funding coverage
and null actual funding cost. The 226-trade MA carry scenario has complete
scenario inputs, not measured funding settlement. Its 10,000 USDT rendering
capital is a smoke-test assumption, not a current account-return assertion.

A local actual Streamlit AppTest clicks `Refresh data` 0.061 s into the
two-second error cache and recovers the failed section with one additional
build. The healthy ledger object's identity and build count remain unchanged;
subsequent rendering adds no build and no exception. AppTest temporarily retains
the old button element after an internal rerun, also reproduced with a plain
Streamlit control; the next normal run removes it. This is interaction evidence,
not native DOM/viewport acceptance. Scripts and outputs are retained under
`operations/apptest-*`.

## Final v65 four-session observation: failed readiness

The final window is 04:56:43.681997–05:06:50.782715 UTC, **607.100718 s**.
Independent audit reconciles all **120 starts with 120 outcomes**: **116 complete,
four timeouts**, no missing/duplicate identities and no declared-summary
differences. Each client attempts each page fifteen times. Exact successful
page shapes pass the observer's classification checks; the four failures remain
in the denominator.

| Page | Complete / attempts | Timeouts | Successful complete p95 | All-outcome duration p95 |
|---|---:|---:|---:|---:|
| Home | 58 / 60 | 2 | 1.852226 s | 2.369965 s |
| Trading | 58 / 60 | 2 | 1.396472 s | 2.055165 s |

The all-outcome duration percentile is supplementary; the canonical successful-
complete p95 does not make a set with failures pass. The four requests start at
05:01:43.862770–05:01:45.356289 UTC and time out after 30.044–30.261 s. Their
first incomplete protocol receipts arrive in 4.307–4.794 s, with at most one
watcher and multiple rerun signals. The next four requests complete in
1.317–3.262 s. This demonstrates later recovery, not indefinite live starvation.

Warm-up is retained separately: Home completes in **11.414767 s**, with its first
incomplete receipt at **5.072113 s**. That single observation misses both the
5 s complete-readiness and incomplete-shell targets; it does not constitute a
twenty-sample cold qualification. Receipt offsets are protocol timing, not
native visual rendering measurements.

All **120 health samples** pass (<5 s), maximum **4.001187 s**. Guest use peaks
at **701.949219 MiB**, and dashboard RSS growth is **65.648438 MiB**. These pass
the observed numeric ceilings on the current **2048 MiB** machine only. The
complete natural cycle is 05:01:34.008593–05:02:04.252059 UTC (**30.243466 s**),
with twelve monitor events and zero recorded cycle errors. The four failures
overlap this cycle; temporal overlap alone does not establish a cause.

The separate 05:07:10 UTC helper checks the one actual proposal in this window:
`session_vwap_pullback` version `1.1.0`, ID
`882b0872-3c7e-474f-a5e3-43b8927c8c0a`. Its sample 47 and expected value
1.529362657442265 match prior closes, and its final state is
`gate_rejected_trend_filter`. No emitted cap rows occur in this final window;
the earlier twelve cap-event comparisons remain a separate observation.

The framed diagnostic capture retains 169 allowlisted records, including seven
`source_changed` records: four projection-stage and three cached-error-stage
events. This proves failed verification paths were encountered, not seven
page failures or an exact request-to-error match. Delivery is asynchronous,
rate-limited and may drop records; Fly timestamps identify sink delivery, not
the throw time. The collector starts after the page window begins and records
no query/request identity. Its earlier empty line-oriented sidecar failed to
decode multiline Fly JSON and is not evidence of zero application diagnostics.

Controlled offline probes reproduce process-wide drain coupling: this page's
activity is complete while an unrelated audit job blocks; twenty watcher polls
produce no rerun until that job finishes. Separate probes reproduce required
two-second freshness revalidation and correct `source_changed` rejection under
valid concurrent appends. These establish a bounded page-progress follow-up
candidate, not the sole cause of the four live timeouts. Pinning an expired
sibling as complete or bypassing generation proof would violate the current
contract. No further application change is implemented by this diagnosis.

Final audit, frozen inputs, diagnostic supplement and offline reproduction are
retained with `operations/` evidence. The historical v64 failures remain
recorded independently.

The separately frozen CPU history was published locally at 07:03:47.085509 UTC,
well after the run; that file time is not the query start. Independent audit
selects 41 samples per series from 04:56:45–05:06:45 UTC, with bounding points
at 04:56:30/05:07:00 and uninterrupted 15 s spacing, excluding 470 out-of-window
values per series. Original-window balance is positive (raw metric
41,601.002–45,501.002), throttle is zero and baseline is 0.0625. This is sampled
buffered-CPU evidence, not depleted qualification; shorter unsampled transients
and exact timeout causality remain unresolved. `cpu-window-proof.json` and
`cpu-supplement.json` preserve the later supplement without rewriting the
initial failed audit.

The separate 07:04:35.888616 UTC closeout refresh confirms the same 182 hashes,
image/instance/configuration and 200/ok public/internal health, with four later
cycles, 48 monitors, zero errors, one time-stop close and zero proposals since
05:06:51 UTC; this is service-continuity evidence outside the 607 s performance
window and does not repair its failed result.

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
