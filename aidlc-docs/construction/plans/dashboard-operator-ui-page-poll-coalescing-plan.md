# Dashboard Page Poll Coalescing

- **Unit / stage:** `dashboard-operator-ui` / Code Generation and Build & Test under approved bounded-loading design.
- **Requirements / stories:** FR-032/036/042, NFR-003/011/012, BDL-NFR-03/04/06/08; US-012/014/020/023; DEBT-083 Critical/active.
- **Evidence:** v61 has exact output/175 hashes/first cycle pass, but both four-session 5s and 20s navigation fail a health deadline. Code registers one half-second background watcher per pending section. Five Home sections can create five watchers, four Trading sections four. This redundancy is verified from code; its causal contribution to observed timeouts is not yet measured.
- **Scope / authority:** Continue remaining authorized same-capacity UI improvement. Coalesce loading checks per render while retaining all section states, retry timing and standalone behavior. No new persistence; proposed checkpoint Functional Design approval remains separate/pending. Retain shared CPU 1 / 2048 MiB, volume, dependencies and paper/Codex controls.

1. [x] Record both v61 failed scenarios and post-load recovery; identify the concrete repeated watcher path.
2. [x] Add a render-scoped watcher collector in `availability.py`; apply to Home, bounded Trading and standalone Funnel, including nested render behavior. Do not use private Streamlit context or persistent session flags.
3. [x] Test one watcher for multiple pending sections, separate coverage messages, terminal/complete states, exception cleanup, nested calls and concurrent render isolation.
4. [x] Run focused/full tests, changed-file Black/Ruff and source mypy. Keep prior projection hashes/measurement claims tied to unchanged code.
5. [ ] Roll out exact verified source on original capacity/dependencies, verify runtime hashes/health/paper cycle and record protocol behavior.
6. [ ] Qualify actual final concurrency with all failures retained. Keep native/original guest and cold target unqualified unless actual evidence passes; preserve deferred cost gate.
7. [ ] Update session/cross-check/state/debt and commit/push scoped evidence; preserve unrelated root work.

- **New persistence question:** [Answer]: Pending separate Functional Design review; this change adds no persistence.
- **Capacity question:** [Answer]: Existing shared CPU 1 / 2048 MiB; performance CPU / added cost remains deferred.

## Exact source checkpoint

- 92 focused tests and 2823 full tests pass (216.01s); changed-file Black/Ruff and 129-file source mypy pass.
- Observable checks: five Home/four Trading/two Funnel pending states each retain their messages while registering one watcher. Nested calls, each concurrent session and exception/rerun-like BaseException cleanup are checked. Standalone availability behavior stays compatible.
- Activity/source/data-service hashes match v61. Its query comparisons are unchanged-reader evidence, not a new page-readiness claim.
- Host metrics were recovered by using the CLI JSON token's actual scheme. Earlier HTTP401 records remain historical; burst falls near zero and host throttling rises around the failed observation windows. No credential was printed/persisted or created.
