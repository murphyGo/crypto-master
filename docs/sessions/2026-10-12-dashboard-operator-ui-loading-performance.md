# Session: Bounded Dashboard Loading Performance

- **Unit / debt:** `dashboard-operator-ui` / DEBT-083, Critical and active.
- **Requirements / stories:** FR-029/031/032/036/042, NFR-003/007/008/011/012, BDL-NFR-01..08; US-012/014/020/023.
- **Authorization:** `계속 진행시켜` continues the remaining performance work; the prior `배포도 해줘` covers its scoped deployment and ordinary verification.
- **Baseline:** main `352fb0f`, runtime `785374b` / Fly v58. Source work began 2026-10-11 KST and qualification continued 2026-10-12 KST.

## Change and semantic verification

Bounded JSON arrays now scan structural and string tokens in runs. Activity rows
use direct model JSON validation and serialize rich details only after a retained
slot admits them. Gate matching uses canonical lookup / grouped legacy prefixes.
Snapshot reductions reuse measured state charges. Record checkpoints now use the
processed count instead of source byte offsets.

Every row still validates; invalid historical rows cannot be hidden by the
display tail. File generations, timestamp ties, exact totals, windows, curve
sampling, deadlines and all resource bounds retain their approved meaning.
Five complete incident projections, including all 13 accounts' sampled curves,
are identical to the baseline at fixed UTC evaluation time. Evidence stores
hashes and coverage rather than the financial payloads.

Validation: 63 focused tests and 2732 full tests pass (208.76s); changed-file
Black/Ruff pass; source mypy passes for 129 files. Review found no unresolved
source correctness issue. The separate benchmark initially hit sandbox denial
of `ps`; the approved module invocation then measured its own process RSS.

## Exact-input query measurements

Twenty fresh-service cold, cached and forced-epoch revalidation samples per query
use a read-only captured dataset, warmed imports and normal OS file caches.
Cold here means empty dashboard service cache. These are query completion times,
not complete page/native visual readiness. All incident samples complete with
verified coverage; initial RSS 193.406 MiB, observed process peak 205.062 MiB.

| Incident query | Cold p95 | Cached p95 | Revalidation p95 |
|----------------|---------:|-----------:|-----------------:|
| Activity, 214686 rows / 7 files | 1.737s | 0.000147s | 0.019392s |
| Proposals, 12183 files | 1.998s | 0.000131s | 0.392082s |
| Paper ledger, 13 accounts | 0.065s | 0.000076s | 0.005170s |
| Snapshots, 13 accounts / 30208686 bytes | 3.746s | 0.000122s | 0.013318s |
| Candidates | 0.0036s | 0.000086s | 0.000756s |

The representative million-event fixture has 10 files / 640453970 bytes. All 20
samples complete: cold p95 **10.546s**, cached 0.000121s, generation-revalidated
0.008977s. Initial RSS 202.359 MiB, peak 204.234 MiB. This still misses the 5s
cold target. The historical implementation measured 21.614s on this fixture;
these separate measurements are not a controlled simultaneous baseline trial.
Benchmark inventories match the final source inputs.

## Deployed release and readiness results

Fly **v59** runs runtime source **`22abf3dba6b35f1ba542a729b982bf334498525b`**,
image digest `sha256:03bf3e7280c36b8c5abcbc65c1edc4a7ce09deaf95ac6e48cdb5bbb35c4f610e`.
Release id `rel_oek82gq9j7l9y6qv`; existing machine `6835752b711958`, instance
`01M4NT7CGTEVTGYR2A3GBQ41P8`, started 2026-10-11T15:45:33Z. Same shared CPU 1,
2048 MiB and encrypted `/data` volume `vol_4m3l58dkk29y19zv` are retained.

All 175 deployed runtime input hashes match. Actual versions are Python 3.13.16,
Pydantic 2.14.0/core 2.50.0, Pandas 3.0.6 and Streamlit 1.65.0. Requirements and
Dockerfile are unchanged; image rebuild resolves the existing dependency ranges.
The protocol decoder is refreshed from the actual deployed version (88 schemas).
Health checks pass; separate HTTP requests return `ok` / 200 at 0.154s and 0.299s.

The first post-rollout paper cycle `4d3f0e4f-46e2-4591-9b57-2ef02b0ff75b`
starts at 15:45:42.179777Z and completes at 15:47:03.985307Z. At 15:49:38Z,
engine/dashboard RSS is 231560 / 237916 KiB and guest available memory 1385976
KiB. Initial engine RSS before UI is 732824 KiB; a single steady-state observation
does not qualify the original shared-guest/startup/four-session memory budget.

First Home protocol readiness **fails** its 240s observation, showing pending /
unavailable states without render exceptions. The subsequent Trading probe times
out; it is not complete. An overlapping independent query diagnostic completes
activity in 75.926s, ledger in 3.600s and proposals in 44.882s. Snapshots are still
pending at its 120s observation, although the final service cache has five entries.
That script correctly exits 1 because the captured query statuses are not all
complete. Overlap and startup conditions prevent a controlled timing comparison.

Fly metrics show baseline **0.0625 CPUs**, burst balance near zero and quota
throttling consuming about 90.5% / 90.9% of two 30s intervals. Memory remains
available (over 1.2 GB in those samples), with zero reported memory pressure.
This establishes an additional CPU-quota bottleneck during these delays; it
does not replace the earlier full-materialization/memory incident evidence.
The [official CPU / metric definitions](https://docs.fly.io/machines/cpu-performance)
support this interpretation; no Python stack or controlled capacity A/B is captured.

After those diagnostic jobs finish, a later first-full-run warm observation gets
complete Home cards / Trading metrics, tables and chart with no exceptions or
incomplete-availability alerts: render **1.443s / 1.251s**, total connection /
navigation **1.891s / 2.063s**. This is one protocol pair, not 20 native samples.
The current UI responds in that warm observation; startup readiness remains open.

Retain v59's lower-cost bounded reducers: there is no demonstrated source
correctness/startup/health failure requiring a source rollback. v58's image
identity is recorded in release evidence. Do not keep repeating heavy cold jobs
to force a pass under depleted shared CPU credits.

The [CPU infrastructure candidate](../../aidlc-docs/construction/dashboard-operator-ui/infrastructure-design/cpu-quota-recovery/infrastructure-design.md)
and exact manifest preserve this image / 2 GiB / machine / volume and change only
CPU kind to performance. Official Tokyo compute estimate: $16.61→$43.16 per
30 continuous days (+$26.55), before tax/traffic/discounts. CPU-class / operating
cost approval was requested, then deferred by operator `보류` (2026-10-12 KST).
Live verification confirms v59 / shared CPU 1 / 2048 MiB with passing health
checks. No CPU change, additional deployment or compute-cost change was made;
active `fly.toml` remains shared. Activation and dependent qualification stay
on hold until a new explicit operator decision.

## Deployment boundary and remaining work

Paper mode, Codex CLI / Claude rollback, the same shared CPU / 2 GiB machine,
original `/data` volume and runtime writers are preserved. No manual runtime-data
migration, durable index or credential change is part of this slice. The root's
unrelated `.claude` configuration and lock remain outside the isolated build.

Native Browser connection was retried and still fails while loading its local
runtime service. Server protocol checks are distinct from native viewport and
four-session resource acceptance. The current 2 GiB machine cannot certify the
original 1 GiB shared-guest target. DEBT-083 remains active until all approved
criteria pass.

- [Performance implementation](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/performance-follow-up.md)
- [Performance plan](../../aidlc-docs/construction/plans/dashboard-operator-ui-bounded-data-loading-performance-plan.md)
- [Cross-check](../cross-checks/2026-10-12-dashboard-operator-ui-loading-performance.md)
- [Incident measurements](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/performance-20261011/incident-20-samples.json)
- [Million measurements](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/performance-20261011/million-20-samples.json)
- [Exact projection parity](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/performance-20261011/projection-parity.json)
- [Release identity / rollback](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/performance-20261011/deployed-release.json)
- [First failed protocol observation](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/performance-20261011/v59-first-protocol-observation.json)
- [Throttled source/process/query verification](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/performance-20261011/v59-throttled-source-process-query-verification.json)
- [Warm protocol observation](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/performance-20261011/v59-warm-protocol-observation.json)
- [CPU/memory measurements](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/performance-20261011/v59-runtime-metrics.json)
