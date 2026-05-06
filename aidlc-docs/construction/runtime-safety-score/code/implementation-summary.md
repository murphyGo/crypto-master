# Implementation Summary: runtime-safety-score

Initial code generation adds the runtime safety score contract:
`RuntimeSafetyInputs`, `RuntimeSafetyPolicy`, `RuntimeSafetyBand`, and
`RuntimeSafetyScore`. The first pass defines bounded input counters and stable
operator-facing bands; event extraction and dashboard rendering remain later
steps.

Score computation now aggregates `ActivityEvent` records into safety inputs and
applies capped penalties for cycle errors, notification failures, LLM timeouts,
stale-quote rejections, liquidations, cold-start blocks, and open drawdown.

The Engine dashboard now computes and displays the runtime safety score, safety
band, and explanatory factors from the same pure scoring helpers.

Notification summaries now accept an optional `RuntimeSafetyScore` and include
the compact `runtime_safety: <score>/100 <band>` line in Slack, Telegram, and
email payloads when supplied by the dispatcher.

Review follow-up connects the runtime path: `TradingEngine` now passes the
current safety score into proposal notifications, and correlation-warning
activity events count as concentration warnings in the score.
