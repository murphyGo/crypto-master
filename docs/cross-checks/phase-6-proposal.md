# Phase 6 Cross-Check: Trading Proposal System

**Date**: 2026-04-26
**Phase**: 6 - Trading Proposal System
**Status**: All sub-tasks complete (6.1, 6.2, 6.3)

## Scope

Phase 6 delivered the user-facing trading-proposal pipeline that sits
between the analysis techniques (Phase 3) + trading strategy (Phase 4)
and a future CLI/dashboard:

- **6.1 Proposal Engine** — `ProposalEngine` ranks techniques by
  composite score (confidence × edge × sample factor), produces
  fully-priced `Proposal` objects (entry / SL / TP / qty / leverage)
  for either a single Bitcoin pair (FR-011) or a multi-symbol altcoin
  scan returning top-K (FR-012).
- **6.2 User Interaction** — `format_proposal` renders a banner;
  `default_decision_prompt` reads accept/reject from stdin;
  `ProposalHistory` persists every decision as a JSON file under
  `data/proposals/`; `ProposalInteraction.present` orchestrates one
  proposal end-to-end. `attach_outcome` is the seam through which
  realized P&L gets linked back to the proposal once a trade closes.
- **6.3 Notification System** — `ConsoleNotifier`, `FileNotifier`
  (JSONL), and `NotificationDispatcher` with a `min_score` quality
  gate (the "good trading opportunities" half of FR-015) and
  per-channel failure isolation.

The whole subsystem is intentionally headless at every layer: the
engine produces data, the interaction layer accepts injected
callbacks, the dispatcher accepts arbitrary `Notifier` protocol
implementations. Everything is reusable from the eventual Streamlit
dashboard without rewrites.

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-011 | Bitcoin Trading Proposal | ✅ Complete | `ProposalEngine.propose_bitcoin` (`src/proposal/engine.py`) selects the best technique by historical edge × sample size and produces a fully-priced `Proposal` via `TradingStrategy.create_position`. Tests: `tests/test_proposal_engine.py::test_propose_bitcoin_*`. |
| FR-012 | Altcoin Trading Proposal | ✅ Complete | `ProposalEngine.propose_altcoins` scans a list of symbols, ranks by composite score, returns the top-K. Per-symbol exchange/strategy errors are logged and skipped so one bad pair doesn't abort the scan. Tests: `tests/test_proposal_engine.py::test_propose_altcoins_*`. |
| FR-013 | User Accept/Reject | ✅ Complete | `ProposalInteraction.present` (`src/proposal/interaction.py`) calls an injectable `decision_callback`, persists the verdict as a `ProposalRecord` (`ACCEPTED` / `REJECTED`), and records the rejection reason if supplied. `default_decision_prompt` provides the CLI default backed by `asyncio.to_thread(input, ...)`. Tests: `tests/test_proposal_interaction.py::test_present_persists_*`, `test_default_decision_prompt_*`. |
| FR-014 | Proposal History Management | ✅ Complete | `ProposalHistory` stores every record as JSON under `data/proposals/{proposal_id}.json` with `save` / `load` / `list_all(decision=...)` / `attach_outcome(...)`. `attach_outcome(proposal_id, trade_id, pnl_percent)` is the FR-014 "actual performance" hook — it links the executed trade and realized P&L back to the proposal. Tests: `tests/test_proposal_interaction.py::test_history_*`. |
| FR-015 | Proposal Notification | ✅ Complete | `NotificationDispatcher.notify_proposal` (`src/proposal/notification.py`) fans out to every registered `Notifier`. `min_score` gates the "good trading opportunities" half of the requirement so users aren't paged for noise. `ConsoleNotifier` and `FileNotifier` (append-only JSONL) provide the two backends called for in the dev plan. Per-notifier failures are isolated. Tests: `tests/test_proposal_notification.py::test_dispatcher_*`, `test_console_notifier_*`, `test_file_notifier_*`. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-007 | Trading History Storage | ✅ Complete (extends to proposals) | `ProposalRecord.trade_id` + `outcome_pnl_percent` + `outcome_recorded_at` carry the link from a proposal to its executed trade in `TradeHistory`, satisfying the proposal-side half of NFR-007. |
| NFR-012 | Live Trading Confirmation | ✅ Complete (Phase 4 already covered) | Phase 6 deliberately does *not* auto-execute accepted proposals; the `LiveTrader` confirmation flow remains the only path to a live order. The interaction layer's accepted record is the trigger; downstream wiring (Phase 7+) supplies the second confirmation. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-002 | Headless Engine | ✅ Complete | `ProposalEngine` returns data, never prints or persists. The user-facing concerns (display, prompt, history, notification) live in separate modules with injectable seams. |

## Phase-Adjacent Requirements Touched

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-005 | Analysis Technique Performance Tracking | ✅ Complete (consumed) | Engine reads `PerformanceTracker.get_performance` to drive composite-score ranking. |
| FR-006 / FR-007 / FR-008 | R/R, leverage, SL/TP | ✅ Complete (delegated) | Position sizing is delegated to `TradingStrategy.create_position`; the engine never reimplements risk math. |

## Test Summary

- **Phase 6-related tests at phase completion**:
  - 6.1: `tests/test_proposal_engine.py` — 19 tests
  - 6.2: `tests/test_proposal_interaction.py` — 22 tests
  - 6.3: `tests/test_proposal_notification.py` — 20 tests
  - **Total: 61 tests across the three sub-tasks**.
- **Full suite at phase completion**: **841 passing, 0 failing**.
- **Lint/format**: `ruff check` clean and `black --check` clean for
  every Phase 6 source and test file.

## Gaps

None. Every FR/NFR/CON mapped to Phase 6 has implementation + tests.

## Risks Carried Forward

Documented in per-task session logs:

1. **Concurrent writers.** `ProposalHistory.save` and
   `FileNotifier.send` are not coordinated. Two processes writing the
   same proposal id (history) or appending simultaneously (notifier)
   could race. Not a concern for the single-process CLI shipping
   today, but worth revisiting before the dashboard runs alongside an
   automated proposal loop. (6.2 / 6.3 session logs)

2. **`data/proposals/` and `data/notifications/proposals.jsonl` growth
   is unbounded.** No retention/rotation policy. Acceptable until the
   dashboard surfaces history; candidate for Phase 7 cleanup.
   (6.2 / 6.3 session logs)

3. **`attach_outcome` exposes the seam but is never called from this
   phase.** Wiring it up to `LiveTrader.close_position` /
   `PaperTrader.close_position` is intentionally deferred — it
   couples otherwise-independent layers and belongs with the CLI
   driver assembly. (6.2 session log)

4. **`min_score` thresholds are caller-supplied with no engine
   default.** A misconfigured threshold can silently mute
   notifications. Should be exposed in the dashboard config when 7.x
   wires the dispatcher. (6.3 session log)

## Cross-Check Result

- ✅ Complete: 8 requirements (5 FR + 2 NFR + 1 CON)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 6 is cleared for Phase 7 (UI Dashboard).**
