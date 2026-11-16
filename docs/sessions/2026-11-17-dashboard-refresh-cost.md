# Dashboard checkpoint reconstruction cost — 2026-11-17 KST

Unit dashboard-operator-ui, related persistence-data-integrity. DEBT-083 Critical.
FR-028–032/036/038/042; NFR-003/007/008/011/012; BDL-NFR-02–08;
US-012/014/020/023, legacy7/8.2/19.3. Work began2026-11-16; the user's renewed
“진행시켜” continues implementation, verification and same-capacity delivery.

## Finding and implementation

Main51b8881 and v72/source71c8787 are unchanged. The exact183 runtime hashes,
configuration, image/instance/process identity and health pass the fresh capture.
Direct initial projection costs2.558796s for snapshots and2.483295s for activity.
A separate isolated checkpoint profile shows activity empty-store3.031558s,
direct2.104447s, reused-store0.644179s, with identical outputs. Instrumented
checkpoint encoding accounts for2.641632 of8.367406s, including repeated complete
size walks used only to decide whether a container exceeds32KiB.

`StateBudget.size` now accepts an optional cutoff. Since accumulated charges are
nonnegative, crossing the cutoff proves the comparison without visiting the rest
of that graph. Only the codec split predicate supplies it. All actual admission,
replacement and scratch-budget accounting retains exact default walks. Shared
identity deduplication, codec bytes/schema/depth/size limits, model validation,
canonical input coverage, freshness and worker/admission caps are unchanged.
The all-source compatibility digest changes normally on deployment.

## Validation and measured result

- 36 new tests:32 fail before implementation; all36 pass after it. Threshold
  boundaries, shared/recursive/dataclass graphs, early termination, full budget
  rejection, byte parity and invalid later values are covered.
- 146 targeted tests pass; full suite **3197 passes**, five existing JUnit
  warnings,55.53s. Changed-file Black/Ruff and mypy136 source files pass.
- 242 seeded frozen-baseline comparisons match:112 identical encodings and130
  matching errors, including deep split/size limits.
- Alternating production method order B/C/C/B/B/C uses fresh isolated `/tmp`
  stores and one fixed evaluation time. All six results per kind have the same
  source and payload hashes. Activity median3.076233→2.665976s (**13.34%**),
  snapshot3.235357→3.195256s (no material snapshot gain claimed). All trials,
  including the slower first baseline, are retained. No canonical/cache writes.
- Probe process high-water229364KiB includes both implementations/imports; it
  does not qualify original1GiB memory or process-cold page readiness.

Implementing-agent review used code-review; it is not independent review.
No blocking finding. Reviewed monotonicity, alias/recursive traversal, exact
default memory accounting, byte/error parity and unchanged source/financial
contracts. Only two runtime files change; trading and credentials stay unchanged.

## Delivery and remaining gates

Source commit/push, exact-v72 image overlay,183-file runtime verification and
bounded operational observation are pending. Keep shared CPU1/2048MiB, existing
volume, paper/Codex and1800s cadence. The v72 image is the rollback target.

DEBT-083 remains Critical. The earlier four13.19–15.18s write-wave responses stay
retained. This isolated codec improvement does not establish their sole cause or
close native/cold/depleted/original1GiB/cost qualification. No budget/capacity
increase or stale-as-complete result is selected.

Evidence: `aidlc-docs/construction/dashboard-operator-ui/code/refresh-cost-20261116/`.
