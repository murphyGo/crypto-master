# Strategy Framework Code Generation Plan: Swing Strategy Expansion

## Target

- **Unit**: `strategy-framework`
- **Stage**: Code Generation
- **Task**: Add deterministic Momentum Pinball ORB, Turtle Soup Reclaim, and Raschke Holy Grail candidates.
- **Related Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-005, NFR-010
- **Related Stories**: US-001, US-002, US-003
- **Related Legacy Context**: Phase 9 deterministic baselines, Phase 17 code-type strategy generation

## Steps

- [x] Add `strategies/momentum_pinball_orb.py` as an OHLCV-only session-breakout candidate.
- [x] Add `strategies/turtle_soup_reclaim.py` as an OHLCV-only liquidity reclaim candidate.
- [x] Add `strategies/raschke_holy_grail.py` as an OHLCV-only trend pullback candidate.
- [x] Add targeted strategy tests covering representative long/short behavior.
- [x] Run targeted tests for strategy loading and deterministic strategy behavior.
- [x] Record implementation summary and session log.

## Verification Commands

```bash
uv run pytest tests/test_baseline_strategies.py tests/test_strategy_loader.py tests/test_strategy_integration.py -q
uv run ruff check strategies/momentum_pinball_orb.py strategies/turtle_soup_reclaim.py strategies/raschke_holy_grail.py tests/test_baseline_strategies.py
uv run black strategies/momentum_pinball_orb.py strategies/turtle_soup_reclaim.py strategies/raschke_holy_grail.py tests/test_baseline_strategies.py
```

## Completion Checklist

- [x] Strategy metadata is valid and discoverable.
- [x] Tests cover newly added strategy signal paths.
- [x] No runtime data or live-trading behavior is changed.
- [x] Session log records decisions, risks, and verification.
