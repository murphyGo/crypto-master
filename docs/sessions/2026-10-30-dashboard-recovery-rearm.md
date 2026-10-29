# Request-driven recovery after source-change exhaustion — 2026-10-30 KST

Unit `dashboard-operator-ui`; DEBT-083 remains Critical. FR-028–032/036/038/042,
NFR-003/007/008/011/012, BDL-NFR-02/03/04/06/07/08; US-012/014/020/023.
The user's continued-work request authorizes the recovery-policy refinement and
the existing same-configuration delivery workflow. Trading/live controls,
canonical data, dependencies, resources and CPU-cost deferral are unchanged.

## Source behavior and evidence

V68 permanently retained exhausted `source_changed` errors across normal
requests, even after writes stopped. The new immutable error token records an
eligibility time: `max(original admission + 30 s, failure + 2 s)`. A later
ordinary request can then start one new shared job. Each episode still has at
most three attempts, one original cooperative window, the same Future/progress
event, fair scheduling and full canonical-generation verification. There is no
timer or idle-page retry loop. Explicit retry can bypass the cooldown only for
its captured token; an old callback cannot erase a newer failure/job.

At most64 failure tokens plus active reservations remain. Unexpired source-error
tokens are protected from eviction; expired ones release capacity. Other errors
keep their existing2s TTL without in-job retries. Freshness/staleness ages never
renew on failure. This is an episode bound, not a sliding3-attempt/30s guarantee.

Three regression cases fail before the source change and pass afterward:
long writes followed by stability, a failure after the30s window retaining the2s
cooldown, and read-only progress plus four-client coalescing after eligibility.
Tests also cover exact boundary timing, old callback identity, bounded metadata,
manual retry, cache age, real file replacement/append and checkpoint behavior.

The protocol observer now retains a timed-out request as failed and closes its
socket before opening the next request's replacement. Reconnect time is included
in the next elapsed time, and replacement never overlaps the previous connection.
A regression test with a queued old response fails before this change. This
addresses the observed timeout contamination; it does not implement a general
server script-run-ID join or native browser acceptance.

## Checks

- Locked local Python3.13.18 environment, Streamlit1.57.0. Deployed1.65.0 remains
  unchanged. Frozen `uv sync --extra dev`; no lock/dependency edits.
- Initial targeted run:82pass/1fail. One tiny activity read exceeded its4s
  foreground wait on this first run; its XML is retained. Unchanged rerun83/83
  passes. This is not evidence that cold latency meets the production target.
- Recovery/observer targeted checks after final edits:80passed.
- Full regression: **3,053 passed**, five existing JUnit `record_property`
  compatibility warnings,86.20s. No failures/skips.
- Black on the four changed Python files, Ruff on those files, mypy across
 135 source files and `git diff --check` pass.

## Initial-load diagnosis

A separate read-only process on current v69 performed sequential initial
projections and then verified previous-result reuse at one fixed evaluation time.
No checkpoint or canonical data was written. It emits metadata/payload hashes,
not source rows. Python imports and OS caches are warm; this is neither process
cold nor browser timing and is a single trial per kind.

| Query | Initial wall seconds | Verified reuse seconds | Selected input |
|---|---:|---:|---|
| Activity |2.215596|0.007742|7files,97,438,217bytes,233,495events|
| Ledger |0.110500|0.002339|13files,1,110,717bytes|
| Snapshots |3.553279|0.011749|13files,34,432,056bytes|
| Candidates |0.012475|0.000338|1file,856bytes|
| Proposals |1.105970|0.115597|13,271files,16,469,074bytes|

All five initial/reuse payload hashes match and every source coverage is verified.
The sequential initial work totals about7s before rendering/network overhead,
already beyond Home's5s target. A separate instrumented activity trial attributes
most time to event reduction, with state-budget accounting and JSON validation
also material. Profiling overhead is not mixed into the unprofiled table.
No speculative parsing/proof shortcut is included. Snapshot initial reduction
and persisted verified summaries are follow-up candidates requiring parity and
source-generation evidence; DEBT-083 retains this performance gap.

## Delivery

Source and local gates are ready. Runtime is still v69/source120b440 at this
checkpoint; deployment and bounded four-session/natural-cycle observation follow.
All historical failed samples, native/cold/depleted/original1GiB requirements and
the shared CPU1/2048MiB configuration remain in force.

Evidence: `aidlc-docs/construction/dashboard-operator-ui/code/recovery-rearm-20261030/`.
Plan: `aidlc-docs/construction/plans/dashboard-recovery-rearm-plan.md`.
