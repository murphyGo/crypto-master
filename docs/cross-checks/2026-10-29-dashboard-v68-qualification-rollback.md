# Cross-check: v68 qualification and rollback

Unit: `dashboard-operator-ui`; related `dashboard-operator-command-center` and
`notifications-ops`. Date: 2026-10-29 KST. No application source change.

**Overall: FAIL acceptance / PASS exact-image rollback verification.**
DEBT-083 remains Critical/active. Current runtime is Fly v69 / source `120b440`,
the exact v67 image restored after persistent v68 activity unavailability.

| Requirement / gate | Evidence | Verdict |
|---|---|---|
| FR-029/031/032, BDL-NFR-03 page readiness | v68: 4/120 complete records, 3 timeouts, 113 incomplete; fresh connections independently confirm activity-unavailable after stable input | FAIL |
| BDL-NFR-04 minimum duration / natural cycle | 610.445559 s, four sessions, 35.832690 s full natural cycle with 12 monitor passes and no cycle errors | Duration/cycle PASS; overall gate FAIL due to pages |
| BDL-NFR-04 health | 121/121 <5 s, max 2.037698 s | PASS in this sample |
| BDL-NFR-02 memory | 676.625 MiB guest peak, 0 MiB observed RSS growth, 8.441406 MiB HWM bound on 2048 MiB | Current sample within ceilings; original 1024 MiB NOT QUALIFIED |
| BDL-NFR-03 cold/warm/native | Single warmup Home 7.321074 s; only 2 successful main views/page; no native viewport | FAIL / NOT QUALIFIED |
| BDL-NFR-06/08 bounded source recovery | Source contract tests historically pass; operational retry exhaustion remains latched across stable input and fresh sessions | Operational suitability FAIL; rollback criterion met |
| NFR-007/008 data meaning and integrity | Same 182 deployed source hashes before/after observation; stable-source probe only reads; no canonical data repair/migration/delete | Preserved operational scope; no new table-cell parity claim |
| NFR-011/012, FR-036 | Same paper/Codex settings, env, volume, capacity and services; no credentials recorded; no live activation | PASS |
| Exact rollback | v69/source120b440, all182 hashes and dependencies/config match; public/internal health; 25.280011 s startup cycle,12 monitor passes,zero errors | PASS mitigation verification |
| Post-rollback page availability | Home11.426338 s / Trading1.030893 s complete; Home incomplete shell8.782085 s | Availability observed; Home latency FAIL |
| Observer contracts |48 offline tests pass; separate artifact reconciliation; queued post-timeout responses limit reused-socket attribution | PASS local tests; attribution limitation remains |
| CPU evidence |41 original-window points plus brackets; balance456.830–500 CPU-seconds; zero new sampled throttle counter increase | Sampled metrics corroborated; depleted NOT QUALIFIED |

The fresh-session corroboration is separate from the original sample and does not
rewrite it. The post-rollback pair also includes a process restart and cannot alone
separate restart from policy effects. Prior v64–v67 failures and v68's user-stopped
sample remain recorded. CPU-cost changes remain deferred.

Current Git HEAD still includes v68 recovery source. Deployment is intentionally
pinned to source120b440; redeploying the v68 policy is blocked by this failed
qualification until redesigned. No new source/test/lint changes were made.

See [session](../sessions/2026-10-29-dashboard-v68-qualification-rollback.md),
[plan](../../aidlc-docs/construction/plans/dashboard-source-recovery-plan.md),
and [audit](../../aidlc-docs/construction/dashboard-operator-ui/code/source-recovery-resume-20261029/operations/audit.json).
