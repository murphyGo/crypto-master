# Cross-check: Dashboard Cold Readiness and Concurrency

**Unit / debt:** `dashboard-operator-ui` / DEBT-083, Critical/active.
**Scope:** FR-029/031/032/036/042; NFR-003/007/008/011/012; BDL-NFR-01..08;
US-012/014/020/023. Same-capacity approved bounded read-side continuation.

| Contract / evidence | Result |
|---|---|
| Canonical activity validation and reduction | Public compiled validator inherits canonical fields/validators and exact enum vocabulary. Every record still validates. All 42 enum values/adversarial JSON tests pass; additional 24 shuffled full-builder cases preserve complete payload/provenance across scopes, file/timestamp ties, minimum UTC, boundary/future events and cross-file cycle/companion/gate cases. |
| Snapshot values and resource admission | All rows validate, selected latest rows alone serialize, first default timestamp remains stable. Byte-selected and normalized publication state are both budgeted; Unicode/Decimal/fixed-shape accounting and expanded-state failures are tested. Curves/extrema/latest/financial output match baseline. |
| Source verification | Native directory metadata capture and directory-relative file stats preserve selected membership and packed file proof. Hidden `.json` file/directory, archive/deeper exclusion, symlinks, source-change and FD closure tests pass. No directory-mtime-only shortcut. |
| Threshold reuse | Trading's exact lifetime scalar borrows only a fresh compatible proposal projection. Original evaluation/coverage age remains; root/source/time/scope/version mismatches and failed revalidation cannot be hidden. Both encoded payloads are charged; oversized optional derivatives are skipped. |
| Foreground requests | Normalize each query once; global deadline includes it. Terminal read failures return verified siblings without an idle extra wait. Pending/rebuild/queue-full behavior keeps retry semantics. |
| Bounds and trading boundary | One worker, four admitted jobs, root/identity/group/state/cache/result and freshness limits remain. No canonical write, exchange/credential/live/provider change. New persistence is a proposed functional contract only. |
| Final tests / review | 171 targeted and **2811 full tests** pass. Six-file Black/Ruff and 129-file mypy pass. No unresolved source correctness finding in this slice. |
| Paired local query evidence | Twenty pairs/workload, exact final file hashes, CPU/wall/warm/revalidation data and all samples retained. Million cold p95 **10.317→7.872s** still fails 5s; snapshots **3.750→2.149s**; proposals **1.482→1.397s**; threshold reuse **1.623s→0.221ms**. Warmed-process empty-service timings are not process-cold/native readiness. |
| Deployment | Fly **v61**, source **`7f185bc`**, exact v60 dependencies plus four dashboard files. All 175 runtime hashes, health and first paper cycle pass. Shared CPU 1 / 2048 MiB, original machine/volume and paper/Codex/Claude controls remain. Source committed/pushed; root unrelated hashes preserved. |
| Five-second navigation stress | Four real server sessions fail a 5s public-health guard after **210.332s**; 39/40 health and 149/153 views complete, four in-flight views incomplete at stop. Successful-only p95 is not a passing series. RSS growth 19.454 MiB / conservative HWM bound 22.582 MiB, guest peak 641.781 MiB on 2 GiB. No process restart. Whole-cycle observation not reached before stop. |
| Twenty-second navigation | **FAIL** after 1171.054s despite a whole 26.686s paper cycle. Health 229/230, Home/Trading each 114/116 complete; final health timeout 5.136s stops the load. Warm successful-only p95 0.583s/0.911s does not qualify the failed series. Dashboard growth 8.496 MiB, guest peak 646.059 MiB on 2 GiB. |
| Native/original guest acceptance | Supported Browser bootstrap fails on a missing local runtime service even on retry. Native viewport/four-browser verification remains blocked. Current 2 GiB data cannot certify original 1 GiB guest acceptance. |
| Capacity / next design | Performance CPU/cost proposal remains deferred. Verified whole-file restart checkpoint Functional Design is reviewable and awaiting explicit approval before NFR/infrastructure and implementation; no checkpoint persistence activated. |

The original acceptance is not closed. Evidence, source review, deployment and
scenario limits are recorded in the [session](../sessions/2026-10-25-dashboard-cold-readiness.md),
[plan](../../aidlc-docs/construction/plans/dashboard-operator-ui-cold-readiness-completion-plan.md),
and [raw evidence](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/cold-readiness-20261025/README.md).
