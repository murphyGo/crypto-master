# Component Methods

This document records the expected method-level responsibilities at the
AI-DLC design level. It is intentionally interface-oriented; source files remain
the executable authority.

| Component | Expected Methods / Operations | Notes |
|-----------|-------------------------------|-------|
| Exchange Adapters | fetch OHLCV, fetch ticker, fetch balance, create orders, normalize errors | Keep exchange-specific behavior behind common abstractions. |
| Strategy Framework | load strategy files, validate metadata, execute analysis, track performance | File addition should remain the normal extension path. |
| Backtesting and Validation | run backtests, analyze metrics, load snapshots, validate robustness, emit reports | Promotion gates should be explicit and testable. |
| Claude AI Integration | build prompts, invoke `claude -p`, enforce timeout/error contracts, parse results | Do not introduce direct API calls without requirement changes. |
| Feedback Loop | collect performance inputs, request improvements, audit generated candidates | Improvement flow should include hypothesis and failure-mode context. |
| Proposal Engine | rank opportunities, create proposal records, persist decisions, dispatch notifications | Execution must remain behind operator and runtime gates. |
| Runtime Engine | run cycles, enforce stale/cap gates, call trading execution, append activity events | Activity data should remain durable and dashboard-readable. |
| Trading Core | calculate sizing/PnL, execute paper/live paths, update portfolio, manage sub-accounts | Preserve paper/live and sub-account isolation semantics. |
| Persistence Utilities | atomic JSON write, UTC timestamp generation, JSONL rotation | Prefer shared helpers over local write logic. |
| Dashboard | load state, render strategy/trading/feedback/runtime pages, surface sub-account context | UI observes and controls explicit workflows; it is not a hidden execution path. |
| Notifications | format and send Slack/Telegram/email/operator messages | Notifications must not bypass approval requirements. |
