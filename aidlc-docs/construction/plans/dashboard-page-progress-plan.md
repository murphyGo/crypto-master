# DEBT-083: Page-dependent dashboard recovery progress

- Unit: `dashboard-operator-ui`; secondary `dashboard-operator-command-center`.
- Queue: Critical DEBT-083; reproduced global-drain coupling in v65 closeout.
- Baseline: main `37b29d7`, runtime source `382c26b`, Fly v65.
- Task: let the existing single page watcher observe its own unfinished read
  generation or queue admission opportunity without waiting for unrelated jobs.
- Stage: bounded implementation refinement of the approved loading/recovery NFR;
  source generation, build/test, same-capacity deployment and operational check.
- Requirements: BDL-NFR-03/04/06/07/08; FR-029/031/032/036/042;
  NFR-003/007/008/011/012; US-012/014/020/023.
- Authority: user's `고칠 수 있음?` follows the registered correction candidate;
  earlier sequential commit/push and deployment/operations authorization remains.
  No new infrastructure, cost, credential or trading interpretation is needed.
- Isolation: `/private/tmp/crypto-master-page-progress-20261027`.
  Preserve root `.claude` work and all other worktrees.

## Existing approved constraints

This changes when a useful page rerender is noticed, not what constitutes a
verified result. Keep one worker, four admitted jobs, one watcher per page,
4 s foreground bound, 2 s complete-result freshness, 30 s explicitly stale
fallback, all memory/root/source-proof limits and manual-only terminal retry.
No busy-loop polling, worker replacement, new background scheduler, payload
retention in progress handles, or read/admission side effects from polling.

The v65 four timeouts and older v64 failures remain failed observations.
Global-drain coupling is reproduced independently; it is not proven to be the
sole cause of those timeouts. Full cold/native/depleted/original 1024 MiB
acceptance remains open regardless of the bounded source correction.

## Work and ownership

- [x] Lead: refresh source/remote/runtime and approved requirements; isolate task.
- [x] Developer and QA: agree a bounded progress-handle design, covering exact
  job generation, queue capacity, close/eviction and session independence.
- [x] Developer: retain a failing regression on the baseline; implement only
  `read_models.py`, `data_service.py`, `availability.py` and targeted tests.
- [x] QA: independently review source and tests; exercise unrelated jobs,
  capacity release, ABA/completed-generation race, multiple sessions, terminal
  failures, unchanged freshness and callback ownership/resource bounds.
- [x] Lead/QA: focused tests, full pytest, changed-file Black/Ruff and source mypy.
- [x] Docs audit: update session/cross-check, current state/debt and this plan;
  distinguish source delivery, observed readiness and remaining qualification.
- [x] Lead: commit/push scoped correction and confirm exact remote source.
- [x] Lead: deploy exact validated source on existing configuration; confirm
  hashes/health and run one four-session protocol observation. Preserve its
  health-guard failure; a full cycle completed only after the closed window.
- [x] QA/docs: preserve all outcomes, compare the reproduced behavior and
  production result, commit/push final operational evidence separately.

## Design applicability and existing answers

- Resilience: [Answer]: observe relevant progress only; terminal failures keep
  explicit retry. Existing user-authorized recovery policy is unchanged.
- Scalability: [Answer]: existing one/four worker/admission limits and bounded
  per-render handles; no session-count multiplier on rebuild jobs or retained data.
- Performance: [Answer]: preserve original 5/2 s complete-readiness targets and
  separate 5 s incomplete shell target; a faster subset cannot hide failures.
- Security: [Answer]: no new external interface, identity logging or credentials;
  progress handles are private, nonserialized, excluded from equality/repr.
- Components: [Answer]: existing service and Streamlit watcher; no new service,
  cost, deployment topology, package or engine-cadence requirement.

## Verification commands

Target dashboard availability/data-service/read-model tests first, then the
full suite using the existing qualified Python environment. Run Black/Ruff on
changed Python files and mypy on `src`. Use an actual local Streamlit AppTest
where useful; it does not replace native Browser acceptance. The production
observer remains `scripts/observe_dashboard_protocol.py` with a fresh output
directory and all failures retained. Do not force engine cycles or overlap
production observers.

Independent design review is GREEN: compact events avoid Future/payload retention;
queue readiness mirrors normal identity/admission semantics without mutation;
per-render latches do not consume shared completion. The implementation is held
to the race/bounds tests above and receives an independent source review.

Final source gate: 3,008 tests pass in 231.58 s on Python 3.13.0, with all
261 source/test/script hashes unchanged. Black/Ruff pass seven changed files;
mypy passes all 135 source files. Independent coverage is 77 focused cases and
a real two-session Streamlit fragment smoke. The first full run exposed three
old one-argument test mocks; their single optional-argument fixture update
preserves assertions and runtime hashes. Both iterations are retained.

Source `ce5c4f5eb71a1954ec264c0380eaa7e5c4b0742d` is confirmed on remote
main and deployed as v66 by the existing-machine rolling command. All 182
runtime hashes match. The 1800.914 s observation is FAIL_SAMPLE: 352/356 complete,
four guard-aborted requests and a 5.219 s health TimeoutError during observed
CPU throttling. A full natural cycle is absent inside the window; subsequent
cycle completion and restored health are separate recovery evidence. No rerun
storm or persistent process failure is observed, so v66 is retained. Original
cold/native/depleted/1024 MiB acceptance remains open; follow-up is bounded
profiling of dashboard baseline and engine-burst CPU cost, not another
unattributed watcher patch or capacity/cost change.
