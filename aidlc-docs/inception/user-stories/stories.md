# User Stories

## Strategy Research and Validation

| Story ID | Story | Acceptance Signals | Requirements | Primary Unit |
|----------|-------|--------------------|--------------|--------------|
| US-001 | As a strategy maintainer, I can add an analysis technique as a markdown prompt or Python file so the system can discover it without core changes. | Loader discovers file, metadata is valid, tests cover loader/factory behavior | FR-003, FR-004, NFR-005, NFR-010 | `strategy-framework` |
| US-002 | As a strategy maintainer, I can evaluate a technique against historical data so weak ideas do not reach trading workflows. | Backtest output is structured, reproducible, and tied to the strategy | FR-005, FR-025, NFR-006 | `backtesting-validation` |
| US-003 | As a trading risk reviewer, I can require robustness gates before strategy promotion so overfit strategies are blocked. | OOS, walk-forward, regime, and sensitivity gates are pass/fail/skipped with blocking semantics | FR-034 | `backtesting-validation` |
| US-004 | As a strategy maintainer, I can ask Claude CLI for improvements that include hypothesis and failure-mode analysis. | Prompt/output contracts include hypothesis and root-cause analysis; direct Anthropic API is not used | FR-022, FR-033, FR-035, NFR-002, CON-001 | `ai-feedback-loop` |

## Proposal and Trading Execution

| Story ID | Story | Acceptance Signals | Requirements | Primary Unit |
|----------|-------|--------------------|--------------|--------------|
| US-005 | As an operator, I can receive Bitcoin and altcoin trade proposals based on available strategy evidence. | Proposal records include symbol, analysis, entry/exit points, and expected risk/reward | FR-001, FR-002, FR-011, FR-012 | `proposal-runtime` |
| US-006 | As an operator, I can accept or reject proposals before execution. | Accept/reject decisions are explicit, persisted, and respected by runtime execution | FR-013, FR-014, CON-003 | `proposal-runtime` |
| US-007 | As an operator, I can paper trade safely without exchange credentials or real funds. | Paper balances, positions, trades, and PnL persist locally | FR-010, NFR-007, NFR-008 | `trading-core` |
| US-008 | As an operator, I can live trade only when credentials and confirmation requirements are satisfied. | Missing live credentials fail startup or execution path; live execution requires explicit intent | FR-009, FR-016, FR-017, NFR-011, NFR-012 | `trading-core` |

## Capital Segmentation and Experiments

| Story ID | Story | Acceptance Signals | Requirements | Primary Unit |
|----------|-------|--------------------|--------------|--------------|
| US-009 | As a trading risk reviewer, I can isolate balances and trade history by sub-account so one strategy's drawdown cannot affect another. | Each sub-account has separate balance, positions, trade history, and equity curve | FR-036 | `sub-account-capital-segmentation` |
| US-010 | As an operator, I can bind live sub-accounts to named credential sets. | Each enabled live sub-account resolves exactly one credential set or fails fast | FR-037, NFR-011 | `sub-account-capital-segmentation` |
| US-011 | As a strategy maintainer, I can run A/B backtests over strategy sets with controlled capital. | Multi-account report includes equity, MDD, Sharpe, and hit rate per sub-account | FR-038 | `backtesting-validation` |

## Dashboard, Notifications, and Operations

| Story ID | Story | Acceptance Signals | Requirements | Primary Unit |
|----------|-------|--------------------|--------------|--------------|
| US-012 | As an operator, I can inspect strategies, feedback progress, trading state, and portfolio summaries from the dashboard. | Dashboard pages show strategy, feedback, trading, runtime, and account state without raw-file inspection | FR-028 - FR-032, NFR-003 | `dashboard-operator-ui` |
| US-013 | As an operator, I can receive notifications for opportunities without bypassing approval gates. | Notifications contain actionable context; execution still requires accept/confirm controls | FR-015, CON-003 | `notifications-ops` |
| US-014 | As a system maintainer, I can deploy and operate the runtime without exposing secrets. | Docker/Fly/startup paths use environment-backed credentials and ignored local files | NFR-004, NFR-011 | `notifications-ops` |

## Governance and Traceability

| Story ID | Story | Acceptance Signals | Requirements | Primary Unit |
|----------|-------|--------------------|--------------|--------------|
| US-015 | As a system maintainer, I can route each change through an AI-DLC unit and construction stage. | Work references unit, stage, plan, tests, session log, and cross-check when warranted | All | `quality-governance` |
| US-016 | As a reviewer, I can trace a requirement to units, code paths, tests, debt, and cross-checks. | Requirement index, unit map, construction plan, and verification report agree on ownership | All | `quality-governance` |

## Product Intelligence Expansion

| Story ID | Story | Acceptance Signals | Requirements | Primary Unit |
|----------|-------|--------------------|--------------|--------------|
| US-017 | As a strategy maintainer, I can review candidate strategies in a promotion lab before adoption. | Candidate score combines backtest quality, robustness gates, trade count, drawdown, liquidation, and observation state | FR-039, FR-027, FR-034 | `strategy-promotion-lab` |
| US-018 | As an operator, I can choose reusable sub-account experiment templates for strategy labs. | Templates declare capital, strategy filters, risk overrides, and notification routes without duplicating YAML by hand | FR-040, FR-036, FR-038 | `sub-account-experiment-marketplace` |
| US-019 | As a trading reviewer, I can inspect why a closed trade was high or low quality. | Autopsy output includes MFE/MAE, thesis invalidation, drawdown-before-exit, and sizing/risk notes | FR-041, FR-005, FR-021 | `trade-quality-autopsy` |
| US-020 | As an operator, I can see whether the runtime is safe to continue. | Safety score rolls up data freshness, notification failures, LLM failures, drawdown, liquidation, and concentration signals | FR-042, FR-014, FR-015, NFR-007 | `runtime-safety-score` |
| US-021 | As a strategy maintainer, I can replay historical proposals under alternate thresholds. | Replay reports compare accepted/rejected outcomes, threshold sensitivity, and alternate exit assumptions | FR-043, FR-013, FR-014, FR-025 | `proposal-replay-simulator` |
| US-022 | As a risk reviewer, I can prevent multiple strategies from making the same correlated bet. | Governor surfaces or blocks highly correlated strategy/asset exposure across open positions and sub-accounts | FR-044, FR-036, FR-038 | `strategy-correlation-governor` |
