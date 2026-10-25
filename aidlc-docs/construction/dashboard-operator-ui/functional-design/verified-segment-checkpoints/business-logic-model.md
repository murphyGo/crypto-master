# Verified Segment Checkpoints: Functional Design Candidate

**Status:** Proposed, awaiting explicit functional-design approval. No checkpoint
writer or storage has been implemented or activated. Existing bounded loading
remains the deployed behavior. This is a new persistence contract, separate from
the deferred performance-CPU/cost proposal.

## Problem and intended behavior

v61 reduces read-side CPU while preserving complete output, but the million-event
empty-cache p95 remains 7.872s against 5s. A whole-query source digest change still
causes complete reduction, and restart discards all verified projection work.
The four-session five-second navigation test also failed its health deadline;
current host throttling was not available to confirm its cause. These findings
justify considering reusable file projections; they do not prove this candidate
will meet the latency targets. The failed five-second test also contains warm
renders; no cause link between that failure and a changed-file rebuild was
established. Checkpoints address restart/rebuild work, while render cost and
higher-frequency navigation need separate evidence and may need another fix.

Retain bounded, validated reduction state for each whole source-file generation.
After a query or process restart, reuse a compatible checkpoint only after the
same eligible source membership, file versions and consumer semantics are
verified. Fully reduce each changed/new source file. Merge compatible partial
reductions into the exact current result, then publish with verified provenance.
All canonical operator records remain authoritative and untouched.

## Read flow

1. Normalize the requested root, scope, mode, accounts, source selection and
   schema/reducer identity. Discover the complete eligible source set.
2. For each file, look up a bounded checkpoint keyed by that whole generation.
   Validate checkpoint integrity/compatibility before considering its state.
3. Reuse a verified compatible state, or stream and canonically validate every
   row of that source using the existing bounded reader. A changed size is not
   proof that the old prefix is immutable: this design does not skip to an append
   offset and does not change canonical activity writers.
4. Merge raw cycle counters and first/start/terminal state across files; apply
   global rejection-companion suppression once. Reconcile exact latest/detail
   selection, global/account scope and event-window expiry at publication time.
   A per-file recent list cannot replace lifetime or cross-file state.
5. Verify captured sources/membership again before publishing a complete result.
   Persist only complete individually verified checkpoints in a separate derived
   namespace. Incomplete global coverage remains explicit even when some source
   checkpoints are independently useful.
6. On incompatibility/corruption/missing checkpoint, fall back to canonical
   bounded reduction. On storage failure, keep usable independently verified
   query results; an optional acceleration failure is not a financial-data zero.

## Bootstrap and acceptance

A never-built or incompatible checkpoint requires original-source validation.
This candidate does not promise a 5s first-ever bootstrap or waive it. Qualification
must separately measure no-checkpoint bootstrap, same-version process restart,
changed-file generation, cache hit, and four sessions with depleted/available
CPU capacity distinguished where telemetry allows. The existing 5s cold / 2s
warm, memory, health and completeness targets remain binding. Failure keeps
DEBT-083 active. No new CPU allocation, external database or paid service is selected.

## Stage boundary

Approval covers this functional contract only. NFR/infrastructure design must
specify bounded encoding/decoding, disk quota and cleanup, crash-safe publication,
source/version proof, concurrency, permissions, free-space handling, resource
measurement and rollback before implementation. A 64 MiB derived-disk envelope
on the existing volume is a candidate for that next stage, not an activated setting.

## Later qualification finding

v62 also records four true 30s page timeouts with substantial CPU credit and
zero throttle; guest peak 1293.313 MiB includes engine peak RSS 878.660 MiB.
Whole-history safety scoring in the engine is a separate allocation path and
feeds actual pause decisions. This checkpoint candidate alone is not a complete
resource remedy or permission to change that gate. A separate runtime-safety-score
Functional Design is pending; the next NFR review must reconcile shared-process
memory and mutable-source coverage rather than assume a cache fixes both.
