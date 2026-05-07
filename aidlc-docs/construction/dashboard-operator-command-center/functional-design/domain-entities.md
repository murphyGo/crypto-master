# Domain Entities: dashboard-operator-command-center

## CommandCenterStatus

| Field | Meaning |
|-------|---------|
| `safety_score` | Numeric runtime safety score from existing safety scoring |
| `safety_band` | `safe`, `degraded`, `risky`, or `pause_recommended` |
| `last_cycle_status` | `ok`, `running`, `errored`, or missing |
| `last_cycle_started_at` | Timestamp of most recent cycle start |
| `open_positions` | Count of open persisted trades in selected scope |
| `latest_snapshot_at` | Latest persisted portfolio snapshot timestamp |
| `snapshot_freshness` | `fresh`, `stale`, `missing`, or `unknown` |
| `actionable_event_count` | Count of recent events requiring operator attention |

## AccountContext

| Field | Meaning |
|-------|---------|
| `mode` | `paper` or `live` |
| `scope` | `Aggregate`, `default`, or sub-account id |
| `sub_account_ids` | Discovered sub-account ids for selected mode |
| `latest_equity` | Latest persisted equity for selected scope |
| `quote_currency` | Snapshot quote currency, defaulting to `USDT` |
| `data_state` | Availability of trades, portfolio snapshots, and activity log |

## ExposureRow

| Field | Meaning |
|-------|---------|
| `symbol` | Trade symbol |
| `side` | `long` or `short` |
| `sub_accounts` | Sub-account ids carrying the exposure |
| `open_count` | Number of open positions in the group |
| `estimated_notional` | Sum of `entry_price * entry_quantity` from persisted trades |
| `max_leverage` | Maximum leverage among grouped positions |
| `duplicate_across_accounts` | True when exposure spans multiple sub-accounts |
| `correlation_status` | `none`, `warning`, or `blocked` from recent runtime events |

## SafetyEventSummary

| Field | Meaning |
|-------|---------|
| `event_type` | Runtime activity event type |
| `count` | Number of recent events of this type |
| `latest_at` | Latest event timestamp |
| `sub_account_ids` | Impacted sub-account ids from event details |
| `details` | Compact display fields with raw details available in drilldown |

## StrategyEvidenceLink

| Field | Meaning |
|-------|---------|
| `strategy_name` | Strategy/technique name |
| `candidate_id` | Full candidate id when available |
| `robustness_status` | PASS, FAIL, SKIPPED, or missing |
| `promotion_score` | Promotion lab score when available |
| `blockers` | Promotion blockers or failed gates |
| `backtest_run_id` | Backtest artifact reference |
| `replay_summary` | Future proposal replay scenario summary |
| `audit_event_count` | Number of audit events linked to the candidate |
