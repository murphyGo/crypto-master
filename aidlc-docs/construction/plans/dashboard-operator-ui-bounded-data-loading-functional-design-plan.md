# Functional Design Plan: Bounded Dashboard Data Loading

- **Date:** 2026-10-09
- **Primary unit:** `dashboard-operator-ui`
- **Secondary units:** `dashboard-operator-command-center`, `persistence-data-integrity`, `notifications-ops`
- **Stage:** Functional Design approved; NFR Requirements/Design authorized
- **Task:** Prevent accumulated runtime history from exhausting the dashboard's shared VM while preserving operator-visible state and metric meaning.
- **Related debt:** DEBT-083 (Critical, active)
- **Requirements:** FR-029, FR-031, FR-032, FR-036, FR-042; NFR-003, NFR-007, NFR-008, NFR-011, NFR-012
- **Stories:** US-012, US-014, US-020, US-023
- **Legacy context:** Phase 7 dashboard; Phase 8.2 engine visibility; Phase 10.4 log retention; Phase 19.3 account selection
- **Authorization:** Documentation-first request followed by `진행시켜`, approving the presented functional design/BDL-NFR targets and advancement through NFR Requirements/Design; recorded at 2026-10-09T22:37:27+09:00 in `aidlc-docs/audit.md`.

## Development Target

The first implementation owner is the dashboard's data-loading boundary.
Shared JSONL primitives may be extended under `persistence-data-integrity`;
Home semantics belong to `dashboard-operator-command-center`; deployment and
temporary resource changes belong to `notifications-ops`.

The existing units remain brownfield-complete. This is a new bounded task,
not a reopening of all historical dashboard work. The simultaneous DEBT-082
Claude/Node repair retains its own scope, state, and acceptance evidence.

## Functional Design Steps

- [x] Record the diagnostic snapshot and distinguish observations from the inferred triggering code path in `../dashboard-operator-ui/functional-design/bounded-data-loading/incident-evidence.md`.
- [x] Inventory Home, Trading, Engine, Ops, and Proposal Funnel activity readers, plus Home's proposal-only funnel summary. A source recheck corrected the earlier claim of a second Home activity read; `load_funnel_summary()` reads proposal history only.
- [x] Define separate latest-state, recent-window, and historical-aggregate queries in `business-logic-model.md`.
- [x] Define completeness, stale-cache, failure, reconciliation, account, and metric rules in `business-rules.md`.
- [x] Define read results and bounded cache ownership in `domain-entities.md`.
- [x] Define page behavior and partial-data presentation in `frontend-components.md`.
- [x] Propose measurable NFR targets and the implementation/verification sequence below; these are targets, not achieved results.
- [x] Obtain explicit approval of this concrete functional design and presented acceptance targets (`진행시켜`).
- [x] Formalize NFR Requirements from the approved targets; advance through the expressly authorized NFR stages without asking again for the same targets.
- [ ] Approve the newly specified NFR Design budgets, timestamp/rebuild algorithms, and process-wide cache/concurrency behavior before Code Generation.
- [x] Assess Infrastructure Design: N/A for the selected source-only NFR candidate; a later resource/recovery/topology change requires a separate concrete infrastructure/operations scope.
- [ ] Create the Code Generation plan and implement the approved bounded slices.
- [ ] Complete targeted tests, resource/latency qualification, cross-check, and authorized operational verification before resolving DEBT-083.

## Decisions for Review

| Question | [Answer] |
|----------|----------|
| Which work is authorized now? | Functional design and presented targets approved; NFR Requirements/Design preparation authorized by `진행시켜`. Newly specified NFR Design and operational rollout have their own review boundaries. |
| What history may be removed? | None. Preserve runtime files, existing retention behavior, paper/live isolation, and historical metric meaning. |
| Which recent window applies? | Retain Home's existing 24-hour safety/incident window. Preserve each other page's existing selected window; never silently convert a lifetime metric to a recent one. |
| How should incomplete reads appear? | Approved: an explicit unavailable/partial/stale state with affected metric coverage; never infer SAFE, zero failures, or no open positions from a failed or incomplete read. |
| What load should qualification cover? | Approved: four concurrent read-only sessions alternating Home and Trading, with single-session checks on every affected activity page. |
| What recovery is in scope? | Document a candidate recovery separately. Restart, memory resizing, and rollout need a concrete operational action and operator authorization; no recovery has been performed by this task. |

## Operator-Approved NFR Acceptance Targets

These task-local targets refine the existing FR/NFR references. The operator
approved the presented design and targets with `진행시켜`; they remain
unmeasured acceptance requirements, not achieved guarantees or new canonical
FR/NFR entries. Measurement definitions are formalized in
`../dashboard-operator-ui/nfr-requirements/bounded-data-loading/nfr-requirements.md`.

| ID | Target | Verification |
|----|--------|--------------|
| BDL-NFR-01 | No affected dashboard render materializes every retained activity event or calls legacy `read_all()` through a hidden nested loader. | Reader integration tests and call-path audit, including Home funnel. |
| BDL-NFR-02 | Peak dashboard RSS increase is at most 256 MiB over its warmed idle baseline; shared engine + dashboard + OS use stays at most 768 MiB on a 1024 MiB qualification VM. | Process RSS and VM memory sampled during one/four-session runs; report both baselines and peaks. |
| BDL-NFR-03 | Complete default-page data readiness p95 <=5 seconds for a cold read and <=2 seconds for a warm read; an unavailable/partial shell appears within 5 seconds if a budget prevents completeness. | At least 20 independent cold and 20 warm samples per Home/Trading scenario on the declared target environment. A fast error shell does not count as complete data readiness. |
| BDL-NFR-04 | Under four concurrent sessions for 10 minutes, health responses stay below the configured 5-second timeout, memory stays within BDL-NFR-02, and engine cycles continue without dashboard-attributable errors. | End-to-end read-only load qualification with engine activity, health, RSS, and latency evidence. |
| BDL-NFR-05 | Resource use does not grow linearly with all retained event payloads at the 214,686-record incident scale or a synthetic >=1,000,000-record scale. | Isolated fixture generation and peak-memory profiling; never generate fixtures in production `data/`. |
| BDL-NFR-06 | Cache entries, retained payload bytes, simultaneously rebuilding queries, and reader work are bounded across the whole dashboard process. | NFR Design specifies numeric byte/entry/work/deadline limits; tests exercise exhaustion and scope churn. |
| BDL-NFR-07 | Complete results preserve existing UTC ordering, safety scoring/deduplication, latest reconciliation selection, paper/live/account scope, aggregate equity, and cumulative counts. | Parity tests against the existing pure builders on complete fixtures. |
| BDL-NFR-08 | Partial writes, malformed rows, file replacement, month rollover, and budget exhaustion produce explicit coverage diagnostics without converting uncertainty to healthy/empty state. | Adversarial reader and AppTest cases. |

Cold means a new cache entry/process scenario, not a warmed entry relabeled
cold. Report shared-CPU model, Python/Streamlit versions, dataset shape, engine
baseline, and actual measured results. The observed VM had about 962 MiB of
usable guest memory despite its configured 1024 MiB allocation.

## Planned Implementation Slices

1. **Bounded activity loading:** introduce query/result boundaries and migrate
   all five affected pages plus Home's funnel path; preserve legacy full-history
   APIs for existing non-UI consumers. Latest reconciliation and latest cycle
   retrieval must remain independent of the recent incident window.
2. **Other dashboard history reads:** bound proposal enumeration and repeated
   snapshot/trade parsing, preserve lifetime aggregates, and qualify all paths
   needed for Home/Trading readiness. Review Feedback audit/drilldown growth as
   part of the call-path inventory. A full-history list retained in a cache is
   not a bounded implementation.
3. **Qualification and operations:** validate the exact candidate's page
   readiness, resource use, health and engine continuity; prepare rollout,
   recovery, and rollback evidence separately from code/test success.

NFR Design must explain how complete latest-state and aggregate queries work
after a restart when no cache exists. If an index/read projection is chosen,
its additive schema, bounded bootstrap, atomic updates, invalidation, and
fallback require review; a sidecar is not authorized by this draft.

## Likely Files and Verification

- `src/dashboard/pages/{home,trading,engine,ops,proposals}.py` and dashboard query adapters
- `src/runtime/activity_log.py`, `src/runtime/jsonl_rotator.py` if additive bounded primitives are selected
- `src/proposal/interaction.py`, `src/trading/portfolio.py`, `src/strategy/trade_history.py` only where query parity or bounded loading requires it
- `tests/test_jsonl_rotator.py`, `tests/test_runtime_activity_log.py`, targeted dashboard/proposal/portfolio/history tests

Documentation validation:

```bash
git diff --check
rg -n 'DEBT-083|bounded-data-loading|BDL-NFR-' aidlc-docs docs/TECH-DEBT.md docs/sessions docs/cross-checks
```

Expected implementation checks, not run by this documentation stage:

```bash
uv run pytest tests/test_jsonl_rotator.py tests/test_runtime_activity_log.py tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_ops.py tests/test_dashboard_proposals.py tests/test_proposal_interaction.py tests/test_portfolio.py -q
uv run pytest
uv run black --check src tests scripts
uv run ruff check src tests scripts
uv run mypy src
```

## Documentation Completion

- [x] Draft artifacts and reproducible sanitized metrics excerpt saved.
- [x] DEBT-083 and debt-unit mapping added without replacing DEBT-082 work.
- [x] AI-DLC task state, session log, and documentation-stage cross-check created.
- [x] Functional Design approved; NFR Requirements/Design preparation authorized.
- [ ] Implementation and production acceptance completed; DEBT-083 remains active.
