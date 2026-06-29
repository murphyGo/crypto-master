# Cross-Check: proposal-funnel-audit DEBT-074

## Scope

Verify DEBT-074: determine why `vcp_breakout` can show many emissions but zero
persisted proposals and zero opens, then file the concrete follow-up.

## Result

PASS.

## Evidence

- `src.tools.audit_strategy_funnel_gap.audit_strategy_funnel_gap` reads
  `data/performance/<sub>/<technique>/fail_closed.json` and
  `data/proposals/<sub>/*.json` without mutation.
- The vcp-shaped pattern is explicitly classified as
  `pre_funnel_candidate_selection_or_history_gap` when emissions are positive,
  fail-closed is zero, proposal records are zero, and opened/linked records are
  zero.
- Code inspection confirms only the selected per-symbol candidate reaches
  `_handle_proposal` and `ProposalHistory.save`; candidate losers are counted
  by emission metrics but have no funnel row.
- DEBT-079 was filed for candidate-level deselection observability.

## Verification

- Targeted pytest: 3 passed.
- Touched-file ruff: passed.
- `uv run mypy src`: passed.

## Residual Risk

Historical snapshots cannot identify the exact winning peer for a deselected
candidate because that candidate-selection evidence was not persisted. DEBT-079
is the implementation follow-up.
