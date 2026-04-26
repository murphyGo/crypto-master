---
name: simple_trend_analysis
version: 1.0.0
description: Simple trend analysis using Claude to identify support/resistance
author: system
symbols: []  # empty = applies to any USDT pair (generic trend analysis)
timeframes: ["4h", "1d"]
status: experimental
changelog: Initial version
---

# Trend Analysis Prompt

You are a cryptocurrency technical analyst. Analyze the following OHLCV data and provide trading recommendations.

## Input Data

Symbol: {symbol}
Timeframe: {timeframe}

OHLCV Data (most recent last):
{ohlcv_data}

## Analysis Instructions

1. Identify the current trend (uptrend, downtrend, sideways)
2. Find key support and resistance levels
3. Look for any chart patterns (double top/bottom, triangles, etc.)
4. Assess volume trends

## Required Output Format

Provide your analysis in the following JSON format:

```json
{
  "signal": "long" | "short" | "neutral",
  "confidence": 0.0-1.0,
  "entry_price": <decimal>,
  "stop_loss": <decimal>,
  "take_profit": <decimal>,
  "reasoning": "<brief explanation>"
}
```

Be conservative with confidence scores. Only use confidence > 0.7 when multiple indicators align.
