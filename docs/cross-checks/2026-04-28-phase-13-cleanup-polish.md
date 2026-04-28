# Phase 13 Cross-Check: Cleanup + Operational Polish

**Date**: 2026-04-28
**Phase**: 13 - Cleanup + Operational Polish
**Status**: All four sub-tasks complete (13.1, 13.2, 13.3, 13.4)

## Scope

Phase 12 closed two real-money risks (cross-cycle position
accumulation and silent LLM-strategy timeouts), batched the residual
mypy debt, and shipped Telegram as the second push backend. Phase 13
is the cleanup phase that follows: it closes the carry-forward
TECH-DEBT items that Phase 12's cross-check left open (DEBT-003,
DEBT-004, DEBT-009, DEBT-010, DEBT-011), extends the engine
env-override surface to the remaining `EngineConfig` fields,
generalises the exchange OHLCV fetch with a `since` parameter
(unblocking Phase 10.3's pagination reach-around once and for all),
and adds email as the third push backend so live-mode notification
redundancy spans webhook + chat + SMTP failure modes. Pure cleanup +
small ops improvements — no new architectural directions, no new
real-money risk surfaces opened.

The phase added **no new functional or non-functional requirements**;
the development plan's Requirements Mapping table records Phase 13
against requirements that were originally introduced in earlier
phases — Phase 13 either closes accumulated debt against them or
extends them by a small increment:

- **NFR-001** — Python 3.10+ tech-stack hygiene (lint / type / test
  coverage). 13.1 closes DEBT-009 (`scripts/lint.sh --fix` unsafe
  for CI), DEBT-010 (long+short same-symbol cap test gap), and
  DEBT-011 (Dashboard `dict[str, object]` casts) in one batch.
- **NFR-004** — Environment-variable management. 13.2 closes
  DEBT-003 by env-overriding the four remaining `EngineConfig`
  fields (`monitor_interval_seconds`, `bitcoin_symbol`,
  `altcoin_top_k`, `actor`); third application of the Phase 10.2
  pattern (10.2 first, 12.1 second).
- **FR-020** — Historical Chart Data Query. 13.3 closes DEBT-004 by
  extending `BaseExchange.get_ohlcv` with `since: int | None = None`;
  Binance + Bybit forward to ccxt; `scripts/backtest_baselines.py`
  drops the `_client` reach-around it carried since Phase 10.3.
- **FR-015 / NFR-012** — Proposal Notification (Phase 6.3) and
  Live Trading awareness redundancy (Phase 4.4 / 10.1). Phase 11.3
  shipped Slack as the first push backend, Phase 12.4 added Telegram
  as the second; 13.4 ships email as the third so an operator
  without either chat platform finally has a push channel and so
  notification redundancy now spans three independent failure modes
  (Slack webhook outage, Telegram API outage, SMTP server outage —
  any two can be down with the third still delivering).

13.1 was added based on the carry-forward DEBT-009/010/011 from the
Phase 12 cross-check. 13.2 was added based on DEBT-003 (Phase 10.2
carry — explicit "repeat the 10.2 pattern when an operator request
lands"; deferred until Phase 13's batch). 13.3 was added based on
DEBT-004 (Phase 10.3 carry — explicit "extend the abstract contract
once a second use case appears"; the abstraction debt was real
enough to fix even without a second consumer). 13.4 was added based
on the Phase 11 + Phase 12 cross-check carry-forward "third push
backend" item.

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 13.1 | Cleanup Batch (DEBT-009/010/011) | `scripts/lint.sh` (no `--fix` — CI / pre-commit safe), `scripts/lint-fix.sh` (with `--fix` — dev convenience; new file, executable), `src/dashboard/pages/trading.py` + `src/dashboard/pages/engine.py` (per-page TypedDicts `TradingSummaryMetrics` + `EngineSummaryMetrics` replacing `dict[str, object]`; consumer-side `cast(...)` calls dropped at every access site; no leftover `from typing import cast`) | `tests/test_runtime_engine.py` (+1: `test_cap_blocks_opposite_side_same_symbol` — 1 BNB long open + BNB short proposal at composite=2.0; cap=1 → positions_opened=0, no open_position call, PROPOSAL_REJECTED with BNB + "cap 1 reached" — pins synthetic-hedge prevention invariant) |
| 13.2 | EngineConfig Remaining-Fields Env Override (DEBT-003) | `src/config.py` (4 new `Settings.engine_*` fields: `engine_monitor_interval: int = Field(default=60, ge=10)` env `ENGINE_MONITOR_INTERVAL`, `engine_bitcoin_symbol: str = Field(default="BTC/USDT")` env `ENGINE_BITCOIN_SYMBOL`, `engine_altcoin_top_k: int = Field(default=3, ge=1)` env `ENGINE_ALTCOIN_TOP_K`, `engine_actor: str = Field(default="auto-engine")` env `ENGINE_ACTOR`; `ge=` validators mirror `EngineConfig`'s own floors), `src/main.py::build_engine` (constructs `EngineConfig(...)` with the 4 new fields alongside the existing 4; 10.2 explicit-config-wins back-compat preserved; docstring rewritten), `.env.example` + `docs/deployment.md` (env var documentation) | `tests/test_config.py::TestEngineSettings` (+4 methods: default + env override + `ge=` validators where applicable; +4 parity assertions in existing default-match test), `tests/test_main_dispatch.py` (+1: `test_build_engine_propagates_all_engine_env_overrides`) — total +6 |
| 13.3 | BaseExchange.get_ohlcv `since` Parameter (DEBT-004) | `src/exchange/base.py` (`get_ohlcv` ABC now declares `since: int \| None = None` — timestamp ms, inclusive on start; default None = pre-13.3 most-recent-page semantics), `src/exchange/binance.py` + `src/exchange/bybit.py` (forward `since` to `ccxt.fetch_ohlcv(since=...)`; default behaviour preserved bytewise), `scripts/backtest_baselines.py::fetch_ohlcv_window` (switched from `exchange._client.fetch_ohlcv(...)` to `exchange.get_ohlcv(..., since=...)` end-to-end; `_client` reach-around + `RuntimeError` it gated + local `Decimal` import + bottom-of-function raw-row → `OHLCV` reconstructor all deleted; "deliberately reach past the BaseExchange contract" comment removed) | `tests/test_exchange_base.py` (`MockExchange.get_ohlcv` grew `since` parameter for ABC parity), `tests/test_exchange_binance.py` (+2: `test_get_ohlcv_forwards_since_to_ccxt` + `test_get_ohlcv_defaults_since_to_none`), `tests/test_exchange_bybit.py` (+2 same shape), `tests/test_scripts_backtest_baselines.py` (`_FakeBinanceExchange.get_ohlcv` absorbed the pagination-cursor logic from the deleted `_FakeCCXTClient`; `_client` attribute dropped) — total +4 |
| 13.4 | Email Notification Backend (FR-015, NFR-012) | `src/proposal/notification.py` (`EmailNotifier` class implementing existing `Notifier` protocol; stdlib `smtplib.SMTP` + `email.message.EmailMessage` wrapped in `asyncio.to_thread` — zero new dep; STARTTLS-only handshake, port 587 default; `_build_email_subject` + `_build_email_body` helpers; `_build_email_body` delegates to `_build_telegram_text` for cross-backend payload sync; `__repr__` masks password unconditionally; `send` does NOT swallow `smtplib` errors — Phase 6.3 failure-isolation contract owns it; configurable `timeout: float = 10.0`), `src/config.py` (6 SMTP fields: `email_smtp_host` / `email_smtp_user` / `email_smtp_password` / `email_from` / `email_to` all `str \| None` default None + `email_smtp_port: int = Field(default=587, ge=1, le=65535)`), `src/main.py::build_engine` (appends `EmailNotifier(...)` when all 5 string fields set; logs presence only — never password), `.env.example` + `docs/deployment.md` (SMTP quintet operator-facing prose) | `tests/test_proposal_notification.py` (+9: `test_build_email_subject_matches_spec`, `test_build_email_body_matches_telegram_text`, `test_email_notifier_subject_and_body_format` end-to-end via `_FakeSMTP`, `test_email_notifier_repr_masks_password`, `test_email_notifier_uses_starttls`, `test_email_notifier_login_called`, `test_email_smtp_failure_does_not_crash_dispatch`, `test_email_notifier_does_not_log_password`, `test_email_notifier_uses_configured_timeout`), `tests/test_main_dispatch.py` (+2: `test_email_notifier_created_when_all_env_set`, `test_email_notifier_silent_when_any_missing` covering 6 partial-config scenarios) — total +11 |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-015 | Proposal Notification | ✅ Complete (extended) | 13.4 adds `EmailNotifier` as a fifth backend alongside Phase 6.3's `ConsoleNotifier` + `FileNotifier`, Phase 11.3's `SlackNotifier`, and Phase 12.4's `TelegramNotifier`. Implements the existing `Notifier` protocol; `NotificationDispatcher` picks it up unmodified. Stdlib `smtplib.SMTP` + `EmailMessage` wrapped in `asyncio.to_thread` (zero new dep — mirrors Slack and Telegram patterns exactly). STARTTLS-only handshake (port 587 default); SMTP_SSL deliberately deferred as DEBT-012 (Low). Subject format `"Crypto Master: {symbol} {side} score={c:.2f}"`; body reuses `_build_telegram_text` via thin `_build_email_body` helper so Slack/Telegram/email all carry identical content. Body parity locked by `test_build_email_body_matches_telegram_text`. `Settings.email_smtp_host` + `email_smtp_user` + `email_smtp_password` + `email_from` + `email_to` all `Optional[str] = None` — non-breaking; activation requires all 5 string fields (`email_smtp_port` has default 587 and cannot fail `all([...])`). `__repr__` masks password unconditionally; host / user / from / to visible for log triage. `send` deliberately does NOT swallow `smtplib` errors — Phase 6.3's per-channel failure-isolation contract handles it (`test_email_smtp_failure_does_not_crash_dispatch` pins the contract). |
| FR-020 | Historical Chart Data Query | ✅ Complete (extended) | 13.3 extends the `BaseExchange.get_ohlcv` ABC with `since: int \| None = None` (timestamp in ms, inclusive on start). Both production adapters (`BinanceExchange` and `BybitExchange`) forward `since` to `ccxt.fetch_ohlcv(since=...)`. Default behaviour (no `since`) is bytewise-equal to pre-13.3 semantics — locked by `test_get_ohlcv_defaults_since_to_none` for each adapter. Explicit-`since` forwarding is locked by `test_get_ohlcv_forwards_since_to_ccxt` (Binance) + same-shape Bybit test. `scripts/backtest_baselines.py::fetch_ohlcv_window` now calls `exchange.get_ohlcv(..., since=...)` end-to-end; the `_client` reach-around + the `RuntimeError` it gated + the local `Decimal` import + the raw-row → `OHLCV` reconstructor are all deleted. Pagination semantics preserved exactly: `earliest_ts` derives from `recent[0].timestamp.timestamp() * 1000` (round-tripped through int) and matches the previous `raw_recent[0][0]` exactly. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-001 | Python 3.10+ Tech Stack Hygiene | ✅ Complete (hardened) | 13.1 closes three accumulated cleanup items in one batch. **DEBT-009**: `scripts/lint.sh` split into CI-safe `scripts/lint.sh` (`ruff check src tests && mypy src` — no `--fix`; safe for CI / pre-commit gates) + dev-only `scripts/lint-fix.sh` (`ruff check src tests --fix && mypy src` — for dev convenience). Both executable. **DEBT-010**: `tests/test_runtime_engine.py::test_cap_blocks_opposite_side_same_symbol` added — pins the synthetic-hedge prevention invariant Phase 12.1 implemented but didn't explicitly cover. Setup: 1 BNB long open + BNB short proposal at composite=2.0; cap=1; assert positions_opened=0 + no `trader.open_position` call + PROPOSAL_REJECTED with BNB + "cap 1 reached" reason. **DEBT-011**: `dict[str, object]` returns from `build_summary_metrics` replaced with per-page TypedDicts (`TradingSummaryMetrics` in `src/dashboard/pages/trading.py`, `EngineSummaryMetrics` in `src/dashboard/pages/engine.py` — shapes differ so per-page rather than shared). Consumer-side `cast(int, ...)` / `cast(float, ...)` / `cast(str, ...)` calls dropped at every access site; no leftover `from typing import cast` in either file. mypy 0 errors across 53 source files preserved. |
| NFR-004 | Environment Variable Management | ✅ Complete (extended) | 13.2 closes DEBT-003 — third application of the Phase 10.2 pattern (10.2 first, 12.1 second). 4 new `Settings.engine_*` fields in `src/config.py`: `engine_monitor_interval` (env `ENGINE_MONITOR_INTERVAL`, default 60, `ge=10`), `engine_bitcoin_symbol` (env `ENGINE_BITCOIN_SYMBOL`, default `"BTC/USDT"`), `engine_altcoin_top_k` (env `ENGINE_ALTCOIN_TOP_K`, default 3, `ge=1`), `engine_actor` (env `ENGINE_ACTOR`, default `"auto-engine"`). `ge=` validators mirror `EngineConfig`'s own floors so env input gets the same validation as direct construction. `src/main.py::build_engine` constructs `EngineConfig(...)` with the 4 new fields alongside the existing 4 (10.2 explicit-config-wins back-compat preserved). Defaults bytewise-match `EngineConfig` so existing deployments are unchanged without an env setting; parity locked by `test_settings_defaults_match_engine_config`. `.env.example` + `docs/deployment.md` document every new env var with operator-facing prose. |
| NFR-012 | Live Trading Confirmation / Awareness | ✅ Complete (extended) | 13.4 extends Phase 11.3's + Phase 12.4's push-backend coverage. Live-mode notification redundancy now spans three independent failure modes: Slack webhook outage, Telegram API outage, SMTP server outage — any two can be down and the third still delivers. The 6-field SMTP `Settings` shape (5 strings + 1 default-587 port) is non-breaking: existing deployments without env vars are unchanged. `tests/test_main_dispatch.py::test_email_notifier_silent_when_any_missing` covers 6 partial-config scenarios (each missing field × silent activation) so a half-configured deploy fails closed (no notifier registered) rather than failing open (registered but un-deliverable). |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-003 | User approval for technique adoption | ✅ Complete (preserved) | No Phase 13 sub-task touches the technique-promotion path. `FeedbackLoop.approve` / `reject` continue to be the only way `experimental/` strategies move to `active`. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-006 / FR-007 / FR-008 | Risk/Reward / Leverage / Entry-SL-TP | ✅ Complete (preserved) | 13.1's DEBT-010 test covers the long+short same-symbol cap path Phase 12.1 implemented. Implementation correct; the test fills a defensive coverage gap rather than changing behaviour. |
| FR-025 | Backtesting | ✅ Complete (consumed) | 13.3's `since`-parameter cleanup means `scripts/backtest_baselines.py` no longer reaches past the abstraction; the operator script is now public-API-clean. |

## Test Summary

- **Phase 13 tests at phase completion**:
  - 13.1: 1 new test in `tests/test_runtime_engine.py`
    (1127 → 1128).
  - 13.2: 6 new tests across `tests/test_config.py` +
    `tests/test_main_dispatch.py` (1128 → 1134).
  - 13.3: 4 new tests across `tests/test_exchange_binance.py` +
    `tests/test_exchange_bybit.py` (1134 → 1138).
  - 13.4: 11 new tests across `tests/test_proposal_notification.py`
    + `tests/test_main_dispatch.py` (1138 → 1149).
- **Full suite at phase completion**: **1149 passing, 0 failing**.
- **Lint/format**: `ruff check` clean across all Phase 13 source.
  `mypy src` clean (53 source files — preserved from Phase 12.2's
  29 → 0 baseline; no regression introduced by any Phase 13 sub-task).

## Gaps

None blocking. All four sub-tasks shipped with passing tests and
clean lint/type baselines on touched files.

Two soft items worth flagging — neither is a gap against the
requirements mapping table, both are intentional choices documented
in their respective session logs:

1. **STARTTLS-only — port-465 SMTP_SSL providers blocked** (13.4) —
   operators on Yahoo, ATT, ProtonMail, or other port-465-only
   providers cannot enable email push without an intermediary relay
   on port 587. Recorded as DEBT-012 (Low). Workaround exists; not
   a hard block. Most modern providers offer STARTTLS / port 587 as
   the recommended path anyway.
2. **Body parity invariant is by-hand** (13.4 + 12.4) — Phase 13.4
   reuses `_build_telegram_text` for the email body (one helper,
   two backends), and `test_build_email_body_matches_telegram_text`
   pins email-side parity. Slack uses the same content via its own
   path — three backends, no central spec. If a future Telegram-only
   tweak lands (emoji, deeplink), email would silently inherit it
   while Slack would not. Phase 12 cross-check flagged the same
   risk. No mechanism enforces the in-sync invariant across all three
   backends; the spec invariant should be re-asserted explicitly in
   each builder if a deliberate divergence is ever warranted.

## Risks Carried Forward

1. **DEBT-012 SMTP_SSL alternative for port 465 SMTP providers**
   (Low, Phase 13.4) — STARTTLS-only ships; operators on port-465
   providers cannot enable email push. Pick up when an operator
   request lands. (Open.)
2. **`chasulang_ict_smc` Claude CLI 120s timeouts STILL occurring on
   prod** — Phase 12.3 deployed retry-on-timeout (1.5× backoff,
   default 1 retry) but Fly logs continue to show
   `ClaudeTimeoutError` on cycles. The retry mechanism is correct;
   the prompt itself appears to consistently exceed the budget for
   that strategy. Worth investigating whether prompts can be
   shortened or the cycle interval extended for that strategy
   specifically. Not a Phase 13-scope item; surfaced for Phase 14
   shaping.
3. **Per-TF RSI baselines deployed but not measured** — Phase 9.4
   shipped `rsi_4h` + `rsi_15m` strategies but their relative
   performance vs the universal `rsi_universal` baseline has not
   been measured. `python -m scripts.backtest_baselines` (now
   public-API clean per 13.3) would surface the comparison. Operator
   action.
4. **Long+short same-symbol cap is a hard cap, not soft** (12.1
   carry) — DEBT-010's new test pins the synthetic-hedge prevention
   invariant; the implementation continues to block outright with no
   "scale down the second position" smoothing. Acceptable; the safe
   default is the simpler shape.
5. **Multi-inheritance `ClaudeTimeoutError` is subtle** (12.3 carry)
   — future callers writing `except ClaudeError` might be surprised
   that a catch on `StrategyError` also fires. The MRO is documented
   and test-locked, but worth keeping on the radar when adding new
   exception subtypes in `src/ai/exceptions.py`.
6. **Bot token + chat id are both credentials** (12.4 carry) +
   **SMTP password is a credential** (13.4) — three push backends
   now hold secrets in `Settings`. `__repr__` masks the secret in
   each (URL for Slack; both token and chat id for Telegram;
   password for email). Operators must know not to commit `.env` or
   paste any of these values into PRs. The `caplog`-asserting test
   `test_email_notifier_does_not_log_password` pins the email
   contract explicitly.
7. **Body parity invariant is by-hand across three backends** (12.4
   + 13.4) — see Gaps section. No mechanism enforces "one spec,
   three backends".
8. **No live-engine smoke run in production yet** (10.1
   carry-forward) — the live wiring landed but the operator still
   needs to redeploy Fly with the live-mode env vars and walk the
   9-step checklist in `docs/deployment.md` with a $100 balance
   before flipping production to live mode at real sizing. Now
   particularly relevant given Phase 12.1's cross-cycle cap +
   Phase 13.4's email push are both in production-ready state.

## DEBT Closure Summary

- **DEBT-003 EngineConfig Remaining Fields Not Env-Overridable**
  (Low, pre-Phase 11 carry from 10.2) ✅ resolved by Phase 13.2
  (4 `Settings.engine_*` fields + `build_engine` wiring).
- **DEBT-004 Baseline Backtest Script Follow-ups** (Low, pre-Phase
  11 carry from 10.3) ✅ resolved by Phase 13.3 (`since: int \| None
  = None` on ABC; both adapters forward; script drops `_client`
  reach-around).
- **DEBT-009 `scripts/lint.sh --fix` unsafe for CI** (Low, Phase
  11.1 carry) ✅ resolved by Phase 13.1 (split into CI-safe
  `lint.sh` + dev-only `lint-fix.sh`).
- **DEBT-010 Long+Short Same-Symbol Test Gap** (Low, Phase 12.1
  carry) ✅ resolved by Phase 13.1 (added
  `test_cap_blocks_opposite_side_same_symbol`).
- **DEBT-011 Dashboard `dict[str, object]` casts** (Low, Phase 12.2
  carry) ✅ resolved by Phase 13.1 (per-page TypedDicts;
  `cast()` calls dropped).
- **DEBT-012 SMTP_SSL alternative for port 465 SMTP providers**
  (Low) — NEW (logged during Phase 13.4; deliberate scope deferral).

Net DEBT: 5 resolved (DEBT-003, 004, 009, 010, 011), 1 added
(DEBT-012). Active count goes from 5 → 1.

## Recommendations for Phase 14 (or follow-up)

Based on accumulated TECH-DEBT (only DEBT-012 left), the
session-log "Follow-up Work" sections, and the cross-check itself,
the next phase shaping should consider:

1. **DEBT-012 SMTP_SSL alternative** (Low, Phase 13.4 carry) —
   add `email_smtp_use_ssl: bool = False` setting; switch
   `EmailNotifier._send` to `smtplib.SMTP_SSL(...)` when set and
   skip `starttls()` (SSL/TLS already established at connect time).
   Default `False` preserves Phase 13.4 behaviour bytewise. Pick up
   only when an operator on a port-465-only provider asks for email
   push. Not urgent.
2. **Operator runs (still standing — neither yet executed in
   production)**:
   - `python -m scripts.backtest_baselines` (Phase 10.3 leftover —
     fills `docs/baselines.md` reference numbers, currently `_TBD_`;
     now uses public API end-to-end thanks to 13.3; cheap, unblocks
     "is the LLM beating the baselines?" measurement and "are the
     per-TF RSI baselines from 9.4 outperforming the universal
     RSI?" measurement).
   - `python -m src.tools.purge_proposals` (Phase 11.4 — manual
     lever for ad-hoc retention windows that differ from the
     configured value; only worth running once proposal volume
     grows enough that monthly records pile up between deploys).
3. **`chasulang_ict_smc` Claude CLI 120s timeouts STILL occurring on
   prod** — Phase 12.3's retry-on-timeout was deployed but Fly logs
   continue to show `ClaudeTimeoutError` on cycles. The retry
   mechanism is correct; the prompt itself appears to consistently
   exceed the budget. Worth investigating whether the
   `chasulang_ict_smc` prompt template can be shortened, whether the
   cycle interval should be longer for that specific strategy, or
   whether `claude_cli_timeout_seconds` should be raised globally.
   Phase 14 candidate.
4. **Per-TF RSI baseline measurement (Phase 9.4 follow-up)** —
   `rsi_4h` and `rsi_15m` strategies are deployed but have not been
   measured against `rsi_universal`. Operator-runnable now via
   `scripts.backtest_baselines`. If results show one TF dominates,
   that informs which baseline to keep front-and-center in
   `docs/baselines.md`.
5. **Email/Slack/Telegram test trade — operator action** — send a
   test proposal through the system (e.g. via a $100 paper-mode
   cycle) to verify all three push channels deliver. Manual
   verification only — no automated test possible without real
   webhooks / SMTP credentials. Should be part of the live-mode
   smoke checklist (10.1 carry-forward).
6. **Body parity enforcement across three push backends** (12.4 +
   13.4 soft item) — if a deliberate divergence is ever warranted
   (e.g. Telegram-only Markdown deeplink), the spec invariant
   should be re-asserted explicitly in each builder. No mechanism
   enforces the in-sync invariant today; a single
   `_build_push_payload` helper feeding all three backends would
   close it. Low priority; only worth if a divergence is proposed.
7. **Periodic-in-loop `purge_old`** vs the current startup-only
   hook (Phase 11.4 carry) — phase 13 candidate that wasn't picked
   up; still relevant if proposal volume grows enough that monthly
   records pile up between deploys / restarts.
8. **Live-mode smoke checklist execution** (10.1 carry-forward) —
   operator action, not a sub-task. Walk the 9-step checklist in
   `docs/deployment.md` with a $100 balance before flipping
   production to live mode at real sizing. Now particularly
   relevant: Phase 12.1's cross-cycle cap, Phase 12.3's LLM timeout
   retry, Phase 12.4's Telegram push, and Phase 13.4's email push
   are all production-ready and should be exercised together.

## Cross-Check Result

- ✅ Complete: 8 requirements (2 FR + 3 NFR + 1 CON + 2
  phase-adjacent consumed)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 13 closes. The development plan's Current Status table now
shows every Phase 13 row as ✅ Complete. The mainline has no
non-deferred unchecked items. Carried-forward deferrals: 7.5 Tapbit
(longstanding) + DEBT-012 SMTP_SSL alternative (Phase 13.4 — Low,
deliberate scope deferral). Recommended Phase 14 shaping above the
line: chasulang_ict_smc prompt-budget / cycle-interval investigation
(real-money relevance — strategy is consistently dropping out of
cycles on prod even with retry); per-TF RSI baseline measurement run
(operator action, unblocked by 13.3); operator runs of the
now-ready baselines + purge tooling; body-parity helper to enforce
"one spec, three push backends" if a deliberate divergence ever
proposes; live-mode smoke checklist execution against the
production-ready cross-cycle cap + LLM retry + three-channel push
stack.**
