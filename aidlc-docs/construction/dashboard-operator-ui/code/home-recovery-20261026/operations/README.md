# v65 operational evidence — 2026-10-26

Source `382c26b1290c4b1a7cc843f28686fc9e2e4f2323` is deployed as Fly v65.
The bounded recovery correction is delivered; full DEBT-083 readiness **fails**.
This is a continuation of existing dashboard debt, not a new strategy defect.

| Check | Result |
|---|---|
| Exact deployment | 182 source hashes match; same image/instance at 04:55, 05:07 and 07:04 UTC. Existing shared CPU 1 / 2048 MiB, volume, dependencies, paper/Codex and 1800 s cadence retained. |
| Four sessions | 04:56:43.681997–05:06:50.782715 UTC (607.100718 s), 120 starts/outcomes, 116 complete and four 30 s timeouts. No censored/missing outcomes. |
| Complete readiness | Home 58/60; Trading 58/60. Successful-only p95 1.852/1.396 s; all-outcome p95 2.370/2.055 s. FAIL_SAMPLE regardless of successful-only p95. |
| Initial observation | Home completes in 11.415 s; first incomplete receipt 5.072 s. Both miss 5 s. One warmup is not a qualified cold p95. |
| Natural cycle and health | Full 30.243466 s cycle, 12 monitor passes, zero errors; 120/120 health checks pass, maximum 4.001187 s. |
| Memory | Observed guest peak 701.949 MiB; dashboard growth 65.648 MiB. These are on current 2048 MiB, not original 1024 MiB qualification. |
| Original acceptance | Cold/native/depleted/original-guest qualification remains open. No cost/capacity change. |

`protocol-audit/` contains the independent freeze, raw request ledger, classified
outcomes, health/memory samples, replay scripts and separately hashed diagnostic,
AppTest and CPU supplements. Replay the initial audit with
`python3 protocol-audit/audit_v65.py --audit-frozen`; later supplements retain
separate verdicts and do not rewrite the failed original capture. Its initial
CPU-unqualified field is superseded only by the separate CPU coverage audit,
not by rewriting original evidence.

`postdeploy.json` is a later 04:55 UTC check after the approximately 02:29 UTC
rollout. `post-observation.json` verifies the observed cycle and exact source at
05:07 UTC. `closeout-current.json` rechecks current identity/health at 07:04 UTC
after the CPU tool approval wait; four later natural cycles and 48 monitor
passes have no recorded errors. Those later cycles are outside the performance
window and cannot turn its failed requests into a pass. CPU capture is also
later; only metrics covering the original window inform its CPU assessment.

`offline-diagnosis.md` and `v65-offline-liveness-*` retain three controlled
probes. Global-drain watcher coupling is reproduced, but is not established as
the sole cause of the four live timeouts. Freshness-driven readmission enforces
the approved 2 s rule, and rejection of changing source generations preserves
correctness. Seven asynchronous `source_changed` deliveries overlap the failed
requests without request/job identities or exact verification-branch attribution.
The next bounded candidate is page-dependent progress notification, subject to
source/design qualification; no speculative runtime patch is included here.

The need for further work comes from a gap between deterministic functional
checks and complete production readiness under changing sources and four active
sessions. Local fixes and a healthy trading engine do not prove that every page
completes within its deadline. Retaining failed runs, exact freshness constraints
and diagnostics prevents a successful deployment from being mistaken for full
acceptance, and keeps subsequent fixes tied to reproduced behavior.

`delivery-manifest.json` covers the initial rollout/AppTest files. The final
`artifact-manifest.json` covers every retained operation artifact except itself.
Temporary diagnostic collectors initially assumed JSONL, while Fly emitted
multiline JSON; those zero-event captures are not evidence of zero failures.
The corrected framed collector is partial/best effort and stops deliberately
after the observation. No credentials or raw non-diagnostic Fly logs are retained.
