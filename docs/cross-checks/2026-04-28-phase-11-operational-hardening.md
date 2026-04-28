# Phase 11 Cross-Check: Operational Hardening + Observability

**Date**: 2026-04-28
**Phase**: 11 - Operational Hardening + Observability
**Status**: All four sub-tasks complete (11.1, 11.2, 11.3, 11.4)

## Scope

Phase 11 takes the system from "operable in production" (the exit
state of Phase 10) to "hardened against the failure modes a
long-running unattended deploy actually hits". Every sub-task closes
a specific operational gap surfaced in Phase 10's TECH-DEBT carry
forward or its session-log "Follow-up Work" sections. No new
framework abstractions — clean-up, in-process memoization, push
notification, and runtime wiring of an already-tested method.

The phase added **no new functional or non-functional requirements**;
the development plan's Requirements Mapping table records Phase 11
against requirements that were originally introduced in earlier
phases — Phase 11 hardens or extends them:

- **NFR-001** — Python 3.10+ tech-stack hygiene was Phase 1's
  baseline. 11.1 cleared the accumulated lint/type drift across
  `src/ai`, `src/strategy`, `src/feedback`, `src/trading`, tests, so
  a future ruff/mypy CI gate has a clean baseline to anchor on.
- **FR-005** — Analysis Technique Performance Tracking was
  introduced in Phase 3.4 and extended through Phase 10.6's
  multi-technique scan. 11.2 hardens the scan's runtime by
  collapsing the N×M `get_ohlcv` calls per cycle to N+M via a
  per-call `(symbol, tf)` cache.
- **FR-015 / NFR-012** — Proposal Notification (Phase 6.3) and Live
  Trading awareness (Phase 4.4 / 10.1) shipped Console + File
  notifier backends. Live mode runs unattended on Fly; those
  backends page nobody when a real-money trade fires. 11.3 added a
  `SlackNotifier` posting via incoming webhook so the operator gets
  paged.
- **NFR-008** — Mode-separated storage with retention was Phase
  10.4's contract. `ProposalHistory.purge_old` shipped tested but
  unwired; 11.4 added the always-on startup hook in `src/main.py::run`
  and an operator CLI (`python -m src.tools.purge_proposals`) for
  ad-hoc windows.

11.1 was added to the plan as the Phase 11 lead-off based on Phase
10.5's touch-and-verify surfacing of pre-existing lint/type drift
(DEBT-001). 11.2 was added based on Phase 10.6's session-log
follow-up flagging the multi-technique fetch-count compound
(DEBT-002). 11.3 was added based on Phase 10.1's "live mode pages
nobody" carry-forward. 11.4 was added based on Phase 10.4's
explicit deferral of the `purge_old` runtime wiring.

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 11.1 | Pre-Existing Lint/Type Sweep | `src/ai/claude.py` (B904 `from e`), `src/strategy/loader.py` (B904 ×5), `src/strategy/factory.py` (UP035 `Callable` from `collections.abc`), `src/ai/improver.py` (parse-time str-coerce), `src/trading/live.py` + `src/trading/paper.py` (`Literal["buy","sell"]` for closing_side; `Order` import + return-type widening on live), `src/backtest/analyzer.py` (`float(...)` cast for no-any-return), 6 test files (F401/F841/I001 `--fix`), `pyproject.toml` (ruff config → `[tool.ruff.lint]`; `types-PyYAML>=6.0` dev extra), `scripts/lint.sh` (new — flagged DEBT-009) | (no new tests — pure typing/lint hygiene; 1083 existing tests pass unchanged) |
| 11.2 | OHLCV Cache for Multi-Technique Scan | `src/proposal/engine.py` (per-call `dict[(str, str), list[OHLCV]]` cache threaded through `propose_bitcoin` / `propose_altcoins` → `_propose_for_symbol` / `_propose_all_for_symbol` → `_build_proposal_for_strategy`; Option A; legacy `_select_best_technique` path also threads the cache for consistency) | `tests/test_proposal_engine_multi_technique.py` (+4: 3 sym × 4 tech 12→3, multi-TF 2-strategy shared-TFs 6→3, sequential 2× `propose_bitcoin` no-leak, legacy 3 sym × 1 tech no-regression) |
| 11.3 | Notification Push Backend | `src/proposal/notification.py` (`SlackNotifier` implementing existing `Notifier` protocol; `urllib.request.urlopen` + `asyncio.to_thread`; `__repr__` redacts URL; `send` does not swallow `HTTPError`), `src/config.py` (`Settings.slack_webhook_url: Optional[str] = None`), `src/main.py::build_engine` (appends `SlackNotifier()` to dispatcher when URL set), `.env.example` + `docs/deployment.md` | `tests/test_proposal_notification.py` + `tests/test_main_dispatch.py` (+9: exact-string spec match, failure-isolation, build_engine both-branches, `__repr__` redaction) |
| 11.4 | ProposalHistory.purge_old Wiring | `src/main.py` (`_purge_old_proposals(history, retention_months)` helper called from `run()` between `build_engine` and signal handlers; INFO log only when archived), `src/tools/__init__.py` (package marker), `src/tools/purge_proposals.py` (operator CLI; `argparse --retention-months` override; reads `Settings`; informative print on both branches; exit 0 in both), `docs/deployment.md` (new "Operator Tools" section) | `tests/test_main_dispatch.py::TestPurgeOldProposalsHook` (4: forwarding / count / silent-on-empty `caplog`-via-`crypto_master.main`-handler / build-engine→hook smoke against real `ProposalHistory`) + `tests/test_tools_purge_proposals.py` (4: Settings-default / `--retention-months` override / end-to-end Jan-2024-archives-fresh-stays / empty-print) |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-005 | Analysis Technique Performance Tracking | ✅ Complete (hardened) | 11.2's per-call OHLCV cache means every applicable technique on a multi-technique-per-symbol cycle sees the *same* candle T (no temporal drift between technique A and technique B mid-cycle), which is the correctness underpinning of FR-005's per-technique attribution. The cache is local to the `propose_bitcoin` / `propose_altcoins` invocation — strategy decisions get fresh data each cycle (no stale-data correctness defect). `tests/test_proposal_engine_multi_technique.py`'s sequential 2× test pins the lifetime contract; the 3 sym × 4 tech 12→3 fetch-count test pins the dedupe behaviour. |
| FR-015 | Proposal Notification | ✅ Complete (extended) | 11.3 adds `SlackNotifier` as a third backend alongside Phase 6.3's `ConsoleNotifier` and `FileNotifier`. Implements the existing `Notifier` protocol; `NotificationDispatcher` picks it up unmodified. Posts via `urllib.request.urlopen` + `asyncio.to_thread` (zero new dep). `Settings.slack_webhook_url: Optional[str] = None` — non-breaking; notifier silent / not registered when unset. `__repr__` redacts URL (webhook URLs are credentials). `send` deliberately does NOT swallow `HTTPError` — Phase 6.3's per-channel failure-isolation contract handles it in the dispatcher. `tests/test_proposal_notification.py::test_build_slack_payload_text_matches_spec` pins the exact payload format; `test_slack_http_failure_does_not_crash_dispatch` pins the failure-isolation contract. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-001 | Python 3.10+ Tech Stack Hygiene | ✅ Complete (hardened) | 11.1 cleared all in-scope ruff (18 → 0) and mypy (12 in-scope → 0; total 39 → 29 with remainder out-of-scope per spec) errors. In-scope fixes spanned `src/ai/claude.py`, `src/strategy/loader.py`, `src/strategy/factory.py`, `src/ai/improver.py`, `src/trading/{live,paper}.py`, `src/backtest/analyzer.py`, and 6 test files. `pyproject.toml` ruff config migrated from deprecated top-level `select`/`ignore` to `[tool.ruff.lint]`; `types-PyYAML>=6.0` added to dev extras. `scripts/lint.sh` shipped (DEBT-009 records the `--fix`-unsafe-for-CI nit). Zero `# noqa` / `# type: ignore` added. 1083 tests pass unchanged. The remaining 29 mypy errors cluster in 4 modules (`src/exchange/binance.py` / `src/exchange/factory.py` / `src/dashboard/...` / `src/main.py` lambda) and are tracked as DEBT-005 / 006 / 007 / 008. |
| NFR-008 | Asset/PnL History (storage / retention) | ✅ Complete (wired) | 11.4 wires `ProposalHistory.purge_old` (Phase 10.4 method) into the runtime. `src/main.py::run` calls `_purge_old_proposals(ProposalHistory(), settings.log_retention_months)` once per process boot, between `build_engine` and signal-handler installation. Logs INFO only when records were archived (silent on empty so daily restarts don't generate noise). Operator CLI `python -m src.tools.purge_proposals` available for ad-hoc windows that differ from the configured retention. `docs/deployment.md`'s new "Operator Tools" section documents both paths. `tests/test_main_dispatch.py::TestPurgeOldProposalsHook` (4 tests) + `tests/test_tools_purge_proposals.py` (4 tests) cover the helper and the CLI end-to-end. |
| NFR-012 | Live Trading Confirmation / Awareness | ✅ Complete (extended) | 11.3 closes the live-mode unattended-paging gap Phase 10.1 carried forward. Live mode runs on Fly; the existing Console + File notifier backends page nobody when a real-money trade fires. `SlackNotifier` posting to an operator-configured incoming webhook is the simplest push-style backend — no OAuth, easy operator-side mute / redirect. The `Settings.slack_webhook_url` Optional / default-None shape is non-breaking; existing deployments without the env var are unchanged. `tests/test_main_dispatch.py` covers `build_engine` both branches (URL set vs unset). |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-003 | User approval for technique adoption | ✅ Complete (preserved) | No Phase 11 sub-task touches the technique-promotion path. `FeedbackLoop.approve` / `reject` continue to be the only way `experimental/` strategies move to `active`. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-011 | Bitcoin Trading Proposal | ✅ Complete (consumed) | 11.2's cache threads through `propose_bitcoin`'s call chain. Existing single-proposal contract preserved. The sequential 2× `propose_bitcoin` test (no leak between calls, count stays at 2 fetches not 1) pins the per-call lifetime invariant. |
| FR-012 | Altcoin Trading Proposal | ✅ Complete (consumed) | 11.2's cache also threads through `propose_altcoins`. `propose_altcoins`'s dedup-first-then-top-K aggregation order from Phase 10.6 preserved. |
| FR-014 | Proposal History Management | ✅ Complete (extended) | 11.4 wires `ProposalHistory.purge_old` into the startup hook + a CLI. The history-listing API is unchanged — `purge_old` archives into a subdirectory the top-level glob ignores, so `list_all` doesn't surface archived records. |

## Test Summary

- **Phase 11 tests at phase completion**:
  - 11.1: no new tests (pure typing/lint hygiene; 1083 existing
    tests pass unchanged at phase entry).
  - 11.2: 4 new tests in
    `tests/test_proposal_engine_multi_technique.py` (1083 → 1087).
  - 11.3: 9 new tests across `tests/test_proposal_notification.py`
    + `tests/test_main_dispatch.py` (1087 → 1096).
  - 11.4: 8 new tests across `tests/test_main_dispatch.py::TestPurgeOldProposalsHook`
    + `tests/test_tools_purge_proposals.py` (1096 → 1104).
- **Full suite at phase completion**: **1104 passing, 0 failing**.
- **Lint/format**: `ruff check` clean across all Phase 11 source.
  `mypy` clean on touched files; the 29 pre-existing errors
  surfaced by 11.1 cluster in 4 modules and are tracked as
  DEBT-005 / 006 / 007 / 008 (out-of-scope per Phase 11.1 spec).
  DEBT-008 (`src/main.py` lambda) line drifted from 220 → 271 in
  11.4 because of the helper insertion — same code, new line.

## Gaps

None blocking. All four sub-tasks shipped with passing tests and
clean lint/type baselines on touched files.

Two soft items worth flagging — neither is a gap against the
requirements mapping table, both are intentional choices documented
in their respective session logs:

1. **Single push backend (Slack only)** — 11.3 shipped Slack via
   webhook; Telegram / email remain future sub-tasks per the 11.3
   spec. Operators without a Slack workspace have no push channel
   until those land. Fallback (Console + File) still runs, so
   detection is still possible via log scrape; just not push-style
   paging. Same Phase 10.1 carry-forward listed multiple times
   across the 11.x cycle.
2. **`purge_old` is startup-only, no in-loop periodic** — 11.4
   considered the in-loop variant and chose startup-only as the
   simpler shape. Operators on long-running deploys (months between
   restarts) have to either `fly machine restart` or invoke the CLI
   manually if proposal volume grows enough that monthly records
   pile up before the next deploy. Phase 12 candidate if proposal
   volume warrants it.

## Risks Carried Forward

1. **DEBT-005 ccxt typing in `src/exchange/binance.py`** (Low) — 11
   mypy errors blocked on missing ccxt type stubs. Recommended fix:
   hand-rolled Protocol covering the 8+ ccxt methods used. Out of
   scope per Phase 11.1 spec. (11.1)
2. **DEBT-006 `src/exchange/factory.py` shape drift** (Low) — 3
   mypy errors look like genuine API-shape drift, not typing
   hygiene. Needs quant-trader-expert review of the three call
   sites first to determine whether the drift is hygiene or real
   signature mismatch. (11.1)
3. **DEBT-007 Dashboard Streamlit type errors** (Low) — ~13 mypy
   errors clustered across `src/dashboard/{theme,app,pages/trading,pages/engine}.py`.
   Mostly missing local annotations / casts. One focused mini-sweep
   covers all four files. (11.1)
4. **DEBT-008 `src/main.py` lambda annotation** (Low) — single
   mypy error; one-line fix candidate. Line drifted from 220 → 271
   in 11.4 because of the helper insertion (same code). (11.1)
5. **DEBT-009 `scripts/lint.sh --fix` unsafe for CI** (Low) — the
   `--fix` flag silently rewrites source on lintable regressions
   instead of reporting them. Fine for local dev, unsafe for a CI
   gate. Drop `--fix` for CI use, or split into two scripts. (11.1)
6. **DEBT-003 `EngineConfig` remaining-fields env override** (Low,
   pre-Phase 11 carry from 10.2) — `monitor_interval_seconds`,
   `bitcoin_symbol`, `altcoin_top_k`, `actor` remain hardcoded.
   Repeat the 10.2 pattern only when an operator request lands.
7. **DEBT-004 `BaseExchange.get_ohlcv` `since` parameter** (Low,
   pre-Phase 11 carry from 10.3) — `scripts/backtest_baselines.py`
   reaches into `BinanceExchange._client` to paginate. Extend the
   abstract contract once a second use case appears.
8. **Cache lifetime contract is implicit** (11.2) — the cache is
   local to the public-method frame. If a future cycle factors
   `_propose_for_symbol` / `_propose_all_for_symbol` out into a
   longer-lived helper, the lifetime contract has to be re-asserted
   explicitly or the per-cycle freshness invariant silently breaks.
9. **Webhook URL is a credential, not just config** (11.3) —
   anyone with the URL can write to the channel. Codebase treats
   it as a secret (redacted in `__repr__`, logged only as
   presence) but operators must know not to commit `.env` or paste
   the value into PRs.
10. **Spec test brittleness** (11.3) —
    `test_build_slack_payload_text_matches_spec` asserts the exact
    payload string; cosmetic format tweaks must be co-changed with
    the test deliberately. The brittleness is intentional — the
    test is the spec.
11. **Dual-view `ProposalHistory` instances** (11.4) — `run()`
    constructs a fresh `ProposalHistory()` for the purge while the
    engine has its own via `build_engine`. Both default to the
    same on-disk dir so semantics agree, but any future change
    that introduces per-instance state would silently diverge.
12. **No live-engine smoke run in production yet** (10.1
    carry-forward) — the live wiring landed but the operator
    still needs to redeploy Fly to exercise it. The 9-step
    checklist in `docs/deployment.md` should be walked with a
    $100 balance before flipping to live mode at real sizing.

## DEBT Closure Summary

- **DEBT-001 Pre-Existing Lint/Type Sweep** (Medium) ✅ resolved by
  Phase 11.1.
- **DEBT-002 OHLCV Per-Technique Refetch in Multi-Technique Scan**
  (Low) ✅ resolved by Phase 11.2.
- **DEBT-003 EngineConfig Remaining Fields Not Env-Overridable**
  (Low) — remains open (cycle 9 carry, pre-Phase 11).
- **DEBT-004 Baseline Backtest Script Follow-ups** (Low) — remains
  open (cycle 9 carry, pre-Phase 11).
- **DEBT-005 ccxt typing in `src/exchange/binance.py`** (Low) —
  remains open (logged in cycle 9 / Phase 11.1 as out-of-scope
  spillover).
- **DEBT-006 `src/exchange/factory.py` shape drift** (Low) — remains
  open (logged in cycle 9 / Phase 11.1 as out-of-scope spillover).
- **DEBT-007 Dashboard Streamlit type errors** (Low) — remains open
  (logged in cycle 9 / Phase 11.1 as out-of-scope spillover).
- **DEBT-008 `src/main.py` lambda annotation** (Low) — remains
  open (logged in cycle 9 / Phase 11.1 as out-of-scope spillover;
  line drifted 220 → 271 in 11.4).
- **DEBT-009 `scripts/lint.sh --fix` unsafe for CI** (Low) — remains
  open (logged in cycle 9 / Phase 11.1 from QA 🟡).

## Recommendations for Phase 12 (or follow-up)

Based on accumulated TECH-DEBT (DEBT-003 through DEBT-009), the
session-log "Follow-up Work" sections, and the cross-check itself,
the next phase shaping should consider:

1. **DEBT-005..008 cleanup mini-sweep** — bundle the 4 modules of
   pre-existing mypy spillover (ccxt typing in
   `src/exchange/binance.py`; `src/exchange/factory.py` shape drift;
   dashboard Streamlit type errors; `src/main.py` lambda
   annotation) into one focused cycle. Same shape as Phase 11.1's
   resolution of DEBT-001 but scoped to the four out-of-scope
   modules. The factory drift (DEBT-006) needs a quant-trader-expert
   review first to determine whether the type drift is hygiene or a
   real signature mismatch — don't pick blindly.
2. **DEBT-009 `scripts/lint.sh --fix` safety** (Low) — drop `--fix`
   for CI use, or split into two scripts: `lint.sh` (CI:
   report-only) and `lint-fix.sh` (dev: with `--fix`). Document
   the contract in the script header. Pairs naturally with the
   DEBT-005..008 sweep — one PR.
3. **DEBT-003 `EngineConfig` remaining-fields env override** (Low,
   pre-Phase 11 carry) — repeat the 10.2 pattern for whichever of
   `monitor_interval_seconds` / `bitcoin_symbol` / `altcoin_top_k` /
   `actor` actually needs operator-tunability in practice. Revisit
   if an operator request lands.
4. **DEBT-004 `BaseExchange.get_ohlcv` `since` parameter** (Low,
   pre-Phase 11 carry) — extend the abstract contract with an
   optional `since: int | None = None` parameter and drop
   `scripts/backtest_baselines.py`'s `_client` reach-around. Revisit
   if a second use case appears.
5. **Telegram or email notification backend** — Phase 11.3 only
   shipped Slack; Telegram / email remain future sub-tasks per the
   11.3 spec. Same Phase 10.1 carry-forward listed multiple times
   across the 11.x cycle. Operators without a Slack workspace have
   no push channel until those land.
6. **Periodic-in-loop `purge_old`** vs the current startup-only
   hook — Phase 11.4 considered this and chose startup-only as the
   simpler shape. Phase 12 candidate if proposal volume grows
   enough that monthly records pile up between deploys / restarts.
   The same `_purge_old_proposals` helper would extend naturally to
   an in-loop call site.
7. **Operator runs**:
   - `python -m scripts.backtest_baselines` (Phase 10.3 leftover —
     populates `docs/baselines.md` reference numbers; cheap,
     unblocks "is the LLM beating the baselines?" measurement).
   - `python -m src.tools.purge_proposals` (now available — manual
     lever for ad-hoc retention windows that differ from the
     configured value).
   Both ready, neither yet executed in production.
8. **Live-mode smoke checklist execution** (10.1 carry-forward) —
   operator action, not a sub-task. Walk the 9-step checklist in
   `docs/deployment.md` with a $100 balance before flipping
   production to live mode at real sizing.
9. **Retire `_select_best_technique`** (10.6 carry-forward) — once
   the multi-technique path has accumulated production miles and
   the `multi_technique_per_symbol=False` rollback flag has not
   been exercised, drop the legacy single-selection code. Cleanup,
   not urgent.

## Cross-Check Result

- ✅ Complete: 9 requirements (2 FR + 3 NFR + 1 CON + 3
  phase-adjacent consumed)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 11 closes. The development plan's Current Status table now
shows every Phase 11 row as ✅ Complete. The mainline has no
non-deferred unchecked items. Carried-forward deferrals: 7.5 Tapbit
(longstanding) and the soft items above (none blocking).
Recommended Phase 12 shaping above the line: DEBT-005..008 cleanup
mini-sweep + DEBT-009 lint.sh safety + Telegram/email notification +
periodic-in-loop `purge_old` (if proposal volume warrants) +
operator runs of the now-ready baselines and purge tooling.**
