# Bounded request-driven recovery

The existing BDL NFR requirements remain unchanged. One worker and four admitted
jobs coalesce concurrent callers. Each job retains three attempts and its own
original30s cooperative recovery deadline, including queue time. Failed iterators
are discarded before retry. Siblings run during retry backoff.

Immutable tokens contain a reason and retry_at. Ordinary errors use failure+2s;
source exhaustion uses max(job deadline,failure+2s). The64-entry metadata budget
counts active reservations and terminal tokens together. Unexpired source tokens
are protected; expired tokens are evictable. Token expiry requires no IO, worker,
timer or persistence. Read-only readiness probes inspect eligibility without
mutating tokens or admitting work. Exact manual callbacks keep identity guards.

Resilience: a long write wave can fail one episode yet a later request recovers
after stability; sustained changes still yield explicit failure. Scalability:
fixed existing work/metadata/cache limits. Performance: no extra source discovery
in the request path; cold/warm targets are not relaxed. Security/data integrity:
same allowlisted diagnostics, full source proof, no raw payload diagnostics,
canonical writes, credentials or trading changes. Infrastructure: no new component,
capacity, dependency or cost. Logical components remain service/cache/worker/UI.

Verification must cover cooldown edges, coalescing, protected/expired metadata,
manual ABA, original cache ages, fairness, cleanup/close, canonical output parity
and the observed long-write scenario. Passing tests is not production acceptance.
