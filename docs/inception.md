# Crypto Master Project

## Project Overview

This project is an automated crypto trading application.
It evolves through a self-feedback loop to continuously improve itself and enhance performance.

This document serves as the basis for generating requirements.md.

## Tech Stack

- Python 3.10+
- Claude

## Key Features

- **Bitcoin Chart Analysis**: Primarily trades Bitcoin. Uses chart analysis techniques to derive Bitcoin trading points.
- **Altcoin Chart Analysis**: Analyzes altcoin charts using chart analysis techniques to derive trading points.
- **Chart Analysis Techniques**: Pre-defined chart analysis techniques are used for analysis. Techniques can be defined as natural language prompts in md files or as code snippets. All chart analysis techniques are stored, and the performance of each technique is tracked and saved.
- **Trading Strategy**: Calculates risk/reward ratio from derived trading points and sets leverage, entry price, take-profit, and stop-loss levels.
- **Trading Modes**: Supports both live trading and paper trading.
- **Bitcoin Trading Proposals**: Analyzes Bitcoin using the best chart analysis technique, derives trading strategy, and proposes trades when good performance is expected. Trading proceeds if the user accepts.
- **Altcoin Trading Proposals**: Analyzes multiple altcoins using the best chart analysis techniques, derives trading strategies, and proposes trades for the token with the best expected performance. Trading proceeds if the user accepts.
- **Exchanges**: Must support multiple exchanges with an extensible architecture.
- **Chart Analysis Technique Generation & Backtesting Feedback Loop**: Claude automatically suggests improvements based on existing technique performance or generates entirely new ideas. Users can also provide ideas for technique generation. Backtesting is performed to verify performance. Claude improves techniques through an automated feedback loop. Ideas are refined and enhanced based on backtesting results to improve performance. If performance is good, it's presented to the user for approval to adopt as an official chart analysis technique.
- **AI-Driven Analysis**: While chart analysis, take-profit/stop-loss generation can be partially replaced by code snippets, all analysis, trading, and chart analysis technique generation is handled by the Claude AI agent.
- **UI Dashboard**: A web dashboard to view chart analysis techniques, ongoing trades, technique generation status, and asset/performance summary at a glance.

The core principle is that all processes run through Claude Agent, and analysis/trading techniques must evolve through an automated feedback loop.

## Claude

Anthropic API is not used for now.
Parts requiring Claude use the CLI execution method (e.g., `claude -p "Do something..." > result.md`)

## Exchanges

The following exchanges are supported. Subject to change in the future.

- Binance
- Bybit
- Tapbit

## Managed Data

The following information needs to be stored and managed in md files or code:

- Chart analysis techniques
- Chart analysis technique experiments and backtesting results
- Trading history
- Current assets, PnL, asset change history (both paper and live)

## Credentials

- Sensitive information such as secrets are stored in .env file (added to .gitignore)

## Build Commands


