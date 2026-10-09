# Bounded Dashboard Loading: Implementation and Qualification

**Date:** 2026-10-10 (KST)

**Unit/debt:** `dashboard-operator-ui` / DEBT-083
**Status:** Source containment implemented; functional verification passed;
performance/production acceptance remains incomplete. DEBT-083 stays active.

**Deployment follow-up:** The operator subsequently requested deployment.
Fly v58 now runs `785374b`, including requested-root projection retention for
verified reuse after the stale display deadline. Source/process/health/engine
checks and complete Home/Trading protocol responses are verified in the
[deployment session](../../../../../docs/sessions/2026-10-10-dashboard-operator-ui-bounded-data-loading-deployment.md).
The source-only/no-deployment statements below describe this report's earlier
checkpoint; complete NFR acceptance remains pending.

## Implemented behavior

Default Home, Trading, Engine, Ops and Funnel activity reads use one locked
process service instead of `ActivityLog.read_all()`. Home's proposal-only
summary and Trading's proposal/ledger/snapshot/curve reads use the same service.
Feedback's default catalog/promotion and candidate audit paths are bounded too.
Existing pure builders and explicit injected legacy fixture adapters remain
available; there is no production failure fallback to full-history loading.

- JSONL and JSON objects/arrays use 64 KiB blocks and a 1 MiB record guard.
  Reverse JSONL traversal reduces retained timeline churn; byte offsets preserve
  original file/line tie order. Open descriptor and pathname generations are
  checked, and malformed/partial/missing-time records cannot certify health.
- Cycle counters use fixed slots, compact companion identities and a second
  bounded rejection pass only when needed. Lifetime metrics use sorted ids and
  at most 50 rich cycle summaries. Safety validates one descriptor at a time.
  A missing cycle start sorts last instead of the legacy mixed naive/aware
  sentinel raising an exception.
- Filesystem manifests use packed relative paths and generation metadata under
  4 MiB. Immutable result payloads are capped at 2 MiB, and the complete LRU
  cache is capped at 16 MiB / 64 entries including key/metadata charges.
- Only one builder owns the 16 MiB working-state budget. At most four distinct
  requests are admitted including active work; identical requests coalesce.
  Two root contexts, 128 account identities, 256 strategies and 50,000 retained
  identity keys are bounded. One active source handle and at most two discovery
  iterators stay below the eight-handle design cap.
- All sections on a page share a four-second foreground deadline. Pending
  work continues on the same worker and triggers a later page refresh. A slow
  kernel read occupies that worker; timeout does not create replacement threads.
- Complete results expire after two seconds. Before reusing an expired compact
  result, the worker verifies the full captured file-generation/membership
  digest and re-evaluates exact time windows. Changed sources rebuild the
  projection; no append cursor is trusted. Stale fallback expires after 30s and
  cannot display a fresh safety/healthy/empty state. Batch results that aged in
  the queue are revalidated too.
- Trade/snapshot JSON arrays stream one object at a time. Trade totals and
  threshold counts retain current definitions. Latest snapshots are reused for
  cards and charts. Curves have a 4096-point **combined** account budget, retain
  first/latest and bucket extrema, and label sampling. Sampled curves do not
  compute financial totals.

The verified unchanged archive is reused as one compact projection. This
implementation rebuilds that projection when any participating source changes;
it does not yet reuse each unchanged monthly segment independently. This and
bootstrap latency remain performance follow-up under DEBT-083.

No trading writers, retention, runtime data, exchange calls, live activation,
credentials, AI provider selection, deployed image or Fly allocation were
changed by this slice. The concurrent operations record reports recovery
capacity and a later release; that is separate evidence, not this code's
production acceptance.

## Verification

Default-route AppTest tests prohibit legacy materializers across all six pages.
A corrupted activity source leaves Trading's independently verified open trade
and equity visible without a healthy banner. Other tests cover block boundaries,
UTF-8/escaping, malformed/partial/oversized inputs, mutable replacement,
membership change, cycle/rejection/safety/window parity, catalog/audit bounds,
coalescing, blocked work, queue/cache/root limits, stale expiry and batch age.

Final regression, formatting/lint/types and documentation checks are recorded
in the linked [session](../../../../../docs/sessions/2026-10-10-dashboard-operator-ui-bounded-data-loading.md)
and [cross-check](../../../../../docs/cross-checks/2026-10-10-dashboard-operator-ui-bounded-data-loading.md).

## Offline qualification evidence

Each series has 20 fresh-service and 20 immediate cached samples, plus 20
forced-epoch-expiry generation revalidations. Imports are warmed; the filesystem
cache is not deliberately dropped. This measures query completion, **not**
browser/page readiness or process-cold startup. Long cold queries are polled
until complete; a four-second pending shell is not counted as complete.

Python 3.13.0 / Streamlit 1.57.0 on macOS; source SHA-256 inventories are in the
JSON evidence. These are not substitutes for the deployed Python/Streamlit
versions or shared-guest measurements. RSS peak is process all-time maximum;
subtracting the measured idle RSS is a conservative local comparison and can
include earlier import/generation peaks. Four decoded session copies are not
qualified by these single-service series.

The measured source revisions precede the final publication-time incident
expiry and reversed-clock guards in `src/dashboard/projections.py`. Those
guards have separate regression coverage; the 20-sample timing series was not
repeated after that change. The evidence retains its actual measured hashes,
and final verification records the source difference. These timings therefore
do not certify the exact final source revision or close the failed latency target.

| Dataset/query | Complete cold p95 | Cached p95 | Generation revalidation p95 | Process peak RSS |
|---------------|------------------:|-----------:|---------------------------:|-----------------:|
| Incident activity, 214,686 events / 90,064,921 bytes | 5.150s | 0.136ms | 20.386ms | 198.047 MiB |
| Incident eligible proposals, 12,183 files / 15,119,764 bytes | 1.784s | 0.105ms | 450.444ms | 208.016 MiB |
| Incident default ledger | 2.929ms | 0.042ms | 1.211ms | 208.016 MiB |
| Incident default snapshots | 65.297ms | 0.075ms | 4.763ms | 208.016 MiB |
| Incident Home candidates | 0.778ms | 0.069ms | 0.573ms | 208.016 MiB |
| Synthetic activity, 1,000,000 events / 640,453,970 bytes | 21.614s | 0.138ms | 18.814ms | 203.344 MiB |

All samples completed. Incident run idle RSS was 194.359 MiB (peak difference
13.656 MiB); million-event run idle was 128.859 MiB (difference 74.484 MiB).
The million fixture spans ten files, 10,000 cycles, four accounts, varied
event types, timestamps, payload sizes, proposal identities and safety signals.
It was generated under `/private/tmp`, never in runtime `data/`.

- [Incident query samples and source hashes](evidence/incident-local-query-qualification.json)
- [Million-event query samples and source hashes](evidence/million-local-query-qualification.json)
- Reproduction: `uv run python scripts/qualify_dashboard_loading.py --root <read-only snapshot> --output <temporary JSON> --samples 20`.

## Acceptance matrix and remaining work

| Requirement | Verdict at this checkpoint |
|-------------|----------------------------|
| BDL-NFR-01 bounded default routes | Functional PASS, including Home's separate proposal path. |
| BDL-NFR-02 RSS / shared VM | Local single-service growth comparison passes 256 MiB; four-session RSS and <=768 MiB guest use remain unqualified. |
| BDL-NFR-03 complete cold/warm readiness | **Not passed.** Incident activity cold p95 exceeds 5s and million bootstrap is 21.614s. Whole Home/Trading 20-sample page readiness is also outstanding; cached query timings are not page timings. |
| BDL-NFR-04 engine continuity | Outstanding four native sessions for >=10min, bounded health responses and an evidenced full engine cycle. Tests do not replace production cycle evidence. |
| BDL-NFR-05 growth fixtures | Both required activity workloads complete locally within the reader/service limits. |
| BDL-NFR-06 budgets/concurrency | Targeted contract tests and source guards pass; full resource/descriptor stress acceptance remains to qualify. |
| BDL-NFR-07 semantics | Deterministic builder parity and default-route tests pass. |
| BDL-NFR-08 damaged/changing input | Tested failures expose unavailable/stale/pending rather than healthy/zero fallback. Shared-VM interruption acceptance remains outstanding. |

Next: reduce cold bootstrap and changed-source rebuild cost without relaxing
the approved resource/semantic limits, then qualify complete native page
readiness, four-session decoded memory, guest use and engine continuity on an
authorized deployment. This checkpoint is not a deployment/closure approval.
