# Candidate Infrastructure Design: CPU Quota Recovery

**Date:** 2026-10-12 KST. **Status:** Deferred by operator response `보류`; not approved or activated. At deferral, Fly v59, shared CPU 1 / 2048 MiB and the existing machine/volume were retained without an additional deployment or compute-cost change.

**Subsequent source checkpoint (2026-10-25):** Fly v60 / `38876fc` retains shared
CPU 1 / 2048 MiB and the original volume. The capacity proposal remains deferred;
the v59 activation image below is historical and must be refreshed from current
source/deployment evidence before any renewed capacity approval. See the
[shared-CPU session](../../../../../docs/sessions/2026-10-25-dashboard-shared-cpu-performance.md).

## Problem and evidence

The bounded v59 image is deployed at source `22abf3d`. Its 175 runtime hashes
match, health passes, and paper cycle `4d3f0e4f-46e2-4591-9b57-2ef02b0ff75b`
completes at 2026-10-11T15:47:03.985307Z. First Home protocol readiness does
not complete within 240s. A separate query completes activity in 75.926s,
ledger in 3.600s and proposals in 44.882s; snapshots remain pending at the
120s observation, then the service has all five cache entries by final capture.
These two diagnostics overlap and are not controlled latency qualification.

Fly metrics during this delay show baseline `0.0625` CPUs, burst balance near
zero and quota throttling increasing. In two 30s intervals, throttling consumes
about 90.5% / 90.9% of wall time. Available memory remains over 1.2 GB in those
samples; the original memory-exhaustion incident is separate. The later warm
Home/Trading responses complete in 1.443s/1.251s (connection totals 1.891s/2.063s).
CPU quota is a measured additional bottleneck; no exhausted-state Python stack
or controlled CPU-class A/B comparison is claimed.

[Fly CPU documentation](https://docs.fly.io/machines/cpu-performance) states that
shared CPU has a 6.25% baseline and performance CPU has 100%; a depleted shared
burst balance enforces the baseline. Its
[metric definitions](https://docs.fly.io/monitoring/metrics#instance-load-and-cpu)
identify throttle and balance units as centiseconds. This supports the measured
quota interpretation, independently of possible host contention in steal time.

## Reviewed change and expected cost

Use one performance CPU and retain 2048 MiB on the same nrt machine and original
volume. [Candidate TOML](fly.performance.toml) changes only `cpu_kind`;
its parsed structure otherwise equals current `fly.toml`. The dashboard reader
stays one worker / four admitted jobs, with the same deadlines, cache/state
limits and failure semantics. Engine/dashboard remain colocated. CPU capacity
removes this shared-quota ceiling; actual full-page timing still requires testing.

The [official price page](https://fly.io/pricing/) supplies base 30-day prices and
Tokyo multiplier 1.307692308. Its current base shared 256 MiB price is $2.194128;
extra RAM is $6.003072/GB; performance-1x includes 2 GiB at $33.001344 base.
For continuous Tokyo operation, current 1 shared CPU / 2 GiB is approximately
**$16.61**, and proposed 1 performance CPU / 2 GiB is **$43.16**, an estimated
**+$26.55 per 30 days** of compute. Tax, credits/reservations, traffic, storage and
other services are excluded. These are a public rate calculation, not the
account's invoice. [Calculation metadata](pricing-calculation.json) records
the source, retrieval time and formula inputs.

## Activation and rollback after approval

After explicit approval, persist the CPU-kind change in root `fly.toml`, commit
and push it. Deploy the existing verified v59 image digest
`sha256:03bf3e7280c36b8c5abcbc65c1edc4a7ce09deaf95ac6e48cdb5bbb35c4f610e`
with explicit performance / 1 CPU / 2048 MiB flags and the same single-machine
update scope. No dependency rebuild or runtime-data migration is required.
Record runtime image source and configuration commit separately.

Verify actual guest settings, all source hashes, health, complete Home/Trading
responses, CPU metrics and one post-change paper cycle. Roll back the CPU kind
to shared / 1 / 2048 with the same image and volume if capacity activation causes
a new failure or is withdrawn. The cost change does not close the million-event
5s miss, native viewport/four-session qualification or original resource target.

The [plan](../../../plans/dashboard-operator-ui-cpu-quota-infrastructure-design-plan.md)
contains the operator-deferred budget choice and the already established provider,
storage, network, messaging, monitoring and trading constraints.
