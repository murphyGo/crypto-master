# Session: Bounded Runtime Safety Inputs

- **Unit / debt:** `runtime-safety-score`, related `proposal-runtime` and
  `dashboard-operator-ui`; DEBT-083 remains Critical/active.
- **Requirements / story:** FR-014/015/042, NFR-007, original BDL-NFR-01..08;
  US-020. The original readiness, concurrency and guest targets remain.
- **Authority:** User `진행시켜` on 2026-10-26 KST approves the concrete runtime
  NFR design and explicit safety-read failure-isolation amendment after the
  runtime-first recommendation. Prior same-capacity rollout intent persists.
- **Baseline:** Source main `4b714fd`; production Fly v63 / `f0f3e52`, shared CPU
  1 / 2048 MiB, original machine/volume/dependencies and paper/Codex controls.
- **Checkpoint:** Source implementation, compatibility review, focused/full tests
  and source-quality checks pass. Authorized same-capacity rollout is pending;
  no deployment of this slice is claimed.
- **Integration boundary:** These results qualify the reviewed local tree based
  on `4b714fd`. Concurrent remote commit `dca38fb` contains overlapping runtime
  and dashboard checkpoint work; reconcile that work before integration/rollout.
  This report does not claim the remote dashboard checkpoint is unimplemented.

## Problem and bounded implementation

The production engine's safety-score path still materializes and sorts full
activity history before selecting the recent 24 hours. Both explicit-extra
score sites bypass the `None` cache and feed real pause/entry decisions. Earlier
dashboard containment did not remove this engine allocation path. The v62
four-session observation measured engine RSS 878.660 MiB and guest use
1293.313 MiB, despite dashboard growth of only 21.652 MiB. These observations and
the source trace justify the runtime slice; they do not prove it was the only
allocator or explain every timeout.

`SafetyAccumulator` now consumes a one-shot iterable, retaining exact counters
and distinct live `(cycle_id, gate_reason, account)` tuples. It preserves raw
scalar equality, shared/distinct NaN behavior, GateReason/string equivalence,
advisories, duplicate rows, None-only cycle fallback and falsy account fallback.
The fixed-time cutoff remains inclusive, future events remain eligible and
nonpositive lookback remains unwindowed. Score factors, caps and bands are
unchanged; `recent_activity_events()` still returns a list for compatibility.
The runtime accumulator rejects unsupported keys explicitly. State reservation
precedes retention, with hard limits of 50,000 distinct keys and 16 MiB including
reserved extras; failure cannot publish partial inputs. Exported legacy helpers
use the shared private one-pass reducer without runtime caps, preserving their
existing arbitrary-hashable-key and unhashable-TypeError behavior for dashboard
and direct consumers.

`src/runtime/safety_inputs.py` adds a runtime-owned legacy source and one lazy
daemon worker, one active job and zero queued jobs. It bounds blocks, rows,
source manifests and extras; preserves legacy UTF-8/universal-line and malformed
row behavior; and proves source membership/version/readability before publishing.
Timeout/cancellation quarantines unfinished work without a replacement worker.
The result carries stable failure reasons rather than source payload tracebacks.
The optional negative metadata cache is omitted, so there is no derived disk
state or old-file skip proof to invalidate. Dashboard strict readers and the
chronological `ActivityLog.read_all()` API stay separate.

Both engine score sites await this service with a fixed request-time UTC instant.
This approved timing change may conservatively retain a 24h-edge penalty that
the former completion-time cutoff expired. Per-read limits are 30s/2 GiB;
per-cycle totals are 60s/4 GiB, including failed work. `None` cache reuse remains
distinct from explicit extras, including `[]`. Typed input failure stops the
account's remaining proposals and records the existing account error, while
allowing one normal monitor/snapshot pass. That can execute an existing
protective stop previously skipped by the broad exception guard. It does not
invent a rejected proposal, fill, new entry or duplicate notification. Actual
task cancellation still propagates. Application teardown closes the shared
reader without waiting for blocked kernel IO.

## Source verification

| Evidence | Result and limit |
|---|---|
| Reducer regressions | One-shot lifetime, exact scalar/NaN/enum semantics, list compatibility, runtime byte/key caps, poison-state behavior and set-resize accounting pass. Final legacy tests also preserve 50,001 distinct keys and arbitrary hashable identities through both exported helpers. |
| Independent old-code oracle | Frozen `4b714fd` source; [184 fixed-time/random cases](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/parity_result.json), including a 2,396-row adversarial corpus, match exact inputs, score, factors and bands. [Twelve legacy source compatibility cases](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/source_compat_result.json) also pass. |
| Independent final targeted suite | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_runtime_safety_inputs.py tests/test_runtime_safety_streaming.py tests/test_runtime_safety_integration.py -p no:cacheprovider --basetemp=/private/tmp/crypto-master-safety-quant-20261026/pytest-final-independent`: **143 passed in 2.49s** after the compatibility correction. |
| Archived incident-scale source | Read-only v62 snapshot captured 2026-10-25T10:50:02Z: seven April–October files, **229,677 rows / 95,961,644 bytes**. Before/after hashes unchanged. Frozen-time old/new outputs exactly equal: score **70 / degraded**, 57 correlation warnings and other counters zero. One local run: old **2.785s**, streaming **1.663s**; state **4,136 bytes**, manifest **26,672 bytes**. This is not the earlier 214,686-row incident inventory or current production. |
| Million-event reducer | **1,000,000 fresh events**, exact old-oracle inputs, **10.407s**, state **4,455 bytes**, one distinct kill key and at most one sampled live event. |
| Million-event source/service | Final-source rerun: **1,000,000 rows / 431,750,000 bytes**, exact inputs, **7.451s**, state **4,495 bytes**, manifest **4,448 bytes**; event-loop heartbeat continues. Process high-water RSS **157,040,640 bytes (149.77 MiB)** is a whole local process observation, not reader RSS growth or a Fly guest result. |
| Integration / lifecycle | Both score sites, paper/live/configured-disabled policy, later-account isolation, actual cancellation, cycle budget resets, shutdown and the real protective-stop regression pass. Source/service suite covers mutation/readability/timeout/quarantine/closure and process-owned lifecycle. |
| Final full regression | `uv run pytest -q`: **3,008 passed in 61.62s**, including the final helper compatibility correction; **143 tests added** against the 2,865-test baseline. |
| Final source quality | Changed-file `uv run black --check` and `uv run ruff check`: **nine files pass**. `uv run mypy src`: **132 source files pass**. |

Durable evidence includes the [frozen source manifest](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/oracle_manifest.json),
[archived-source replay](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/incident_archive_result.json),
[million-event reducer](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/reducer_million_result.json)
and [million-event source](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/source_million_result.json).
The [final independent review](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/independent_review_result.json)
records exact reviewed hashes, resolved findings and no remaining source defect.
The local harness and frozen source are in
`/private/tmp/crypto-master-safety-quant-20261026/`. Harness invocation is
`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /private/tmp/crypto-master-safety-quant-20261026/quant_harness.py MODE`,
with `MODE` equal to the corresponding result prefix without `_result.json`.
Single local timings are not percentile, cold-browser or depleted-CPU acceptance.

Final scope review found and corrected the propagation of runtime caps and
unsupported-key failures through exported legacy helpers. Strict bounds remain
at the runtime service accumulator. The [compatibility replay](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/legacy_compat_result.json)
preserves 50,001 distinct keys, tuple/bytes/Decimal/custom hashable identities and
six unhashable-TypeError cases through the legacy helpers; the strict runtime
state limit still rejects its over-budget input. The 184-case frozen oracle was
rerun successfully after this correction.

## Production baseline before this rollout

[Predeployment evidence](../../aidlc-docs/construction/runtime-safety-score/code/streaming-qualification-20261026/predeploy.json)
checks all **177 runtime hashes**, public/internal HTTP200, original volume,
shared CPU 1 / 2048 MiB and paper/Codex controls against v63 / `f0f3e52`.
A later natural v63 cycle, **2026-10-25T17:30:50.363557Z–17:31:13.647862Z**,
records proposals 1 / accepted 1 / rejected 1 / opened 0 and no deployment-window
activity errors. This extends the initial DEBT-087/088/089 rollout's zero-proposal
observation; it is baseline evidence before the runtime streaming deployment.

## Why further prerequisites became visible

Earlier work verified specific dashboard boundaries and observable page metrics.
As production qualification expanded to concurrent sessions and a whole engine
cycle, the shared engine's separate full-history allocator became visible.
Tracing that actual runtime path also exposed the broad exception guard that
skipped protective monitoring on a read failure. The response is to verify the
real source-to-decision and source-to-monitor paths first, preserving failed
observations and checking the selected boundary end to end. It is not evidence
for an unbounded new rewrite or for automatically expanding trading policy.

## Remaining acceptance and operations

All source gates pass in the reviewed local tree. Proceed with the already
authorized same-capacity exact-dependency rollout after source integration.
Deployment follow-up must record exact
hashes, health, a complete engine cycle, observed error/coverage limits and the
actual capacity conditions. Until then production remains v63 / `f0f3e52`.
Dashboard checkpoint integration/qualification is separate from this local
runtime slice. Original cold
5s/warm 2s, 20-sample readiness, four-session/full-cycle, native browser,
depleted-CPU and <=768 MiB on the declared 1 GiB guest requirements remain open.
Local reader bounds do not close them. The deferred CPU/cost proposal remains
deferred, and no canonical runtime history, funding ledger or account policy is
changed by this work.

See the [implementation plan](../../aidlc-docs/construction/plans/runtime-safety-score-streaming-activity-code-generation-plan.md)
and [cross-check](../cross-checks/2026-10-26-runtime-safety-streaming.md).
