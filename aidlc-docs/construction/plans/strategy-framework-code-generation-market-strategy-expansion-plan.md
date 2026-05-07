# Strategy Framework Code Generation Plan: Market Strategy Expansion

## Target

- **Unit**: `strategy-framework`
- **Stage**: Code Generation
- **Task**: Add deterministic VCP Breakout, VWAP continuation/reversion, and Weinstein Stage 2 strategy candidates.
- **Related Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-005, NFR-010
- **Related Stories**: US-001, US-002, US-003
- **Related Legacy Context**: Phase 9 deterministic baselines, Phase 17 code-type strategy generation

## Steps

- [x] Add `strategies/vcp_breakout.py` as an OHLCV-only Minervini/VCP-style breakout candidate.
- [x] Add `strategies/session_vwap_pullback.py` and `strategies/vwap_mean_reversion.py` as OHLCV-only VWAP candidates.
- [x] Add `strategies/weinstein_stage2_filter.py` as a deterministic regime/filter candidate.
- [x] Add targeted strategy tests covering long/short or long/neutral behavior and loader discovery.
- [x] Run targeted tests for strategy loading and deterministic strategy behavior.
- [x] Record implementation summary and session log.

## Verification Commands

```bash
uv run pytest tests/test_baseline_strategies.py tests/test_strategy_loader.py -q
```

## Completion Checklist

- [x] Strategy metadata is valid and discoverable.
- [x] Tests cover newly added strategy signal paths.
- [x] No runtime data or live-trading behavior is changed.
- [x] Session log records decisions, risks, and verification.
