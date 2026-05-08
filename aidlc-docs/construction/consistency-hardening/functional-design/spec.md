# Functional Design: consistency-hardening

## Purpose

`consistency-hardening` owns cross-cutting refactor and code-consistency work
that is too broad for a single existing functional unit but too concrete to
leave as unstructured review notes. It exists to preserve operational
correctness while the brownfield system expands across sub-accounts, live
trading, generated strategies, dashboard command-center workflows, and
backtest-driven promotion gates.

The unit does not replace the underlying owner units. Each implementation slice
must still name its primary functional owner and targeted tests.

## Source Findings

The unit starts from the 2026-05-08 five-subagent review after commit
`1a01866 Harden live safety contracts`. Findings already fixed in that commit
are out of scope unless a regression reappears:

- named testnet credentials satisfying live mode,
- partial/zero/non-filled live market orders being persisted,
- missing `ENGINE_MAX_TICKER_AGE_SECONDS` settings wiring,
- `symbols: []` not being treated as universal strategy metadata.

## Scope

### Live and Exchange Safety

- Align exchange instance mode with credential selection for legacy
  Binance/Bybit configs.
- Preserve actual live fill price, quantity, and fee information in
  trade history.
- Complete account-scoped exchange routing for proposal validation,
  SL/TP monitoring, and portfolio snapshots.
- Track persisted open-position hydration after restart.

### Runtime and Notification Consistency

- Isolate runtime cycle failures by sub-account so one account cannot block
  scan, monitor, or snapshot work for later accounts.
- Surface backend-specific notification failures as activity events that feed
  runtime safety scoring.
- Recompute or otherwise update runtime safety hard-pause inputs after
  same-proposal notification/correlation incidents.
- Normalize proposal lifecycle timestamps and avoid sub-account-ambiguous
  proposal history updates.

### Generated Strategy and Feedback Contracts

- Keep `.py` candidate promotion from injecting markdown frontmatter.
- Use atomic writes for generated strategy and operator artifact files.
- Ensure markdown prompt outputs cannot bypass Output Contract checks with
  `technique_type: code`.
- Keep prompt Output Contract validation aligned with runtime parser fields.

### Backtest and Promotion Validity

- Distinguish warmup/data insufficiency from structural strategy contract
  errors in `StrategyValidationError` handling.
- Route multi-timeframe strategies correctly through the backtest harness.
- Represent skipped robustness gates as conditional operator evidence rather
  than indistinguishable pass/fail state.
- Reduce serializer/report drift across backtest engine, baseline scripts, and
  combination reports.

### Dashboard and Quality Governance

- Make command-center sub-account discovery include configured-only accounts.
- Compute aggregate equity from latest snapshot per sub-account rather than a
  single latest snapshot.
- Apply command-center scope consistently to incidents, safety factors, and
  candidate evidence.
- Align active queue references away from legacy `docs/development-plan.md`
  where team routing still drifts.

## Non-Goals

- Do not batch all findings into one large implementation PR.
- Do not use this unit to bypass the owning unit's tests or requirements.
- Do not migrate or delete runtime `data/`.
- Do not change live trading defaults without explicit safety tests and
  operator-facing documentation.

## Prioritized Backlog

| Priority | Slice | Primary Owner Units | Suggested Tests |
|----------|-------|---------------------|-----------------|
| P1 | Legacy exchange config mode/credential alignment | `exchange-integration`, `trading-core` | `tests/test_main_dispatch.py`, `tests/test_exchange_*` |
| P1 | `.py` strategy promotion integrity | `ai-feedback-loop`, `strategy-framework` | `tests/test_feedback_loop.py`, `tests/test_strategy_loader.py` |
| P1 | Sub-account runtime failure isolation | `proposal-runtime`, `sub-account-capital-segmentation` | `tests/test_runtime_engine.py` |
| P1 | Notification backend failure visibility | `notifications-ops`, `runtime-safety-score` | `tests/test_proposal_notification.py`, `tests/test_runtime_engine.py` |
| P1 | Dashboard aggregate/scope consistency | `dashboard-operator-command-center` | `tests/test_dashboard_app.py`, `tests/test_dashboard_trading.py` |
| P2 | Backtest validation and harness contract | `backtesting-validation`, `strategy-framework` | `tests/test_backtest_engine.py`, `tests/test_backtest_harness.py` |
| P2 | Proposal timestamp and history scoping | `proposal-runtime`, `persistence-data-integrity` | `tests/test_proposal_interaction.py`, `tests/test_runtime_engine.py` |
| P3 | Shared dashboard read models and query parsing | `dashboard-operator-ui`, `quality-governance` | `tests/test_dashboard_*` |

## Acceptance Criteria

- Each slice has a focused implementation summary and cross-check evidence.
- Each slice adds or updates regression tests for the exact consistency issue.
- Cross-unit behavior changes cite both this unit and the primary owner unit.
- Deferred findings are linked to `docs/TECH-DEBT.md` rather than left as
  free-text TODOs.
