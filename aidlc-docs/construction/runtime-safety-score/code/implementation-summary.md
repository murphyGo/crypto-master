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
