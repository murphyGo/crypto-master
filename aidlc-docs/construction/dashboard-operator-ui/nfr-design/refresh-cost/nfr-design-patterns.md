# Checkpoint encoding cost — NFR amendment, 2026-11-17 KST

DEBT-083, dashboard-operator-ui with persistence-data-integrity; existing
BDL-NFR-02–08 and FR-028–032/036/038/042, US-012/014/020/023 remain binding.

[Answer]: Continuing the approved performance task authorizes this measured
implementation refinement. No new functional/infrastructure decision is needed:
resilience, source proof, security, cache schema/identity, scheduling, one worker,
four admissions, all memory caps, freshness and trading semantics stay unchanged.

## Evidence and selected change

The v72 isolated empty checkpoint-store trial reads eight activity files and
104,776,874 bytes in3.031558s, versus2.104447s without checkpoints; reuse takes
0.644179s. All four direct/empty/warm/profiled outputs have the same source and
payload digests. A separate instrumented trial attributes2.641632 of8.367406s
to checkpoint encoding, including repeated exact recursive size walks. These are
projection timings, not page readiness or an attribution of all previous15s tails.

The existing codec splits containers when `StateBudget.size(value) > 32KiB`.
Only that boolean is needed; computing the rest of a large graph wastes work.
Add an optional `stop_after` cutoff to the same identity-aware size walk. Return
as soon as the nonnegative accumulated charge exceeds the cutoff. With no cutoff,
retain exact traversal and accounting. The codec uses the cutoff exclusively for
its split predicate; all memory admission, state replacement and scratch-budget
checks continue requesting exact sizes.

This preserves the split decision even for shared/cyclic graphs: charging is
monotone and duplicate identities remain counted once within a walk. The codec
still visits/encodes all children and enforces its original depth/row/total caps.
No object/model validation, history row or source proof is skipped. Exact codec
bytes and final projections must match the baseline on supported values.

## Verification

Test cutoff equivalence at below/equal/above exact size for nested/shared graphs,
dataclasses, recursive containers and large scalars. Verify early termination on
large containers and that default budget charges/exhaustion remain exact. Compare
encoded bytes and decoded state against a full-walk oracle, including size limits,
deep/unsupported/nonfinite data. Use alternating baseline/candidate production
trials in standalone processes with isolated disposable /tmp caches; retain all
timings, source/output hashes and process high-water memory. Run targeted/full
tests, formatting/type checks and implementing-agent review before delivery.

Other measured costs (snapshot parsing/eligibility and activity reduction) remain
unchanged. Original native/cold/depleted/1GiB and tail-latency qualification remain
open. No increase to server capacity or cache limits is selected.
