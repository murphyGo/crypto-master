# Cross-check: Retained-Capacity Dashboard Performance

**Unit:** `dashboard-operator-ui`. **Debt:** DEBT-083 remains Critical/active.
**Scope:** FR-029/031/032/036/042; NFR-003/007/008/011/012; BDL-NFR-01..08;
US-012/014/020/023. This continues the approved bounded read-side design on the
existing budget; it does not activate the deferred CPU proposal.

| Contract / evidence | Result |
|---------------------|--------|
| Exact activity reduction | UTC datetimes remain internal until publication; stable first/terminal ties, counters and started/unstarted ordering are preserved, including the minimum timestamp. Focused parity tests pass. |
| Snapshot financial / display state | Direct JSON validation uses the existing model and the same reduction. Numeric legacy values, latest-row ties, complete curves and sampled display limits are tested against dictionary input. |
| Damage / allocation / closure | Raw object bytes remain record/block bounded; invalid old rows invalidate coverage. Compatibility decoder still validates JSON. Both array interfaces release source handles on early close. |
| Cache invalidation | Exact selected members and per-file generations remain in the digest; irrelevant directory metadata can reuse compact results. Relevant additions/removals/replacement and concurrent directory changes are tested. Publication-time directory verification is retained. |
| Existing limits / trading boundary | One worker, admission, foreground deadline, cache/state/result ages and bytes are unchanged. No writer, runtime-data, exchange credential, live-mode or provider change. |
| Paired query / semantic evidence | All 120 complete results across three workloads match full business payload and coverage. Million cold p95 10.467→10.872s (no p95 improvement; 5s target FAIL); snapshot p95 3.781→3.648s; unrelated-directory revalidation 0.773→0.00398s. Offline query times are separate from native full-page/guest acceptance. |
| Production before rollout | v59 / `22abf3d`, shared CPU 1 / 2048 MiB. Source hashes, health, paper/Codex controls and a recent completed cycle verified. One Home/Trading protocol pair completes in 14.702s / 2.504s, without exception or incomplete-data alerts. Uncontrolled cache state, not a percentile comparison. |
| Native viewport / concurrency | Browser runtime service cannot load. Native viewport/four-session and original guest/memory acceptance remain unqualified. |
| Capacity decision | Performance CPU / added-cost proposal remains deferred by `보류`; no capacity change is authorized or performed by this slice. |

Final regression, paired measurements and scoped rollout evidence are recorded in
the [session](../sessions/2026-10-25-dashboard-shared-cpu-performance.md) and
[construction plan](../../aidlc-docs/construction/plans/dashboard-operator-ui-shared-cpu-performance-plan.md).
