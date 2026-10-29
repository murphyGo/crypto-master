# Source-error rearming

The2026-10-30 continuation authorizes correcting the failed manual-only latch.
The [plan](../../../plans/dashboard-recovery-rearm-plan.md) is the current
contract; prior source-recovery artifacts remain historical.

Entities: normalized Query, one logical Recovery job/Future/Event, a verified
cache entry with its original evaluation age, and an immutable ErrorToken with
reason and monotonic retry eligibility. Token identity protects old callbacks.

Transitions: request → admitted job → verified success or settled failure.
Only source_changed gets finite within-job retries. After exhaustion, requests
before eligibility return explicit incomplete data; after eligibility a request
can create a new job. The eligibility time is the later of the old30s recovery
deadline and2s after failure. No new background timer or infinite page watcher.
An exact manual callback can clear its token early; stale callbacks cannot clear
newer tokens. Close settles all progress and clears service-owned state.

UI structure stays unchanged: explicit coverage, one watcher for active work,
and the existing manual retry for terminal results. Navigating or refreshing a
page after cooldown can recover without requiring that specific retry callback.
Successful content must still pass full source verification. Failure never
becomes healthy/empty or renews cached data age.
