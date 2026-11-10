# Exchange rate-limit exception containment — active 2026-10-30

- Unit: `exchange-integration`; secondary `proposal-runtime`, `trading-core`,
  `notifications-ops`.
- Debt: DEBT-090 High; discovered during DEBT-083 v70 observation.
- Requirements: FR-016–020/046, NFR-006/009/011, CON-002;
  stories US-008/014/025; legacy2/10.1/13.3.
- Stage: Functional/NFR amendment recorded; implementation and verification active.

[Answer]: The user's subsequent “진행시켜” authorizes this next bounded repair,
verification and the existing same-capacity delivery workflow. Routine design
decisions below preserve credentials, live intent, cadence and freshness gates.
No exchange probes, IP rotation or automatic order resubmission are authorized.

- [x] Retain HTTP418/code-1003 cycle evidence and11versus12monitor coverage.
- [x] Reproduce raw DDoSProtection escaping get_ohlcv with a network-free mock.
- [x] Audit all CCXT method exception boundaries and scan/monitor dependencies.
- [x] Specify domain error mapping and bounded venue/backoff behavior, including
  ban deadlines, shared request budgets and protective-work fail-closed semantics.
- [x] Add failure tests for429/418/transport errors, no retry storm, account
  isolation, preserved monitor attempts and unavailable/stale quote safeguards.
- [x] Implement the smallest verified change; run exchange/runtime targeted tests,
  broader regression and static gates. Preserve order idempotency and credentials.
- [ ] Same-capacity delivery only after source verification; retain every failed
  sample and verify a natural error-free cycle without extra exchange probes.
- [ ] Update session/cross-check/state/debt/map on completion.

Evidence: `docs/sessions/2026-10-30-dashboard-recovery-rearm.md` and its operation
artifacts. Root cause of the venue's IP ban is unproven; no producer attribution
or recovery guarantee may be inferred solely from the reported expiry time.

Design: `../exchange-integration/functional-design/rate-limit-containment/design.md`
and `../exchange-integration/nfr-design/rate-limit-containment/design.md`.
Verification: exchange tests, runtime/position-monitor/derivatives tests, full
`.venv/bin/python -m pytest`, changed-file Black/Ruff, full mypy, source/image
hashes and a natural completed cycle. No infrastructure change is needed.
