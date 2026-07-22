# Business Rules: Funding+OI Crowding Filter

## CR-01 — No look-ahead

Every input timestamp is at or before proposal `as_of`. Live and replay use the
same pure classifier. Predicted Funding is excluded.

## CR-02 — Conjunctive crowding signal

Funding extreme alone and OI rising alone are neutral. A crowding label needs
both conditions and the Funding sign determines the crowded side.

## CR-03 — Deterministic thresholds

Sort the trailing settled rates and use nearest-rank percentiles. Do not use
platform-dependent interpolation. A complete 30-day 8h window needs at least
90 observations.

## CR-04 — Side-aware scope

Crowded-long affects new long entries only; crowded-short affects new short
entries only. Existing positions, exits, sizing, strategy analysis, and the
opposite side are unchanged.

## CR-05 — Missing context fails open

Missing, stale, short, or invalid context never blocks a proposal. Emit stable
`gate_skipped_missing_market_context` telemetry with normalized unmet reasons.

## CR-06 — Shadow-first

The initial action is `shadow`. It may calculate `would_block` and emit an
event but cannot change `ProposalRecord.final_state`, acceptance counters,
orders, balances, or positions.

## CR-07 — Evidence before veto

Veto requires qualifying proposal replay and pinned Snapshot-v2 backtest
reports. Live or mixed-generation evidence cannot qualify. Missing evidence is
not an operator override surface.

## CR-08 — Gate ordering

Evaluate after correlation and existing OHLCV regime gating and before sizing,
kill-switch/cap enforcement. This preserves current terminal precedence and
measures the population that survives earlier market-selection gates.

## CR-09 — Safe telemetry

Persist only the approved derived-field allowlist. Never serialize raw
exchange payloads, exception messages, credentials, URLs, or signed query
material.

## CR-10 — Honest dashboard language

Shadow rows say `SHADOW — NOT ENFORCING`. `would_block` is not counted as an
actual rejection or opened-trade prevention.
