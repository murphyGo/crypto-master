# Code Generation Plan: market-regime

## Task

Implement the existing `market-regime` functional design: shared bull / bear /
sideways / unknown classification, per-sub-account regime gating, runtime
proposal decisions, activity evidence, and dashboard visibility.

## Related Context

- Unit: `market-regime`
- Stage: Code Generation
- Requirements: FR-045, FR-036, FR-029, FR-031, NFR-003, NFR-007, NFR-008
- Functional design: `aidlc-docs/construction/market-regime/functional-design/spec.md`
- Source evidence: 2026-05-13 Fly snapshot showed repeated
  `counter_trend_long_in_downtrend` rejections and weak RSI/mean-reversion
  outcomes in trend conditions.
- Related units: `proposal-runtime`, `sub-account-capital-segmentation`,
  `dashboard-operator-ui`, `strategy-framework`

## Steps

- [x] Implement deterministic regime classifier and tests.
- [x] Add sub-account policy fields for allowed/blocked regimes and defaults.
- [x] Wire runtime proposal gating with structured rejection/activity records.
- [x] Surface current regime and account gating state in dashboard views.
- [x] Add fixtures/tests for bull, bear, sideways, unknown, and policy override
      behavior.

## Verification

- [x] `uv run pytest tests/test_runtime_engine.py tests/test_trading_sub_account.py -q`
- [x] Targeted dashboard tests for regime visibility.
- [x] Targeted strategy/proposal tests for regime-gated rejection records.

## Completion Checklist

- [x] Code implemented.
- [x] Tests pass.
- [x] Session log and cross-check added.
- [x] `aidlc-docs/aidlc-state.md` updated.
