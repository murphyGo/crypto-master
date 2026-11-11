# Dashboard initial-read cost cross-check

Scope: BDL-NFR-02–08; FR-028–032/036/038/042; US-012/014/020/023.
Implementing-agent review only. This is a bounded performance slice under DEBT-083.

| Contract | Evidence | Result |
|---|---|---|
| Every record retains decoder/model validation and exact bytes | 9,000 baseline differential cases; 34 new boundary/damage tests | PASS |
| Bounded records, cooperative yields, close and generation proof | Existing and new bounded-reader tests; source mutation and large records | PASS |
| Snapshot metrics/ties/sampling remain identical | All six production trial hashes match; 12 fixed-fixture payload hashes match | PASS |
| Material measured initial-read improvement | Production direct median 3.786125→2.411901 s, about36.3% | PASS for probe only |
| Existing dashboard/trading behavior | 602 targeted and3,161 full tests; Black/Ruff/mypy | PASS |
| Same-capacity source/image/settings and natural cycle | v72/source71c8787;183 hashes/settings;22.915302s startup cycle,12 monitors,no errors | PASS |
| Native Home/Trading visual smoke | Chrome metrics/tables/Trading chart visible; task tab closed; no timing or cell oracle claim | PASS, bounded smoke |
| Four-session Home/Trading readiness |1387.074688s;277/277complete; Home/Trading p95 0.584077/0.678392s; no shape/request mismatch | PASS, bounded protocol sample |
| Health/memory/engine continuity |275/275health;655.273438MiB guest;14.933594MiB RSS growth;19.246960s natural cycle,12 monitors,no errors | PASS on current2GiB |
| CPU and cleanup |93points with both brackets;26.157164–51.077178CPU-seconds balance,zero sampled throttle; all task probes absent | PASS for observation/cleanup; depleted gate OPEN |

The original full DEBT-083 qualification remains OPEN: a direct projection timing
is not browser/process-cold p95 or the original1GiB/depleted/four-session acceptance.
No failed historical sample is replaced or relabeled by this slice.

Four complete requests take13.19–15.18s around the engine write wave, with
transient incomplete shells followed by automatic completion. They are retained,
not counted as sub-2s responses or discarded from the sample. One native visual
smoke and one protocol warmup after it do not establish cold/native percentiles.
Full DEBT-083 verdict remains OPEN; source/deployment and bounded operations PASS.
