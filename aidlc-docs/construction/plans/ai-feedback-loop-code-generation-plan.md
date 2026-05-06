# Code Generation Plan: ai-feedback-loop

## Migration Status

Legacy Phase work is migrated as brownfield-complete. This plan is not a queue
of unfinished historical tasks.

## Source Legacy Components

| Component | Phase | Secondary Unit |
|-----------|-------|----------------|
| Claude Integration | 3 | |
| Strategy Improver (Hypothesis-Driven) | 5 | `strategy-framework` |
| Feedback Loop | 5 | `backtesting-validation` |
| LLM Strategy Timeout Handling | 12 | |
| Chasulang Timeout Mitigation | 14 | `strategy-framework` |
| chasulang Parse + Wedge Mitigation | 16 | `strategy-framework` |
| Auto-Research Operator Workflow + Catalog-Aware Improver | 17 | `backtesting-validation` |
| Auto-Research Workflow Unblock | 17 | `backtesting-validation` |
| Code-Type Steering for Deterministic Catalog Picks | 17 | `strategy-framework` |

## Completed Code Generation Steps

- [x] Implement Claude CLI integration, response parsing, and failure handling.
- [x] Implement strategy improver, feedback loop, and audit behavior.
- [x] Add LLM timeout handling and Chasulang-specific mitigation.
- [x] Wire auto-research operator workflow and catalog-aware improvement.
- [x] Preserve deterministic catalog steering for generated code strategies.
- [x] Thread auto-research parameter sensitivity grids into feedback-loop gating.
- [x] Guard improvement generations from dropping existing runtime Output Contracts.
- [x] Pin code-type auto-research fixtures through a trade-producing backtest path.

## Evidence

- Requirements: FR-021, FR-022, FR-023, FR-024, FR-026, FR-027, FR-033, FR-035, NFR-002.
- Primary paths: `src/ai/`, `src/feedback/`, `scripts/auto_research_candidates.py`, `tests/test_ai_*`, `tests/test_feedback_*`.
- Cross-checks: phase 3, phase 5, phase 12, phase 14, phase 16, and phase 17 reports.
- Session logs: related Phase 3, 5, 12, 14, 16, and 17 entries under `docs/sessions/`.

## Future Work

Add future Claude, strategy improver, auto-research, or feedback audit changes
as new unchecked steps here.
