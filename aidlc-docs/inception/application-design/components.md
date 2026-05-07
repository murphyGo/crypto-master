# Components

## Component Catalog

| Component | Responsibility | Primary Paths | Related Units |
|-----------|----------------|---------------|---------------|
| Exchange Adapters | Fetch market data, query balances, and execute orders behind a common interface | `src/exchange/`, `src/config.py` | `exchange-integration` |
| Strategy Framework | Load prompt/Python strategies, indicators, factories, and performance metadata | `src/strategy/`, `strategies/` | `strategy-framework` |
| Backtesting and Validation | Run historical simulations, snapshot validation, robustness gates, and reports | `src/backtest/`, `scripts/backtest_*`, `data/backtest/` | `backtesting-validation` |
| Claude AI Integration | Execute Claude CLI calls and strategy-improvement workflows | `src/ai/` | `ai-feedback-loop` |
| Feedback Loop | Orchestrate performance analysis, generated candidates, and audit records | `src/feedback/`, `scripts/auto_research_candidates.py` | `ai-feedback-loop` |
| Proposal Engine | Generate ranked trade proposals and handle operator interaction | `src/proposal/` | `proposal-runtime` |
| Runtime Engine | Run proposal/trading cycles and emit activity logs | `src/runtime/`, `src/main.py` | `proposal-runtime` |
| Trading Core | Execute paper/live trades, risk math, portfolios, profiles, and sub-accounts | `src/trading/`, `src/utils/trading_math.py`, `trading_profiles/` | `trading-core`, `sub-account-capital-segmentation` |
| Persistence Utilities | Provide atomic writes, timestamp helpers, and JSONL rotation | `src/utils/io.py`, `src/utils/time.py`, `src/runtime/jsonl_rotator.py` | `persistence-data-integrity` |
| Dashboard | Present operator UI for runtime, trading, strategies, feedback, and command-center safety workflows | `src/dashboard/` | `dashboard-operator-ui`, `dashboard-operator-command-center` |
| Notification Backends | Deliver proposal/operator notifications | `src/proposal/notification.py` | `notifications-ops` |
| Quality Governance | Maintain AI-DLC overlay, generated skills, debt, sessions, and cross-checks | `aidlc-docs/`, `.agents/`, `.claude/`, `docs/` | `quality-governance` |

## Brownfield Source Material

This catalog normalizes:

- `aidlc-docs/inception/reverse-engineering/component-inventory.md`
- `aidlc-docs/inception/reverse-engineering/architecture.md`
- `aidlc-docs/inception/units/unit-of-work.md`

The reverse-engineering documents remain evidence. This file is the standard
AI-DLC application-design entry point for component lookup.
