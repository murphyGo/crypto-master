# Cross-check: One Dashboard Loading Watcher per Page

**Unit / debt:** `dashboard-operator-ui` / DEBT-083 Critical/active.
**Scope:** FR-032/036/042, NFR-003/011/012, BDL-NFR-03/04/06/08;
US-012/014/020/023. Existing approved bounded-loading contract; no new persistence.

| Contract / evidence | Result |
|---|---|
| Individual section coverage | All loading/stale/terminal messages remain. Home five, Trading four and Funnel two pending sections each register one watcher in integration tests. Independently verified siblings stay usable. |
| Render ownership / lifetime | Nested render calls share the outer collector; concurrent sessions use independent ContextVar state. Normal, Exception and BaseException/rerun-like exits restore the old context. No private Streamlit context or persistent session flag. |
| Refresh semantics | Existing half-second refresh and standalone behavior remain. Complete/terminal sections do not create a watcher; stale rebuild-pending sections do. |
| Source / financial / resource boundary | No reader/service/source changes; their v61 SHA256s match exactly. Existing model validation, periods, ties, cache/state/admission budgets, original runtime data, exchange/provider/live controls remain. New checkpoint storage is only an approval-pending Functional Design. |
| Exact source checks | 92 focused / **2823 full tests in 216.01s**, six-file Black/Ruff, 129-file mypy pass. Source review has no unresolved correctness finding. |
| Rollout | Fly **v62** / **`d86f76f`**, four-file overlay on exact v61 dependencies; all **175 runtime inputs** match. Same shared CPU 1 / 2048 MiB, original machine/volume/paper/Codex/Claude. First cycle 03:47:14.646139Z–03:47:52.451427Z and later cycles pass. |
| Actual first navigation | Home 12.180s / Trading 1.149s complete with no exception/incomplete alert; Home registers one actual watcher. One pair after restart, with earlier HTTP startup excluded. Home cold target and twenty process-cold observations remain unaccepted. |
| Final server scenario | **FAIL**: 23m36s, recorded 276/280 views complete; four actual 30s timeouts. Health 280/280 pass (max 1.286s), whole cycle 09:52:48.579Z–09:53:33.021Z completes. Actual watchers <=1. Dashboard growth 21.652 MiB passes; guest peak 1293.313 MiB fails 768 MiB. Engine peak RSS 878.660 MiB. |
| CPU/data measurement limits | About **459 CPU-seconds** of initial burst credit, no initial throttle. v61 failures were depleted; elapsed idle time and runtime data differ. Any buffered pass is not a causal A/B or a depleted-CPU qualification. Official metric units and recovered raw host series are recorded. |
| Native / original guest / cost gate | Supported Browser connection unavailable at last retry. Native/four-browser and declared 1 GiB guest acceptance remain open; current guest is 2 GiB. Performance CPU/added cost remains deferred. |

DEBT-083 is not closed. See [session](../sessions/2026-10-25-dashboard-page-poll-coalescing.md),
[plan](../../aidlc-docs/construction/plans/dashboard-operator-ui-page-poll-coalescing-plan.md),
and [evidence](../../aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/evidence/page-poll-20261025/README.md).

Final host series show no throttle and large burst balance (~459→410 CPU-seconds).
This does not qualify depleted CPU or isolate timeout cause. Successful-only
page p95 0.620s/0.829s does not qualify a failed series. Boundary-censored requests
may be omitted by the driver and are never counted as successes. Recovery Home/
Trading 0.597s/0.515s and final 175 source hashes/health/process controls pass.
Whole-history safety input allocation is traced in the engine, with an actual
pause-gate consumer. Its streaming/time contract is a separate approval-pending
Functional Design; no runtime safety code is changed. Native bootstrap still
fails on its local service. All original acceptance gaps remain explicit.
