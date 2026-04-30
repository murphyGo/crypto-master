# Phase 15 Cross-Check: Diagnostic Clarity

> **Backfill notice.** This cross-check was written 2026-05-01 per
> Phase 23.1's AIDLC hygiene backfill. Phase 15 sealed in the
> change-history table on 2026-04-28 (`15.1 | 2026-04-28 | Phase
> 15.1 complete - Diagnostic Clarity (NFR-001) ...`) and the
> Current Status table flipped to ✅ Complete at the same time, but
> no cross-check file was written then. Reconstructed from the
> single sub-task spec at `docs/development-plan.md` Phase 15 (lines
> 1376–1434), the session log at
> `docs/sessions/2026-04-28-phase-15.1-diagnostic-clarity.md`, and
> the change-history row at line 3199 of `docs/development-plan.md`.

**Date**: 2026-04-28 (sealed); 2026-05-01 (cross-check backfilled)
**Phase**: 15 - Diagnostic Clarity
**Status**: All one sub-task complete (15.1 ✅)

## Scope

Phase 15 closed the diagnostic gap that produced the 2026-04-28
misdiagnosis cycle: while monitoring the Phase 12 redeploy on Fly,
the `crypto_master.trading.strategy` logger emitted lines like
`Created position: short BTC/USDT @ 76750.0` that read as "a trade
was opened" — but the line was actually emitted from
`TradingStrategy.create_position` during proposal sizing
(`src/trading/strategy.py:473`), called from
`ProposalEngine._propose_for_symbol`, **before** the threshold
gate runs. The actual trade-open log
(`Opened paper position: ...`) lives in `PaperTrader.open_position`
at `src/trading/paper.py:546` and never fired because every
proposal was rejected at `auto_approve_threshold = 1.0` while
composite scores topped out around 0.35. Net result: an hour of
mistaken "trades are happening" reads on logs that turned into
"why does the dashboard show 0?" — both assumptions wrong. Phase
15 ships the two safe, mechanical changes that make this
misdiagnosis impossible to reproduce: a verb rename on the
proposal-sizing log and a dashboard rejection-reason summary so
operators see *why* the trade table is empty.

The phase added **no new functional or non-functional
requirements**; the development plan's Requirements Mapping
table records Phase 15 against existing requirements:

- **NFR-001** — Operability / observability. The phase is purely
  diagnostic surface: same trading-engine semantics, same
  proposal-sizing math, only the verbiage of one log line and one
  new dashboard metric card change.

Phase 15 is bounded to a single sub-task (15.1). No new framework
abstractions, no new architectural directions. No ADR.

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 15.1 | Diagnostic Clarity (Log + Dashboard) (NFR-001) | `src/trading/strategy.py:474` (verb rename `Created position: ...` → `Sized position candidate: ...`); `src/dashboard/pages/trading.py` (`TradingSummaryMetrics` TypedDict gains `proposals_rejected_threshold_count: int`; `build_summary_metrics` accepts `proposal_history: ProposalHistory \| None = None` defaulting to `ProposalHistory()`; new private `_count_threshold_rejections(history)` counts `decision == "rejected"` records whose `rejection_reason` matches `^composite \d+\.\d+ below threshold \d+\.\d+$`; cap-rejected pattern `"symbol "` excluded explicitly; `try/except` returns 0 on malformed proposals dir; layout `st.columns([3, 1])` next to "Active Positions"; `render(...)` accepts `proposal_history=` for test injection) | `tests/test_dashboard_trading.py` (+2 net new — `test_summary_metrics_counts_threshold_rejections` seeds 4 records (accepted / threshold-rejected / cap-rejected / no-reason) and asserts only the threshold-rejected one surfaces; `test_summary_metrics_handles_empty_proposal_history` pins backward-compat for absent proposals dir; existing `test_summary_metrics_empty_inputs` extended with `tmp_path` fixture; AppTest smoke tests updated to inject `ProposalHistory(data_dir=...)`) — total 1160 → 1162 |

## Compliance Matrix

### Functional Requirements

(None — Phase 15 introduces no FR coverage. Behaviour-preserving
diagnostic surface only.)

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-001 | Operability / Observability | ✅ Complete (extended) | The `Sized position candidate: ...` verb rename eliminates the misread vector that produced the 2026-04-28 misdiagnosis (proposal sizing emit reading like trade execution). The `proposals_rejected_threshold_count` dashboard card surfaces *why* the trade table is empty — operators seeing 0 active positions immediately see how many proposals were threshold-rejected (and the exclusion of cap-rejected records keeps the metric interpretable, since cap-saturation is a different cause). The cap-rejected exclusion is pinned by `test_summary_metrics_counts_threshold_rejections` (4-record fixture, only the threshold-rejected one surfaces). The `try/except` around `history.list_all()` keeps the dashboard render robust against a malformed proposals dir. |

### Constraints

(None directly addressed — Phase 15 is diagnostic surface only.)

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-005 | Trading Strategy Profile Logging | ✅ Complete (preserved) | `TradingStrategy.create_position`'s log fields (`position.side`, `symbol`, `position.entry_price`, `position.quantity`, `leverage`, `position.stop_loss`, `position.take_profit`) are byte-identical to the pre-15.1 emit; only the verb changes. |
| FR-026 | Trading Proposal Persistence | ✅ Complete (preserved) | `ProposalHistory.list_all()` is the read path; `_count_threshold_rejections` only reads, never mutates. The Phase 12.1 cap-rejection record format (`rejection_reason` starting with `"symbol "`) is preserved; the count helper explicitly excludes them so the threshold-vs-cap distinction stays interpretable. |
| Phase 13.1 TypedDict pattern | (no FR/NFR — internal contract) | ✅ Complete (extended) | `TradingSummaryMetrics` gains one new field (`proposals_rejected_threshold_count: int`); the existing fields are preserved bytewise. Test fixtures that build the dict get one additional assertion. |

## Test Summary

- **Phase 15 tests at phase completion**:
  - 15.1: 2 new tests in `tests/test_dashboard_trading.py`
    (1160 → 1162) — `test_summary_metrics_counts_threshold_
    rejections` (4-record seed fixture, asserts only the
    threshold-rejected one surfaces) and `test_summary_metrics_
    handles_empty_proposal_history` (backward-compat for absent
    proposals dir). Existing `test_summary_metrics_empty_inputs`
    extended with `tmp_path` fixture and the new field
    assertion. AppTest smoke tests updated for the
    `ProposalHistory(data_dir=...)` injection.
- **Full suite at phase completion**: **1162 passing, 0
  failing**.
- **Lint/format**: `ruff check` clean. `mypy src` clean.

## Gates

| Gate | Result |
|---|---|
| pytest | 1162 passed |
| ruff check | clean |
| mypy src | clean |

## Verdict

**PASS.**

## Gaps

**None blocking phase seal.** Phase 15 is a single-sub-task
diagnostic-surface phase; all spec items shipped, tests green,
lint/type clean.

Three soft items worth flagging — none is a gap against the
requirements mapping table, all three are intentional choices
documented in the session log:

1. **Operator action still owed (`ENGINE_AUTO_APPROVE_THRESHOLD=
   0.30`)** — Phase 15.1's diagnostic surface is observation-only;
   the actual trade-execution unblock requires the operator to
   set `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` via Fly secrets so
   composite scores around 0.35 actually clear the gate. Phase
   15.1 deliberately keeps this out of scope (operator concern,
   not a code change). The threshold setting carries forward as a
   standing operator action across Phases 16, 17, 18, 21, 22.

2. **Composite scores topping out around 0.35 is the binding
   constraint, not the diagnostic surface** — Phase 15's metric
   card answers "is the threshold gate the cause" but does not
   reduce *why* composites are low. Production composites in the
   2026-04-28 redeploy data plateau around 0.35; raising them is
   strategy-quality work (Phase 16 chasulang parse fix, Phase 17
   strategy-evolution operator workflow). Phase 15 is purely
   diagnostic.

3. **Cap-rejection counts are not separately surfaced** — the
   Phase 12.1 cap-rejected pattern (`rejection_reason` starting
   with `"symbol "`) is excluded from the threshold count by
   design, but the dashboard does not (yet) carry a parallel
   `proposals_rejected_cap_count` card. If cap saturation
   becomes a recurring failure mode, the parallel metric is the
   obvious extension. Not in scope for Phase 15.

## Risks Carried Forward

1. **`ENGINE_AUTO_APPROVE_THRESHOLD=0.30` Fly secret action still
   owed (15.1)** — without this, the dashboard's
   `proposals_rejected_threshold_count` card will keep climbing
   on every cycle while the trade table stays empty. Operator
   action; pivots from "diagnostic gap" to "execution gap"
   without this setting.
2. **Live verification of Phase 14.1 chasulang 240s override
   still owed** (14.1 carry) — orthogonal to 15.1 but shipped
   together; redeploy verification was deferred at the time
   Phase 15.1 sealed.

## DEBT Closure Summary

- **Phase 15 introduced no TECH-DEBT items**, and resolved none.
  The TECH-DEBT tracker was empty entering Phase 15 (DEBT-012
  resolved by Phase 14.2) and remained empty at Phase 15 seal.

Net DEBT: 0 resolved, 0 added. **Active count remains at 0** at
phase seal.

## Recommendations for Phase 16 (or follow-up)

(Recommendations as recorded retrospectively, matching what
actually unfolded between Phase 15 sealing on 2026-04-28 and
Phase 16 starting the same day.)

1. **Operator: redeploy Fly with `ENGINE_AUTO_APPROVE_THRESHOLD=
   0.30`** — without this, Phase 15.1's metric card surfaces a
   correctly diagnosed but unfixed problem.
2. **Address chasulang's two production-only defects** — the
   2026-04-28 redeploy surfaced `KeyError: 'signal'` on every
   chasulang Claude response (nested `trade.*` shape) and a
   12-hour engine wedge from a chasulang retry timeout that
   didn't actually kill the child. Phase 16.1 picks both up.
3. **Standing operator-run set carried forward unchanged from
   the Phase 14 cross-check** (baseline backtest, manual
   purge-proposals smoke, 3-channel push test, per-TF RSI
   measurement, live-mode smoke checklist). 15.1 doesn't change
   any of these.

## Cross-Check Result

- ✅ Complete: 1 NFR + 3 phase-adjacent preserved
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 15 closed on 2026-04-28. The development plan's Current
Status table shows the Phase 15 row (Diagnostic Clarity) as ✅
Complete. The TECH-DEBT tracker remained empty across the phase
(no items added or resolved). The dashboard's
`proposals_rejected_threshold_count` card and the
`Sized position candidate: ...` log rename are the operator-
visible surface of the phase — both make the 2026-04-28
misdiagnosis structurally impossible to reproduce. Operator
action `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` carries forward as
the standing complementary fix that turns "correctly diagnosed"
back into "trades execute".**
