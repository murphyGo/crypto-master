# Dashboard source-generation recovery

- Unit: `dashboard-operator-ui`; related `dashboard-operator-command-center`.
- Queue: DEBT-083 Critical / active; v67 residual-analysis follow-up.
- Requirements: FR-028–032, FR-036, FR-038, NFR-003; story US-012,
  related US-023; legacy phases 7, 8.2, 19.3.
- Stages: Functional/NFR refinement → Code Generation → Build and Test →
  same-configuration deployment and operational verification.
- Baseline: main `7d604ad`; runtime v67 source `120b440`.
- Isolation: `/private/tmp/crypto-master-source-recovery-20261027`.

## Authorization and scope

[Answer]: User says “계속 진행” after the proposed limited read retry and prior
fix/commit/push/deploy/operations instructions. This explicitly authorizes the
source_changed recovery correction; ordinary implementation bounds are selected
here. Prior explicit-only terminal behavior is intentionally refined only for
source_changed while a finite recovery sequence remains active. Other terminal
errors and exhausted recovery retain explicit manual retry. Existing functional
and NFR requirements, acceptance thresholds and deployment configuration stay.
[Answer]: Three total attempts, thirty-second monotonic eligibility window
from original admission, retry delays 0.25 and 0.5 seconds. This bounds additional
cooperative work; it cannot interrupt blocking filesystem IO or promise a hard
wall-clock completion deadline. The first ordinary slow read remains compatible.
[Answer]: Keep one worker/four admissions, four-second foreground wait,
two-second verified freshness, thirty-second stale age, bounded state/cache,
full discovery and generation proof, one page watcher. No stale-as-complete.
[Answer]: Exhaustion is latched across TTL and normal rerenders. Protect at most
cache_entries terminal tokens and reserve capacity for admitted jobs; if full,
fail new admission explicitly without silently erasing exhaustion. Exact-query
manual retry releases its matching token; close releases service metadata.
[Answer]: No changes to credentials, trading policy, engine cadence, resources,
cost, canonical data, dependencies or infrastructure. Historical failed samples
and cold/native/depleted/original 1024 MiB gates remain independently open.

## Work sequence

- [x] Lead: current repository/context and v67 residual evidence reviewed.
- [x] Lead/developer/QA: finite recovery design and bounded metadata policy.
- [x] Developer: deterministic baseline-red regressions and narrow implementation
  in `src/dashboard/data_service.py`, `read_models.py`/`read_diagnostics.py` only
  if necessary, and related `tests/test_dashboard_*`.
- [x] QA: independent race/age/source-proof/manual-retry/close review and tests.
- [x] Lead: final full `uv run pytest`, changed-file Black/Ruff and `mypy src`;
  freeze final source hashes and meaningful source/canonical parity evidence.
- [x] Docs: session/cross-check/state/debt-map/TECH-DEBT updates.
- [x] Lead: source commit/push, remote exact confirmation; same-config deploy.
- [x] Lead/QA: source/image/settings/health verification; one bounded four-session
  observation including a full natural engine cycle; retain every failure.
- [x] Lead/docs: operational evidence and separate commit/push confirmation.

## Required regression coverage

One mutation then stable source; two snapshot replacements then stable source;
four concurrent sessions coalesce; fairness while a retry waits; persistent
churn/attempt and admission-deadline exhaustion; error-TTL cannot reset budget;
terminal metadata capacity; stale age and exact freshness/window boundaries;
canonical output/source verification at actual generation barriers; malformed,
budget and cleanup errors remain terminal; close during backoff/build; same-query
ABA/manual callback does not erase newer failure; one watcher and compact signals.

Verify targeted dashboard/read-source tests first, then full suite. Source
correctness, initial warmup, main observation and original qualification gates
are separate conclusions. Never mark DEBT-083 resolved from local tests alone.

## Operational decision boundary

Source policy correctness does not prove full production recovery. In particular,
three attempts may finish before a long write wave ends; protected exhaustion
intentionally requires manual action instead of v67 passive TTL healing. Preserve
all failed requests and use the same observation contract. Consider rollback to
the exact v67 image for persistent new page unavailability after stable-source
evidence, as well as persistent health/process/bounds regression. Cycle completion
is a timing proxy, not proof that every source stopped changing. Do not hide a
failed sample with manual refresh, retry-budget expansion or a second load run.

User stopped work on2026-10-28KST. Source7b87d9a is pushed/deployed as v68;
182hashes/settings verified. Long observation remains unchecked/incomplete,
with partial16complete outcomes and no full-cycle qualification. All owned
collection processes stopped. Final stop record is committed separately;
resume only on new user instruction.

## Operational continuation — 2026-10-28 KST

[Answer]: User says “계속 진행” after the remaining-work report. Resume the
bounded v68 operational observation and evidence audit. Preserve the original
failed/stopped samples and CPU-cost deferral. No capacity or trading-policy
change is selected.

- [x] Reconfirm v68 image, 182 runtime hashes, settings and process identity.
- [x] Run the existing four-session observer at 20 s cadence for at least 600 s
  and one full natural cycle, bounded by 2100 s and the existing health/memory
  abort guards. Retain warmup separately and every failed request.
- [x] Capture allowlisted diagnostics and recorded CPU history; reconcile
  starts/outcomes, cycle evidence, memory, health and post-run identity.
- [x] Record the outcome in a new session/cross-check, debt, state and unit map.

Related requirements remain FR-028–032/036/038, NFR-003/007/008/011/012,
US-012/014/020/023. This continuation is Operations / Build and Test evidence;
application source is unchanged. Native browser access is currently unavailable
in this session and cannot be inferred from WebSocket results.

The resumed sample crosses 2026-10-29 KST. It already contains activity
`source_changed` retry exhaustion and persistent incomplete page results after
the natural cycle. Finish and retain the bounded sample, then compare full
activity membership/generations/content across a quiet interval and use fresh
connections to distinguish persistence from buffered observer responses. If
confirmed, the existing rollback criterion applies: restore the exact v67
image `sha256:2aa60d27cf4aed283b9e4596e17cf3403f39b88794b3347f5abeb40462700382`
on the existing machine, volume, shared CPU 1 / 2048 MiB and paper/Codex setup,
then verify hashes, configuration, health, page availability and startup cycle.
This mitigates the new persistent failure; it cannot resolve DEBT-083 or
erase the v67 failures. Preserve the v68 source in Git for follow-up design.

**Final operational result (2026-10-29 KST):** 610.445559 s /120 outcomes:
4 complete,3 timeouts,113 incomplete. Health121/121 and full natural cycle pass;
the overall sample fails. Seven activity files/97,090,668 bytes have identical
manifest/content across20s; two fresh sessions still fail. Exact v67 image was
restored as **Fly v69 / source120b440**, with182 hashes/settings and a clean
startup cycle verified. Home/Trading complete11.426338/1.030893s; Home latency
still fails. All failed samples remain. Git retains v68 source, not qualified
for redeployment; next stage is recovery-policy redesign plus observer response
attribution hardening under DEBT-083. See the2026-10-29 session/cross-check.

Delivery confirmed on2026-10-30 KST: operational evidence commit `e14e9be`
was pushed to `origin/main`. A read-only delivery check still finds v69 on the
same rollback instance/image; public health is200/ok in0.195136s. This later
health check is not an extension of the failed observation or a new acceptance
sample. All task observer/collector sessions have ended.
