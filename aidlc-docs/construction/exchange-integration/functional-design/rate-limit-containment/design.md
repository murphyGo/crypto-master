# DEBT-090 functional amendment — 2026-10-30

Unit: exchange-integration; FR-016–020/046, NFR-006/009/011, CON-002;
US-008/014/025; legacy 2/10.1/13.3. This extends the existing adapter port and
derivatives design; runtime data, portfolio semantics and AI CLI are unchanged.

[Answer]: “진행시켜” authorizes this repair. Keep existing scan containment and
protective quote checks; do not change strategy, live intent, credentials or
trading cadence. No additional product decision is required for these defaults.

1. Every core CCXT request (including connect/load_markets, both order types and
   order cancellation) crosses one request boundary. RateLimitExceeded and
   DDoSProtection establish a cooldown; other NetworkError failures become domain
   ExchangeAPIError through each operation's existing error ladder. Authentication,
   insufficient-funds, invalid-order and not-found behavior remain compatible.
2. Existing core RATE_LIMIT and derivative rate_limited codes remain. A numeric
   retry_after_seconds field communicates remaining cooldown without raw URLs,
   response bodies or credentials. A failed request is never automatically repeated
   by the adapter. Order timeout is an error with uncertain remote outcome, never a
   fabricated success or fill. Existing reconciliation remains authoritative.
3. All adapter instances in this process share cooldown by venue, endpoint market
   family and testnet. Binance spot and USD-M futures are separate; derivative
   funding/OI calls always use the futures scope. Bybit uses its unified scope.
   Accounts/keys sharing an endpoint share cooldown. Recreating/reconnecting an
   adapter cannot erase an active deadline. Unrelated venues/modes remain usable.
4. While cooldown remains, callers fail immediately without CCXT invocation.
   Later normal requests can proceed after expiry; no timer or probe is added.
   In-flight work is not cancelled. Existing ccxt pacing and derivative budgets,
   circuit breakers and wall-time bounds remain in force.
5. The engine's existing domain-error scan handler can reach the account's monitor
   and snapshot work. A monitor attempt does not promise successful protection:
   unavailable/stale prices still fail closed. No cached price is relabeled fresh.
   Normalized transport errors must not manufacture orders or bypass safety reads.

This is reactive containment, not a new global request scheduler. It cannot account
for other processes or external actors sharing the public IP, and does not identify
the producer of the observed ban. Full-cycle dashboard acceptance stays separate.
