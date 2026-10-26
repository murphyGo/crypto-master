# Dashboard and runtime bounded reads implementation and rollout

## Authority and preserved work

Operator `gogo` approves both concrete NFR designs, the typed safety-read
monitoring amendment and their presented implementation/test/same-capacity rollout
sequence. No repeated stage permission is required for the same scope. Cost/
performance-CPU proposal stays deferred. Work is isolated; root configuration and
scheduled-task lock remain untouched. The three separately authorized strategy
corrections and their v63 rollout docs are preserved from upstream4b714fd.

## Resulting behavior

Runtime safety reads no longer materialize/sort all rich activity models. A
canonical one-event stream and exact single-pass reduction run on one bounded
process-owned daemon, with30s/read and60s/cycle work budgets. Explicit-extra reads
never fall back to an old score. Typed failures stop new entries while existing
position monitoring/snapshot still runs once; later accounts continue. Same
score weights, live intent, account policies, SL/TP and CLI providers remain.

The existing dashboard worker optionally reuses validated source-file reductions
from a private64 MiB total derived store on the existing volume. Global cycle/
companion/window/tie calculations remain exact. Snapshots reuse whole unique
account files with their existing curve semantics; ledger keeps sequential float
math. Small proposal files (average<16 KiB) use the measured faster canonical
path; larger proposals have typed compact checkpoints. Cache/codec/lock/disk
faults cannot hide valid canonical data. No canonical writer lock or data migration.

Lossless framed JSONL avoids an unbounded intermediate tree; packs are<=1 MiB,
stricter than approved maxima. Existing16 MiB cache includes the packed-index
reservation, and the16 MiB active/4 MiB manifest limits include optional work.
One shared lock per query is released for atomic owned-only publication/cleanup.
No65th temp can exceed the64-file admission cap. Free-space floor/reserve remain
192/128 MiB. `DASHBOARD_CHECKPOINTS_ENABLED=0` selects canonical-only operation.

## Source verification

- Final regression: **2916 passed in60.35s**; changed11 Python files Black/Ruff
  pass; mypy passes134 source files.
- Independent multipass safety oracle, all42 types, UTC/future/advisory/dedup
  edges, one-shot lifetime, legacy parsing, hard failures, timeouts/cancellation,
  cache bypass and paper/live pre/post-notification no-entry/monitor continuity.
- Restart/full-payload cache parity, cross-file companions, rebased ties,
  snapshot curve/dynamic defaults, proposal windows/group universes, corruption,
  disk/atomic/lock/owner/symlink faults, two roots and global budgets.
- Million-event safety input3 alternating subprocess pairs: complete score parity;
  extra peak RSS2487.7–2703.5 MiB→0.84–1.28 MiB; wall15.0–22.7s→8.69–8.79s.
  This is an input benchmark, not full-page/native/original-guest qualification.
- Twenty fixed-source projection pairs: million seeded restart p957.817→0.695s;
  13-account snapshots2.087→0.070s; exact full payloads match. Unseeded million
  remains11.143s, so the original5s cold target is not closed.
- Measured small-proposal cache regression is retained as failed intermediate
  evidence. Final admission uses canonical reading:20 pairs p951.327/1.367s,
  zero disk hits and identical results. No cache speedup is claimed for that case.

Evidence includes exact source hashes and drivers under the two unit code folders.
The activity/snapshot matrix precedes only the final proposal-only admission
conditional; proposal is separately remeasured on final hashes and the full
regression gate follows that conditional. This boundary is explicit, not hidden.

## Operational boundary

Build on verified v63 image digest106055713d985c44720c6386de719c500dff8113dfdc894dab8b2b0b54fc3187,
copy tracked source only, run target-Python compile check and install no packages.
Keep existing machine6835752b711958, sharedCPU1/2048 MiB, encrypted1 GiB volume,
paper/Codex, cadence and dependencies. Verify exact running artifact hashes,
health, processes and a new engine cycle after rollout. The four-session protocol
harness records every request start/outcome and drains normal-end requests;
timeouts/partials/cancellations remain failures. Native Browser bootstrap still
fails missing its packaged service. No substitute is called native acceptance.

DEBT-083 remains Critical/active until original cold/depleted/native/declared-guest
acceptance actually passes. Build/source/operational results are separate and
will be appended with the exact release/image/cycle evidence after rollout.


## V64 deployment / initial operational checkpoint

- Deployed source `dca38fbf25a9b96ec91400b628bc71513cf3357d`; remote main
  exact SHA confirmed. Fly release64 on original machine6835752b711958.
- Image digest `sha256:a0e1bd753ba92935c7227bb7c1c5f52fa267eebe2784d1ece99c0a1fab070786`;
  target-Python compile check passed; no package install. All180 runtime hashes
  match. Python3.13.16 / Streamlit1.65.0 / pandas3.0.6 / Pydantic2.14.0/core2.50.0 /
  NumPy2.5.4 are unchanged. Same sharedCPU1/2048 MiB/encrypted1 GiB volume,
  paper/Codex/Astra/1800s cycle interval. Fly checks and public health pass.
- First v64 paper cycle `4e40fc4d-6ad3-47e4-bc6a-0bf307cc51f9` starts
  2026-10-25T17:39:25.480138Z, completes17:39:40.574350Z,12 monitor passes,
  zero proposal/open/close events and no cycle error. It does not prove the new
  read path was naturally exercised by a proposal; local negative/integration
  evidence and a separate read-only deployed-input check cover that boundary.
- First observed server protocol pair is complete: Home17.838s / Trading0.960s,
  at most one watcher, no incomplete alert. This is one pair, not cold p95;
  Home still misses5s. Four20s sessions are in observation through the next real
  engine cycle, with every request start/outcome retained and no censoring.
- A further20 fresh local Python processes per fixture include imports/service
  startup and data query: p95 million2.816s, snapshots1.862s, small proposals4.042s;
  all complete/full-payload equal. These are data-query process tests, not full
  Streamlit pages, Fly restarts, native viewports or original1GiB acceptance.
- Root now contains a concurrent different runtime safety implementation. The
  attempted fast-forward was safely rejected; no stash/reset/overwrite followed.
  Root HEAD remains4b714fd and its work is preserved. Both original configuration/
  lock hashes are unchanged; isolated source only is deployed. Clarification about
  that concurrent work was asked asynchronously; no answer/cleanup is inferred.

CPU metrics are normalized by100 because Fly documents balance/throttle units as
centiseconds in [Instance Load and CPU](https://docs.fly.io/monitoring/metrics#instance-load-and-cpu).
The observed0.0625-CPU baseline is kept separate from remaining burst credit;
no depleted-CPU pass is inferred without actual depletion/throttling evidence.


## Final observation and current deployed-input verification

The29m07s four-session run is **not a complete-readiness pass**:349 starts have
349 outcomes,347 complete and two Home incomplete; no timeout/cancellation/
censoring. Home172/174, Trading175/175. Successful-only p950.761/0.724s cannot
remove the failures. All347 health checks pass (max0.269s), dashboard growth is
83.902 MiB and guest use peaks708.25 MiB on the current2GiB guest. The complete
natural engine cycle is18:09:40.673–18:10:00.940 UTC with12 monitor passes and
no cycle error. Both Home failures overlap that cycle; no stable reason or
first-shell timestamp was retained, so source churn/queue saturation are
hypotheses, not demonstrated causes. No incomplete-shell5s claim is made.

The measured CPU balance stays positive (12.77–30.76 CPU-seconds within the
observation) and sampled throttle is zero. This is not depleted-CPU acceptance.
The708.25 MiB observation is not original1GiB qualification. The first observed
Home17.838s and twenty canonical no-store query p957.817s remain cold failures.
The historical11.143s first_unseeded field did not prove an empty store; retain
it as a labelled observation. The fresh-process20-query results likewise do
not certify full Streamlit/native/Fly restart readiness.

Independent reconciliation and cold profiling are preserved in upstream5fcad54;
see [qualification continuation](2026-10-26-dashboard-v64-qualification-continuation.md).
The next diagnostic slice needs bounded status/reason/age/queue/stage and first-
shell evidence before choosing retry changes. No speculative retry or unrelated
source change is deployed here. Identical frozen raw files are reused rather
than committing duplicate datasets.

At2026-10-26T01:46:38Z a separate **read-only deployed** safety stream processes
230271 canonical rows from7 files (96190075 bytes), completes in2.541s with
0.625 MiB added peak RSS and exactly matches an independent streaming count/
score oracle. Before/after source generations match; no canonical write, order
or forced engine cycle is performed by the probe. This later probe is outside
the concurrent observation and cannot qualify that run's memory/CPU conditions.
The private derived cache has16 owner-only files and6.297 MiB charged usage,
well below64 MiB; free space is707.695 MiB. No volume/cost change is made.

Current verification at01:57:36Z again confirms180/180 hashes, unchanged
Python/dependencies/paper-Codex and the same engine/dashboard PIDs655/656.
A later natural paper cycle01:44:21–01:44:46 has five generated/accepted
proposals, four position-open events, one rejection, twelve monitor passes and
no cycle error. This is naturally occurring runtime coverage, separate from the
read-only probe; the probe did not trigger it. Browser bootstrap was retried
again and still fails before page selection with the missing packaged service.

The parallel candidate was archived as8053ae0, not merged/deployed; main adopted
v64 and its independent docs. The earlier async conflict question is superseded
by that observed reconciliation. Unrelated configuration/lock changes are kept.
Implementation, validation, rollout and observation are recorded; **DEBT-083
remains Critical/active** for Home completeness/cold/native/original-resource
acceptance. The application remainsv64/dca38fb; this closeout changes docs only.
