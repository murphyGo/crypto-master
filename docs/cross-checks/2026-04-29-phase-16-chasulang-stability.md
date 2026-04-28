# Phase 16 Cross-Check: Chasulang Stability

**Date**: 2026-04-29
**Phase**: 16 - Chasulang Stability
**Status**: All one sub-task complete (16.1)

## Scope

Phase 15.1's redeploy on 2026-04-28 surfaced two prod-only chasulang
defects that Phase 14.1's per-strategy timeout override and Phase
12.3's retry-on-timeout could not address — the failures were
downstream of both: (a) every successful Claude return parsed with
`KeyError: 'signal'` because the chasulang_ict_smc.md template
returns the actionable trade nested under `trade.*` rather than flat
top-level, so the parser never saw a `signal` field; (b) at
`2026-04-28T15:02:15Z` a chasulang retry timed out at 360s and the
engine then sat silent for 12+ hours, suggesting the prior
`asyncio.create_subprocess_exec` + `asyncio.wait_for` path raised
the timeout but didn't actually kill the child process — the
wrapper's declared timeout was a lie. Both rendered chasulang
effectively disabled in production and posed an open wedge risk for
the engine. Phase 16 is a one-sub-task closure phase: 16.1 fixes the
parser to accept the chasulang nested shape and rebuilds
`_execute_cli_once` on `subprocess.Popen` so a timeout actually
SIGKILLs the child. No new framework abstractions, no new
architectural directions.

The phase added **no new functional or non-functional requirements**;
the development plan's Requirements Mapping table records Phase 16
against requirements that were originally introduced in earlier
phases — Phase 16 either extends them (FR-022) or hardens them
(NFR-001):

- **FR-022** — Claude AI Integration (Phase 3.3 + Phase 12.3 +
  Phase 14.1). 16.1 extends `_parse_response` to accept the
  chasulang nested-`trade` response shape and rebuilds the
  subprocess driver to guarantee SIGKILL on timeout. The
  `ClaudeCLI` public contract is bytewise unchanged: same `analyze`
  signature, same exception types, same retry semantics, same
  `attempt_number` propagation from Phase 14.1.
- **NFR-001** — Python 3.10+ tech-stack hygiene (lint / type / test
  coverage). 16.1 lands cleanly: ruff + mypy clean across 53 source
  files at sub-task commit, every new helper type-hinted, every new
  branch test-locked.

16.1 was added based on direct production observation of the Phase
15.1 redeploy: every chasulang Claude response failed with the
`'signal'` `KeyError`, AND the engine wedged at `15:02:15` for 12+
hours on a single chasulang retry. Both were single-cycle prod
defects with operator-visible impact (chasulang effectively
disabled; engine wedged), so the phase is bounded to those two
fixes and seals in this cycle.

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 16.1 | chasulang Parse + Wedge Mitigation (FR-022, NFR-001) | `src/ai/claude.py` (`_parse_response` calls a new `_normalize_trade_fields` helper after JSON extraction; helper promotes nested `trade.*` keys — `signal`, `entry_price`, `stop_loss`, `take_profit`, `confidence`, `reasoning` — to the top level when present, prefers explicit `take_profit` over `take_profit_1` over nothing, raises `ClaudeParseError` mentioning both candidate paths when neither has `signal`. Original `trade` sub-dict is left intact in the returned dict so downstream callers that want the full nested view — e.g. to read `take_profit_2` — still can. `_execute_cli_once` rebuilt on `subprocess.Popen` run via `asyncio.to_thread`; `proc.communicate(timeout=...)` drives the timeout, `proc.kill()` + `proc.wait(timeout=5)` on `subprocess.TimeoutExpired`; distinct error message — "did not respond to SIGKILL within 5s" — when SIGKILL itself fails to reap, same `ClaudeTimeoutError` exception type so the proposal engine's existing `except StrategyError` path still treats it as a clean per-strategy skip. New `import subprocess` at module scope.) | `tests/test_ai_claude.py` (+8 net new tests; full mock-surface migration from `asyncio.create_subprocess_exec`/`AsyncMock` to `subprocess.Popen`/`MagicMock(spec=Popen)`. Two helpers `_make_popen_success` and `_make_popen_timeout` factor the new mock pattern. New `TestParseResponseNestedTradeForm` class covers 6 cases: chasulang nested-form happy path, top-level back-compat for `sample_prompt.md`/`simple_trend_analysis.md`, TP1 picked over TP2, explicit `take_profit` beats TP1, clear-error names both candidate paths when neither has signal, top-level signal wins when trade lacks one. New `TestSubprocessKillOnTimeout` class covers 2 cases: `proc.kill()` called exactly once + `proc.wait(timeout=5)` with `attempt_number == 1` and `timeout_seconds == 0.05` preserved on a normal timeout, distinct `ClaudeTimeoutError` with `"SIGKILL"` in the message when SIGKILL itself hangs. Existing `TestClaudeCLIRetryOnTimeout` class rewired onto Popen-shaped mocks; the `test_timeout_escalates_each_retry` test captures the `timeout` kwarg passed to `proc.communicate` instead of patching `asyncio.wait_for`.) — total +8 net (1162 → 1170) |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-022 | Technique Improvement Suggestion (Claude) | ✅ Complete (extended) | 16.1 unblocks chasulang's actual production path: `_parse_response` now accepts the chasulang_ict_smc.md template's nested `trade.*` shape via the new `_normalize_trade_fields` helper. Promotion is non-destructive (original `trade` sub-dict preserved in the result), TP1-over-TP2 precedence is documented in a parser comment, and a missing-signal error names both candidate paths so operators can spot the failing template fast. The subprocess rebuild on `subprocess.Popen` + `proc.kill()` + bounded `proc.wait(timeout=5)` closes the prod wedge observed at `2026-04-28T15:02:15Z` where a 360s chasulang retry timeout failed to actually terminate the child. `ClaudeTimeoutError` continues to carry `attempt_number` (Phase 14.1 contract); a distinct error message ("did not respond to SIGKILL within 5s") makes the harder failure mode visible in logs. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-001 | Python 3.10+ Tech Stack Hygiene | ✅ Complete (preserved) | 16.1 lands with ruff + mypy clean across all 53 source files at sub-task commit. New helpers are typed (`_normalize_trade_fields(self, result: dict[str, Any]) -> dict[str, Any]`, `_run_blocking() -> tuple[str, str, int]`); `subprocess.Popen` import + usage typed. Test count climbs 1162 → 1170 (+8 net) with the chasulang nested-form parse path covered (6 tests across happy path, back-compat, TP1-over-TP2, explicit-tp-beats-TP1, clear-error, top-level-signal-wins) and the subprocess wedge mitigation covered end-to-end (2 tests: kill+reap success, SIGKILL-itself-fails distinct error). Existing retry-loop tests rewired onto Popen-shaped mocks; behaviour assertions unchanged. No `# noqa` / `# type: ignore` added. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-003 | User approval for technique adoption | ✅ Complete (preserved) | Phase 16 doesn't touch the technique-promotion path. `FeedbackLoop.approve` / `reject` continue to be the only way `experimental/` strategies move to `active`. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-001 / FR-002 / FR-003 | Strategy framework input contract | ✅ Complete (preserved) | The chasulang nested-`trade` parse path is layered inside `_parse_response`; the `BaseStrategy` / `ClaudeCLI` boundary is unchanged. Existing flat-shape strategies (`sample_prompt.md`, `simple_trend_analysis.md`) parse bytewise unchanged because their responses have no `trade` sub-dict — the helper is a no-op for them. |
| FR-005 / FR-012 | Multi-Technique Per-Symbol Scan | ✅ Complete (preserved) | Phase 10.6's `_propose_all_for_symbol` dispatch is unchanged. With chasulang's parse path unblocked, the scan can now legitimately produce chasulang proposals where it previously dropped them. The dedup-by-symbol invariant (Phase 10.6) holds: a chasulang proposal can now compete with baseline-strategy proposals for the highest-composite winner per symbol. |

## Test Summary

- **Phase 16 tests at phase completion**:
  - 16.1: 8 new tests in `tests/test_ai_claude.py` (1162 → 1170)
    — 6 in `TestParseResponseNestedTradeForm` covering the
    chasulang shape and back-compat invariants, 2 in
    `TestSubprocessKillOnTimeout` covering the wedge mitigation
    end-to-end. Existing retry-loop tests rewired to Popen mocks
    with no behaviour assertion change.
- **Full suite at phase completion**: **1170 passing, 0 failing**.
- **Lint/format**: `ruff check` clean across all Phase 16 source.
  `mypy src` clean (53 source files — preserved from Phase 12.2's
  29 → 0 baseline; no regression introduced).

## Gaps

None blocking. The single sub-task shipped with passing tests and
clean lint/type baselines on touched files.

Three soft items worth flagging — none is a gap against the
requirements mapping table, all three are intentional choices
documented in the session log:

1. **Live verification still owed** — the parser fix and the wedge
   mitigation are unit-tested but neither has been observed working
   on Fly. The operator needs to redeploy and check that (a)
   chasulang's responses now produce actual `Proposal` objects in
   the cycle log instead of every cycle ending with the
   `'signal'` `KeyError`, and (b) any subsequent timeout (if 240s
   × 1.5 = 360s isn't enough) terminates the child within 5s of
   the per-attempt timeout instead of wedging. Without the live
   verification, both fixes are unproven against the actual prod
   failure mode they target.
2. **TP2 information is silently dropped from the canonical view**
   — when chasulang returns both `take_profit_1` and
   `take_profit_2`, the top-level promoted view only carries
   `take_profit_1`. A future strategy that wants to honour the
   second target (e.g. scale-out at TP1, hold remainder for TP2)
   would have to read `result["trade"]["take_profit_2"]` directly.
   Acceptable for Phase 16.1's bounded scope; if a multi-target
   strategy materialises, the right next move is extending
   `AnalysisResult` with an optional `take_profit_targets:
   list[Decimal]` field.
3. **Composite scores topping out around 0.35 is still the binding
   constraint on actual trade execution** (Phase 15.1 carry,
   still standing) — even with Phase 16.1 unblocking chasulang's
   proposals, `auto_approve_threshold = 1.0` (default) means
   proposals get rejected at the gate. The operator action — set
   `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` via Fly secrets — is still
   required for trades to actually execute. Phase 16.1 delivers
   proposals; the threshold setting is what turns proposals into
   trades. Surface in this cross-check rather than the session
   log because it's a phase-completion-relevant note about whether
   "phase complete" means "trades will execute": it doesn't,
   without the operator action.

## Risks Carried Forward

1. **Live verification of 16.1 chasulang parse + wedge mitigation
   still owed** — the operator needs to redeploy Fly and confirm
   that (a) the `KeyError: 'signal'` log line stops appearing on
   every chasulang cycle, and (b) any subsequent timeout
   terminates within 5s of the per-attempt timeout instead of
   wedging. Highest-priority operator action for the next cycle.
2. **Live verification of Phase 14.1 chasulang 240s override still
   owed** (14.1 carry) — Phase 14.1 deployed the per-strategy
   override but the operator still needs to redeploy and verify
   it eliminates timeouts in production. With Phase 16.1's wedge
   mitigation now in place, even if 14.1's leash is still too
   short, the engine recovers cleanly within 5s of the timeout
   instead of wedging. Reducing timeout *frequency* is still the
   better lever and lives in the prompt — escalate to
   prompt-slimming if `attempt_number == 2` continues to appear
   in `LLM_TIMEOUT` events.
3. **`ENGINE_AUTO_APPROVE_THRESHOLD=0.30` Fly secret action still
   owed** (15.1 carry) — without this, Phase 16.1's parser fix
   only delivers proposals to the threshold gate which then
   rejects them; the dashboard's
   `proposals_rejected_threshold_count` metric (Phase 15.1) will
   keep climbing on every cycle while the trade table stays
   empty. Operator action.
4. **No live-engine smoke run in production yet** (10.1
   carry-forward) — the live wiring landed but the operator still
   needs to redeploy with live-mode env vars and walk the 9-step
   checklist in `docs/deployment.md` with a $100 balance before
   flipping production to live mode at real sizing. Now
   particularly relevant: Phase 12.1's cross-cycle cap, Phase
   12.3's LLM timeout retry, Phase 14.1's per-strategy timeout
   override, Phase 12.4's Telegram push, Phase 13.4 + 14.2's
   email push, **and Phase 16.1's chasulang parse + wedge
   mitigation** are all production-ready and should be exercised
   together.
5. **3-channel push test trade — operator action** (12.4 + 13.4
   + 14.2 carry) — send a test proposal through the system to
   verify Slack + Telegram + Email all deliver. Manual
   verification only — no automated test possible without real
   webhooks / SMTP credentials. Should be part of the live-mode
   smoke checklist.
6. **Per-TF RSI baselines deployed but not measured** — Phase 9.4
   shipped `rsi_4h` + `rsi_15m` but their relative performance
   vs `rsi_universal` has not been measured. `python -m
   scripts.backtest_baselines` (public-API clean since 13.3)
   would surface the comparison. Operator action.
7. **`subprocess.Popen` rebuild changes the retry-loop wrapper
   shape** (16.1 introduced) — Phase 14.1's `attempt_number`
   propagation contract is preserved bytewise (locked by
   `test_subprocess_kill_on_timeout` asserting `attempt_number
   == 1` and the existing
   `TestClaudeCLIRetryOnTimeout::test_timeout_error_carries_final_attempt_number`
   asserting through 3 attempts), but a future refactor that
   changes the retry-loop's wrapper shape needs to keep the
   `attempt_number=attempt + 1` forwarding intact. Test coverage
   pins this; intentionally surfacing as a risk so future code
   archaeologists know the invariant.

## DEBT Closure Summary

- **Phase 16 introduced no TECH-DEBT items**, and resolved none
  (none were active prior to the phase). The TECH-DEBT tracker
  remains empty (active count = 0, unchanged since Phase 14.2
  sealed DEBT-012).

Net DEBT: 0 resolved, 0 added. **Active count remains at 0.**

## Recommendations for Phase 17 (or follow-up)

With the TECH-DEBT tracker empty and Phase 16 sealed in a single
sub-task, the next phase's shaping is driven entirely by the
session-log "Follow-up Work" section, this cross-check's "Risks
Carried Forward", and any new operator-observed defects from the
upcoming Fly redeploy. Candidates:

1. **Operator: redeploy Fly to verify chasulang now produces
   actual proposals** — the primary verification action for Phase
   16.1. Watch for: (a) absence of `KeyError: 'signal'` on
   chasulang cycles in `fly logs`, (b) chasulang `Proposal`
   records in `data/proposals/`, (c) composite scores in those
   proposals — does chasulang push the per-symbol-best composite
   above the 0.30 threshold or are baseline-only scores still
   the cap? If the threshold gate is now the binding constraint,
   Phase 17 shaping converges with Recommendation 2 below.
2. **Operator: set `ENGINE_AUTO_APPROVE_THRESHOLD=0.30` via Fly
   secrets** (15.1 + 16.1 joint carry) — without this, Phase
   16.1's parser fix only delivers proposals to the threshold
   gate which rejects them. Trade-execution unblock requires
   both parts: 16.1's parse path delivers proposals, the
   threshold setting turns them into trades.
3. **Operator: redeploy Fly to verify Phase 14.1 chasulang 240s
   override eliminates timeouts** (14.1 carry, still standing) —
   Phase 16.1's wedge mitigation is the *fallback* for the
   timeout-firing path; reducing how often timeouts happen is
   still the better lever and lives in the prompt. Escalate to
   prompt-slimming if `attempt_number == 2` continues to appear
   in `LLM_TIMEOUT` events post-redeploy.
4. **Operator runs (still standing)**:
   - `python -m scripts.backtest_baselines` (Phase 10.3 leftover
     — fills `docs/baselines.md` reference numbers, currently
     `_TBD_`; public API end-to-end since 13.3; cheap, unblocks
     "is the LLM beating the baselines?" measurement and "are
     the per-TF RSI baselines from 9.4 outperforming the
     universal RSI?" measurement).
   - `python -m src.tools.purge_proposals` (Phase 11.4 — manual
     lever for ad-hoc retention windows).
5. **3-channel push test trade — operator action** (Phase 14.2
   carry) — send a test proposal through the system to verify
   Slack + Telegram + Email all deliver. Should be part of the
   live-mode smoke checklist (10.1 carry-forward).
6. **Per-TF RSI baseline measurement (Phase 9.4 follow-up)** —
   `rsi_4h` and `rsi_15m` are deployed but have not been measured
   against `rsi_universal`. Operator-runnable now via
   `scripts.backtest_baselines`.
7. **Live-mode smoke checklist execution** (10.1 carry-forward)
   — walk the 9-step checklist in `docs/deployment.md` with a
   $100 balance before flipping production to live mode at real
   sizing. With Phase 16.1's parser + wedge mitigation in place,
   the chasulang path is now production-ready end-to-end (parse
   path delivers proposals, wedge mitigation contains worst-case
   timeout failures), making the smoke checklist execution
   meaningfully more useful than it was pre-16.1.
8. **Multi-target take-profit support** (16.1 soft item) — if a
   future strategy wants to honour the chasulang `take_profit_2`
   secondary target alongside `take_profit_1` (e.g. scale-out at
   TP1, hold remainder for TP2), the right shape is extending
   `AnalysisResult` with an optional `take_profit_targets:
   list[Decimal]` field. Out of scope today; only worth opening
   when a multi-target strategy materialises.

## Cross-Check Result

- ✅ Complete: 5 requirements (1 FR + 1 NFR + 1 CON + 2
  phase-adjacent preserved)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 16 closes. The development plan's Current Status table now
shows the Phase 16 row as ✅ Complete. The mainline has no
non-deferred unchecked items. Carried-forward deferrals: 7.5 Tapbit
(longstanding). The TECH-DEBT tracker remains empty for the third
phase running. Recommended Phase 17 shaping above the line:
operator live verification of Phase 16.1's chasulang parse + wedge
mitigation against the actual prod failure modes (the highest-value
verification the project has open right now — the fix is unproven
on Fly); operator action on the threshold setting that turns
chasulang's now-deliverable proposals into actual trades; operator
verification of Phase 14.1's 240s override as a complementary
prompt-slimming-or-not signal; the standing operator-run set
(baselines, purge tooling, 3-channel push test, per-TF RSI
measurement, live-mode smoke checklist) which is now meaningfully
more useful with the chasulang path production-ready
end-to-end.**
