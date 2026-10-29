# V68 operational qualification and exact-image rollback — 2026-10-29 KST

**Outcome:** The resumed v68 sample fails. Activity source-change recovery
exhausts and remains unavailable after stable input, including on two fresh
connections. The existing rollback criterion was met. Fly **v69** now runs the
previous v67 image, source **`120b440`**, with all 182 runtime hashes and unchanged
configuration verified. Home/Trading complete again. **DEBT-083 stays Critical.**

Unit: `dashboard-operator-ui`; related `dashboard-operator-command-center`,
`notifications-ops`. FR-028–032/036/038/042, NFR-003/007/008/011/012,
US-012/014/020/023; BDL-NFR-02/03/04/06/07/08. Legacy phases 7, 8.2 and 19.3.

User “계속 진행” resumed the stopped operational work. Fly authentication was
initially absent; the user completed login. Sandboxed credential access failed
for the wrapper and the approved execution passed. These were local preflight
limitations, not production health failures. No application source was changed.
The observation began on October 28 KST and crossed midnight; UTC times below
are retained without conversion in raw evidence.

## Resumed observation

The unchanged `scripts/observe_dashboard_protocol.py` ran four actual Streamlit
WebSocket sessions at 20 s cadence, with the existing minimum 600 s, maximum
2100 s, 30 s page deadline, health/memory abort guards and natural engine cadence.
Before and after, v68 source `7b87d9a`, all 182 runtime hashes, dependencies,
settings, machine, volume, instance and engine/dashboard process identities match.
The deployed protobuf descriptor matches the historical digest.

| Evidence | Result |
|---|---|
| Formal window | 2026-10-28 14:55:39.459873–15:05:49.905432 UTC; **610.445559 s** |
| Recorded requests | **120 starts / 120 outcomes: 4 complete, 3 timeouts, 113 incomplete** |
| Per page | Home 2/60 complete; Trading 2/60 complete |
| Health | 121/121 successful and <5 s; maximum 2.037698 s |
| Natural engine cycle | `9c4354b0-71e6-421a-bd82-941723c45a74`, 35.832690 s; 12 monitor passes, zero cycle errors; 3 proposals/rejections, no opens/closes |
| Memory | Guest peak 676.625 MiB on configured 2048 MiB; observed dashboard RSS growth 0 MiB; historical process HWM minus warmed baseline 8.441406 MiB |
| CPU | 41 in-window samples; burst balance 456.830–500 CPU-seconds; no sampled throttle-counter increase; 15 s grid with surrounding brackets |
| Separate initial warmup | Home 7.321074 s, first incomplete shell 4.926641 s; Trading 0.458902 s |

The four successful records have the expected metric labels/counts, non-placeholder
values, complete element shape and no incomplete alerts. Their successful-only
p95 values cannot turn a failed sample into a pass; neither page has twenty
successful observations. The warmup is one pair, not cold-percentile evidence.

The observer records starts/outcomes bijectively but does not join server response
generation IDs. After a timeout, queued messages can contaminate the next reused
socket's page/timing attribution; very short incomplete records occur here. Thus
120/120 is a record-accounting claim, not proof of exact server-request attribution.
Separate fresh connections below corroborate the actual persistent failure.
Keep this observer limitation attached to DEBT-083's next qualification work.

## Persistence and rollback decision

Allowlisted diagnostics show two activity `retry_scheduled` events, then
`source_changed` / `retry_exhausted`, followed by repeated `error_cache` outcomes.
The engine's write period outlasts the finite attempts. Source code inspection
confirms that the v68 latch deliberately survives normal rerenders and error TTL.
This is operational unsuitability of the approved finite/manual-terminal policy;
the earlier source tests verified that policy and did not establish suitability.

At 15:14:55–15:15:15 UTC, a separate read-only probe rediscovers all **7 selected
activity files / 97,090,668 bytes**, hashes their complete contents and performs
full manifest generation verification twice. Membership/generation digest and all
content hashes match across the 20 s interval. This is endpoint stability evidence,
not proof about every instant or every runtime source. Immediately afterward,
two new Home WebSockets return activity-unavailable with no watcher in
0.558387/0.565130 s. They have no responses queued from the original sample.
No manual retry, cache clearing or source write is used to obtain this evidence.

These observations satisfy the plan's existing rollback consideration: persistent
new page unavailability after retained stable-source evidence. CPU samples show
ample burst balance and zero new throttling; neither CPU depletion nor an exact
writer/verification-branch causal join is claimed. Async diagnostic timestamps
and local/Fly clock differences also prevent precise request-level attribution.

## Exact-image mitigation and verification

Restored image:
`registry.fly.io/crypto-master@sha256:2aa60d27cf4aed283b9e4596e17cf3403f39b88794b3347f5abeb40462700382`.
This is the exact prior v67 image, source `120b4408dc0d3eedb241edf26f8f161c062cf126`.
The new Fly release is **v69**, instance `01M61HDNQ1BNPYJJ2X8NNQ46YZ` on the existing
machine `6835752b711958`. Only one existing machine was targeted; no image build,
new machine, new volume, capacity change or dependency installation occurred.

The two image source differences are `data_service.py` and `read_diagnostics.py`.
The previous CPU optimization and all earlier bounded reads remain. Post-rollback
verification matches all **182 hashes**, dependencies, env, init, services,
restart policy, original encrypted volume, shared CPU 1 / 2048 MiB and paper/Codex.
Public/internal health pass. The startup cycle completes in **25.280011 s**, with
12 monitor passes, zero cycle errors, one proposal/rejection and no opens/closes.
One fresh protocol session completes Home **11.426338 s** and Trading **1.030893 s**.
Home's first incomplete shell is **8.782085 s**: both Home targets still miss.
This is restored availability plus one startup cycle, not renewed four-session
or latency qualification. The restart also clears cache state, so the single
post-rollback pair alone cannot isolate image policy from restart effects.

The observer and diagnostic collector have exited (codes 1 and 0). The original
remote sampler belonged to the replaced v68 instance. Source recovery commit
`7b87d9a` remains in Git for redesign; **do not redeploy that HEAD behavior** until
the persistent-terminal policy is replaced and qualified. Runtime intentionally
uses source `120b440`; this documentation does not assert source/runtime parity
against the current Git HEAD.

## Checks, remaining work and evidence

- Offline observer tests: **48 passed** on Python 3.13.18. Application tests were
  not rerun for this operations-only step; historical 3,048 passes remain historical.
- Independent calculation over retained raw artifacts confirms failed page counts,
  health, full cycle and memory. This is a separate offline calculation, not an
  independent-agent review. Source/runtime validation and rollback checks pass.
- Initial CPU capture lacked a following bracket for the final seconds. A second
  query of the **same original interval plus 30 s brackets** fills that coverage;
  both files and the initial audit are preserved. CPU units/counter semantics were
  checked against [Fly metrics](https://docs.fly.io/monitoring/metrics) and
  [CPU performance](https://docs.fly.io/machines/cpu-performance).
- Browser connector host was unavailable. Native Chrome discovery worked, but
  navigation attempts were rejected because the user changed the app; no task
  viewport or native timings were obtained.
- Next: revise the source-change terminal recovery contract using this long-write
  case, preserve bounded work/full proof and explicit incomplete states, then
  rerun qualification with response-generation-aware observer attribution.
- Cold/process-cold/native/depleted-CPU/original 1 GiB acceptance, all historical
  failed samples, and the deferred CPU-cost decision remain open. No new debt item;
  the findings stay under **DEBT-083**.

Evidence:
`aidlc-docs/construction/dashboard-operator-ui/code/source-recovery-resume-20261029/operations/`.
Key files are `audit.json`, original `observation/`, `activity-stability.json`,
`fresh-session-check.json`, `rollback-verification.json`, before/after/rollback
runtime captures, CPU history/supplement, `observer-tests.xml`, scripts and manifest.

## Delivery checkpoint — 2026-10-30 KST

Evidence/documentation commit **`e14e9be`** was pushed to `origin/main`.
The initial commit attempt lacked local Git author configuration; the successful
command used this repository's existing author identity for that command only.
No global Git configuration was changed. A later read-only status check still
finds v69 and the same rollback image/instance; public health at
2026-10-29T15:24:48Z is200/ok in0.195136s. This is delivery-time health evidence,
not a repeated or extended acceptance run. Local `.tmp/` tooling and scratch
captures remain untracked; only the selected documents/evidence were committed.
