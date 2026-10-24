# Session: Remaining Dashboard Cold Readiness and Concurrency

- **Unit / debt:** `dashboard-operator-ui` / DEBT-083, Critical and active.
- **Requirements / stories:** FR-029/031/032/036/042, NFR-003/007/008/011/012, BDL-NFR-01..08; US-012/014/020/023.
- **Authorization:** `나머지도 계속 진행해줘` continues the outstanding source, rollout and qualification work. Performance CPU / added cost remains deferred; retain shared CPU 1 / 2048 MiB, original volume, dependencies and paper/Codex safeguards.
- **Baseline:** main `bf44822`, runtime `38876fc` / Fly v60. Work is isolated from unrelated root `.claude` configuration and lock.
- **Checkpoint:** Source verification complete; rollout/concurrency follow below. This checkpoint does not assert complete NFR acceptance.

## Selected changes

The activity reducer uses typed per-file loops, direct fixed-slot cycle state,
cheap rank rejection and one lazy row payload. Its read-side JSON model inherits
the canonical event model and all validators, with the exact enum value set as
literal names; the public TypeAdapter compiled validator removes the repeated
Python wrapper and enum construction. Every canonical event type, unknown and
malformed values, duplicate keys, coercion and old out-of-display rows are
checked against the existing model. No record validation or historical totals
are skipped.

Snapshots keep only one selected bounded row per account, alongside its first
validated timestamp. Common rows retain bounded bytes; oversized selected rows
use the normalized compatibility path. Only selected rows serialize at publication.
Normalized published state is admitted through the same global state budget, so
compact retained bytes cannot hide oversized expanded output. Fixed-shape curve
and selected-row charges are measured against recursive accounting, including
Unicode keys and large numeric values. Curves, extrema, latest-row ties and all
financial output stay unchanged. A missing timestamp keeps its original default
instant rather than receiving a new publication-time default.

Proposal discovery captures directory-entry metadata once. Publication verifies
all packed file versions with directory-relative stats, then verifies directory
generations. The portable path remains for platforms without directory-relative
stats. Source selection, hidden `.json` handling, excluded archive/deeper folders,
symlinks, device/inode/size/nanosecond mtime checks and descriptor closure are
covered. Metadata work is reduced without replacing file proof with directory
mtime alone.

Trading requests an exact lifetime threshold scalar. If Home already has a fresh
complete proposal projection, its separately encoded scalar/provenance can be
borrowed without a second proposal read. Both payloads are charged and stay within
the entry/result limits. The borrowed scalar keeps the original evaluation age;
it cannot cross root/source/scope/time/version identities. A cold threshold query
still validates every proposal, with no unrelated window/group state dependency.

Page requests canonicalize each query once before polling, rather than resolving
the same paths every 50ms while the worker is busy. Direct request deadlines still
include normalization. Known terminal read failures return verified sibling
sections immediately; pending, queue-full and just-finished rebuilds retain retry
behavior. Source-root identity stays fixed for the page wait.

## Verification method

The final targeted scope covers reader, projection, service, default pages and
Trading. Full regression, changed-file Black/Ruff and source mypy are run before
rollout. Twenty alternating baseline/candidate samples use the existing generated
million-event and 13-account snapshot fixtures, plus 12,000 valid generated
proposal records. UTC evaluation and inputs are fixed. Full payload/provenance
parity is required, with the lifetime scalar and coverage compared separately
for the deliberately compact threshold query. Warm and generation-revalidation
times are separate from cold empty-service times; CPU and wall time are recorded.

An intermediate run completed the activity/snapshot comparisons, then correctly
failed on invalid generated proposal decisions. The synthetic fixture was repaired
and every proposal validated before the final run. Intermediate evidence is
explicitly labelled and is not final qualification.

## Browser and server concurrency

Browser bootstrap still cannot load its local runtime service. Plugin discovery
did not expose a repair operation for that built-in connection. Recovery was
requested asynchronously; source work continues. No substitute browser is claimed
as native viewport acceptance.

The prepared server test uses four actual Streamlit WebSocket sessions alternating
Home/Trading, with original-version protobuf schemas, full script completion,
metrics/tables/chart checks, placeholders and explicit incomplete-data states.
Read-only guest/process sampling records RSS/HWM, memory, process continuity and
engine cycle events; public health is sampled independently. The minimum window
is ten minutes and may extend to capture a full existing 1800s engine cycle, without
changing engine timing. Low available memory, excessive dashboard growth, failed
health or process disappearance stops the load. This is server evidence, distinct
from native browser and the original declared 1024 MiB guest qualification.

## Remaining acceptance

Final measurements and rollout/concurrency outcomes will be recorded from actual
results. The original cold/warm, native, four-session and guest requirements are
not waived. Any new persistence/topology contract requires its applicable design;
this slice changes no canonical writer, durable index, exchange or live control.

- [Construction plan](../../aidlc-docs/construction/plans/dashboard-operator-ui-cold-readiness-completion-plan.md)
- [Approved NFR design](../../aidlc-docs/construction/dashboard-operator-ui/nfr-design/bounded-data-loading/nfr-design-patterns.md)

## Final source verification

- Focused reader/projection/service/page/Trading tests: **171 passed**.
- Full suite: **2811 passed in 231.38s**.
- Changed-file Black/Ruff clean; source mypy clean across **129 files**.
- Code review found no unresolved correctness issue in this slice. Every-record
  validation, source proof, time/tie ordering, financial outputs and resource
  admission were reviewed; unchanged business output was verified independently.

All twenty pairs completed per workload. Cold below means a fresh query service
in a warmed local process with generated input, not process-cold/native latency.

| Workload | Baseline p95 | Candidate p95 | Result |
|---|---:|---:|---|
| 1M activity records | 10.317s | 7.872s | Full output/provenance equal; 5s still fails |
| 84,500 snapshots / 13 accounts | 3.750s | 2.149s | Full output/provenance equal |
| 12,000 proposal records | 1.482s | 1.397s | Full output/provenance equal |
| Proposal generation revalidation | 0.276s | 0.124s | Same generation proof |
| Home-to-Trading lifetime scalar reuse | 1.623s | 0.000221s | Exact scalar/evaluation/coverage, no second read |

The fixture and exact source hashes, CPU times, warm times, all observations and
reproduction drivers are in [cold-readiness evidence](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/cold-readiness-20261025/README.md).

## v61 rollout and initial server stress result

Source `7f185bc7c0195e286b32f509c6502e44b3eca844` was committed/pushed to main
and deployed as Fly **v61**, image
`sha256:cad5a65e6c194eb43db0d068a4e4700fb016459d98996a20e0178492b9a96cb6`.
The overlay copies exactly four dashboard files on the v60 digest; no dependency
installation occurs. All **175 deployed runtime input hashes** match. Python
3.13.16 / Streamlit 1.65.0 / Pydantic 2.14.0 / core 2.50.0 / pandas 3.0.6 /
NumPy 2.5.4 remain the deployed versions.

Machine `6835752b711958`, shared CPU 1 / **2048 MiB** and original volume
`vol_4m3l58dkk29y19zv` are retained. Paper/Codex `gpt-6-astra` / Claude rollback
sonnet are verified. The first post-rollout paper cycle starts at
2026-10-24T19:47:13.774794Z and completes at 19:47:34.702961Z. HTTP health passes.
The root main checkout fast-forwards to the deployed source; unrelated settings
and lock hashes remain identical to the preservation snapshot.

A local protocol-driver mistake (`Metric.value` instead of deployed `Metric.body`)
failed before concurrent observation. The actual descriptor was inspected and
the metric/arrow element fields corrected. This harness failure is recorded and
never counted as a successful cold or page sample. The corrected warmup pair
Home 0.656s / Trading 1.035s uses an already warmed server, **not process-cold**.

The subsequent **four-session, five-second navigation** observation starts
19:49:20.119258Z and stops at 19:52:50.451578Z (**210.332s**):

- Health: 39/40 pass; the final sample times out at **5.102s**, triggering the
  prescribed stop guard. The run fails and is not extended to manufacture a pass.
- Home 74/77 and Trading 75/76 views complete. Four in-flight views remain
  incomplete when the health guard stops the run. Their driver status says
  `timeout`, but they did not independently exhaust their full 30s timeout;
  the global health stop ended them. They remain in the completion denominator.
- Successful-only p95 Home 0.594s / Trading 1.235s does **not** qualify a series
  with failures. Required native and cold page acceptance is not claimed.
- 209 memory samples: dashboard observed RSS growth **19.454 MiB**, conservative
  process HWM minus warmed RSS **22.582 MiB**, peak guest use **641.781 MiB**.
  These are current 2 GiB guest observations, not the original 1 GiB qualification.
- Engine/dashboard PIDs remain 655/656; no restart or sampled memory spike.
  A whole engine cycle is not inside this short failed test interval.

After stopping its clients, public HTTP health recovers and source/process/
paper-cycle verification passes again. Current host Prometheus metrics return
HTTP401 with the existing credential; no credential is printed/persisted or newly
created. The guest exposes unlimited internal cgroup quota and zero internal
throttles, which cannot stand in for host quota counters. The cause of the
transient failure is **not attributed conclusively** to host throttling. Earlier
CPU evidence is historical; [Fly metric units](https://docs.fly.io/monitoring/metrics#instance-load-and-cpu)
were checked to distinguish host and guest counters.

A separate **twenty-second navigation** scenario is running with its own phase
and raw evidence. It neither replaces nor erases the five-second stress failure.
It must run at least ten minutes and extend over a whole existing engine cycle.

## Additional semantic verification and next contract

A further **24 complete full-output/provenance parity cases** cover all **42**
canonical event types, eight shuffled inputs, Aggregate/a/b scopes, cross-file
cycles/companions, exact/legacy simultaneous gates, minimum UTC, offsets,
cutoff boundaries and future events. Every case matches `bf44822` exactly.

A [new functional design candidate](../../aidlc-docs/construction/dashboard-operator-ui/functional-design/verified-segment-checkpoints/business-logic-model.md)
proposes disposable verified whole-file checkpoints across restart, with exact
cross-file merging and unchanged canonical data/financial rules/capacity.
Modified files validate in full; no size-only append cursor is assumed safe.
This changes the prior no-durable-checkpoint contract, so it is **awaiting explicit
functional approval** before NFR/infrastructure design and implementation.
A candidate 64 MiB derived-disk envelope is not an active setting. Unseeded cold
bootstrap and all existing acceptance targets remain required; no latency outcome
is promised by the candidate itself.

## Completed twenty-second server observation

The separate scenario runs **1171.054s (19m31s)**, from 19:58:47.997734Z to
20:18:19.051838Z. It captures a whole paper cycle: 20:17:34.805551Z to
20:18:01.491378Z, with twelve monitor passes and no errored event in its captured
start-to-completion interval. Engine/dashboard PIDs remain 655/656.

It **fails**: 229/230 public health requests pass; the final request times out at
**5.136s** while the engine cycle/source updates overlap navigation. Home and
Trading each complete **114/116** views; four in-flight views abort after the
health guard stops the test. Successful-only p95 is 0.583s / 0.911s, but the
failure ratio prevents passing acceptance. Peak dashboard RSS/HWM growth over
the warmed baseline is **8.496 MiB**, guest use **646.059 MiB** on the unchanged
2 GiB guest. Engine/dashboard CPU increase is 14.26s / 77.07s. These do not
measure host quota. Public health and source/process verification recover after
stopping load. Both navigation scenarios remain failed, not replaced by a pass.

Code-path inspection finds each pending section registers its own half-second
background fragment (five Home sections; four Trading sections). A follow-up
will coalesce those registrations per page while preserving individual coverage
messages. This is a source-backed redundancy finding, not a proven attribution
of either observed health timeout. It requires new exact-source verification and
rollout before any performance claim.
