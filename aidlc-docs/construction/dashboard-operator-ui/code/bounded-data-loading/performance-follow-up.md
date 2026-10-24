# Bounded Loading Performance Follow-up

**Date:** 2026-10-11–12 KST. **Unit/debt:** `dashboard-operator-ui` / DEBT-083.

**Subsequent checkpoint (2026-10-25):** Source `38876fc` is deployed on Fly v60,
retaining shared CPU 1 / 2048 MiB and the original volume/dependencies. Activity
timestamp work, direct snapshot JSON validation and irrelevant-directory cache
invalidation are improved; 2743 tests and 175 deployed hashes pass. Complete
Home/Trading protocol responses and the first paper cycle are verified, while
cold/native/resource targets remain open and performance CPU stays deferred.
See the [shared-CPU session](../../../../../docs/sessions/2026-10-25-dashboard-shared-cpu-performance.md).
The implementation and measurements below describe the earlier v59 slice.

The operator requested continued work after the v58 rollout. The remaining
target is complete cold readiness, within the approved read-side budgets and
exact financial/safety semantics. The [performance plan](../../../plans/dashboard-operator-ui-bounded-data-loading-performance-plan.md)
records implementation, final-input qualification and the authorized rollout.

## Source changes

- Scan JSON arrays with C regex searches for structural / quote / escape tokens
  and whitespace runs. Extend the current object only after the 1 MiB guard.
  Keep 64 KiB read checkpoints, descriptor/path generation validation and the
  JSON decoder's complete syntax/UTF-8 checks.
- Expose a bounded raw reverse-JSONL iterator. Activity validates each row
  directly with the existing Pydantic model's JSON decoder, avoiding a separate
  transient Python JSON dictionary. Missing timestamps and invalid old rows
  outside the display tail still fail coverage.
- Materialize rich activity payloads only after a timeline/table/latest slot
  admits the event. All events still feed exact lifetime and safety reductions.
  Canonical gate lookup and first-token prefix buckets preserve legacy sample
  matching, including non-rejection events and simultaneous gate matches.
- Reuse measured snapshot state charges on replacement and curve compaction.
  Charge the retained charge/account slots as well; the 16 MiB state limit is
  preserved. Snapshot model validation, latest timestamp ties, curve sampling,
  financial totals and the combined 4096-point limit keep their meaning.
- Use the processed record counter for the 256-record cooperative checkpoint,
  rather than reverse source byte ordinals. Block checkpoints remain intact.

No runtime writer, persistent index, dependency, service, trading control,
provider, credential or deployment capacity change is part of this slice.
Changed sources still rebuild the complete compact projection; unchanged
sources still require full manifest verification before expired-cache reuse.

## Evidence so far

The [baseline profile](evidence/performance-20261011/baseline-profile.json)
identifies repeated gate matching / serialization and byte scanning / recursive
size calculations. Its timings include profiler overhead and are not acceptance
measurements.

The full outputs for activity, 13-account snapshots, ledger, proposals and
candidates are structurally identical to main `352fb0f` on the captured incident
dataset at fixed UTC evaluation time, including sampled curves and source
coverage. The [parity record](evidence/performance-20261011/projection-parity.json)
contains output hashes and coverage, excluding financial payloads.

Parser tests cover long UTF-8/escaped runs, exact size limits, invalid escapes and
nested syntax. Activity tests cover lazy retention, timestamp ties and gate
samples, and reject invalid historical records outside the visible tail.
Snapshot state exhaustion and expired-cache no-reread guards remain enforced.
Focused verification: 63 passed. Source mypy: 129 files passed. Full regression:
**2732 passed in 208.76s**. Changed-file Black/Ruff pass; review found no
unresolved source correctness finding.

## Twenty-sample final-input measurements

All cold/cached/revalidated samples complete with verified coverage. Cold means
a new service cache, with warmed imports and ordinary OS file caches; it is not
native full-page readiness. Benchmark inventories match the final runtime files.

| Read-only workload | Cold p95 | Cached p95 | Revalidation p95 |
|--------------------|---------:|-----------:|-----------------:|
| Incident activity, 214686 events | 1.737s | 0.000147s | 0.019392s |
| Incident proposals, 12183 files | 1.998s | 0.000131s | 0.392082s |
| Incident ledger, 13 accounts | 0.065s | 0.000076s | 0.005170s |
| Incident snapshots, 13 accounts | 3.746s | 0.000122s | 0.013318s |
| Incident candidates | 0.0036s | 0.000086s | 0.000756s |
| Representative activity, 1000000 events | 10.546s | 0.000121s | 0.008977s |

Incident process RSS: initial 193.406 MiB, peak 205.062 MiB. Million fixture:
initial 202.359 MiB, peak 204.234 MiB. These are separate local process
observations. They do not measure shared-guest or four-session native memory.

The incident queries meet the query-only 5s cold / 2s cached target. The million
fixture still misses cold 5s. The historical implementation measurement was
21.614s on the same million fixture; this final-input measurement is 10.546s,
with no controlled simultaneous baseline comparison claimed. Changed sources
still rebuild the complete projection, so their large-archive cost remains open.

- [Incident 20-sample record](evidence/performance-20261011/incident-20-samples.json)
- [Million 20-sample record](evidence/performance-20261011/million-20-samples.json)
- [Session / requested rollout](../../../../../docs/sessions/2026-10-12-dashboard-operator-ui-loading-performance.md)

## Acceptance boundaries

**Deployment follow-up:** Fly v59 runs source `22abf3d`; 175 artifact hashes,
health and one paper cycle pass. First Home protocol readiness is incomplete
at 240s while measured shared-CPU balance is depleted and quota throttling rises.
Later warm Home/Trading renders complete in 1.443s/1.251s. The source optimization
does not remove this infrastructure bottleneck. The
[candidate CPU design](../../infrastructure-design/cpu-quota-recovery/infrastructure-design.md)
was prepared for explicit CPU-class / incremental cost approval, then deferred
by operator `보류` (2026-10-12). Current v59 / shared CPU 1 / 2048 MiB are retained;
no additional deployment or compute-cost change was made. The session records
failed as well as successful observations.

Query completion, Streamlit protocol rendering and native visual acceptance
remain distinct. The Browser connection was retried and still fails during
bootstrap because its local runtime service module is missing. No screenshot or
four-native-session acceptance is inferred from protocol/HTTP results. The
retained 2 GiB machine cannot prove the original 1 GiB qualification target.
DEBT-083 stays active unless all approved criteria are evidenced.
