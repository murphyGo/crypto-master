# Phase 12 Cross-Check: Risk Hardening + Reliability

**Date**: 2026-04-28
**Phase**: 12 - Risk Hardening + Reliability
**Status**: All four sub-tasks complete (12.1, 12.2, 12.3, 12.4)

## Scope

Phase 11 closed the operational hardening agenda (lint, OHLCV cache,
push notifier, purge wiring). Phase 12 closes two real-money risks
surfaced by live Fly monitoring on 2026-04-28 — cross-cycle position
accumulation (the BNB-double-open) and LLM-strategy timeouts that
silently dropped proposals — batches the residual mypy debt that
Phase 11.1 deferred to other modules, and adds a second push backend
so live mode isn't single-channel. Two are direct real-money safety
closures (12.1, 12.3); one is type-hygiene baseline cleanup (12.2);
one is the second operator paging channel (12.4).

The phase added **no new functional or non-functional requirements**;
the development plan's Requirements Mapping table records Phase 12
against requirements that were originally introduced in earlier
phases — Phase 12 hardens or extends them:

- **FR-006 / FR-007 / FR-008** — Trading Strategy (Risk/Reward,
  Leverage, Entry/SL/TP) was Phase 4.1's contract. The risk envelope
  assumed a single open position per symbol; cross-cycle accumulation
  was an unmodelled gap. 12.1's `EngineConfig.max_open_positions_per_symbol`
  cap closes it at the engine layer (not the proposal layer —
  proposals continue to record for audit; only execution is blocked).
- **NFR-001** — Python 3.10+ tech-stack hygiene. Phase 11.1 cleared
  the in-scope mypy debt and logged the four out-of-scope clusters
  as DEBT-005..008. 12.2 closed all four in one mini-sweep, taking
  `mypy src` from 29 errors to 0.
- **FR-022** — Technique Improvement Suggestion (Claude) was Phase
  5.3's contract. The Claude CLI's 120s timeout was logged but
  silently dropped the strategy from the cycle's multi-technique
  scan. 12.3 wraps the existing `subprocess.run(..., timeout=...)`
  with retry-on-timeout (1.5× backoff, default 1 retry) and emits a
  new `LLM_TIMEOUT` activity event for dashboard observability.
- **FR-015 / NFR-012** — Proposal Notification (Phase 6.3) and Live
  Trading awareness (Phase 4.4 / 10.1). Phase 11.3 shipped Slack as
  the first push backend; 12.4 ships Telegram as the second so an
  operator without a Slack workspace finally has a push channel for
  live mode.

12.1 was added to the plan as the Phase 12 lead-off based on Phase
10.6's quant-flagged "cap at TradingEngine" follow-up plus the live
2026-04-28 BNB-double-open observation. 12.2 was added based on
Phase 11.1's logged DEBT-005..008. 12.3 was added based on the live
2026-04-28 `chasulang_ict_smc` 120s-timeout observation. 12.4 was
added based on Phase 11's "single push backend" carry-forward
(flagged twice in the Phase 11 cross-check).

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 12.1 | Cross-Cycle Position Cap | `src/runtime/engine.py` (`EngineConfig.max_open_positions_per_symbol: int = Field(default=1, ge=1)`; `TradingEngine._handle_proposal` checks `trader.get_open_trades()` filtered by symbol *after* the composite-accept gate; on count ≥ cap increments `proposals_rejected`, logs `PROPOSAL_REJECTED` with reason `"symbol X cap N reached (M open)"` + structured `cap` / `open_count` event details, skips `_execute`), `src/config.py` (`Settings.engine_max_open_positions_per_symbol: int = Field(default=1, ge=1)` env-overridable as `ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL`), `src/main.py::build_engine` (threads the env override into `EngineConfig`), `.env.example` (`ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL`) | `tests/test_runtime_engine.py` (+5: default value / env wiring / cap-hit rejection / cap-not-reached execution / other-symbol-doesn't-block) |
| 12.2 | Residual mypy Sweep | `src/exchange/binance.py` (hand-rolled `CCXTClient` Protocol covering 10 ccxt methods used; `_client` typed `CCXTClient \| None`), `src/exchange/factory.py` (tightly-scoped `cast(Any, exchange_class)(...)` + comment explaining the typing-system gap), `src/dashboard/theme.py` + `src/dashboard/app.py` + `src/dashboard/pages/trading.py` + `src/dashboard/pages/engine.py` (`Literal` types for theme constants, `StreamlitPage` import for navigation, `cast(...)` on `st.metric` numeric values), `src/main.py` (targeted `# type: ignore[misc]` on the asyncio signal-handler lambda) | (no new tests — pure typing refactor; 1109 existing tests pass unchanged) |
| 12.3 | LLM Strategy Timeout Handling | `src/ai/claude.py` (retry-on-timeout loop with 1.5× escalation 120 → 180 → 270; retry only on `asyncio.TimeoutError`; per-attempt process cleanup), `src/ai/exceptions.py` (`ClaudeTimeoutError` multiply-inherits `ClaudeError + StrategyError`; MRO `[ClaudeTimeoutError, ClaudeError, StrategyError, Exception, ...]`), `src/strategy/loader.py` (`PromptStrategy.analyze` re-raises `ClaudeTimeoutError` UNWRAPPED; other `ClaudeError` subtypes still wrap into `StrategyError(...)` per pre-existing contract), `src/proposal/engine.py` (`ProposalEngine` accepts optional `activity_log`; emits `LLM_TIMEOUT` with `strategy_name`/`version`/`symbol`/`timeout_seconds` on final exhaustion), `src/runtime/activity_log.py` (`ActivityEventType.LLM_TIMEOUT`), `src/config.py` (`Settings.claude_cli_timeout_seconds` + `claude_cli_max_retries`), `src/main.py::build_engine` (shares one `ActivityLog` between `ProposalEngine` + `TradingEngine`), `.env.example` | `tests/test_ai_claude.py` + `tests/test_proposal_engine.py` + `tests/test_strategy_integration.py` (+10: 6 retry tests + 3 LLM_TIMEOUT event tests + 1 unwrap-propagation test) |
| 12.4 | Telegram Notification Backend | `src/proposal/notification.py` (`TelegramNotifier` implementing existing `Notifier` protocol; `urllib.request.urlopen` + `asyncio.to_thread`; bolded headline + code-fenced Markdown detail; `__repr__` masks both token AND chat id; `send` does not swallow `HTTPError`; `_build_telegram_text` helper module-private), `src/config.py` (`Settings.telegram_bot_token: str \| None` + `telegram_chat_id: str \| None`), `src/main.py::build_engine` (appends `TelegramNotifier(...)` when both env vars set; logs presence only), `.env.example` + `docs/deployment.md` | `tests/test_proposal_notification.py` + `tests/test_main_dispatch.py` (+8: 6 in test_proposal_notification.py — `_build_telegram_text` summary+detail spec, `__repr__` masks both secrets, end-to-end POST format, HTTP 5xx isolation; 2 in test_main_dispatch.py — `build_engine` registers when both env set + silent across the three partial-config scenarios) |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-006 | Risk/Reward Calculation | ✅ Complete (hardened) | 12.1's `max_open_positions_per_symbol` cap closes the cross-cycle accumulation gap that compromised the per-position risk envelope. The cap operates at the execution gate (engine layer, not proposal layer) so the per-proposal risk-reward calculation continues unchanged; the cap simply blocks the *N+1* same-symbol position from opening. Default cap=1 is bytewise-equal to the pre-12.1 effective behaviour for any symbol that hadn't accumulated. `tests/test_runtime_engine.py`'s cap-hit-rejection test pins the contract. |
| FR-007 | Leverage Setting | ✅ Complete (hardened) | 12.1's cap closes the *concentration* multiplier of leverage. Pre-12.1, four cycles each opening a position at `risk_percent=R` and `leverage=L` ended with 4× the intended notional risk on a single pair; with the cap the second cycle's proposal-accept gate is unchanged but the execution gate blocks. Leverage on the *first* same-symbol position is unaffected. |
| FR-008 | Entry/Take-Profit/Stop-Loss Setting | ✅ Complete (hardened) | 12.1's cap preserves per-position SL/TP semantics; cap operates strictly at the symbol-count denominator. The proposal continues to record entry / SL / TP for audit even when the cap blocks execution (rejection logged with reason; structured `cap` / `open_count` event details). |
| FR-015 | Proposal Notification | ✅ Complete (extended) | 12.4 adds `TelegramNotifier` as a fourth backend alongside Phase 6.3's `ConsoleNotifier` + `FileNotifier` and Phase 11.3's `SlackNotifier`. Implements the existing `Notifier` protocol; `NotificationDispatcher` picks it up unmodified. POSTs form-encoded `chat_id` + `text` + `parse_mode=Markdown` to `https://api.telegram.org/bot<TOKEN>/sendMessage` via stdlib `urllib.request.urlopen` + `asyncio.to_thread` (zero new dep — mirrors Slack's Phase 11.3 stdlib pattern). `Settings.telegram_bot_token` + `telegram_chat_id` both `Optional[str] = None` — non-breaking; activation requires both. `__repr__` masks BOTH token AND chat id (tighter contract than Slack's URL-only redaction). `send` deliberately does NOT swallow `HTTPError` — Phase 6.3's per-channel failure-isolation contract handles it. `tests/test_proposal_notification.py::test_build_telegram_text_has_summary_and_detail` pins payload format; `test_telegram_http_failure_does_not_crash_dispatch` pins the failure-isolation contract; `test_telegram_notifier_silent_when_either_missing` pins the partial-config silent-on-misconfig contract across all three scenarios. |
| FR-022 | Technique Improvement Suggestion (Claude) | ✅ Complete (hardened) | 12.3 closes the silent-strategy-drop-out gap on Claude CLI timeouts. The existing `subprocess.run(..., timeout=...)` call in `src/ai/claude.py` is wrapped with a configurable retry-on-timeout loop (1.5× escalation, default 1 retry, `Settings.claude_cli_max_retries: int = Field(default=1, ge=0)` — 0 = single shot). Retry only on `asyncio.TimeoutError`; any other exception propagates immediately (`tests/test_ai_claude.py::test_non_timeout_errors_do_not_trigger_retry` verifies `mock_exec.call_count == 1`). `ClaudeTimeoutError` now multiply-inherits `ClaudeError + StrategyError` so the engine's existing `StrategyError` catch handles it cleanly without a new except block at every call site. `PromptStrategy.analyze` re-raises `ClaudeTimeoutError` UNWRAPPED so the engine emits `LLM_TIMEOUT` with original `timeout_seconds` payload intact (locked by `test_unwrap_propagation`). New `ActivityEventType.LLM_TIMEOUT` adds dashboard observability for LLM reliability over time. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-001 | Python 3.10+ Tech Stack Hygiene | ✅ Complete (hardened) | 12.2 cleared all 4 out-of-scope clusters that Phase 11.1 deferred. `mypy src` 29 errors → 0 across 53 source files. DEBT-005 (binance.py, 11 errors): hand-rolled `CCXTClient` Protocol covering the 10 ccxt methods used (`load_markets`, `close`, `fetch_ohlcv`, `fetch_ticker`, `fetch_balance`, `create_market_order`, `create_limit_order`, `cancel_order`, `fetch_order`, `fetch_open_orders`); `_client` typed `CCXTClient \| None`. DEBT-006 (factory.py, 3 errors): investigated — NOT a behavioural mismatch; registry's `type[BaseExchange]` widens away subclass `__init__` params; resolved with tightly-scoped `cast(Any, exchange_class)(...)` + comment explaining the typing gap (runtime preserves exact call shape). DEBT-007 (dashboard cluster, 13 errors): `Literal` types for theme constants, `StreamlitPage` import for navigation, `cast(...)` on `st.metric` numeric values. DEBT-008 (main.py lambda, 1 error): targeted `# type: ignore[misc]` (canonical case for asyncio signal-handler callback shape mismatch). 1109 tests pass unchanged (refactor not a feature). 8 files modified. Public API preserved. |
| NFR-012 | Live Trading Confirmation / Awareness | ✅ Complete (extended) | 12.4 extends Phase 11.3's single-push-backend coverage. Phase 11.3 added Slack as the first push backend; 12.4 adds Telegram as the second so an operator without a Slack workspace finally has a push channel for live mode. The `Settings.telegram_bot_token` + `telegram_chat_id` Optional / default-None shape is non-breaking; existing deployments without the env vars are unchanged. `tests/test_main_dispatch.py` covers `build_engine` both branches (both env set vs any env unset → silent). 12.3's `LLM_TIMEOUT` activity event also extends NFR-012 by giving live operators dashboard visibility into LLM reliability — pre-12.3, a Claude timeout silently dropped the strategy from the cycle with no operator-visible signal beyond a log line. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-003 | User approval for technique adoption | ✅ Complete (preserved) | No Phase 12 sub-task touches the technique-promotion path. `FeedbackLoop.approve` / `reject` continue to be the only way `experimental/` strategies move to `active`. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-009 | Live Trading Execution | ✅ Complete (consumed) | 12.1's cap operates against `trader.get_open_trades()` regardless of `Trader` implementation (paper or live). `LiveTrader` and `PaperTrader` both surface the same shape. |
| FR-010 | Paper Trading Execution | ✅ Complete (consumed) | Same as FR-009 — the cap is `Trader`-agnostic. |
| FR-011 | Bitcoin Trading Proposal | ✅ Complete (consumed) | 12.3's `ProposalEngine` accepts an optional `activity_log` for `LLM_TIMEOUT` emission. `propose_bitcoin` continues to honour the existing single-proposal contract; if the LLM strategy times out after retries, the proposal is dropped cleanly and `LLM_TIMEOUT` is emitted (vs the pre-12.3 silent drop). |
| FR-012 | Altcoin Trading Proposal | ✅ Complete (consumed) | Same — `propose_altcoins`'s aggregation continues unchanged; the cycle survives a single-strategy timeout where it previously lost that strategy's contribution silently. |

## Test Summary

- **Phase 12 tests at phase completion**:
  - 12.1: 5 new tests in `tests/test_runtime_engine.py`
    (1104 → 1109).
  - 12.2: no new tests (pure typing/lint refactor; 1109 existing
    tests pass unchanged).
  - 12.3: 10 new tests across `tests/test_ai_claude.py` +
    `tests/test_proposal_engine.py` +
    `tests/test_strategy_integration.py` (1109 → 1119) — 6 retry
    tests + 3 LLM_TIMEOUT event tests + 1 unwrap-propagation test.
  - 12.4: 8 new tests across `tests/test_proposal_notification.py`
    + `tests/test_main_dispatch.py` (1119 → 1127).
- **Full suite at phase completion**: **1127 passing, 0 failing**.
- **Lint/format**: `ruff check` clean across all Phase 12 source.
  `mypy src` clean (29 → 0 across 53 source files; first
  fully-clean baseline since the type-hygiene baseline drift was
  diagnosed in Phase 10.5).

## Gaps

None blocking. All four sub-tasks shipped with passing tests and
clean lint/type baselines on touched files.

Three soft items worth flagging — none is a gap against the
requirements mapping table, all are intentional choices documented
in their respective session logs:

1. **Long+short same-symbol cap test gap** (12.1) — the cap counts
   trades regardless of side (correct: prevents accidental synthetic
   hedge), but the test suite does not explicitly cover the
   long-already-open + short-arrives path. Recorded as DEBT-010
   (Low). Implementation is correct; the gap is purely defensive
   against future regression.
2. **Two push backends, no email** (12.4) — Phase 12 ships Slack
   (11.3) + Telegram (12.4); email remains a future sub-task.
   Operators without either Slack or Telegram still have no push
   channel until email lands. Email is heavier than either webhook
   backend (SMTP creds, retry/backoff for transient delivery
   failures); only worth shipping when an operator request lands.
3. **Telegram payload sync with Slack is by-hand** (12.4) — the
   intent is "one payload spec, two backends"; if a deliberate
   divergence is ever warranted (e.g. Telegram-only Markdown link to
   a dashboard), the spec invariant should be re-asserted explicitly
   in both builders. No mechanism enforces the in-sync invariant
   today.

## Risks Carried Forward

1. **DEBT-003 `EngineConfig` remaining-fields env override** (Low,
   pre-Phase 11 carry from 10.2) —
   `monitor_interval_seconds`, `bitcoin_symbol`, `altcoin_top_k`,
   `actor` remain hardcoded. Repeat the 10.2 pattern only when an
   operator request lands. (Open.)
2. **DEBT-004 `BaseExchange.get_ohlcv` `since` parameter** (Low,
   pre-Phase 11 carry from 10.3) —
   `scripts/backtest_baselines.py` reaches into
   `BinanceExchange._client` to paginate. Extend the abstract
   contract once a second use case appears. (Open.)
3. **DEBT-009 `scripts/lint.sh --fix` unsafe for CI** (Low, Phase
   11.1 carry) — the `--fix` flag silently rewrites source on
   lintable regressions instead of reporting them. Fine for local
   dev, unsafe for a CI gate. Drop `--fix` for CI use, or split into
   two scripts. (Open.)
4. **DEBT-010 long+short same-symbol cap test gap** (Low, Phase
   12.1) — implementation correct (counts both sides, prevents
   synthetic hedge); suite doesn't explicitly cover. Add
   `test_cap_blocks_opposite_side_same_symbol` in a follow-up cycle.
   (Open.)
5. **DEBT-011 Dashboard `dict[str, object]` casts** (Low, Phase
   12.2) — `build_summary_metrics` returns `dict[str, object]`;
   consumers need `cast(int, ...)` / `cast(float, ...)` at each
   access site. Pure typing refactor; replace with `TypedDict`. (Open.)
6. **`max_open_positions_per_symbol` is a hard cap, not soft** (12.1)
   — the cap blocks execution outright; there's no "scale down the
   second position" smoothing. Operators wanting fractional
   accumulation across cycles have to widen the cap, which loses the
   default safety. Acceptable; the safe default is the simpler
   shape.
7. **Multi-inheritance `ClaudeTimeoutError` is subtle** (12.3) —
   future callers writing `except ClaudeError` might be surprised
   that a catch on `StrategyError` also fires. The MRO is
   documented and test-locked, but worth keeping on the radar when
   adding new exception subtypes in `src/ai/exceptions.py`.
8. **`ProposalEngine.activity_log` Optional means missing emit if
   caller forgets** (12.3) — `None` default is backward-compat-preserving
   but means a caller wiring up a fresh `ProposalEngine` without
   threading an `ActivityLog` will silently lose `LLM_TIMEOUT`
   events. `build_engine` does it correctly today; the contract is
   "if you want timeline events, pass an `ActivityLog`."
9. **Bot token + chat id are both credentials** (12.4) — anyone
   with the token can drive the bot, anyone with the chat id can
   identify the operator's destination channel. Codebase treats both
   as secrets (`__repr__` masks them, `build_engine` logs presence
   only), but operators must know not to commit `.env` or paste
   either value into PRs. Same operational discipline as Phase
   11.3's Slack webhook URL, with double the surface area.
10. **Partial Telegram config is silent** (12.4) — token-only or
    chat-id-only deploys silently skip notifier construction. Loud
    crash on boot would be worse, but operators expecting Telegram
    alerts and not getting them need to check `build_engine`'s INFO
    log line as the diagnostic surface. Documented in
    `docs/deployment.md`.
11. **Telegram payload sync with Slack is by-hand** (12.4) — see
    Gaps section. No mechanism enforces the "one spec, two backends"
    invariant.
12. **No live-engine smoke run in production yet** (10.1
    carry-forward) — the live wiring landed but the operator still
    needs to redeploy Fly to exercise it. The 9-step checklist in
    `docs/deployment.md` should be walked with a $100 balance before
    flipping to live mode at real sizing.

## DEBT Closure Summary

- **DEBT-005 ccxt typing in `src/exchange/binance.py`** (Low) ✅
  resolved by Phase 12.2 (`CCXTClient` Protocol covering 10
  methods).
- **DEBT-006 `src/exchange/factory.py` shape drift** (Low) ✅
  resolved by Phase 12.2 (typing-system gap, NOT behavioural;
  `cast(Any, ...)` + comment).
- **DEBT-007 Dashboard Streamlit type errors** (Low) ✅ resolved by
  Phase 12.2 (`Literal` types + `StreamlitPage` + numeric casts).
- **DEBT-008 `src/main.py` lambda annotation** (Low) ✅ resolved by
  Phase 12.2 (targeted `# type: ignore[misc]`).
- **DEBT-003 `EngineConfig` remaining-fields env override** (Low) —
  remains open (cycle 9 carry, pre-Phase 11; not Phase 12-scope).
- **DEBT-004 Baseline Backtest Script Follow-ups** (Low) — remains
  open (cycle 9 carry, pre-Phase 11; not Phase 12-scope).
- **DEBT-009 `scripts/lint.sh --fix` unsafe for CI** (Low) —
  remains open (Phase 11.1 carry; not Phase 12-scope).
- **DEBT-010 Long+Short Same-Symbol Test Gap** (Low) — remains open
  (logged during Phase 12.1; defensive test gap, implementation
  correct).
- **DEBT-011 Dashboard `dict[str, object]` casts** (Low) — remains
  open (logged during Phase 12.2; QA-flagged TypedDict follow-up).

Net DEBT: 4 resolved (DEBT-005..008), 2 added (DEBT-010, DEBT-011),
3 carried forward (DEBT-003, DEBT-004, DEBT-009). Active count
goes from 9 → 5.

## Recommendations for Phase 13 (or follow-up)

Based on accumulated TECH-DEBT (DEBT-003, DEBT-004, DEBT-009,
DEBT-010, DEBT-011), the session-log "Follow-up Work" sections, and
the cross-check itself, the next phase shaping should consider:

1. **DEBT-009 `scripts/lint.sh --fix` safety** (Low) — drop `--fix`
   for CI use, or split into two scripts: `lint.sh` (CI:
   report-only) and `lint-fix.sh` (dev: with `--fix`). Document the
   contract in the script header. Pairs naturally with any
   CI-gate work.
2. **DEBT-010 long+short same-symbol cap test** (Low, Phase 12.1
   carry) — add `test_cap_blocks_opposite_side_same_symbol` to lock
   the synthetic-hedge prevention invariant. Setup: existing open
   long position on `BTCUSDT`; proposal arrives for short on
   `BTCUSDT` with cap=1. Assert: cap-hit rejection fires;
   `proposals_rejected` increments; `PROPOSAL_REJECTED` logged with
   the symbol-cap reason; no `trader.open_position` call. Mirror
   the existing cap-hit test's shape; only difference is the side
   of the existing position vs the proposal's side.
3. **DEBT-011 TypedDict for `build_summary_metrics`** (Low, Phase
   12.2 carry) — replace the `dict[str, object]` return type with a
   `TypedDict` declaring the exact key→type mapping; drop
   consumer-side `cast(...)` calls. Pure typing refactor; no
   functional change.
4. **DEBT-003 `EngineConfig` remaining-fields env override** (Low,
   pre-Phase 11 carry) — repeat the 10.2 pattern for whichever of
   `monitor_interval_seconds` / `bitcoin_symbol` / `altcoin_top_k` /
   `actor` actually needs operator-tunability in practice. Revisit
   when an operator request lands.
5. **DEBT-004 `BaseExchange.get_ohlcv` `since` parameter** (Low,
   pre-Phase 11 carry) — extend the abstract contract with an
   optional `since: int | None = None` parameter and drop
   `scripts/backtest_baselines.py`'s `_client` reach-around.
   Revisit when a second use case appears.
6. **Email notification backend** — third push backend per Phase
   10.1's "notification redundancy for live mode" follow-up. Slack
   (11.3) + Telegram (12.4) are both webhook-style and zero-dep;
   email needs SMTP infrastructure (operator-side SMTP creds,
   retry/backoff for transient delivery failures). Heavier than
   either webhook backend; only worth if an operator request
   lands. Operators without Slack or Telegram still have no push
   channel until this lands.
7. **Periodic-in-loop `purge_old`** vs the current startup-only
   hook — Phase 11.4 considered this and chose startup-only as the
   simpler shape. Phase 13 candidate if proposal volume grows
   enough that monthly records pile up between deploys / restarts.
   The `_purge_old_proposals` helper would extend naturally to an
   in-loop call site.
8. **Operator runs**:
   - `python -m scripts.backtest_baselines` (Phase 10.3 leftover —
     populates `docs/baselines.md` reference numbers; cheap,
     unblocks "is the LLM beating the baselines?" measurement).
   - `python -m src.tools.purge_proposals` (Phase 11.4; manual
     lever for ad-hoc retention windows that differ from the
     configured value).
   Both ready, neither yet executed in production.
9. **Live-mode smoke checklist execution** (10.1 carry-forward) —
   operator action, not a sub-task. Walk the 9-step checklist in
   `docs/deployment.md` with a $100 balance before flipping
   production to live mode at real sizing. Now particularly
   relevant given 12.1's cross-cycle cap closes the BNB-double-open
   real-money concern that surfaced on the last live cycle.

## Cross-Check Result

- ✅ Complete: 12 requirements (5 FR + 2 NFR + 1 CON + 4
  phase-adjacent consumed)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 12 closes. The development plan's Current Status table now
shows every Phase 12 row as ✅ Complete. The mainline has no
non-deferred unchecked items. Carried-forward deferrals: 7.5 Tapbit
(longstanding) and the soft items above (none blocking).
Recommended Phase 13 shaping above the line: DEBT-009 lint.sh
safety + DEBT-010 long+short cap test + DEBT-011 TypedDict refactor +
email notification backend (third push channel) + periodic-in-loop
`purge_old` (if proposal volume warrants) + operator runs of the
now-ready baselines and purge tooling + live-mode smoke checklist
execution against the new cross-cycle cap.**
