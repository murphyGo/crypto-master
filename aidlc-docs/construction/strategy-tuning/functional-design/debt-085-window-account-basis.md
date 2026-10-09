# DEBT-085 evidence contract

## Business model and rules

Build each recommendation from non-synthetic closed records, ordered by UTC exit timestamp (record id breaks ties), then take the configured last N. The tracker supplies account/technique/version isolation. Compute quote-currency net PnL using actual-entry notional times gross return minus fees, without multiplying leverage again. PF uses positive/negative quote amounts; win rate uses net signs. Cumulative return divides window net PnL by the explicitly supplied initial account quote capital. Drawdown walks an equity curve initialized to that same capital and uses each running peak as denominator. This is an initial-capital benchmark, not a reconstructed window-opening cash balance.

## Unknown evidence and NFR requirements

Missing exit timestamps make window selection uncertain. Missing/nonpositive/nonfinite capital, unknown net amounts, and mixed quote currencies make economic evidence incomplete. Never silently drop unknown rows to manufacture a healthier window. Show a coverage reason, suppress economic recommendations, and preserve fail-closed-rate pause recommendations independently. A missing quantity cannot produce quote PnL, even when the gross percentage is known. Existing aggregate-only evidence remains a legacy API but is marked incomplete because it cannot establish window/account units.

## Consumers and compatibility

The dashboard and observation writer share the same pure builder and per-strategy N override. The render boundary reads validated sub-account capital config without constructing traders; settings seed is used only for the legacy default paper account when no config exists. Unknown account/live capital remains unavailable. Observation snapshots add basis/window/coverage fields with legacy defaults. Seed fallback remains operator guidance and never updates applied policy. No thresholds, sizing, order execution, runtime data, deployment or account funding is changed.
