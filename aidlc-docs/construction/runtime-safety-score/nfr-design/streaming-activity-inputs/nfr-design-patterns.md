# NFR Design Candidate: Streaming Runtime Safety Inputs

**Status:** Approved by operator `gogo` for implementation, verification and same-capacity rollout; not yet implemented.
Base streaming/request-time Functional contract is approved for continuation.
The [failure-isolation amendment](../../functional-design/streaming-activity-inputs/failure-isolation-amendment.md)
and this numerical/resource design require explicit approval together.
Existing v62/source `d86f76f`, paper/Codex, allocation and canonical data remain.

## 1. Scope and immutable semantics

Replace archive-sized input retention with one canonical event at a time and a
single-pass scalar/distinct-condition reduction. Keep all score weights/factors,
clipping, bands, configured pause thresholds and modes. At fixed explicit UTC,
outputs must match an independent reference of the old helpers. Preserve stale
reason/message OR semantics, advisory truthiness, cycle/account/gate fallback,
Python equality of supported scalar kill keys, duplicates, extra events, future
timestamps and the inclusive 24h boundary. An explicitly nonpositive lookback
still includes all eligible events. No price/fee/PnL/position rule changes.

Freeze one UTC evaluation instant before admitting the read. This approved base
contract can conservatively retain a boundary incident that the old post-load
clock would expire. Recheck clock/age before publication: UTC reversal or age
beyond the call deadline makes the evaluation unavailable, never younger/fresh.
Keep `None`-only per-cycle score-cache identity semantics; an explicit list,
including an empty one, still requests a new evaluation and never falls back to
that score on error. Do not fabricate a new evaluation time on a cache return.

## 2. Proposed quantitative design

These are implementation proposals, not new acceptance targets or measured passes.

| Resource | Proposed process-wide limit / accounting |
|---|---|
| Runtime read workers | One lazy **daemon** thread in one process-owned service; no per-proposal/account thread. |
| Admitted runtime jobs | One active, zero waiting jobs. A busy/quarantined slot fails promptly; never spawn a replacement for stuck IO. |
| Read block / raw row | 64 KiB / 1 MiB, checked before raw accumulation/model creation. |
| Active reducer/state | 16 MiB, including exact kill keys, counters, owned extra references and temporary state/sort structures; conservative structural sizing before retain. |
| Distinct live kill keys | 50,000 and the byte cap, whichever is reached first. No approximate count. |
| Source manifest | 4 MiB; streaming directory selection reserves before keeping names/versions. |
| Optional validation-summary cache | 2 MiB / 64 files / two source roots; included in reader-owned accounting, LRU; no persistent runtime cache. |
| Extra/replay input | At most 4096 events and 2 MiB structural charge, included in active state; check count before copying references. |
| Handles | At most eight including directory iterators; deterministic close on every cooperative exit. |
| One evaluation | 30s monotonic including admission/discovery/IO/reduction and at most 2 GiB actual read bytes. |
| Whole-cycle safety work | 60s cumulative safety-read wall time and 4 GiB raw reads; reset at cycle start. Exhaustion refuses later new reads but does not suppress existing position management. |
| Cooperative checks | Every read block and at most 256 decoded rows; one bounded row is the unchecked validation unit. |

The accounted reader-owned envelope is **22 MiB**: active state 16 MiB + source
manifest 4 MiB + optional summary cache 2 MiB. The 2 MiB extra cap is inside the
active 16 MiB, not additional. One raw/decode working row is separate.
Manifest/summary-cache storage is explicitly counted alongside active state;
raw/decode working memory is one bounded row, not a second archive. Logical
caps are not RSS guarantees: the original <=768 MiB guest and dashboard <=256 MiB
growth targets remain authoritative. Engine baseline/process peaks are sampled
separately; do not sum shared RSS to infer guest use. A million-event cold read
under depleted CPU may exhaust 30s: that is a guarded failure and still **not**
a performance acceptance pass.

## 3. Source capture and legacy parser compatibility

Discover exactly the current monthly-plus-legacy source set with bounded
selection. Preserve the actual retention behavior (legacy plus newest N rotated
files); do not fix its historical documentation discrepancy. Capture selected
membership and each file's device/inode/length/mtime plus optional ctime/mode.
Open/readability and final membership/file proof are required even for cache
skips. Any replacement, truncation, append/change during the captured read or
unreadable source makes that evaluation unavailable. Size growth does not prove
an immutable prefix; no append cursor or canonical writer lock is introduced.

Add a forward raw-row interface using existing bounded-block mechanics, with a
**separate runtime legacy parsing policy**. Do not weaken dashboard strict readers.
Preserve universal LF/CRLF/CR line endings and text `strip()` semantics,
including Unicode whitespace. Decode UTF-8 text then use the old JSON/Pydantic validation route; do not silently
accept UTF-16/BOM, change NaN/scalar identity behavior, or normalize arbitrary gate
values differently. Preserve blank-line handling, JSON/model ValueError warning
and skip behavior, and a syntactically valid final row without newline. Invalid
UTF-8, non-object rows that were hard failures, hard IO and oversized/cap-exhausted
rows remain typed hard failures. Record legacy-skip counts; this is the existing
best-effort runtime policy, not a claim of strict dashboard coverage.

The chronological `read_all()` and its legacy callers remain intact. The new
source iterator is explicitly unsorted and is used only by order-independent
safety reduction. `finally`/delegated close must release nested readers on early
exit, cancellation, malformed hard input and state exhaustion.

## 4. Optional negative file validation cache

To avoid reparsing unchanged irrelevant archives on every explicit-extra call,
cache only complete per-file validation metadata: generation, canonical model/
parser version, maximum validated timestamp, legacy-skip count and a flag for
dynamic timestamp defaults. There is no rich-event or score cache here.

A file may be skipped only when its current readable generation still matches,
its complete validated maximum is **strictly older** than this request's cutoff,
and it has no missing/dynamic timestamp default. Retain future/out-of-order
records regardless of filename month. Missing timestamps can become "now" on
revalidation, so those files are never skipped by this optimization. Nonpositive
lookback disables the shortcut. Preserve legacy warning/skip visibility for a
cached legacy-skip count. A partial scan never publishes a summary.

Changing file/retention/root/model/Python/Pydantic/parser contract invalidates its
summary. Permission/readability changes must not be hidden by a stat-only hit.
Eviction/unknown/default flags cause bounded streaming, not healthy empty output.
No runtime consumer trusts dashboard counters or a persisted checkpoint to make
a pause decision in this first slice.

## 5. Worker lifetime and trading failure isolation

The event loop awaits a concurrent future under a monotonic deadline; IO and
source validation stay off it. Copy the extra-event **container** into an owned
bounded tuple; the engine owns these fresh canonical models and does not mutate
them while awaiting. Do not JSON-roundtrip/deep-normalize condition identities.
Freeze/charge only supported owned structures; unsupported sizing fails explicitly.

After timeout/cancellation, mark the result discarded and cancel cooperatively.
The slot remains occupied until the worker actually unwinds; late results cannot
populate a score cache or admit an order. A blocked kernel syscall cannot be
force-cancelled. There is no queue growth or second worker. Close flags prevent
new jobs; bounded shutdown/daemon ownership must not hang the existing process
exit. Normal engine `stop()` keeps its finish-current-cycle behavior; actual task
cancellation/teardown is distinct. No new process supervisor or Fly hook.

Expected failures return a fresh typed stable-reason exception without raw
payload/source traceback retention. Long-lived cycle error records store a
sanitized new exception, not the worker's accumulator/extra/source frames.

Use the proposed amendment: fail the current account's risk-dependent proposal
path, record the existing error event, break remaining proposals for that account,
then run its existing monitor and snapshot exactly once. Later accounts continue;
exhausted cycle budget refuses further reads promptly. Never invent a reject/fill,
retry a partial execution, duplicate an already delivered notification, or skip
monitoring merely because safety inputs are unavailable. The two call sites are
before execution and require negative execution tests. Ordinary unexpected
scan/monitor/exchange failures retain their existing guard.

## 6. Observability, verification and rollout boundary

Allowlisted diagnostics: kind/reason, UTC evaluation time/age, outcome, counts,
bytes, durations, cache hits and exhaustion. No raw rows, free-form exception,
source path, credential, URL or operator ID in telemetry. Existing canonical
per-account error context remains in its authorized activity record; message
uses only a stable reason. This slice adds no notification recipient.

Require an independent old-helper oracle at fixed UTC; all canonical types,
nonfinite/scalar edge keys, advisory/fallback/duplicates and lookbacks; one-shot
iteration/object-lifetime and close tests; both pause call sites with configured
and disabled policy in paper/live; failure isolation, timeout/quarantine/cancel,
clock reversal, limits, source mutation and later-account monitor continuity.
Qualify incident/>=1M fixtures, filled/depleted CPU separately, 20 cold/warm page
samples and four sessions through a real cycle with original guest semantics.
Fix the prior harness's normal-end censoring: log every request start and retain
all timeout/partial/cancelled observations; never count boundary cancellations
as successes. Native browser still requires the supported connection.

No application/source change or deployment occurs before this NFR and the
amendment are approved. Then implement/qualify the engine slice first, checkpoint
slice second. Stop on unqualified conditions rather than declaring debt closed.
Infrastructure design is N/A: internal thread only, same process/machine/mount/
credentials/cadence/allocation. Existing scoped source-rollout authority persists
only after required design approval; performance CPU/cost stays deferred.
