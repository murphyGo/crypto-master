# Requirements

## Canonical Source

This file is the AI-DLC inception requirements index for Crypto Master. It
normalizes the existing brownfield requirements into the standard AI-DLC
`aidlc-docs/inception/requirements/` location.

The detailed requirement text remains in `docs/requirements.md` to preserve the
project's historical source of truth. Future AI-DLC work should read this file
first, then open `docs/requirements.md` for the full FR/NFR descriptions and
change history.

## Requirement Groups

| Group | Requirement IDs | Primary Units |
|-------|-----------------|---------------|
| Chart analysis and strategy framework | FR-001 - FR-005, FR-033 - FR-035, NFR-005, NFR-010 | `strategy-framework`, `backtesting-validation`, `ai-feedback-loop` |
| Trading strategy and execution | FR-006 - FR-010, NFR-007, NFR-008, NFR-012 | `trading-core`, `proposal-runtime`, `persistence-data-integrity` |
| Trading proposal lifecycle | FR-011 - FR-015 | `proposal-runtime`, `notifications-ops` |
| Exchange integration | FR-016 - FR-020, NFR-009, NFR-011 | `exchange-integration`, `notifications-ops` |
| Feedback loop and validation | FR-021 - FR-027, FR-034, FR-035, NFR-002, NFR-006 | `ai-feedback-loop`, `backtesting-validation`, `strategy-framework` |
| Sub-account capital segmentation | FR-036 - FR-038 | `sub-account-capital-segmentation`, `trading-core`, `backtesting-validation`, `dashboard-operator-ui` |
| Product intelligence expansion | FR-039 - FR-044 | `strategy-promotion-lab`, `sub-account-experiment-marketplace`, `trade-quality-autopsy`, `runtime-safety-score`, `proposal-replay-simulator`, `strategy-correlation-governor` |
| Operator dashboard | FR-028 - FR-032, NFR-003 | `dashboard-operator-ui` |
| Security and constraints | NFR-004, NFR-011, NFR-012, CON-001 - CON-003 | `exchange-integration`, `notifications-ops`, `trading-core`, `quality-governance` |

## Functional Requirement Index

| ID | Summary | Priority | Primary Unit |
|----|---------|----------|--------------|
| FR-001 | Analyze Bitcoin charts to derive trading points | High | `strategy-framework` |
| FR-002 | Analyze altcoin charts to derive trading points | High | `strategy-framework` |
| FR-003 | Define analysis techniques as prompt or Python strategy artifacts | High | `strategy-framework` |
| FR-004 | Store and manage analysis techniques in the file system | High | `strategy-framework` |
| FR-005 | Track strategy performance | High | `strategy-framework`, `backtesting-validation` |
| FR-006 | Calculate risk/reward from trading points | High | `trading-core` |
| FR-007 | Configure leverage | Medium | `trading-core` |
| FR-008 | Set entry, take-profit, and stop-loss prices | High | `trading-core` |
| FR-009 | Execute live trades with real funds | High | `trading-core`, `exchange-integration` |
| FR-010 | Simulate paper trades with virtual funds | High | `trading-core` |
| FR-011 | Propose Bitcoin trades from the best available technique | High | `proposal-runtime` |
| FR-012 | Propose the best altcoin opportunities | High | `proposal-runtime` |
| FR-013 | Support operator accept/reject decisions | High | `proposal-runtime` |
| FR-014 | Store proposal history and outcomes | Medium | `proposal-runtime`, `persistence-data-integrity` |
| FR-015 | Notify operators about opportunities | Medium | `notifications-ops` |
| FR-016 | Integrate Binance API | High | `exchange-integration` |
| FR-017 | Integrate Bybit API | High | `exchange-integration` |
| FR-018 | Support Tapbit as a future exchange integration | Medium | `exchange-integration` |
| FR-019 | Provide exchange abstraction for new exchanges | High | `exchange-integration` |
| FR-020 | Collect historical OHLCV for backtesting | High | `exchange-integration`, `backtesting-validation` |
| FR-021 | Analyze strategy performance and generate reports | High | `ai-feedback-loop`, `backtesting-validation` |
| FR-022 | Generate Claude-assisted improvement suggestions | High | `ai-feedback-loop` |
| FR-023 | Generate new analysis technique ideas | High | `ai-feedback-loop` |
| FR-024 | Generate techniques from operator ideas | Medium | `ai-feedback-loop` |
| FR-025 | Execute backtests against historical data | High | `backtesting-validation` |
| FR-026 | Automate backtest, analysis, improvement, and revalidation loops | High | `ai-feedback-loop`, `backtesting-validation`, `proposal-runtime` |
| FR-027 | Promote validated techniques after operator approval | High | `strategy-framework`, `ai-feedback-loop` |
| FR-028 | Show strategy status in the dashboard | Medium | `dashboard-operator-ui` |
| FR-029 | Show active trading state | Medium | `dashboard-operator-ui` |
| FR-030 | Show feedback loop progress | Medium | `dashboard-operator-ui` |
| FR-031 | Show asset and performance summaries | Medium | `dashboard-operator-ui` |
| FR-032 | Provide a Streamlit web dashboard | Medium | `dashboard-operator-ui` |
| FR-033 | Require falsifiable hypotheses for Claude-generated techniques | High | `strategy-framework`, `ai-feedback-loop` |
| FR-034 | Gate strategy promotion through robustness validation | High | `backtesting-validation`, `strategy-framework` |
| FR-035 | Require failure-mode analysis before strategy improvement | High | `ai-feedback-loop`, `strategy-framework` |
| FR-036 | Isolate capital, positions, history, and equity by sub-account | High | `sub-account-capital-segmentation`, `trading-core` |
| FR-037 | Bind live sub-accounts to explicit credential sets | High | `sub-account-capital-segmentation`, `exchange-integration` |
| FR-038 | Run strategy-combination A/B backtests by sub-account | Medium | `sub-account-capital-segmentation`, `backtesting-validation` |
| FR-039 | Score and stage strategy candidates through an explicit promotion lab | High | `strategy-promotion-lab` |
| FR-040 | Package sub-account configurations as reusable experiment templates | Medium | `sub-account-experiment-marketplace` |
| FR-041 | Analyze closed trades for post-trade quality and thesis failure modes | Medium | `trade-quality-autopsy` |
| FR-042 | Compute an operator-facing runtime safety score from live health signals | High | `runtime-safety-score` |
| FR-043 | Replay historical proposals under alternate approval and exit assumptions | Medium | `proposal-replay-simulator` |
| FR-044 | Govern runtime exposure using strategy and asset correlation constraints | High | `strategy-correlation-governor` |

## Non-Functional Requirement Index

| ID | Summary | Primary Unit |
|----|---------|--------------|
| NFR-001 | Use Python 3.10 or higher | `quality-governance` |
| NFR-002 | Use Claude CLI through `claude -p` instead of Anthropic API | `ai-feedback-loop` |
| NFR-003 | Implement the dashboard with Streamlit | `dashboard-operator-ui` |
| NFR-004 | Manage sensitive configuration through ignored environment variables | `notifications-ops`, `exchange-integration` |
| NFR-005 | Store techniques as prompt markdown or Python code | `strategy-framework` |
| NFR-006 | Store backtest results in structured artifacts | `backtesting-validation`, `persistence-data-integrity` |
| NFR-007 | Persist trade history with prices, quantity, leverage, fees, PnL, and timestamps | `trading-core`, `persistence-data-integrity` |
| NFR-008 | Persist asset and PnL history separately by mode | `trading-core`, `persistence-data-integrity` |
| NFR-009 | Keep exchange additions plugin-like and low-impact | `exchange-integration` |
| NFR-010 | Add analysis techniques by adding files, without core code edits | `strategy-framework` |
| NFR-011 | Protect exchange API keys from source code | `exchange-integration`, `notifications-ops` |
| NFR-012 | Require explicit live trading confirmation | `trading-core`, `proposal-runtime` |

## Constraints

| ID | Summary | Applies To |
|----|---------|------------|
| CON-001 | Do not call the Anthropic API directly; use Claude CLI | `ai-feedback-loop` |
| CON-002 | Respect exchange API rate limits | `exchange-integration` |
| CON-003 | Require operator approval for live trading and strategy adoption | `trading-core`, `strategy-framework`, `proposal-runtime` |

## Traceability Pointers

- Detailed descriptions and change history: `docs/requirements.md`
- Unit ownership and test scope: `aidlc-docs/inception/units/unit-of-work.md`
- Legacy phase mapping: `aidlc-docs/inception/units/legacy-phase-map.md`
- Debt mapping: `aidlc-docs/inception/units/debt-unit-map.md`
- Verification questions: `aidlc-docs/inception/requirements/requirement-verification-questions.md`
