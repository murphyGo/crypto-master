# Personas

## Primary Personas

| Persona | Goal | Needs | AI-DLC Units |
|---------|------|-------|--------------|
| Operator | Run paper/live trading safely and understand current state | Clear proposals, accept/reject controls, dashboard visibility, safe live defaults | `proposal-runtime`, `trading-core`, `dashboard-operator-ui`, `notifications-ops` |
| Strategy Maintainer | Add, test, improve, and promote strategies | File-based strategy artifacts, performance data, robustness gates, failure-mode feedback | `strategy-framework`, `backtesting-validation`, `ai-feedback-loop` |
| Trading Risk Reviewer | Prevent unsafe execution and misleading results | Conservative live gates, correct leverage/PnL math, capital isolation, reproducible validation | `trading-core`, `sub-account-capital-segmentation`, `backtesting-validation`, `persistence-data-integrity` |
| System Maintainer | Keep the brownfield system reliable and traceable | Unit ownership, tests, session logs, cross-checks, TECH-DEBT, deployment constraints | `quality-governance`, `notifications-ops`, `persistence-data-integrity` |

## Supporting Actors

| Actor | Role | Boundary |
|-------|------|----------|
| Claude CLI | Generates strategy ideas and improvement suggestions | Called through local CLI only; no direct Anthropic API calls |
| Exchange APIs | Provide market data and live order execution | Accessed through exchange adapters and credential boundaries |
| Streamlit Dashboard | Presents operator-facing state | Reads persisted runtime/trading/strategy data |
| Fly.io Runtime | Hosts long-running deployment | Uses conservative startup and credential handling |
