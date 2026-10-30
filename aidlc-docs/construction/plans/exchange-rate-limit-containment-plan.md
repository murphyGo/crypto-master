# Exchange rate-limit exception containment — queued 2026-10-30

- Unit: `exchange-integration`; secondary `proposal-runtime`, `trading-core`,
  `notifications-ops`.
- Debt: DEBT-090 High; discovered during DEBT-083 v70 observation.
- Requirements: FR-016–020/046, NFR-006/009/011, CON-002;
  stories US-008/014/025; legacy2/10.1/13.3.
- Stage: evidence/triage complete; Functional/NFR refinement and implementation
  are queued. No exchange or trading source change in the dashboard delivery.

[Answer]: The ongoing work permits diagnosis and debt tracking. This plan records
the concrete next bounded work; it does not authorize evading exchange limits,
changing live intent or trading cadence, or fabricating fresh protective prices.

- [x] Retain HTTP418/code-1003 cycle evidence and11versus12monitor coverage.
- [x] Reproduce raw DDoSProtection escaping get_ohlcv with a network-free mock.
- [ ] Audit all CCXT method exception boundaries and scan/monitor dependencies.
- [ ] Specify domain error mapping and bounded venue/backoff behavior, including
  ban deadlines, shared request budgets and protective-work fail-closed semantics.
- [ ] Add failure tests for429/418/transport errors, no retry storm, account
  isolation, preserved monitor attempts and unavailable/stale quote safeguards.
- [ ] Implement the smallest verified change; run exchange/runtime targeted tests,
  broader regression and static gates. Preserve order idempotency and credentials.
- [ ] Same-capacity delivery only after source verification; retain every failed
  sample and verify a natural error-free cycle without extra exchange probes.
- [ ] Update session/cross-check/state/debt/map on completion.

Evidence: `docs/sessions/2026-10-30-dashboard-recovery-rearm.md` and its operation
artifacts. Root cause of the venue's IP ban is unproven; no producer attribution
or recovery guarantee may be inferred solely from the reported expiry time.
