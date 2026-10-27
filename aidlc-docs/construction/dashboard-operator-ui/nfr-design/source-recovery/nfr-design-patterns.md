# Resilience and scheduling

Finite, coalesced transient retry lives inside the existing read service.
Recreate the builder per attempt; close safely before retry. Queue rotation and
Condition timeout make backoff fair to ready siblings. Preserve exact job Event
until final outcome. Protect terminal exhaustion with capacity reservation;
fail admission visibly at metadata capacity. Cleanup faults are terminal and
must not strand Future/Event or kill the worker silently. Use existing bounded
allowlisted diagnostics if an extra retry stage is needed.

Scalability/state, freshness, source proof and security constraints remain in
the plan. Initial blocking reads remain compatible; retry deadline checks are
cooperative rather than unsafe thread cancellation.
