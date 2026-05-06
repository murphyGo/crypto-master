# Session Log: 2026-05-07 - proposal-replay-simulator - Input Model

## Overview

- **Date**: 2026-05-07
- **Primary Unit**: `proposal-replay-simulator`
- **Stage**: Code Generation
- **Task**: Define replay input model over proposal history and candle windows.

## Work Summary

This cycle starts the Proposal Replay Simulator with a deterministic input
contract. `ProposalReplayInput` builds replay cases from historical
`ProposalRecord` entries plus explicit per-proposal `OHLCV` candle windows.

The model validates that candle windows are sorted, present for every proposal,
and include data at or after the proposal creation time. It can load records
from `ProposalHistory` with an optional decision filter and exposes direct case
lookup by proposal id.

## Files Changed

- Created: `src/proposal/replay.py`
- Created: `tests/test_proposal_replay.py`
- Modified: `src/proposal/__init__.py`
- Modified: `aidlc-docs/construction/plans/proposal-replay-simulator-code-generation-plan.md`
- Modified: `aidlc-docs/construction/proposal-replay-simulator/code/implementation-summary.md`
- Modified: `aidlc-docs/aidlc-state.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Pair records with explicit candle windows | Replay must be deterministic and not fetch live exchange data implicitly. |
| Validate chronological candle order | Later exit simulations depend on first-hit order. |
| Require post-proposal candle coverage | Replay cannot evaluate an alternate decision with only pre-decision candles. |
| Keep threshold logic out of the input model | The next plan step can compare approval thresholds without changing the data contract. |

## Verification

- `uv run pytest tests/test_proposal_replay.py -q`
- `uv run ruff check src/proposal/replay.py src/proposal/__init__.py tests/test_proposal_replay.py`
- `uv run black src/proposal/replay.py`

## Follow-Up

- Compare alternate approval thresholds and exit assumptions.
