# v65 offline diagnosis: source verification and page recovery

Source: `382c26b1290c4b1a7cc843f28686fc9e2e4f2323`, imported from the isolated Home recovery worktree. No application/source changes, production load or production-data mutations were performed. Controlled fixtures existed only in a temporary directory. This is a DEBT-083 follow-up candidate, not a new deployment or acceptance claim.

## Evidence and causal bounds

- `protocol-audit/frozen/raw/v65-page-observations.jsonl:61–64`: four requests (two Home, two Trading) started at 05:01:43.862770–05:01:45.356289 UTC on 2026-10-26 and timed out after 30.044–30.261s. First incomplete shells appeared after 4.307–4.794s. Each retained at most one watcher, with multiple rerun signals. The bounded shell/watcher-count behavior worked; complete-page readiness failed for these requests.
- `protocol-audit/supplements/diagnostics/v65-diagnostics-framed.jsonl:66,73,76,77`: emitted `source_changed` / `projection` records for activity, snapshots, proposals and activity respectively, with Fly delivery times 05:01:45.502706749, 05:01:49.330098936, 05:01:50.252235531 and 05:02:06.806411296 UTC. These prove at least four failed projection verifications during the observation interval. They do not identify the failed file, verification branch, query scope/window or client request.
- Diagnostic delivery is asynchronous (`src/dashboard/read_diagnostics.py:97–108`), rate-limited and bounded. Fly timestamps are delivery timestamps; absence of an event is not absence of a failure. No request/job identifier is retained. Do not assign each diagnostic to a particular timed-out page or infer CPU contention or the writer responsible.
- The next four requests completed in 1.317–3.262s (`protocol-audit/frozen/raw/v65-page-observations.jsonl:65–68`). This sample shows recovery, not indefinite live starvation. Multiple reruns in the failing requests also rule out describing them as a single uninterrupted wait for global drain. The historical v64 failures remain causally unresolved.

## Exact source paths

1. **Freshness-driven repeated admission.** `src/dashboard/data_service.py:206–224` revisits even a previously complete sibling when its verification age exceeds `fresh_seconds`. `_request_normalized` accepts a cached complete result only within that bound (`:87–91`) and otherwise admits/coalesces work. The approved contract is a maximum 2s complete-result cache age, with at most 30s explicitly stale fallback (`aidlc-docs/construction/dashboard-operator-ui/nfr-design/bounded-data-loading/nfr-design-patterns.md:29–33`). Therefore renewed admission is currently required behavior, not by itself a correctness bug.
2. **Global-drain watcher coupling.** `src/dashboard/availability.py:100–104` reruns only when the process service has zero admitted jobs. It does not ask whether this page's dependency completed or its rejected admission now has capacity. An unrelated long-running query can therefore delay an otherwise useful page rerender.
3. **Correct rejection of changing generations.** Forward/reverse readers reject generation mismatches (`src/utils/bounded_read.py:53–71,180–223`). Discovery/final manifest checks verify file metadata and directory membership (`src/dashboard/sources.py:154–182`). Projections verify again before publication (`src/dashboard/projections.py:1288–1305`); checkpoint keys also require the captured generation (`src/dashboard/checkpoint_store.py:511–515`). Changed source digests skip whole-query reuse (`projections.py:1147–1158`), and changed segment keys cannot reuse a prior generation. Repeated valid writes during each verification interval can prevent completion, correctly, without malformed data.
4. **Retry policy.** Failures become bounded error metadata (`data_service.py:356–371`), reused for the existing 2s interval (`:105–107`). A later caller may admit another attempt after expiry; terminal UI results do not themselves start a watcher (`availability.py:83–95`). Explicit refresh only removes the captured failure generation. Other pending page work can cause rerenders, so this is neither an unconditional automatic retry nor a guarantee that a terminal result will recover without operator action.

## Deterministic offline reproduction

Run from the isolated worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /private/tmp/crypto-master-home-recovery-delivery/v65-offline-liveness-repro.py
```

[Harness](v65-offline-liveness-repro.py) and [results with source SHA-256 values](v65-offline-liveness-result.json). All three probes passed. Events and a controlled clock determine the first two cases; real-time waits are only bounded failure guards, not scheduling assumptions.

| Probe | Controlled result | Interpretation |
|---|---|---|
| Completed sibling with a blocked second query | Activity verified at fake time 1000; at 1003 it was admitted again behind snapshots. At the 4s deadline the result was activity=`stale`, snapshots=`pending`; original activity verification epoch stayed 1000. Final builder calls: activity 2, snapshots 1; one worker. | Reproduces repeated admission inside one bounded batch. Pinning the first activity result as `complete` at time 1004.01 would falsely pass the 2s freshness rule, even if its old timestamp were retained. |
| Page ready while unrelated job remains active | Activity was complete/fresh. An unrelated audit query blocked. Twenty watcher polls produced zero reruns; finishing audit caused one rerun. | Reproduces global-drain coupling independently of source failure, cache expiry or CPU assumptions. It does not establish the sole cause of the four live timeouts. |
| Valid append during generation verification | Three attempts each read a synthetic activity fixture, then received one valid appended row at a reader checkpoint. Each failed `source_changed`; the fourth quiet attempt verified all 532 bytes. | Demonstrates correct fail-closed source verification and a possible liveness constraint under continuing writes. No production source was modified. |

## Smallest safe follow-up candidate

Design a **page-dependent progress notification** for the existing single watcher. Retain bounded, private handles for only that page's unfinished job generations; rerun when a relevant job completes or a previously queue-full request has admission capacity. Polling must inspect progress only: it must not build, bypass verification, clear terminal failures or create replacement workers. Preserve one watcher per session, one read worker, four admissions, the 4s foreground bound, cache budgets, original ages and explicit stale/unavailable states. Keep terminal failures on explicit manual retry. Register/review this bounded design before source implementation.

Do not simply keep a completed sibling marked complete until the 4s deadline: at age>2s it must be stale, or it must receive genuine source verification/window re-evaluation. A retained per-page result alone cannot satisfy complete-page readiness. Do not weaken generation verification, trust append-only prefixes without a proven contract, increase CPU/capacity or add indefinite `source_changed` retries on the strength of this sample.

Acceptance tests for the candidate:

1. With this page's dependency finished and an unrelated event-controlled job still blocked, the page watcher signals progress once; no global drain is required.
2. A fifth queue-full dependency becomes admissible while unrelated work remains; one watcher resumes that page without exceeding four admissions or one worker. Four sessions still coalesce identical work.
3. Repeated polls with no relevant progress do not rerun/admit work. Terminal validation/source errors do not auto-loop; explicit retry retains generation guards.
4. Retain the controlled 2s/4s expiry regression: no expired sibling returns falsely complete or receives a fabricated verification timestamp. Any proposed retention remains explicitly stale unless genuinely reverified.
5. Continuous mutation remains explicitly incomplete; a quiet later explicit request recovers with full-payload parity. Exercise append, replace, truncate and membership changes, with/without checkpoints.
6. Preserve source/static/full-suite checks and rerun the existing bounded same-capacity operational protocol after approval. Keep these four failed live samples in the denominator. Diagnostic improvements may separate allowlisted verification phases, but must keep bounded cardinality/privacy and must not retroactively identify old failures.
