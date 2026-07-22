# Performance Test Instructions: market-regime Funding+OI Crowding Shadow Filter

## Requirement and command

CFO-NFR-002 requires pure classification p95 <=0.005 seconds at 90 settled
Funding and 500 OI observations.

```bash
uv run pytest -q -s \
  tests/test_runtime_funding_oi_filter.py::test_classifier_p95_is_within_five_milliseconds_at_design_envelope
```

Verified result over 100 local deterministic runs: p95 0.000064 seconds,
PASS. This measures only the I/O-free classifier. Exchange/network latency is
not part of the hot-path classifier and no production latency claim is made.

---

# Prior Performance Test Instructions: backtesting-validation Derivatives Data Slice 4

## Applicability

LC-11 defines deterministic offline replay but no production latency,
throughput, concurrency, or snapshot-size acceptance target. Build & Test does
not invent one.

## Bounded observations

- Hermetic refresh/reload/replay/report E2E: 1 test passed in 1.27 seconds.
- Final focused Slice 4 regression: 210 passed in 11.69 seconds.
- Generated-path coverage run: 183 passed in 17.80 seconds.
- Complete repository regression: 2585 passed in 46.89 seconds.

These are local test-run observations, not production performance guarantees.
The replay source loads one selected generation and each context is sliced
from immutable in-memory series; network latency is structurally absent.

## Live performance boundary

Public Binance latency and production refresh throughput were not tested. A
live smoke remains opt-in and is not a CI or LC-11 completion requirement.

---

# Prior Performance Test Instructions: exchange-integration Derivatives Data Slice 3

## Applicable requirements

- DD-NFR-001: four-symbol and 20-symbol deterministic load envelopes.
- DD-NFR-002: at least 100 latency-injecting fake cycles with p95 <= 5 seconds
  for four symbols and p95 <= 15 seconds for 20 symbols.
- DD-NFR-006: semaphore peak <= 4 and no unbounded queued work.

## Command

```bash
uv run pytest \
  tests/test_runtime_derivatives_context.py::test_latency_injecting_load_records_percentiles_without_task_leaks \
  -q -s
```

## Verified result

| Symbols | Cycles | Injected latency | p50 | p95 | Max | Peak | Result |
|---------|--------|------------------|-----|-----|-----|------|--------|
| 4 | 100 | 1ms/source call | 0.005066s | 0.005630s | 0.007676s | 4 | Pass |
| 20 | 100 | 1ms/source call | 0.020101s | 0.027393s | 0.034632s | 4 | Pass |

Both parameterized cases completed all `symbols * 2` series outcomes per
cycle, recorded zero deadline cancellations, left source concurrency at zero,
and left no service-owned in-flight task after close.

## Interpretation

These measurements validate the scheduler's deterministic in-process overhead
and bounded concurrency under a latency-injecting fake. They are not a public
Binance latency or throughput benchmark. Real network smoke remains opt-in and
is not a CI prerequisite.

## Failure handling

If p95 exceeds the configured envelope, inspect task cancellation, semaphore
contention, history due checks, and rolling-budget admission before changing a
deadline. Capacity above 20 symbols requires a new official endpoint-limit and
load review; do not raise the configured maximum in place.

---

# Prior Performance Test Instructions: backtesting-validation Derivatives Snapshot Schema v2

## Current applicability

No latency, throughput, concurrency, or snapshot-size performance target is
defined for the offline LC-10 persistence store. A load/stress benchmark would
therefore create an unsupported acceptance threshold and is not applicable in
this stage.

## Deterministic bounds verified

- Publication performs bounded passes over the four allowlisted data files.
- Readers load exactly one pinned/current generation and never scan directories
  by mtime.
- The manifest contains fixed file keys and validates hashes, sizes, and row
  counts before bundle use.
- The 84-test focused run completed in 3.05 seconds and the 102-test
  snapshot/atomic integration run completed in 3.26 seconds; these are test-run
  observations, not production performance guarantees.

## Later performance owner

The runtime `DerivativesContextService` slice owns deadlines, cache latency,
request budgets, and concurrency. LC-11 owns replay-level performance once a
real snapshot-backed consumer exists.

---

# Prior Performance Test Instructions: exchange-integration Derivatives Data Slice 1

## Applicability

Runtime performance testing is not applicable to Slice 1. This slice provides
domain contracts and an adapter only; it does not include the planned
`DerivativesContextService`, concurrency control, cache, rolling request
budgets, request deadlines, or an operator/runtime consumer.

## Deterministic bounds verified now

- Binance funding-history requests are capped at 1,000 records per page.
- Binance OI-history requests are capped at 500 records per page.
- Pagination advances from the final record actually returned plus one grid
  step, preventing request-size assumptions and non-progress loops.
- Funding uses an 8h grid; OI uses a 1h grid.

These behaviors are covered by the 221-test exchange run. They are functional
safety bounds, not a latency or throughput benchmark.

## Later-slice performance owner

The service slice must verify the approved DD-NFR deadline, concurrency,
request-budget, cache, and degraded/fail-closed behavior with service-level
tests. No latency claim is made by this Build & Test stage.
