# Proposal refresh CPU correction — evidence

The single runtime change is in `src/dashboard/projections.py`: do not rebuild
all proposal source objects for an optional checkpoint decision when that
decision cannot be used. `design.md` describes the unchanged source proof,
window, budget and size-threshold contracts.

`developer/` retains the measured baseline, all twenty alternating local CPU
pairs, full-output hashes, fixture/source manifests, the initial method-label
correction and source regression iterations. `artifact-manifest.json` lists
the copied files and exact hashes; raw runtime fixtures, logs, derived stores
and binary profiler files are excluded. Initial missing-store-root mistakes
remain visible with their corrections. Actual enabled-store page AppTest is
corroboration with only two warm samples per page; it is not native acceptance.

`qa/` holds independent design/source review, 175 targeted test passes,
Black/Ruff checks, mypy for 135 sources, exact window-boundary proof and an
independent paired-benchmark audit. The final full regression passes 3,021
tests in 228.36 s on Python 3.13.0, with all 262 source/test/script input hashes
unchanged. `source-qualification.json` and `full-pytest.txt` retain the command,
environment, timestamps and complete output.

Median local query-service CPU falls 30.20% for Home and 29.70% for Trading,
with identical full payloads in all twenty pairs. Direct proposal refresh falls
34.38% without checkpoints and 35.16% with explicitly prepared checkpoints.
The controlled services prime only verified encoded results at expired ages;
they run real generation revalidation. They are not full-page/native or guest
latency measurements. Concurrent host testing is disclosed for wall times.

`engine-context/` is a separate read-only historical snapshot serialization
profile. It establishes another existing cost, without changing engine code,
asserting a production CPU fraction or assigning the v66 failure to it.
The valid activity-append replay in `developer/` likewise retains full result
parity and demonstrates that changed activity rebuilds are outside this fix.

Exact-source delivery and a same-configuration operational observation follow.
The prior v66 FAIL_SAMPLE and original cold/native/depleted/1024 MiB gates
remain open; local performance improvement does not erase operational failures.
