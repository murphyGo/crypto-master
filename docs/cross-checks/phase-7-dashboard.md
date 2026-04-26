# Phase 7 Cross-Check: UI Dashboard

**Date**: 2026-04-27
**Phase**: 7 - UI Dashboard
**Status**: All sub-tasks complete (7.1, 7.2, 7.3, 7.4); 7.5 Tapbit explicitly deferred

## Scope

Phase 7 delivered the operator-facing Streamlit dashboard for every
data surface the prior phases produce:

- **7.1 Streamlit App Basic Structure** — `src/dashboard/{app,theme}.py`
  with the `st.navigation` chassis, sidebar branding, page-config
  helper, and a Home view with section cards.
- **7.2 Analysis Technique Status Page** — `pages/strategies.py`
  with summary table + per-technique cumulative-P&L trend chart.
- **7.3 Trading Status Page** — `pages/trading.py` with a
  paper/live mode toggle, summary metrics, active positions, recent
  trade history, and equity-curve chart.
- **7.4 Feedback Loop Status Page** — `pages/feedback.py` with
  status summary cards, candidates table, per-candidate detail, and
  audit-log timeline.

The whole dashboard is **read-only**. Mutating operations
(approving a candidate, opening a live trade) stay behind their
existing API surfaces — `FeedbackLoop.approve` (CON-003),
`LiveTrader.open_position` (NFR-012). The dashboard surfaces what
those operations produced; it does not bypass them.

Each page extracts its data-shaping logic into pure helpers
(`build_*_dataframe`, `build_summary_metrics`) so the bulk of the
test surface runs without spinning up Streamlit. End-to-end behavior
is covered by `streamlit.testing.v1.AppTest` smoke tests for both
empty and populated states.

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-028 | Chart Analysis Technique Status | ✅ Complete | `pages/strategies.py::render` lists every registered technique via `load_all_strategies` and renders a summary table (`build_summary_dataframe`) plus a per-technique cumulative-P&L trend chart (`build_trend_dataframe`). Tests: `tests/test_dashboard_strategies.py` (14 tests). |
| FR-029 | Active Trading | ✅ Complete | `pages/trading.py::render` shows `TradeHistoryTracker.get_open_trades(mode)` as a sortable table (`build_open_positions_dataframe`) for the selected paper/live mode. Tests: `test_open_positions_*` in `tests/test_dashboard_trading.py`. |
| FR-030 | Technique Generation Status | ✅ Complete | `pages/feedback.py::render` reads every `CandidateRecord` snapshot via `load_candidate_records`, surfaces status counts (`build_summary_metrics`), the candidate list (`build_candidates_dataframe`), per-candidate detail (`_render_record_detail`), and the audit-log timeline (`build_audit_timeline_dataframe`). Tests: `tests/test_dashboard_feedback.py` (15 tests). |
| FR-031 | Asset and Performance Summary | ✅ Complete | `pages/trading.py::render` shows summary cards (open count, closed count, win rate, realized P&L), the latest equity / unrealized P&L from the most recent snapshot, and an equity-curve line chart from `PortfolioTracker.get_equity_curve`. Tests: `test_summary_metrics_*` and `test_equity_curve_*` in `tests/test_dashboard_trading.py`. |
| FR-032 | Streamlit Web App | ✅ Complete | `src/dashboard/app.py` is the entry point (`streamlit run src/dashboard/app.py`); uses Streamlit's modern `st.navigation` / `st.Page` API for multi-page routing under "Overview" + "Sections" groups. Tests: `tests/test_dashboard_app.py` (8 tests including AppTest smoke). |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-003 | Streamlit UI | ✅ Complete | All four pages built on Streamlit; no other UI framework introduced. `streamlit>=1.30.0` is declared in `pyproject.toml`; the codebase uses 1.36+ APIs (`st.navigation`, `st.Page`) which are the documented forward path. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-002 | Headless engines remain headless | ✅ Complete | The dashboard reads from `PerformanceTracker`, `TradeHistoryTracker`, `PortfolioTracker`, `AuditLog`, and the candidate state directory. None of those modules gained UI dependencies. The dashboard imports them; they don't import it. |
| CON-003 | User approval for technique adoption | ✅ Complete | The Feedback Loop page is read-only — there is no approve / reject button. CON-003 stays enforced inside `FeedbackLoop.approve()`. |

## Phase-Adjacent Requirements Touched

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-005 | Analysis Technique Performance Tracking | ✅ Complete (consumed) | `pages/strategies.py` reads `PerformanceTracker.get_performance` and `load_records`. |
| FR-026 / FR-027 | Feedback loop / technique adoption | ✅ Complete (consumed) | `pages/feedback.py` reads candidate snapshots produced by `FeedbackLoop` and audit events from `AuditLog`. |
| NFR-007 | Trading History Storage | ✅ Complete (consumed) | `pages/trading.py` reads `TradeHistoryTracker.load_trades`. |
| NFR-008 | Asset/PnL History | ✅ Complete (consumed) | `pages/trading.py` reads `PortfolioTracker.load_snapshots` / `get_equity_curve`. |

## Test Summary

- **Phase 7 tests at phase completion**:
  - 7.1: `tests/test_dashboard_app.py` — 8 tests (1 backfill nav-presence + AppTest smoke)
  - 7.2: `tests/test_dashboard_strategies.py` — 14 tests
  - 7.3: `tests/test_dashboard_trading.py` — 18 tests
  - 7.4: `tests/test_dashboard_feedback.py` — 15 tests
  - **Total: 55 tests across the four sub-tasks**.
- **Full suite at phase completion**: **896 passing, 0 failing**.
- **Lint/format**: `ruff check` and `black --check` clean for all
  Phase 7 source and tests.

## Gaps

None. Every FR/NFR/CON mapped to Phase 7 has implementation + tests.

## Risks Carried Forward

Documented in per-task session logs:

1. **No caching anywhere.** Each navigation re-reads strategies,
   trades, snapshots, candidate state, and the audit log from disk.
   Acceptable at current data volumes; revisit with
   `@st.cache_data(ttl=...)` once the dashboard sees real-world
   usage. (7.1–7.4 session logs)

2. **Stale unrealized-P&L numbers.** The Trading page's "latest
   equity" reflects the most recent `AssetSnapshot`, which can lag
   live prices badly between snapshot captures. The card prints the
   snapshot timestamp so operators see the staleness; a future
   iteration could trigger a fresh snapshot on page load or wire a
   refresh button. (7.3 session log)

3. **Strategy load failures are silently logged.** A broken `.md`
   file in `strategies/` doesn't appear in the page at all, which
   could mask configuration drift. The chassis logger captures the
   exception; a "X strategies failed to load" banner would be a
   small future improvement. (7.2 session log)

4. **No mutating UI for the feedback loop.** Approve / reject still
   has to happen through `FeedbackLoop.approve(...)` — by design
   per CON-003. A future iteration could surface a "copy this
   command" affordance without taking on the mutation
   responsibility itself. (7.4 session log)

5. **Audit log re-read for every per-candidate detail render.**
   `AuditLog.filter` walks the entire JSONL file each time; with
   thousands of events the per-candidate filter becomes wasteful.
   If it bites, the audit log can grow either a streaming filter or
   an index. (7.4 session log)

## Cross-Check Result

- ✅ Complete: 8 requirements (5 FR + 1 NFR + 2 CON)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 7 is cleared. The development plan's mainline is now
fully complete; 7.5 Tapbit Integration remains as the explicitly
deferred item.**
