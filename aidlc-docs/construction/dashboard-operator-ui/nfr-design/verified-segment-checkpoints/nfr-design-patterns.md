# NFR Design Candidate: Verified Segment Checkpoints

**Status:** Approved by operator `gogo` for implementation, verification and same-capacity rollout; not yet active.
Base Functional persistence contract is approved for continuation. Original BDL
requirements and budgets remain binding; this is not evidence of acceptance.
Same v62/175 runtime inputs, shared CPU 1 / 2048 MiB, original volume, paper/Codex
and deferred CPU/cost proposal remain. No canonical writer changes.

## 1. Selected scope and fixed targets

Initially accelerate **activity**, **snapshots** and **proposals**, using lossless
file-generation reductions. Keep ledger/candidates/promotion/audit on the existing
bounded canonical path in this slice. In particular, do not merge per-file ledger
float sums: Python sequential addition is non-associative, and grouping can change
financial output. This is an optional cache miss, not a new financial calculation.
Preserve all current periods, upper/lower inclusivity, UTC/source ties, exact
counts and consumer-specific equity. No win-rate/fee/PnL rule correction is mixed in.

The original cold <=5s / warm <=2s p95 (>=20 observations each), dashboard growth
<=256 MiB, guest use <=768 MiB on declared 1 GiB, all health <5s and four sessions
through a full cycle remain. Current 2 GiB/buffered-CPU observations cannot certify
original 1 GiB or depleted CPU. Unseeded bootstrap remains a separate requirement;
a checkpoint does not promise its first-ever canonical scan will pass 5s.

## 2. Process and disk admission

| Resource | Proposed rule |
|---|---|
| Existing dashboard worker/admission | One worker / four admitted jobs total; no cache thread/executor per session. |
| Existing RAM budgets | Completed result cache 16 MiB / 64 entries; active state 16 MiB; source manifest 4 MiB; roots two. Do not add an uncharged cache. |
| Packed cache index | At most 4 MiB, reserved from the existing 16 MiB completed-cache budget; evict optional results/index work first, never exceed it. Sort/decode scratch counts in active state. |
| Logical source checkpoint | At most 2 MiB encoded, no rich archive; each JSONL codec record <=1 MiB. |
| Physical pack / index | Pack <=4 MiB; binary packed index <=4 MiB. Stream 64 KiB blocks, never read an unknown file wholesale. |
| Disk total | **64 MiB** across all published/temp/index/marker/lock files and two source-root contexts, not 64 MiB per root. Count allocated blocks plus conservative per-file/directory overhead. |
| Persistent counts | At most 64 physical files including temporary/metadata files, 50,000 logical source keys; bounded packed index rather than thousands of Python dictionaries. |
| Shared handles | Existing maximum eight, including pack/lock/source/directory handles. Cache work releases handles before another phase needs them. |
| Time/work | Existing 4s foreground/quantum, 512 MiB raw IO per quantum and cooperative 64 KiB / 256-record checks remain. Cache IO participates in the deadline/work accounting. |
| Fresh/stale reporting | Existing 2s fresh / 30s stale; a disk file's mtime is never a result's evaluation time. |

The codec/index/buffer caps are logical accounting, not exact RSS guarantees.
Decoded expansion, DataFrames and concurrent sessions still need peak RSS/guest
measurement. No simultaneous per-file/global copy may bypass active-state charge;
transfer/merge state incrementally and release the consumed local state. If an
optional cache path needs extra scratch that cannot fit, discard it and run the
canonical bounded path. Only canonical coverage failure can make required data
unavailable; acceleration failure alone cannot hide valid siblings.

## 3. Namespace and current capacity

Production cache base: `<Settings.data_dir>/.dashboard-read-cache/v1`, one store
for two hashed query roots, with a global quota. Prepare it **before** capturing
canonical source-directory generations, or first creation could invalidate a
query whose missing-source proof uses the data-root ancestor. Never create a
missing canonical data root/input directory just to enable caching.

Use private owner-only directories/files (0700/0600), a producer marker and
noncanonical suffixes `.cachepack`, `.idx`, `.owner`, `.lock`, `.tmp`. Do not use
`.json`/`.jsonl` marker names that a legacy proposal selector could ingest.
Canonical selectors/symlink compatibility stay unchanged. If a custom source
selection overlaps the derived namespace, disable acceleration for that request;
do not alter its canonical selection. Direct test services default to no store;
the production factory explicitly supplies the approved store and tests inject
an isolated temporary store.

Read-only preflight records `/data`: 997076 KiB total, 197504 used, **731580 KiB
available (~714.434 MiB)**. This is a snapshot, not a future reservation. Enable
writes only with at least 192 MiB free (64 quota + 128 reserve); before each
publication require >=128 MiB plus the admitted write allocation. Below the
floor, stop optional writes and reclaim only owned disposable files as possible.
Never resize the volume, delete/migrate canonical records or change retention.
One optional disable switch may select the existing bounded reader; no new UI
storage control or automatic paid resource is selected.

## 4. Eligibility and identity

Every logical checkpoint key includes normalized root/source/kind/mode/scope/
accounts/order/window/version contract, codec version and a conservative runtime
compatibility digest. The digest covers the deployment's allowlisted runtime
source/config/model files and Python/Pydantic/core/Pandas/NumPy versions, without
reading `.git`, credentials or arbitrary environment. Compute it once under a
bound, not on each page poll. Any mismatch is a miss; do not infer compatibility
across code upgrades. First use after incompatible code may still be cold.

A per-file key additionally includes source-relative identity and the captured
file generation. Exclude the full selected-membership digest from that key so
unchanged files survive additions; always rediscover current membership globally.
Rebase source order when membership changes. Permission/readability/source proof
is mandatory at load/publication, never directory mtime alone. Source changes,
including append, rebuild the whole affected file; there is no size-only cursor.

**Ineligible in the first slice:** source/model state with missing dynamic
factories (time/UUID etc.), unsupported codec values/nonfinite numbers, oversized
state or insufficient exact cross-file proof. Re-read canonically rather than
freezing a dynamic default or changing NaN/key identity across serialization.
Known deterministic builtin empty factories can be explicitly allowlisted only
with parity tests; future unreviewed defaults stay ineligible. Snapshot default
timestamps are not silently carried across process restart. Cache misses cannot
become a false source failure or healthy empty view.

Fixed `Query.at` identities match exactly. For default advancing time, retain
coverage lower bounds and future descriptors; reject a state if the current
cutoff is earlier than its covered base. UTC reversal rejects/rebuilds rather
than inventing freshness. Preserve different safety/funnel window rules instead
of imposing one generic range.

## 5. Lossless per-kind reduction and merge

### Activity

Store **unfinalized** cycle state (first/start/earliest terminal/error/raw counters),
raw account counters, companion counts, bounded detail/latest heaps, exact recent
safety/window descriptors and necessary provenance. Never cache only top-50 cycle
summaries for lifetime metrics, and never finalize companion rejection adjustment
inside each file. Merge cycle extrema/counters globally, then perform global
rejection-companion suppression **once**. Recompute duration aggregation in the
same globally sorted cycle order; do not sum per-file floating durations.

Persist positive source-local offsets, not a baked global ordinal. Rebase against
the current file rank, preserving the distinct first/last tie policies used by
latest, timeline and derivative tables. Top-K per-file merge is lossless only
with the same timestamp/tie ranking; all totals use independent raw reductions.
Keep per-metric latest risk state and exact latest reconciliation/cycle evidence.

A complete small rejection-membership index may accelerate the global companion
join within budgets. If it cannot fit, mark it **needs canonical join scan**;
never mark a partial index complete or absent. Gather the global companion IDs,
then use the existing bounded second pass for files whose required membership
proof is missing. A verified type-set can prove that a file has no rejected rows;
otherwise no recent-only/PID sample replaces exact lifetime joining.

### Snapshots

One source file per unique account can retain its exact latest row, captured
first-validation timestamp and full per-account curve reduction. Eligibility
includes account order/count and curve limit. Hierarchical extrema sampling is
not generally associative: do not merge arbitrary pre-sampled fragments or
replay a compact curve as raw history. Duplicate accounts/multiple files per
account fall back to the canonical path. Preserve account insertion order and
Decimal text/exponents; do not change summation order in consumer equity helpers.

### Proposals

Small files are logical source entries packed together, not one disk file per
proposal. Retain exact lifetime threshold, classification/group universes,
time-window descriptors (including future ones), and source proof. Re-evaluate
window counts at the current approved time, preserving empty lifetime groups
where existing output retains them and excluding the existing archive/deeper
paths exactly. Group/count identities remain subject to existing limits.
Home-to-Trading threshold reuse retains its fresh-compatible age/provenance rules.

### Unaccelerated kinds

Ledger metrics retain original sequential float accumulation, raw row semantics
and order. Candidate/promotion/audit continue the existing bounded implementation.
No universal merge is assumed merely because two objects are JSON-compatible.

## 6. Codec, packs and integrity

Use a versioned non-executable UTF-8 JSONL codec with strict record schemas,
lossless integer/Decimal/UTC representations and explicit supported state types.
Flatten tuple-key maps into typed records; never use pickle, arbitrary class
construction or silently stringified dictionary keys. Preserve source fields
needed by the existing published payload. Reject incompatible records as cache
misses. Nonfinite/unsupported/dynamic-default sources are not persisted.

Pack multiple logical file states into an immutable <=4 MiB container. A logical
checkpoint remains <=2 MiB. Footer records contain counts/length and a SHA256 of
preceding bytes; truncated/missing/footer/type/checksum mismatch is a miss, never
partial success. An index maps a 32-byte source key to bounded pack/offset/length
locators, structurally checked against the pack/header/current source identity.
Charge any Python sort scratch before constructing it; no unbounded index list.
Verify each needed immutable pack once per job, not once per tiny proposal.

Current source owner and private namespace are the trust boundary; checksums
protect corruption, not a privileged owner forging both canonical and derived
files. Validate regular file/owner/mode/link shape and reject symlinks/special
files in the derived store, without tightening canonical source compatibility.
No credential or external signing key is introduced.

## 7. Atomic publication, cleanup and failure recovery

Use a nonblocking POSIX store lock: shared readers, exclusive publication/cleanup;
no wait on the page path and no lock on canonical writers. If unsupported/busy,
use bounded canonical reads. Do not hold source handles while waiting for a
store lock. Index is copy-on-write: admit space/count for old/new/temp files,
write an exclusive temp pack, flush/fsync, rename the immutable pack, then fsync/
atomically replace the new index and fsync its directory. Never truncate an
existing cache path, follow a derived symlink or expose a half-written index.

After a crash, the old index is still usable or the new complete one is selected;
orphan temps/packs remain optional, quota-counted and removable under exclusive
ownership. Before eviction publish an index omitting owned victim references,
then unlink those packs after readers are excluded. Count all temp/metadata and
open-reader constraints; do not require doubling the 64 MiB quota to rotate.
If no safe headroom exists, skip the cache write and still deliver a verified
query. Unknown files are not deleted; they can disable writes via quota.

Disk/index/lock/permission/full/corruption failures are cache misses with stable
reason codes. Canonical source failure still yields explicit incomplete coverage
and verified siblings. A disk checkpoint is **not a stale result**: load only as
candidate state, verify current source set/versions, merge, re-evaluate windows,
verify again, then publish a new result/evaluation time. Preserve source event
age separately. Never relabel an old serialized report as fresh just because it
was read from disk.

## 8. Verification, rollout and unresolved acceptance

Require fixed-time full-payload parity with independent canonical builders:
new/missing/replaced/truncated/overwritten sources, rollover/retention, same-size
mtime changes, cross-file cycles/companions, duplicate PID/ties, current offsets,
window expiry/future rows, missing timestamps/defaults, nonfinite/Decimal values,
raw fields, duplicate account/curve exclusions and non-associative ledger fallback.
Test every cap and total across two roots/four sessions, source and codec handles,
corrupt footer/index, interrupted fsync/rename, lock contention, disk full/free
floor, unknown/symlink files, restart/model upgrade and cancellation. A cache
fault alone must not suppress independently valid data.

Qualify separately: no-cache bootstrap, seeded cache in restarted process,
unchanged generation, changed file, membership/retention change, disk-ineligible
fallback; include app imports and full script completion. At least 20 cold/warm
observations, failure ratios and normal-end censored requests are retained.
Filled/depleted CPU, native pages and original guest are separate conditions.
A fast seeded result never waives failed first bootstrap or other original goals.

Implement runtime memory slice first after its approvals, then these three-kind
checkpoints; verify unchanged trading semantics/source hashes and use the existing
minimal-overlay same-capacity rollout. No deployment occurs in this design step.
Infrastructure design is N/A while only this application-owned namespace is added
to the existing volume/process. Any mount/VM/process/credential change reopens it.
Rollback disables optional caching or uses the previous exact image; canonical
data is untouched and old selectors ignore the private noncanonical suffixes.
