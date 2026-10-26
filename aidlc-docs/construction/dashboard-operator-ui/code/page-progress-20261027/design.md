# Page-dependent progress: implementation refinement

Baseline `37b29d7` / runtime `382c26b`. This implements the already registered
DEBT-083 correction under existing approved loading/freshness constraints;
it introduces no changed NFR target, infrastructure or trading policy.

## Problem and observable behavior

The existing page watcher reruns only when every service job has drained.
A page whose needed read has finished can remain incomplete while an unrelated
query is still running. The prior controlled probe demonstrates this without
source mutation or CPU assumptions. Replace the process-wide dependency with
read-only progress for this page, while retaining one watcher per page.

## Components and bounds

- `ReadResult` gains an optional private progress probe, excluded from repr and
  equality, defaulting to None for existing callers. It is not encoded into
  public payloads or diagnostic events. Explicit terminal retry is separate.
- Each admitted job owns a compact completion event. At most four events are
  service-owned with the four jobs; retired page handles retain only this small
  signal, never a Future, encoded result or service cache. Capture the signal
  before waiting so settlement or same-query replacement cannot change the
  generation represented by a timed-out request.
- Settlement and service close publish progress. A signal reports a completed
  attempt, not verified success; the normal render fetches/classifies the result.
- Queue-full results carry a pure readiness probe using a weak service reference
  and the already normalized bounded query. It notices relevant admission,
  completed cached/error state or a usable admission opportunity. Polling does
  not normalize paths, read files, admit work, clear errors or change cache ages.
- A render aggregates/deduplicates at most sixteen probes. One per-render latch
  prevents repeated notification, and separate sessions have separate latches.
  Any useful page probe can wake the page. Missing or excess probes retain one
  conservative legacy drain fallback; they cannot suppress known ready probes.
- Complete-result expiry and terminal retry semantics are unchanged. No new
  worker, thread, scheduler, durable metadata or runtime-data write is introduced.

## Race and compatibility obligations

A timeout racing completion must retain the original attempt's signal. A new
attempt of the same query must not reset or consume an older event. Closing
must notify active and queued attempts without waiting for a slow builder.
Multiple sessions coalesced onto one job must independently observe completion.
A queue-full page must recover when another session admits its query even if
four unrelated/relevant jobs remain admitted. Unknown/custom old results retain
bounded compatibility behavior. Fragment absence retains the existing manual
control and does not add an extra retry button.

## Validation and acceptance boundary

Deterministic regressions cover unrelated work, exact-generation/ABA races,
queue capacity and same-query coalescing, close/garbage collection, no poll-side
mutation, per-page/session bounds, no payload retention, mixed terminal results,
and unchanged 2 s freshness. Use actual Streamlit AppTest for the interaction
where practical, then exact-source static/full-suite gates before commit/push.

Deploy on the existing v65 configuration after source qualification and compare
one fresh four-session observation spanning a full natural engine cycle. Retain
all failures and first incomplete timings. This correction is not evidence that
source churn or all earlier timeouts are fixed. Original cold/native/depleted/
1024 MiB acceptance and CPU/cost deferral remain unchanged.
