# DEBT-090 exchange-integration cross-check

Scope: FR-016–020/046; NFR-006/009/011; CON-002; US-008/014/025.
Functional/NFR amendments and construction plan are under the exchange unit.
This checks the bounded containment change, not the entire trading system or
DEBT-083 dashboard acceptance. Review is by the implementing agent.

| Contract | Evidence | Result |
|---|---|---|
| Core transport failures stay inside the exchange port |48 parameterized real-adapter cases across Binance/Bybit and all eight request paths | PASS |
| Rate-limit wait applies to sibling accounts, replacement clients and reconnect | Shared scope, reconnect and all-call suppression tests | PASS |
| Credentials/modes/markets remain separate where endpoints differ | Venue, spot/futures, testnet and derivatives scope tests | PASS |
|429/418 hints never trigger adapter retry storms | Header/date/deadline/expiry tests; one physical invocation on order failures | PASS |
| Protective flow is reached without invented pricing | Injected418 two-account engine test: two monitors, no cycle error or order | PASS |
| Derivative pagination/retries remain bounded | Next-page suppression, actual service deadline cancellation; legacy derivative tests | PASS |
| Existing financial/freshness contracts remain |688 exchange/runtime/live/paper tests | PASS |
| Full regression and static gates |3,127 passed; changed-file Black/Ruff; mypy136files | PASS |
| Exact same-capacity delivery and natural completed cycle | Preflight v70 matches; delivery pending | PENDING |

Residual limitations: in-process reactive cooldown is neither a persistent ban
registry nor an IP-wide request budget. Original ban producer is unproven. Production
fault-path execution is not inferred from an error-free cycle. Existing DEBT-083
failed samples and pending initial/native/cold/depleted/cost gates are unchanged.
