# Session: DEBT-061 per-strategy fail-closed-rate observability

## Unit

- `proposal-runtime` (primary — counter instrumentation + persistence)
- Secondary unit: `dashboard-operator-ui` (Strategies page column)

## Related Requirements

- FR-028: Show strategy status in the dashboard — closest match for the
  per-strategy fail-closed-rate column landing on the Strategies page.
- FR-014: Store proposal history and outcomes — closest match for the
  proposal-engine-side counter persistence (`data/performance/<sub_account_id>/<technique_name>/fail_closed.json`).
- No requirement in `aidlc-docs/inception/requirements/requirements.md` is
  scoped specifically to proposal-engine observability; FR-028 / FR-014 are
  the closest existing entries, surfaced for future-readers in case a more
  specific requirement is ever filed.

## Scope

Shipped DEBT-061 single-counter fail-closed-rate observability — a
scope-split close-out from DEBT-060 to make a future silent throughput
collapse (the failure-mode that hid ~50% of RSI proposals fail-closing at
the R/R gate for ~12 days after the 1.5 → 2.0 floor bump in `7e9162e`)
visible per-strategy on the Strategies dashboard page rather than requiring
operators to tail logs.

## Changes

- `src/proposal/fail_closed_metrics.py` (NEW) — `StrategyFailClosedCounts`
  Pydantic model (with `Field(ge=0)` enforced via `model_validate(...)`
  re-run on every increment) + `FailClosedMetricsTracker`. Storage at
  `data/performance/<sub_account_id>/<technique_name>/fail_closed.json` via
  `src/utils/io.py::atomic_write_text`. `sub_account_id` is a per-call
  argument on `record_emitted` / `record_fail_closed` / `get` /
  `list_techniques` (constructor default kept only as fallback for callers
  that don't pass per-call).
- `src/proposal/engine.py` — `ProposalEngine.__init__` accepts optional
  `fail_closed_tracker`; `_record_emitted` / `_record_fail_closed` helpers
  (OSError-tolerant) thread per-call `sub_account_id`; three increment
  sites in `_build_proposal_for_strategy`: emit (~L709, post short-circuits,
  pre-analyze), `StrategyError` catch (~L730), `TradingValidationError`
  catch (~L780, the canonical R/R-floor / sizing-failed path that triggered
  the DEBT-060 silent ~50% RSI collapse).
- `src/main.py` — wires `FailClosedMetricsTracker()` into
  `_build_engine_config_phase`.
- `src/dashboard/pages/strategies.py` — `build_summary_dataframe` + `render`
  gain `Emitted`, `Fail-Closed`, `Fail-Closed %` columns; accepts optional
  `sub_account_id` (resolved from `perf_tracker.sub_account_id` when None,
  scoped inside the `fail_closed_tracker is not None` branch to avoid
  `MagicMock(spec=PerformanceTracker)` test breakage).
- `tests/test_proposal_fail_closed_metrics.py` (NEW) — 20 tests incl.
  round-trip / restart / per-call sub-account isolation /
  per-call-overrides-constructor-default / corrupt-file degrade.
- `tests/test_proposal_engine.py` — +8 tests (3 increment-site semantics +
  3 short-circuit non-increment + 2 per-call sub-account routing end-to-end
  via `propose_bitcoin`).
- `tests/test_dashboard_strategies.py` — +3 tests (column shape, end-to-end
  percent, per-sub-account rendering).
- `docs/TECH-DEBT.md` — Moved DEBT-061 from Active to Resolved (same-day
  filing-and-close); Statistics Active 1 → 0, Low 1 → 0, Resolved 56 → 57;
  Change History row added for the 2026-05-13 close-out.
- `aidlc-docs/aidlc-state.md` — DEBT-061 closeout appended to
  `proposal-runtime` row; per-strategy fail-closed-rate column noted on
  `dashboard-operator-ui` row.

## Quant Adjudications

The team-lead routed four semantic questions to quant-trader-expert; the
operator-facing rationale is recorded verbatim because future-readers will
want to know why the shipped behaviour was chosen over alternatives.

- **Q1 (pre-emit data outage)**: kept as "neither emitted nor
  fail_closed". Operator signal "emitted=0 → data outage" stays distinct
  from "fail_closed_rate=high → gate rejection"; conflating destroys the
  triage signal.
- **Q2 (neutral signal)**: kept as "emitted only". Strategies returning
  `neutral` are doing their job — counting as fail_closed would make
  conservative strategies look like they're silently collapsing.
- **Q3 (sub_account_id="default" plumbing)**: 🔴 fixed in second round
  per quant's option (a) — `sub_account_id` is now a per-call argument,
  not a constructor binding.
- **Q4 (per-reason breakdown)**: deferred. DEBT-060 retro signal was
  "emissions still happening but proposals dropped to ~0", caught by a
  single rate column. Per-reason becomes valuable for triage after the
  alarm fires; the cost of shipping it now (reason taxonomy + wider
  dashboard table) doesn't pay until the simple rate column proves
  insufficient. Non-breaking extension: `Dict[str, int]` optional field
  on the snapshot.

## 🔴-and-Fix

The sub-account plumbing defect was caught after the first dev round by
quant-trader-expert (Q3) and fixed in a second dev round per quant's
option (a): `sub_account_id` moved from a constructor binding (which
would have aggregated every sub-account's counters under `default/`) to a
per-call argument on every tracker public method (`record_emitted`,
`record_fail_closed`, `get`, `list_techniques`). The constructor default
is retained only as a fallback for callers that don't pass per-call.
Second-round test additions (7 of the net +31) lock the per-call routing
end-to-end via `propose_bitcoin`, per-call sub-account isolation on disk,
and the per-call-overrides-constructor-default precedence.

The first-round 🟡 from QA (validator enforcement) was addressed in the
same second round: `StrategyFailClosedCounts` now re-runs `Field(ge=0)`
on every increment via `model_validate(...)` rather than relying on the
instantiation-time constraint alone.

## Verification

- `pytest -q`
  - Result: 1843 passed (was 1812; net +31).
- `pytest tests/test_proposal_fail_closed_metrics.py tests/test_proposal_engine.py tests/test_dashboard_strategies.py -q`
  - Result: 106 passed.
- `ruff check src tests`
  - Result: fully clean.
- `mypy src/proposal/fail_closed_metrics.py src/proposal/engine.py src/dashboard/pages/strategies.py src/main.py`
  - Result: clean (no new errors).
- `mypy src` overall
  - Result: 3 pre-existing errors in `src/dashboard/app.py:268,852,865`
    remain (out of scope for this cycle).

## Risks

- Hot-path observability calls (`_record_emitted` / `_record_fail_closed`)
  are wrapped in OSError-tolerant helpers so that disk-side failures
  (full disk, permission flip on `data/performance/`, transient FS error)
  never propagate to interrupt a proposal cycle. **Observability never
  crashes trading.** A side effect: silent loss of a counter increment is
  possible if the disk is failing; this is the chosen tradeoff over
  letting trading stall.
- New file-tree node `data/performance/<sub_account_id>/<technique_name>/fail_closed.json`
  sits alongside the existing performance-records tree. Operators
  inspecting raw storage will see the new sibling files; not a behaviour
  change beyond inventory.

## Future Work (not filed as new DEBT)

- **Per-reason fail-close breakdown** — the optional extension named in
  DEBT-061's suggested resolution; non-breaking extension to
  `StrategyFailClosedCounts` (`Dict[str, int]` optional field).
- **Windowed / rolling fail-closed rate** — operators currently only see
  lifetime cumulative; useful for "last 7 days" triage when a regression
  lands today but the lifetime denominator is large.
- **MagicMock-spec trap** — dev surfaced during second-round dashboard
  test work: `MagicMock(spec=PerformanceTracker)` does not expose
  instance-attrs set in `__init__` (e.g. `sub_account_id`). The current
  `src/dashboard/pages/strategies.py` works around this by scoping the
  `sub_account_id` resolution inside the `fail_closed_tracker is not
  None` branch; any future dashboard feature reading a perf-tracker
  instance attribute will hit the same trap. Note for the next dev who
  edits `src/dashboard/pages/strategies.py`.
