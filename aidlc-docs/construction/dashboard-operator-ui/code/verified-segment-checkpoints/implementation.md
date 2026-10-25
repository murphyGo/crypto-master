# Verified segment checkpoint implementation

## Scope and ownership

The existing single dashboard worker optionally uses one private disposable store
under `<Settings.data_dir>/.dashboard-read-cache/v1`. Production factory enables
it; `DASHBOARD_CHECKPOINTS_ENABLED=0` restores canonical-only operation. Direct
services do not write disk unless explicitly given a store. Prepare before
canonical manifest capture, never create absent canonical roots, and reject
namespace overlap without changing canonical selectors.

Activity stores unfinalized cycles/counters/companion evidence and source-local
ties; global rejection suppression and duration order remain canonical. Missing
complete rejection indexes run the bounded second pass. Snapshots reuse one whole
file per unique account with the same order/count/curve limit; hierarchical curve
fragments are not merged. Large proposal datasets store only canonical classification, time,
group and lifetime-threshold descriptors, reevaluated at current time. Small
proposal files (average below16 KiB) keep the faster existing canonical path;
20-pair evidence showed cache/proof overhead there. This is optional acceleration
admission, not a change to source/metric semantics. Ledger
keeps its original sequential float calculation. Unsupported/dynamic/nonfinite
state is a canonical miss, never healthy empty or stale data relabelled fresh.

## Bounds and correctness

64 MiB total disk includes old/new/temp/index/lock/marker data;64 physical files,
50k logical keys,two roots. Actual packs are <=1 MiB (stricter than the approved
4 MiB ceiling), with logical states <=1 MiB-40 (within2 MiB upper bound). Typed
lossless JSONL splits large containers into small leaf records to avoid restoring
a large intermediate JSON tree. A fixed proposal codec avoids generic map tags.
No pickle/unknown class loader. SHA footer/length/header/locator checks, owner-only
namespace and a producer marker delimit disposable ownership.

The packed index reserves up to4 MiB inside the existing16 MiB result cache;
smaller configured caches shrink that reservation too. Codec/pack/index rewrite
scratch and temporary local reductions share the original16 MiB active budget;
4 MiB source manifest includes current-key proof buffers. Existing one worker/
four jobs,2s fresh/30s stale and4s foreground wait remain. Caps/acceleration faults
fall back canonically; no unbounded second executor or per-session index is added.

One nonblocking shared store lock is held for a query, released for exclusive
COW publication and closed on every generator exit. Canonical writers never lock.
Current membership, full file generation/ctime/mode, readability and model/runtime
compatibility must match before and after global merge. No size-only append skip.
Corrupt/absent/incompatible/locked/full stores cannot hide valid canonical siblings.

Atomic publication admits old/new/tmp space and count, fsyncs packs/index/directory,
then removes only producer-owned victims/orphans. Unknown files are retained and
charged; a full64-file store cannot create a65th temp. Enable writes at192 MiB
free and retain128 MiB reserve. No volume resize, canonical migration or deletion.

## Qualification boundary

Tests cover full-payload restart parity, all activity types/cross-file companions,
UTC ties and membership rebasing, proposal windows/future/groups, snapshot curve
sampling and dynamic-default exclusions, corruption/disk/atomic/lock/owner/symlink
faults, two roots/global quota, index reservation and canonical-only services.
An intermediate measured regression prompted framed decoding and once-per-query
locking; its failure evidence is retained separately. Final20-pair benchmarks
and production/native/guest evidence are reported without waiving original targets.
