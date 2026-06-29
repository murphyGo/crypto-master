# Session: proposal-funnel-audit DEBT-079 candidate deselection

## Unit

- Primary: `proposal-funnel-audit`
- Secondary: `proposal-runtime`
- Debt: DEBT-079
- Requirements: FR-011, FR-012, FR-014, FR-036, NFR-007, NFR-012

## Summary

Resolved candidate-level proposal deselection visibility. When
multi-technique proposal generation builds multiple valid candidates for the
same symbol, the lower-ranked candidates now emit
`proposal_candidate_deselected` before per-symbol dedup drops them.

This keeps the existing risk contract intact: only one selected proposal per
symbol enters the runtime gate chain and persisted `ProposalHistory`. Deselected
candidates are not counted as runtime gate rejections.

## Files Changed

- `src/runtime/activity_events.py`
- `src/proposal/engine.py`
- `tests/test_proposal_engine.py`
- `docs/TECH-DEBT.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/construction/plans/proposal-funnel-audit-code-generation-debt-079-candidate-deselection-plan.md`

## Verification

- `uv run pytest tests/test_proposal_engine.py::test_propose_altcoins_emits_candidate_deselection_events tests/test_proposal_engine.py::test_propose_bitcoin_single_candidate_emits_no_deselection -q`
- `uv run ruff check src/runtime/activity_events.py src/proposal/engine.py tests/test_proposal_engine.py`
- `uv run mypy src`

## Decisions

- Used an activity event instead of a `ProposalRecord` terminal because
  deselected candidates never enter the runtime gate chain.
- Included both losing and winning proposal ids/techniques/composites so
  operators can explain why a strategy emitted but did not reach proposal
  history.
- Kept emission gated by the existing optional `ProposalEngine.activity_log`;
  no activity log means no crash and no behavior change.

## Risks

- Dashboard aggregation for the new event is not added in this unit. The raw
  event is available in activity history and can be surfaced by a future
  dashboard refinement if needed.
