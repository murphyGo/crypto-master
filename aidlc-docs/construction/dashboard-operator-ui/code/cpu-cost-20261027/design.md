# Avoid unused proposal checkpoint admission work

The current proposal projection reconstructs every packed source into Python
`Source`, `Path` and `Generation` objects to compute average source size. That
heuristic selects whether optional per-source checkpointing is economical. It
runs before verified whole-query reuse and when checkpointing is disabled, even
though those paths never consult its result.

On the frozen October 25 Fly snapshot (13,084 proposal files), five exact-source
instrumented unchanged refreshes cost 2.135 s; 1.215 s is this size iteration.
Other query kinds have materially lower unchanged-refresh costs. These local
profile samples identify removable work, not the cause of every production
timeout or a production latency percentile.

The correction changes only `src/dashboard/projections.py`: after the unchanged
source-digest fast return, calculate the average-size heuristic only if
checkpoint preparation succeeded. Preserve the exact arithmetic and strict
`< 16 * 1024 * max(1, manifest.file_count)` cutoff on changed/cold inputs.

Every eligible refresh still discovers membership, computes the source digest,
charges retained state, re-evaluates time windows and verifies all selected
files and directories. A replacement, append or membership change must still
reject/rebuild as before. No validation, filesystem verification, source
coverage, TTL, business metric, checkpoint schema or resource bound changes.

Independent design review is GREEN. Verification covers no-store/prepare-false,
unchanged whole-query reuse with checkpoint preparation, mutated source/member
proof, time-window refresh, small/equal/mixed average-size thresholds, and full
payload equality. Local unprofiled paired CPU measurements are kept separately
from cProfile diagnostics and actual production observation.

The same-machine deployment is authorized by the existing user instructions.
Use the verified immutable v66 base image and copy only this runtime file;
dependencies, configuration, one shared CPU/2048 MiB, volume, engine cadence
and paper/live controls stay unchanged. Run one existing-shape protocol
observation plus a natural cycle; preserve every failure and check exact source
identity. Persistent health/process or bound regression warrants restoring the
v66 digest; a pre-existing readiness miss alone does not.

DEBT-083 remains open until its original cold/native/depleted/1024 MiB conditions
are independently qualified. The v66 failed sample is retained unchanged.
