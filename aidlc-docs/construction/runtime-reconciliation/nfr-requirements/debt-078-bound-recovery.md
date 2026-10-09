# DEBT-078 NFR requirements

- NFR-007/008: additive boolean default, atomic existing ledger persistence, account/mode isolation, restart-safe pending/acknowledged state.
- NFR-012: no new order, exchange, confirmation, credential or deployment operation; only close-reason attribution changes.
- Reliability: failed provenance persistence must not prevent existing bound monitoring; retain conservative attribution and log the error.
- Performance: no extra write for normal trades; at most one persisted acknowledgement per recovered row, using existing tracker IO. Recovery writes occur only when missing bounds are actually found.
- Stack/scalability/security: retain existing Python/Pydantic JSON ledger and single-owner account writes; no new service, lock, dependency, secret or topology.
