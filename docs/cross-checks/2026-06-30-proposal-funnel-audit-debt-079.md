# Cross-Check: proposal-funnel-audit DEBT-079

## Scope

Verify DEBT-079: valid candidates dropped by per-symbol dedup leave structured
evidence without changing runtime proposal selection.

## Result

PASS.

## Evidence

- `ActivityEventType.PROPOSAL_CANDIDATE_DESELECTED` is a stable event string.
- `ProposalEngine._record_deselected_candidates` emits one event for each
  candidate whose proposal id is not the per-symbol winner.
- Payload includes losing/winning proposal ids, technique names, composite
  scores, score delta, symbol, signal, sub-account, and reason.
- `propose_bitcoin` and `propose_altcoins` both call the helper after
  `_dedup_by_symbol`.
- Single-candidate paths emit no deselection event.

## Verification

- Targeted pytest: 2 passed.
- Touched-file ruff: passed.
- `uv run mypy src`: passed.

## Residual Risk

Dashboard rollups do not yet count this event type. The raw activity event is
now available for operator inspection and future UI aggregation.
