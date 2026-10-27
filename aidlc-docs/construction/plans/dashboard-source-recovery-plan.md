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
- [ ] Docs: session/cross-check/state/debt-map/TECH-DEBT updates.
- [ ] Lead: source commit/push, remote exact confirmation; same-config deploy.
- [ ] Lead/QA: source/image/settings/health verification; one bounded four-session
  observation including a full natural engine cycle; retain every failure.
- [ ] Lead/docs: operational evidence and separate commit/push confirmation.

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
