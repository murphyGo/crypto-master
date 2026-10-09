# NFR Design Patterns: Bounded Dashboard Data Loading

**Status:** Approved by operator `진행시켜` on 2026-10-09; design requirements.
Measured implementation status is in the Code Generation qualification report;
the approved targets below are not claims of full acceptance.

## 1. Work and Memory Admission

All limits apply across the dashboard process unless marked per query/record.
Do not multiply them by session count. Resource counters reserve capacity
before retaining a new value; exceeding a cap produces explicit limited
coverage for the dependent section.

| Limit | Proposed value | Accounting / consequence |
|-------|----------------|--------------------------|
| File read block | 64 KiB | Stream in bounded blocks; a huge line cannot allocate an unbounded `readline()` buffer. |
| JSONL line / JSON object | 1 MiB | Check raw bytes before rich-model creation; oversized records invalidate required coverage. |
| Encoded result per entry | 2 MiB | Include returned detail/curve data; if it cannot fit, mark affected detail/aggregate incomplete rather than silently drop required state. |
| Completed result cache | 16 MiB, at most 64 entries | Count encoded payload, keys/metadata and a conservative 4 KiB entry overhead reservation. LRU eviction; no cached raw archives. |
| Live reducer/checkpoint state | 16 MiB total | Account owned containers, keys/strings and values, with conservative structural overhead; no hidden unbounded cycle or dedup map. |
| Source manifest/provenance | 4 MiB total | Bound file-generation metadata and discovery state; inability to cover the source set is a partial result. |
| Record decode/working buffer | One worker, bounded by record/read limits | Decode one record at a time; do not retain a second archive in the generator. Actual Python expansion must pass the RSS criterion. |
| Rebuild workers | 1 | One process-owned worker, not a worker per page/session. |
| Admitted distinct rebuilds | 4 total, including the active job | Coalesce identical work; full admission returns a busy/unavailable or valid stale result without spawning another worker. |
| Resident source-root contexts | 2 | Share one global memory budget; evict/cancel inactive contexts without deleting files. |
| Accounts / strategy groups | 128 / 256 per projection | Complete aggregate counters remain separate; required group overflow is explicit incomplete coverage. |
| Identity/dedup state | 50,000 keys maximum, also subject to the 16 MiB cap | Never fall back to an approximate distinct count for an exact metric. |
| Source handles | 8 per worker, including directory iterators | Close descriptors on completion, invalidation and eviction. |
| Foreground wait / rebuild quantum | 4.0s monotonic | Includes queue wait. Return available sections plus explicit missing coverage within the 5s shell target. |
| Raw IO per rebuild quantum | 512 MiB, also subject to deadline | Independent work cap covering the >=1M-event fixture; bytes beyond it need a bounded continuation. |
| Cooperative checks | Each read block and at most 256 decoded records | Check deadline/cancellation/capacity and yield execution; parsing one bounded record is the maximum unchecked parse unit. |
| Complete-result cache age | At most 2s | Source changes can invalidate earlier; display result evaluation/source times. |
| Last complete fallback age | At most 30s since its evaluation | May be displayed only as stale, with dependent safety/coverage notice. An old report's event timestamp is distinct from cache age. |
| Timeline / cycles / duration rows | Existing 300 / 25 / 50 | Display-only limits; totals and cycle correctness have separate reducers. |
| History rows / curve points | Existing 25 / proposed at most 4096 | Preserve history order; disclose curve reduction and retain extrema/latest values. Never use sampled curves for financial aggregates. |

The logical byte limits are not claims about exact RSS. Encoded payloads can
expand when parsed or placed in DataFrames; one/four-session RSS and guest
memory qualification is authoritative. Cap decoded working structures as well
as serialized cache content. If the approved 256/768 MiB targets fail, the
implementation does not pass by reporting only encoded cache bytes.

## 2. Coverage Before Healthy State

Each result carries independent completeness and freshness. Required source
failure, oversize/corrupt records, reducer overflow, bootstrap still running,
generation inconsistency, or a spent budget cannot become an exact zero or a
fresh SAFE/no-position claim. Reuse previous complete data only with a stale
label. Independently complete ledger/snapshot sections remain available.

A limited recent list is not the input to a lifetime/latest-state builder.
Latest successful or failed reconciliation, latest cycle, exact recent safety
inputs and lifetime counters are different projections. A adverse partial
candidate can be shown as found evidence, but cannot be advertised as the
verified latest report before source coverage completes.

## 3. Streaming and Restart

On first use, capture the eligible source set and per-source versions/prefix
lengths within the manifest budget. Stream records, normalize using existing
contracts, update compact reducers and bounded detail heaps, then publish one
immutable result. Do not call the legacy generator that first fills/sorts all
raw payloads. Preserve its effective retained monthly-plus-legacy source set;
this task does not fix or alter its retention policy.

When a quantum expires, retain only a bounded checkpoint at a completed record
boundary and the reducer/provenance state, not a decoded event backlog. A
later admitted request may continue compatible work. Source changes that
invalidate a checkpoint restart the relevant bounded reduction. Old partial
work never replaces a prior complete result as fresh. After process restart
there is no durable checkpoint; cold bootstrap and degraded behavior are
explicit and must qualify. Fast partial output is not a complete cold pass.

Reuse compact, verified segment projections for unchanged source generations.
Changing recent cutoffs require exact expiry/re-evaluation of compact event
descriptors within their own caps, or a bounded rebuild. Do not reuse a window
aggregate merely because the underlying files have not changed.

## 4. Invalidation and Mutable Stores

- JSONL reads have fixed captured lengths and complete-line boundaries.
  Concurrent later append is a newer generation to be read on refresh; it
  does not force unlimited catch-up in the current request.
- Preserve stable timestamp/source-order tie rules. Reading file tails or
  seeing an old timestamp does not prove coverage of earlier out-of-order
  records. Complete latest-state results require covered eligible sources.
- Detect inode/device, size, nanosecond mtime and relevant directory/source
  membership changes. Replacement/truncation invalidates any dependent
  checkpoint and derived segment. No cursor crosses into another inode.
- The initial selected algorithm rescans changed source segments in bounded
  streaming form. Append-offset optimization is **not** assumed safe merely
  because size increased; it needs its own proven immutable-prefix contract
  and parity/invalidation tests before use.
- Proposal records can be overwritten at the same id; trade/snapshot arrays
  are atomically replaced. Rebuild dependent aggregates when versions change,
  rather than double-counting updates as new records.
- Directory mtime alone does not certify every contained file is unchanged.
  Validate the captured member metadata within budget before publishing a
  refreshed complete result. Cache reuse is an explicitly timed prior result,
  not an assertion of a transactional/current multi-file snapshot.

## 5. Single Rebuild and Cooperative Timeout

A locked module-owned service owns the one executor, admission table and
cache. Identical query identity/generation shares the same job and immutable
encoded result; no session creates another executor/archive scan. Different
scope/root requests consume existing admission and memory limits. Queue
waiting consumes the caller's 4s deadline.

Rendering stays on Streamlit's script thread. Readers/reducers never call
`st.*`, exchange clients, engine controls or source writers. Do not create an
executor context inside render whose exit waits indefinitely for worker work.

The wait deadline is bounded; stdlib thread cancellation cannot interrupt a
blocked kernel file read. A stuck worker retains its slot, surfaces unavailable
state, and cannot cause replacement-worker growth. Process-level recovery
requires the separate operational action. Worker shutdown, query cancellation
and releasing idle contexts need tests; there is no claim of hard syscall
preemption or a new process supervisor.

## 6. Observability and Infrastructure

Report stable outcome/reason, cache hit, work/retained bytes, row counts,
coverage, queue/rebuild duration and cap exhaustion. Allowlisted telemetry
contains no raw detail, resolved path, URL, secret, exception text or operator
identifier. UI notices describe missing business information without internal
budget/cache details.

Infrastructure Design is N/A for this candidate: existing dashboard/engine
processes, Fly allocation/mounts and runtime writers are retained. The worker
is an internal dashboard resource, not a new Fly process or durable service.
No database/sidecar is selected. A later resource change, native rollout or
recovery has a separate concrete plan and authorization.
