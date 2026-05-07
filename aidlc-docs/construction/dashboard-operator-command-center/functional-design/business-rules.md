# Business Rules: dashboard-operator-command-center

## Read-Only Runtime Rules

1. The command center must not mutate runtime/operator data under `data/`.
2. The command center must not call live exchange APIs during render.
3. The command center must not execute live trades or promote strategies.
4. Any future operator action must route through existing approval APIs and
   preserve explicit operator intent.

## Safety Presentation Rules

| Safety Band | Presentation Rule | Operator Meaning |
|-------------|-------------------|------------------|
| `safe` | Normal status | No immediate dashboard-visible blocker |
| `degraded` | Warning status | Investigate before increasing exposure |
| `risky` | Error status | Avoid adding exposure until cause is understood |
| `pause_recommended` | Stop-level alert | Operator should consider pausing runtime |

Safety factors must be split into readable rows instead of only a compressed
caption string.

## Account Context Rules

1. Every command-center metric must identify its scope: `paper` or `live`, and
   `Aggregate`, `default`, or concrete sub-account id.
2. Aggregate summaries must not hide per-account risk. They must retain a path
   to account-level rows.
3. Missing persisted trade/portfolio paths are not fatal; they render as
   `missing` or empty-state rows.
4. Snapshot freshness is based on the latest persisted portfolio snapshot and
   never implies a fresh exchange price.

## Exposure Rules

1. Open exposure is grouped by `symbol` and `side`.
2. Cross-account duplication is highlighted when the same `symbol`/`side`
   appears in more than one sub-account.
3. Notional is computed from persisted entry price and quantity only; it is a
   stale-safe historical estimate unless fresh market data is explicitly wired
   in a later unit.
4. Correlation warnings from runtime activity are displayed as advisory or
   blocking according to the recorded event payload.

## Evidence Rules

1. Strategy promotion evidence must preserve the full candidate id somewhere in
   the drilldown, even if tables use short ids.
2. Robustness PASS/FAIL/SKIPPED state must remain visible next to promotion
   score and blockers.
3. Replay comparisons are decision evidence, not automatic approval.
4. Long JSON details should be available through an expanded raw view instead
   of being only truncated.
