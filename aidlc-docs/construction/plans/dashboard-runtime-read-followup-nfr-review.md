# Dashboard and Runtime Read Follow-up: Concrete Review

**Status:** Base Functional Designs were approved by operator
`나머지도 계속 진행해줘`. On 2026-10-26, user `진행시켜` approved the concrete
runtime NFR and explicit failure-isolation amendment after the runtime-first
recommendation. That runtime slice passes 3,008 tests, source-quality checks and
independent review; rollout remains pending. The dashboard checkpoint candidate
remains a separate next bounded step. Track the runtime slice in its
[implementation plan](runtime-safety-score-streaming-activity-code-generation-plan.md).

## Reviewed choices and subsequent implementation boundary

| Area | Concrete design choice |
|---|---|
| Runtime failure isolation | On typed unavailable safety inputs, record the existing account error and stop remaining risk proposals for that account, but run its existing position monitor/snapshot once. This restores protective work the old broad guard skipped. No new order/rejection/fill/duplicate notification is invented. |
| Runtime worker | One process-owned lazy daemon worker, one active/zero queued jobs. Timeout/quarantine never creates another worker; no event-loop disk IO. |
| Runtime limits | 64 KiB blocks, 1 MiB rows, 16 MiB active state + 4 MiB manifest + 2 MiB summary cache; 50k exact kill keys, 4096/2 MiB extras. Per read 30s/2 GiB; per cycle 60s/4 GiB. Hard failure never becomes a healthy score. |
| Runtime semantics | Approved explicit request-time UTC snapshot; same fixed-time math/window/duplicates/cache distinction. Legacy UTF-8/universal-line/malformed policy preserved. Old unchanged irrelevant files may be skipped only with complete model/version/readability/max-timestamp proof and no dynamic timestamp default. No runtime disk cache. |
| Dashboard disk | One private derived store on the existing data volume, **64 MiB total**, including temporary/index/lock data; max64 physical files, 50k logical sources, two roots. Enable only with >=192 MiB free, keep128 MiB reserve. Current available is ~714 MiB. |
| Dashboard memory | Original one worker/four jobs, 16 MiB cache/16 MiB active/4 MiB source manifest stay. Packed index <=4 MiB is charged inside existing cache; no extra session cache. |
| Cache format / publication | Logical state <=2 MiB; pack <=4 MiB; record <=1 MiB; versioned non-executable lossless codec, SHA integrity, owner-only namespace, nonblocking reader/writer lock, admitted fsync/atomic index publication and owned-only eviction. |
| Initial acceleration scope | Activity/raw cycle state, unique per-account snapshot files and proposals. Ledger stays canonical to preserve float addition order; unsupported/nonfinite/dynamic-default state and non-associative curve cases are misses, not altered data. |
| Compatibility proof | Current source set/version and canonical model/runtime compatibility, exact offsets/rebased ties, global companion join and window expiry. No size-only append shortcut, no canonical writer lock, no direct serving old disk reports as fresh. |
| Infrastructure / cost | Same existing Fly process/machine/volume, CPU1 shared / 2048 MiB, paper/Codex, no provider/credential/new service. Original CPU/cost proposal remains deferred. |
| Acceptance | Original cold5s/warm2s, >=20 samples, dashboard256 MiB growth, guest768 MiB on declared1 GiB, four sessions/health<5s/full cycle, all failure ratios remain. Current2 GiB or buffered CPU cannot certify missing scenarios. No debt closure is promised by the design. |

## Review artifacts

- [Runtime failure amendment](../runtime-safety-score/functional-design/streaming-activity-inputs/failure-isolation-amendment.md)
- [Runtime NFR patterns](../runtime-safety-score/nfr-design/streaming-activity-inputs/nfr-design-patterns.md) and [components](../runtime-safety-score/nfr-design/streaming-activity-inputs/logical-components.md)
- [Dashboard NFR patterns](../dashboard-operator-ui/nfr-design/verified-segment-checkpoints/nfr-design-patterns.md) and [components](../dashboard-operator-ui/nfr-design/verified-segment-checkpoints/logical-components.md)

The explicit continuation now authorizes implementation/independent testing of
the runtime memory slice first, with the previously authorized same-capacity
exact-source rollout after source verification. Dashboard checkpoints remain the
next separate bounded step; their activation is not claimed by this runtime
source checkpoint. Any additional Fly/mount/process/credential change reopens
infrastructure review. No stage approval is inferred for such a change.
