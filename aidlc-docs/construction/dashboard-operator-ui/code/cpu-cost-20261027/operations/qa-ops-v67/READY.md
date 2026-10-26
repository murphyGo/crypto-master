Offline operational audit adapter ready

This folder does not start an observer, Fly call, measurement, deployment, or network request. v67 is only the anticipated phase; confirm actual release, source manifest, image/config and unchanged observer hash before using the final paths. Source correctness QA is separate under ../qa/.

Adapter changes are limited to v66 -> v67 filenames, the current worktree's observer source path, and correction of the CPU interpretation sentence. No acceptance thresholds changed. adapter-self-check.json proves the complete v66 summary is identical and the detailed audit differs only in dynamic audit timestamps and manifest path. It retains FAIL_SAMPLE, 356 starts/outcomes, 352 complete, 4 guard-aborted, one health failure and no full cycle in the observation window. CPU series also match, including positive throttle with low positive balance.

Expected future evidence paths (must not be reused for a different release):
- ../v67-observation/v67-*
- ../v67-diagnostics-framed.jsonl
- ../v67-cpu-final.json

Freeze raw/context only after observer exit and final health file exists. Initial copies preserve source generation, content hashes and sizes; freeze-manifest.json prevents a second initial freeze. Replay only uses --audit-frozen. Diagnostics are copied separately after the parent confirms collector termination. CPU is a separate immutable supplement, with coverage restricted to the original page observation interval.

Commands to execute only once the corresponding final evidence is available:

    python3 audit_v67.py --wait-seconds 0
    python3 supplement_audit.py --diagnostics ../v67-diagnostics-framed.jsonl --name diagnostics-supplement
    python3 supplement_audit.py --cpu ../v67-cpu-final.json --name cpu-supplement
    python3 cpu_window_proof.py

The CPU proof pins the existing crypto-master instance 6835752b711958. Confirm that identity with the parent's deployment record; a changed instance requires an explicit provenance/path adjustment before capture. It does not fetch identity itself.

First-shell offsets are protocol receipt times, not native rendering. Intermediate query diagnostics are not failed-page counts. Async delivery timestamps provide temporal overlap only. Completed-only and all-attempt latency distributions remain separate, guard aborts remain censored outcomes, and any post-window recovery cannot qualify the original interval. Preserve warmup misses and all failed attempts. Positive sampled balance alone is neither unthrottled nor depleted-load acceptance.

No native, cold/process-cold, depleted CPU, or original 1GiB acceptance claim follows from this adapter or replay. The existing production configuration remains a separate evidence record.
