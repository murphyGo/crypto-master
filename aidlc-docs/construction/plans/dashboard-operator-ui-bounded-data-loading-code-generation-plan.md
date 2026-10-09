# Code Generation Plan: Bounded Dashboard Data Loading

- **Unit:** `dashboard-operator-ui`; command-center, persistence and operations participation
- **Stage:** Code Generation complete; source Build and Test passed; NFR qualification partial
- **Debt:** DEBT-083, active
- **Requirements:** FR-029/031/032/036/042, NFR-003/007/008/011/012, BDL-NFR-01..08
- **Stories:** US-012/014/020/023; legacy Phase 7, 8.2, 10.4, 19.3
- **Authorization:** The latest operator `진행시켜` approves the presented NFR Design and transition to implementation. This plan executes that approved scope, including ordinary verification. Deployment and production acceptance remain separate.

## Ordered implementation and verification

1. [x] Add bounded source readers in `src/utils/bounded_read.py`; source-generation capture, bounded JSONL/object/array parsing and explicit failures. Test chunk boundaries, UTF-8, damaged input, replacement and oversize guards in `tests/test_bounded_read.py`.
2. [x] Add result contracts and the single-worker process service in `src/dashboard/read_models.py` and `src/dashboard/data_service.py`. Enforce cache, state, manifest, queue, deadline and cardinality budgets; test coalescing, stale/unavailable results and cleanup.
3. [x] Add compact activity/history projections in `src/dashboard/projections.py` and source discovery in `src/dashboard/sources.py`. Verify parity with existing cycle, safety, funnel, trade and snapshot builders.
4. [x] Connect Home, Trading, Engine, Ops and Funnel defaults through bounded results in `src/dashboard/pages/`. Preserve operator controls and independent usable sections; forbid full-history failure fallback. Test incomplete states and page seams.
5. [x] Run targeted and appropriate broader regression tests, formatting, lint and types. Profile isolated representative archives; distinguish query evidence from Streamlit, guest and engine acceptance. Functional checks pass; measured cold targets do not pass, and native resource/engine acceptance remains pending.
6. [x] Write implementation notes under `aidlc-docs/construction/dashboard-operator-ui/code/bounded-data-loading/`, a session and cross-check. Update state/debt narrowly, retaining unverified production and resource targets.

## Verification commands

```sh
uv run pytest tests/test_bounded_read.py tests/test_dashboard_data_service.py tests/test_dashboard_projections.py
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_ops.py tests/test_dashboard_proposals.py
uv run black --check <changed Python files>
uv run ruff check <changed Python files>
uv run mypy src
git diff --check
```

## Completion

- [x] Source and meaningful tests complete
- [x] Actual validation and partial qualification evidence recorded
- [x] Session, cross-check, state and debt updated
- [x] Runtime data and unrelated concurrent changes preserved

## Outstanding acceptance work

- [ ] Reduce cold/bootstrap and changed-source cost without relaxing budgets or exact semantics; qualify the exact final source with 20 samples.
- [ ] Qualify complete native Home/Trading cold and warm readiness, four sessions for at least 10 minutes, guest memory/health and one full engine cycle on an authorized deployment.
- [ ] Resolve DEBT-083 only after the approved performance and production criteria pass. Source implementation alone does not close this task's NFR acceptance.
