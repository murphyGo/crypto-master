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
