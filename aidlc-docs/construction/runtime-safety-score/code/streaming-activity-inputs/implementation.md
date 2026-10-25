# Streaming runtime safety inputs implementation

## Behavior

`SafetyAccumulator` consumes each eligible canonical event once. Existing weights,
bands, inclusive24h cutoff, duplicates, scalar equality, stale-reason OR behavior,
advisory/fallback conditions and public chronological APIs remain. The approved
request-time UTC anchor is explicit; a boundary event may conservatively remain.
Drawdown validation is preserved at input construction, including negative rejection.

`SafetyReadService` owns one lazy daemon for the process, one occupied slot and
zero queued evaluations. It streams retained monthly/legacy sources with the old
UTF-8/universal-newline/final-row/legacy-skip policy. Source/readability proofs,
16 MiB active state,4 MiB manifest,2 MiB optional old-file summaries,1 MiB row,
50k exact conditions,4096/2 MiB extras,30s/2 GiB read and60s/4 GiB cycle caps
are explicit. A summary only skips fully validated unchanged old data without
dynamic timestamp defaults. Two roots/64 summaries remain bounded.

Both engine score reads now await this service off the event loop. `None` retains
its original per-cycle score identity; explicit lists bypass it. Timeouts/cancel
quarantine the original worker until unwind; no replacement worker, late-cache
publication or healthy fallback. Teardown is cooperative/idempotent and daemon
ownership cannot block process exit. Normal `stop()` still finishes the cycle.

Typed safety-read failure records a sanitized existing account error, stops its
remaining entry proposals, then runs existing monitor/snapshot once. Later
accounts continue. Already sent notifications/persisted proposal state remain;
no synthetic rejection/fill/duplicate notice is made. Real cancellation propagates.
Long-lived cycle records contain a fresh exception without worker/source frames.

## Verification / limits

Independent multipass oracle covers all42 event types, fixed UTC boundaries,
future events, advisory/fallback and mixed/NaN kill keys. Targeted tests cover
legacy line endings, malformed versus hard failures, source/limits, cache bypass,
quarantine/cancel and paper/live pre/post-notification failures with monitor
continuity, later accounts and drawdown validation. Full regression and exact
source/machine rollout evidence are recorded in the session.

Three independent subprocess million-event pairs have complete score parity:
legacy extra peak RSS2487.7–2703.5 MiB, streamed0.84–1.28 MiB; wall15.0–22.7s
versus8.69–8.79s. This is a local fixed-UTC input benchmark, not page p95/native/
depleted CPU or original1 GiB qualification. Remaining whole-guest/latency failures
keep DEBT-083 active; no weights, live mode or cost allocation is changed.
