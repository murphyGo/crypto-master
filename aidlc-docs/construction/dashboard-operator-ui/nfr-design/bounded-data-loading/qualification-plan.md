# Qualification Plan: Bounded Dashboard Data Loading

**Status:** Approved qualification requirements. The Code Generation report
records functional tests/local measurements and incomplete performance/native
acceptance; this plan itself does not assert those gates passed.

## Deterministic Contract Tests

| Area | Required cases / oracle |
|------|-------------------------|
| Bounded JSONL | 64 KiB crossings, multibyte UTF-8, absent/newline-terminated files, partial tail, oversized line, invalid JSON/model timestamp, capped work; never accumulate the archive before first yield. |
| JSON object/array | Chunk crossings, escaped strings, Decimal/UTC legacy fields, oversized object, bad separator/trailing data, atomic replacement, genuine empty array versus read failure. |
| Timestamp/latest state | Out-of-order records/files, equal timestamp/source order, naive UTC legacy, latest adverse reconciliation older than 24h, later health-check failure. |
| Cycle and risk | Cross-window/month cycles, earliest terminal plus later error, advisory rejection, repeated/absent ids, per-cycle companion suppression and per-account safety deduplication. |
| Window/aggregates | Exact 24h safety cutoff and Funnel 24h/7d/30d/lifetime inclusive timestamps; original thresholds/classification; latest-per-account equity and complete cumulative totals. |
| Scope/cache | Paper/live, aggregate/default/account and root switching; TTL/expiry even with unchanged files; cache/reducer/manifest byte and key caps; four consumers share one build. |
| Mutation/restart | Replace/truncate, month rollover/legacy source, directory membership/in-place metadata changes, invalidated checkpoint, no durable cache after process restart. |
| Fault/concurrency | Full admission, stale fallback, oversized required state, failed worker, blocking-reader stub, cancellation/close, continuous source changes and no executor/descriptor growth. |
| UI parity | Complete builders match current fixtures; missing data never becomes SAFE/zero/no-position; valid ledger remains visible through activity failure; sampled curves are labeled. |

For pure parity, compare normalized values and stable row ordering against
existing helpers. Oracle inputs can be small complete fixtures; don't invoke
the old full-history implementation on the million-event resource fixture.
Prohibit default render calls to full-history APIs and audit every nested
loader. Source-check Home funnel separately: it is proposal-only.

## Resource and Latency Runs

1. Build isolated incident-scale fixtures (~214,686 events, representative
   86 MiB payload shape) and a >=1M-event fixture. Vary payload sizes,
   month distribution, recent-window density, identities/accounts and corrupt
   inputs; simply repeating one tiny event does not establish capacity.
2. Include representative proposal, trade, snapshot and candidate stores.
   Exercise mutable record replacement and lifetime counts alongside events.
   Fixtures belong in temporary qualification storage, not production `data/`.
3. Declare candidate SHA/dirty slice, Python/Streamlit versions, OS/CPU type,
   configured/usable guest memory, source shapes and baseline engine/dashboard
   RSS. A local Mac result is not a passing 1024 MiB Fly-equivalent gate.
4. Measure cache-cold and process-cold separately, and warm reruns, with at
   least 20 observations for each Home/Trading page/scenario. Record every
   successful completion, partial response, exception and timeout. Include
   process bootstrap/import cost in process-cold timings.
5. Verify complete data plus `script_finished` and meaningful values/coverage,
   not a title/HTML/health response. Show p95, full-completion ratio and
   incomplete-shell latency separately; partial runs cannot hide a cold failure.
6. Sample process/guest memory throughout the run (<=100ms where practical),
   retain RSS high-water evidence, and report baseline/delta/peak and guest
   `(MemTotal-MemAvailable)`. Check cache/reducer counters and worker/handle
   counts, not just final RSS after cleanup.
7. Run four sessions alternating Home/Trading for 10 minutes, plus individual
   Engine/Ops/Funnel checks and scope/root churn. Poll health continuously and
   retain engine activity spanning a complete isolated cycle; extend the run
   if the existing 1800s interval does not yield a complete cycle.

Pass only when BDL-NFR-01..08 all meet their definitions. Expected partial
behavior under deliberately over-budget/invalid fixtures proves safe failure,
not complete-readiness acceptance. If the valid qualification corpus exceeds
a proposed cap or misses latency, report failure and revise the design through
review; do not relabel required data optional or weaken targets silently.

## Repository and Native Validation

Use the targeted dashboard/activity/JSONL/proposal/portfolio/history tests,
then the full suite and normal Black/Ruff/mypy checks from the Functional
Design plan. New parser, budget/cancellation and incomplete-state tests must
cover failure modes rather than merely repeat the implementation structure.

Before a production rollout, prepare a concrete native image/runtime candidate
and authorized deployment/recovery/rollback action. Record deployed source,
full Home/Trading readiness, memory, health and engine continuity separately
from local verification. A restart or larger VM can provide temporary recovery
but does not close the bounded-loading debt. No production action is performed
by this plan; DEBT-082 image work and other metric debts retain their own gates.
