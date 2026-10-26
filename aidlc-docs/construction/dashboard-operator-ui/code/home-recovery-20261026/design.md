# Home recovery correction contract

This correction implements the previously documented loading/retry intent under
the user's continued DEBT-083 authorization. It changes no financial definition,
runtime safety decision, source-proof rule or resource threshold.

## Queue saturation

`request_many` already treats `queue_full` as retryable while the bounded worker
drains. The availability layer must retain one page-level loading watcher for
both unavailable and stale queue-full results, as it does for pending rebuilds.
Do not add another worker, exceed four admitted jobs, clear source validation or
count a stale result as complete.

## Explicit retry after a terminal failure

The existing terminal messages say "Refresh to retry" but previously rendered
no actionable control. One page-level control retries failed sections. A plain
rerun inside the two-second error cache would not actually retry, so a result
may carry an optional private retry callback (`repr` and equality excluded).
The callback removes only the exact captured error generation for its own query
under the service lock. It cannot clear a newer error, a healthy cache result,
another query, or active work. The next normal request performs full verification
and shares the existing worker/coalescing path.

Only explicit operator interaction invokes terminal retry. A persistent corrupt
source stays incomplete and does not create an automatic rebuild loop. Verified
siblings and their original evaluated/freshness times remain unchanged.

## Evidence and diagnostics

The service records finite, allowlisted query/status/reason/stage values plus
bounded numeric cache-age/admission information. Diagnostic cardinality, retained
state and output rate must be bounded. No path, account/trade/proposal identity,
persisted payload or exception text is emitted; no runtime file is created.
Diagnostic failures must not affect read completion or the worker lifecycle.

The enhanced protocol observer records allowlisted alert classification and
first incomplete receipt/script-finish times, retains all failures, and requires
exact required labels, meaningful values and element presence for completeness.
It never presses trading controls or substitutes for native viewport evidence.

The historical v64 failures have no recorded reason. Their coincidence with a
cycle does not prove either corrected defect caused them. New diagnostics and
post-deployment observation must determine any remaining failure path.
