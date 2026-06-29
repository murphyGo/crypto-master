# Session: proposal-funnel-audit DEBT-074 vcp gap

## Unit

- Primary: `proposal-funnel-audit`
- Secondary: `strategy-framework`, `proposal-runtime`
- Debt: DEBT-074
- Follow-up filed: DEBT-079
- Requirements: FR-011, FR-012, FR-014, FR-036, NFR-007, NFR-012

## Summary

Resolved the `vcp_breakout` emitted-but-zero-open anomaly as a pre-funnel
candidate-selection/history gap, not a downstream gate rejection. Added
read-only audit tooling that compares fail-closed emissions, persisted proposal
records, and opened/linked funnel states for one strategy and optional
sub-account.

The important code-path finding: `proposals_emitted` is counted when a strategy
candidate reaches `analyze()`, while `ProposalHistory.save` happens only after
the per-symbol winner returned by `_dedup_by_symbol` enters runtime
`_handle_proposal`. Deselected candidates have no `ProposalRecord` today.

## Files Changed

- `src/tools/audit_strategy_funnel_gap.py`
- `tests/test_tools_audit_strategy_funnel_gap.py`
- `docs/TECH-DEBT.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/units/debt-unit-map.md`
- `aidlc-docs/construction/plans/proposal-funnel-audit-code-generation-debt-074-vcp-gap-plan.md`

## Verification

- `uv run pytest tests/test_tools_audit_strategy_funnel_gap.py -q`
- `uv run ruff check src/tools/audit_strategy_funnel_gap.py tests/test_tools_audit_strategy_funnel_gap.py`
- `uv run mypy src`

## Decisions

- Kept the tool read-only and raw-JSON tolerant so it can be pointed at
  operator snapshots without mutating runtime data.
- Classified emitted/no-fail-closed/no-proposal/no-open as
  `pre_funnel_candidate_selection_or_history_gap`, because it happens before
  the persisted proposal funnel has a row to classify.
- Filed DEBT-079 instead of changing runtime persistence in this unit. Adding
  candidate-level records/events changes funnel semantics and deserves its own
  bounded implementation.

## Risks

- The audit can identify the terminating class but cannot name the exact winning
  peer candidate from historical data, because losing candidates were not
  persisted before this unit. DEBT-079 covers that missing evidence.
