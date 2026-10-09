# DEBT-084: economic outcomes

## Business logic and entities

`PerformanceRecord.outcome` and existing `TechniquePerformance.wins/losses/breakevens/win_rate` retain their historical exit-label meaning. Add `net_wins`, `net_losses`, `net_breakevens`, `net_unknown`, and nullable `net_win_rate` to the aggregate. Economic sign comes from the stored gross price return minus realized fees divided by actual-entry notional (signal entry only when actual entry is unavailable).

## Rules and compatibility

Only closed, non-synthetic rows participate. Count strictly positive/negative/zero economic return independently of the exit label. The denominator is the number with known net return; expose unknown count alongside it. No known outcomes means an unavailable net win rate. Missing gross return is unknown. With nonzero fees, missing/nonpositive notional is unknown; zero-fee legacy returns remain classifiable. Non-finite inputs are unknown. Persisted old summaries load with additive defaults; normal tracker reads recompute from records.

## Consumers and NFR requirements

The strategy summary shows financial Wins/Losses/Win Rate and separate explicitly labeled exit counts. Unknown win rate is displayed as unavailable. Recommendation win rate consumes the financial rate (zero when unavailable, never the label rate). Exit execution, persisted outcome labels, price-return/PF aggregates and configured thresholds are unchanged in this item; rolling/account-base evidence is DEBT-085. Pure Decimal arithmetic avoids fee-cancellation sign drift. No runtime data migration, live order, or deployment is required.
