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
