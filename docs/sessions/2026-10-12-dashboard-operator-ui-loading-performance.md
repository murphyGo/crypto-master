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
Benchmark inventories match the final source inputs. Requested release
verification is the next step; its final identity/evidence will be recorded here.

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
