# Dashboard checkpoint reconstruction cost — 2026-11-17 KST

Unit dashboard-operator-ui, related persistence-data-integrity. DEBT-083 Critical.
FR-028–032/036/038/042; NFR-003/007/008/011/012; BDL-NFR-02–08;
US-012/014/020/023, legacy7/8.2/19.3. Work began2026-11-16; the user's renewed
“진행시켜” continues implementation, verification and same-capacity delivery.

## Finding and implementation

The starting baseline was main51b8881 and v72/source71c8787. The exact183 runtime
hashes, configuration, image/instance/process identity and health passed the
fresh pre-change capture.
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

Source779b60e is committed/pushed and deployed as Flyv73. All183 hashes,
settings/dependencies and health pass. Only checkpoint_store.py/projections.py
are overlaid on exact v72. Shared CPU1/2048MiB, existing volume, paper/Codex and
1800s cadence are unchanged. Image
`sha256:b1fb37ffbba7f93c387c4af4caee85c9c5d21de4b5cc59e3de9edbc1ab810281`,
instance `01M7JMF6WMA4MV26FCE1XFWRZ0`. Startup cycle
`e462b543-2540-474e-ad23-ae4386228c13` completes14.819189s with no cycle error,
proposals or opens/closes and12 distinct monitor accounts. The exact v72 image
remains the rollback target.

The four-session sample runs1627.271215s,2026-11-16 16:57:59.330571 through
17:25:06.601786UTC (Nov17 KST). All325 starts have one complete outcome:
Home162 and Trading163. No timeout, reconnect or shape failure occurs. Home and
Trading p95 are0.628590/0.507615s; all323 health checks pass (maximum0.217347s).
Guest peak649.605469MiB and dashboard RSS growth17.582031MiB are on2GiB.
Collection is continuous. Natural cycle `77c32d78-f79a-42a9-9a82-73989f60624e`
takes16.627561s with12 distinct monitor accounts, no cycle error and no
proposals/opens/closes. Image, instance and engine/dashboard start ticks persist.

The bounded warm protocol audit passes, but five requests exceed2s: Trading
2.338051s and four cycle-overlap requests10.519957–12.306462s. The latter first
show incomplete shells in4.189756–4.310148s and complete automatically. All
requests remain in the evidence; overlap does not identify an individual cause.
The initial protocol pair is separate: **Home14.572192s, first incomplete
shell7.795116s, both fail5s**; Trading0.971223s. One initial pair does not prove
process/cache-cold isolation or a20-sample cold/native percentile.

CPU has109 in-window points per series with15s spacing and both brackets.
Balance28.372215–46.332249CPU-seconds stays positive; sampled throttle increments
and counter resets are zero. All runner stages exit0 and remote sampler cleanup
passes immediately after observation. Daemon recovery delays final recording
until Nov18: the00:18:47.786825UTC late capture still verifies183hashes/settings,
same image/instance/processes; the04:26UTC local check finds no task collector,
observer or matching bounded idle guard. These checks do not extend the sample.
The offline audit uses project Python3.11 after system Python rejected a Fly
nanosecond timestamp; raw observations are unchanged. No application code changed
after the3197-test source validation.

DEBT-083 remains Critical. The earlier four13.19–15.18s write-wave responses stay
retained. This isolated codec improvement does not establish their sole cause or
close native/cold/depleted/original1GiB/cost qualification. No budget/capacity
increase or stale-as-complete result is selected.

Next measure initial startup/import, query and rendering contributions. Home
already shares one foreground deadline, and eager imports address an earlier
deployed Streamlit failure; do not change those contracts on inference alone.

Evidence: `aidlc-docs/construction/dashboard-operator-ui/code/refresh-cost-20261116/`.
