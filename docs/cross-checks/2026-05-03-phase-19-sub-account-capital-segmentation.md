# Phase 19 Cross-Check: Sub-Account / Capital Segmentation

- **Date**: 2026-05-03
- **Phase**: Phase 19 — Sub-Account / Capital Segmentation
- **Verdict**: ✅ PASS
- **Cross-check author**: Claude

## Scope

Phase 19 introduced first-class sub-accounts across runtime, paper
trading, live credential routing, dashboard surfaces, and offline
strategy-combination backtests.

## Sub-task Status

| Sub-task | Status | Closure |
|----------|--------|---------|
| 19.1 Sub-Account Foundation | ✅ Complete | `SubAccount`, `RiskOverrides`, registry, default migration, main wiring |
| 19.2 Engine Integration | ✅ Complete | Runtime fan-out, per-sub-account proposals, trades, performance, portfolio paths |
| 19.3 Multi-Paper + YAML + Dashboard | ✅ Complete | `config/sub_accounts.yaml` parsing, isolated paper traders, dashboard selectors, notification attribution |
| 19.4 Multi-Credential Live Mode | ✅ Complete | `EXCHANGE_<REF>_*` credentials, live trader cache, missing-credential startup failure, live lifecycle hooks |
| 19.5 Strategy-Combination Backtest Harness | ✅ Complete | `BacktestHarness`, `MultiAccountReport`, operator script artifacts, latest-run dashboard viewer |

## Compliance Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FR-036 Sub-Account Capital Isolation | ✅ Complete | Entity/registry, runtime fan-out, isolated paper/live traders, partitioned ledgers |
| FR-037 Multi-Credential Live Routing | ✅ Complete | Named exchange credential refs and per-sub-account `LiveTrader` construction |
| FR-038 Strategy-Combination Testing | ✅ Complete | Multi-sub-account harness, report model, correlations, merged ledger, operator artifacts |
| FR-005 Technique Performance Tracking | ✅ Complete | `sub_account_id` flows through performance records and paths |
| FR-009 Live Trading | ✅ Complete | Live sub-accounts fail loud on missing creds and connect/disconnect owned exchanges |
| FR-013 UI Dashboard | ✅ Complete | Trading/engine sub-account surfaces plus strategy-combination latest-run viewer |
| FR-025 Backtesting Execution | ✅ Complete | Existing backtester reused by the multi-account harness with per-account sizing |
| FR-027 Technique Adoption | ✅ Complete | Robustness verdicts are available per sub-account for promotion decisions |
| FR-034 Robustness Validation Gate | ✅ Complete | Harness routes gate evaluation per active sub-account |
| NFR-003 User Interface | ✅ Complete | Dashboard selectors and comparative charts added |
| NFR-007 Trading History Storage | ✅ Complete | Trades partition by `mode/sub_account_id` and merged backtest ledgers preserve attribution |
| NFR-008 Asset/PnL History | ✅ Complete | Portfolio/performance/backtest histories carry sub-account identity |
| NFR-011 Security | ✅ Complete | Live credentials are explicit named refs; missing refs reject startup |
| NFR-012 Operational Safety | ✅ Complete | Live credential conflicts reject; auto-approval thresholds route per sub-account |

0 ⚠️ Partial. 0 ❌ Gap.

## Tests

Phase 19 added and updated tests across:

- sub-account model, registry, YAML parsing, and migration
- runtime engine fan-out and per-account risk overrides
- proposal, notification, performance, trade, and portfolio attribution
- multi-credential env parsing and live trader isolation
- multi-account backtest harness, operator script, and dashboard helpers

## Final Gates

| Gate | Result |
|------|--------|
| Targeted 19.5 pytest | ✅ clean |
| Changed-source ruff | ✅ clean |
| Changed-source mypy | ✅ clean |
| Full pytest | ✅ 1413 passed |

## DEBT

No new Phase 19.5 debt was registered. DEBT-052 remains the known
Phase 19.3 follow-up for richer per-sub-account notification routing
overrides; it does not block Phase 19 compliance.

## Verdict

**✅ PASS.** Phase 19 now has an end-to-end sub-account model from
configuration through execution, persistence, live credentials,
operator dashboards, and comparative backtesting.
