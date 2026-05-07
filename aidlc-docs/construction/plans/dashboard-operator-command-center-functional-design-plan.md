# Functional Design Plan: dashboard-operator-command-center

## Unit

- **Unit**: `dashboard-operator-command-center`
- **Stage**: Functional Design
- **Task**: Design an operator-first Streamlit command center for runtime
  safety, sub-account context, exposure risk, and strategy evidence.
- **Related Requirements**: FR-028, FR-029, FR-030, FR-031, FR-032, FR-036,
  FR-039, FR-042, FR-043, FR-044, NFR-003, NFR-007, NFR-008.
- **Related Stories**: US-012, US-017, US-020, US-021, US-022, US-023.
- **Related Legacy Phases**: Phase 7, Phase 8.2, Phase 19.3, Phase 24,
  Phase 25, Phase 26.4.
- **Related Debt**: none active; this plan comes from user-perspective UI
  review, not from an active TECH-DEBT item.

## Review Input

- Operator safety review: Home does not answer whether the bot is safe to keep
  running; Runtime Safety is buried in Engine and lacks action-level severity.
- Strategy maintainer review: Strategies and Feedback do not combine candidate,
  robustness, promotion, replay, and evidence into a promotion-decision view.
- Risk review: Aggregate/sub-account views do not expose cross-account
  exposure, snapshot freshness, route failures, correlation warnings, or
  liquidation events as first-class tables.

## Target Files

- `src/dashboard/app.py`
- `src/dashboard/pages/engine.py`
- `src/dashboard/pages/trading.py`
- `src/dashboard/pages/feedback.py`
- `src/dashboard/pages/strategies.py`
- `src/runtime/safety_score.py`
- `src/runtime/correlation_governor.py`
- `src/proposal/replay.py`
- `tests/test_dashboard_app.py`
- `tests/test_dashboard_engine.py`
- `tests/test_dashboard_trading.py`
- `tests/test_dashboard_feedback.py`
- `tests/test_dashboard_strategies.py`
- `tests/test_runtime_safety_score.py`

## Design Steps

- [x] Define the command-center information architecture and navigation
  contract: first-screen safety status, drilldown targets, and page ordering.
- [x] Define account-context and data-freshness semantics for paper/live,
  default/aggregate/sub-account states, including stale/missing data states.
- [x] Define cross-account exposure and correlation-warning presentation for
  open positions and runtime events.
- [x] Define promotion/evidence drilldown semantics linking strategy,
  candidate, robustness, promotion score, replay, audit, proposal, and trade
  evidence.
- [x] Define dashboard safety-score presentation, including severity bands,
  contributing factors, and recent actionable events.
- [x] Identify the smallest code-generation slice and targeted AppTest/DataFrame
  verification plan.

## Verification Commands

Design stage:

```bash
rg -n "dashboard-operator-command-center|US-023" aidlc-docs
```

Expected code-generation verification after design approval:

```bash
uv run pytest tests/test_dashboard_app.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_dashboard_feedback.py tests/test_dashboard_strategies.py tests/test_runtime_safety_score.py -q
```

## Completion Checklist

- [x] Functional design artifact created under
  `aidlc-docs/construction/dashboard-operator-command-center/functional-design/`.
- [x] Construction plan updated with implementation slice and tests.
- [x] Code-generation stage plan created or this plan advanced to code
  generation after design approval.
- [ ] Session log created when implementation begins.
- [ ] Cross-check created after the command-center slice ships.
