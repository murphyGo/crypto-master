# Phase 14 Cross-Check: Production Reliability

**Date**: 2026-04-28
**Phase**: 14 - Production Reliability
**Status**: All two sub-tasks complete (14.1, 14.2)

## Scope

Phase 13 closed the carry-forward TECH-DEBT items from Phase 12's
cross-check (DEBT-003, DEBT-004, DEBT-009, DEBT-010, DEBT-011),
extended the engine env-override surface to the remaining
`EngineConfig` fields, generalised the exchange OHLCV fetch with a
`since` parameter, and added email as the third push backend. The
phase introduced one new debt item (DEBT-012 SMTP_SSL alternative for
port 465 SMTP providers — deliberate scope deferral) and surfaced an
ongoing production reliability concern (Phase 12.3's retry-on-timeout
shipped, but Fly logs continued to show `chasulang_ict_smc`
ClaudeTimeoutError on cycles even with the retry path firing). Phase
14 is the compact two-sub-task phase that closes both: 14.1 ships a
per-strategy Claude CLI timeout override + retry observability so
chasulang gets a longer leash without slowing the baselines, and 14.2
closes DEBT-012 by adding `email_use_ssl` so port-465-only SMTP
providers (Yahoo Mail, AT&T, ProtonMail) finally have a path. Pure
production reliability polish — no new architectural directions, no
new framework abstractions.

The phase added **no new functional or non-functional requirements**;
the development plan's Requirements Mapping table records Phase 14
against requirements that were originally introduced in earlier
phases — Phase 14 either extends them (FR-015, FR-022) or hardens
them (NFR-001):

- **FR-015** — Proposal Notification (Phase 6.3 + Phase 11.3 +
  Phase 12.4 + Phase 13.4). 14.2 adds the SMTP_SSL transport
  alternative to `EmailNotifier`, closing the DEBT-012 gap that
  blocked operators on port-465-only SMTP providers (Yahoo / AT&T /
  ProtonMail). Default `email_use_ssl=False` keeps every existing
  deployment unchanged.
- **FR-022** — Claude AI Integration (Phase 3.3 + Phase 12.3). 14.1
  extends the per-strategy configuration surface with
  `claude_timeout_seconds` so chasulang can run on a longer leash
  (240s base × 1.5 retry = 360s worst case) without slowing the
  baselines that finish well under 30s. `LLM_TIMEOUT` event payload
  grows `attempt_number` + `final_timeout_seconds` for retry-path
  observability.
- **NFR-001** — Python 3.10+ tech-stack hygiene (lint / type / test
  coverage). Both 14.1 and 14.2 land cleanly: ruff + mypy clean
  across 53 source files at every sub-task commit, every new field
  type-hinted, every new branch test-locked.

14.1 was added based on the carry-forward Phase 13 cross-check
"chasulang_ict_smc Claude CLI 120s timeouts STILL occurring on prod"
recommendation. 14.2 was added based on DEBT-012 (Phase 13.4 carry —
explicit "pick up when an operator request lands" deferral, brought
forward into Phase 14 because Phase 14 was already scoped narrowly
around production reliability).

## Sub-Task Implementation Map

| Sub-task | Title | Primary file(s) | Test file(s) |
|----------|-------|-----------------|--------------|
| 14.1 | Chasulang Timeout Mitigation (FR-022, NFR-001) | `src/strategy/base.py` (`TechniqueInfo` gains `claude_timeout_seconds: int \| None = Field(default=None, ge=1)` — `None` falls back to `Settings.claude_cli_timeout_seconds`, integer overrides go straight to `ClaudeCLI`; `ge=1` rejects zero at load time as a config bug), `src/strategy/loader.py` (`PromptStrategy.analyze` reads `self.info.claude_timeout_seconds`; when set constructs `ClaudeCLI(timeout=float(override))`, when `None` constructs `ClaudeCLI()` so the wrapper resolves Settings lazily), `src/ai/exceptions.py` (`ClaudeTimeoutError.__init__` adds `attempt_number: int = 1` parameter; default preserves Phase 12.3 single-shot semantics for unmigrated callers), `src/ai/claude.py` (`_execute_cli_once` accepts `attempt_number: int = 1` kwarg and stamps it onto the raised `ClaudeTimeoutError`; retry loop in `analyze` forwards `attempt + 1` so the surfacing error carries the final attempt's index), `src/proposal/engine.py` (`_log_llm_timeout` event payload gains `attempt_number` from `error.attempt_number` + `final_timeout_seconds` alias of `error.timeout_seconds` — intent-revealing; legacy `timeout_seconds` key preserved for back-compat), `strategies/chasulang_ict_smc.md` (frontmatter gains `claude_timeout_seconds: 240` — 240 × 1.5 = 360s worst case with one retry, comfortably above the observed Fly timeout floor) | `tests/test_ai_claude.py` (+2: `test_timeout_error_carries_final_attempt_number` exercises 3 attempts → `attempt_number == 3`, `test_timeout_error_attempt_number_is_one_with_no_retry` pins single-shot default), `tests/test_ai_exceptions.py` (+2: `test_attempt_number_defaults_to_one`, `test_attempt_number_is_set`), `tests/test_strategy_base.py` (+2: `test_claude_timeout_seconds_accepts_positive_int`, `test_claude_timeout_seconds_rejects_zero` pinning the `ge=1` constraint), `tests/test_strategy_loader.py` (+2: `test_analyze_passes_per_strategy_timeout_to_claude` `cli_ctor.assert_called_once_with(timeout=240.0)`, `test_analyze_falls_back_to_settings_when_no_override` `cli_ctor.assert_called_once_with()` no kwargs), `tests/test_proposal_engine.py` (+1: `test_engine_llm_timeout_event_carries_attempt_metadata` — verifies `attempt_number == 2` + `final_timeout_seconds == 360.0` with legacy `timeout_seconds` preserved) — total +5 (1153 → 1158) |
| 14.2 | SMTP_SSL Alternative (FR-015, NFR-001; resolves DEBT-012) | `src/config.py` (`Settings.email_use_ssl: bool = Field(default=False)` — env `EMAIL_USE_SSL=true` activates SMTP_SSL on port 465 instead of SMTP+STARTTLS on port 587; default False keeps Phase 13.4 STARTTLS path bytewise unchanged), `src/proposal/notification.py` (`EmailNotifier.__init__` accepts keyword-only `use_ssl: bool = False` stored as `self._use_ssl`; class docstring expanded to describe both transports — STARTTLS default for Gmail / Mailgun / SendGrid / corporate, SMTP_SSL for Yahoo Mail / AT&T / ProtonMail; inner `_send` closure branches at send-time: `use_ssl=True` → `smtplib.SMTP_SSL(host, port, timeout=...)` with NO `starttls()` call, `use_ssl=False` → existing `smtplib.SMTP(host, port, timeout=...)` + `starttls()`; `with smtp:` socket cleanup + `login` + `send_message` shared by both paths), `src/main.py::build_engine` (reads `settings.email_use_ssl` and forwards to `EmailNotifier(use_ssl=...)`), `.env.example` + `docs/deployment.md` (document `EMAIL_USE_SSL` with Yahoo / AT&T / ProtonMail pairing guidance: `EMAIL_USE_SSL=true` + `EMAIL_SMTP_PORT=465`; deployment doc adds a `fly secrets set` example for Yahoo) | `tests/test_proposal_notification.py` (+2: `test_email_notifier_uses_smtp_ssl_when_flag_set` patches BOTH `smtplib.SMTP_SSL` (to `_FakeSMTP`) AND `smtplib.SMTP` (to a `_wrong_constructor` raising stub) so a regression where the SSL path accidentally hits the wrong constructor fails loudly — asserts `host`/`port=465`, `starttls_called is False`, login args, exactly one `send_message`; `test_email_notifier_uses_starttls_when_flag_unset` is the mirror image — patches `smtplib.SMTP` to `_FakeSMTP`, patches `smtplib.SMTP_SSL` to a raising stub, asserts STARTTLS path intact with default `use_ssl=False`) — total +2 (1158 → 1160) |

## Compliance Matrix

### Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| FR-015 | Proposal Notification | ✅ Complete (extended) | 14.2 adds the SMTP_SSL transport alternative to Phase 13.4's `EmailNotifier`. `Settings.email_use_ssl: bool = Field(default=False)` is non-breaking — every existing deployment is unchanged without an env setting. `EmailNotifier.__init__` accepts keyword-only `use_ssl: bool = False`; the inner `_send` closure branches at send-time: `use_ssl=True` constructs `smtplib.SMTP_SSL(host, port, timeout=...)` and skips the `starttls()` call (channel already encrypted on connect), `use_ssl=False` constructs the existing `smtplib.SMTP(host, port, timeout=...)` and calls `starttls()`. `with smtp:` socket cleanup, `login`, and `send_message` are shared by both paths. `src/main.py::build_engine` reads `settings.email_use_ssl` and forwards to `EmailNotifier(...)`. `.env.example` + `docs/deployment.md` document the Yahoo / AT&T / ProtonMail pairing (`EMAIL_USE_SSL=true` + `EMAIL_SMTP_PORT=465`) with a `fly secrets set` example. Cross-protection in tests: each test patches BOTH `smtplib.SMTP` AND `smtplib.SMTP_SSL` and raises `AssertionError` from the wrong-constructor stub, so a regression where both branches accidentally call the same constructor fails loudly rather than silently passing. |
| FR-022 | Technique Improvement Suggestion (Claude) | ✅ Complete (extended) | 14.1 extends the per-strategy Claude CLI configuration surface — `TechniqueInfo` gains `claude_timeout_seconds: int \| None = Field(default=None, ge=1)`. `None` (default) keeps existing strategies on `Settings.claude_cli_timeout_seconds`, integer overrides go straight to `ClaudeCLI`; `ge=1` rejects zero at load time as a config bug rather than producing a silently never-succeeding strategy. `PromptStrategy.analyze` reads `self.info.claude_timeout_seconds`; when set constructs `ClaudeCLI(timeout=float(override))`, when `None` constructs `ClaudeCLI()` so the wrapper resolves Settings lazily — back-compat is bytewise. `strategies/chasulang_ict_smc.md` frontmatter sets `claude_timeout_seconds: 240` (240 × 1.5 = 360s worst case with one retry, comfortably above the observed Fly timeout floor on shared-CPU/1GB). `ClaudeTimeoutError` grows `attempt_number: int = 1` on `__init__` (default preserves Phase 12.3 single-shot semantics for unmigrated callers); `_execute_cli_once` accepts the kwarg and stamps it onto raised errors; the retry loop forwards `attempt + 1` so the surfacing error carries the final attempt's index. `_log_llm_timeout` extends the `LLM_TIMEOUT` event payload with `attempt_number` + `final_timeout_seconds` (alias of `error.timeout_seconds` — intent-revealing) so operators triaging Fly logs can distinguish "first attempt fails, retry didn't fire" (wiring bug) from "every attempt timed out" (leash too short). Legacy `timeout_seconds` key preserved for back-compat. |

### Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| NFR-001 | Python 3.10+ Tech Stack Hygiene | ✅ Complete (preserved) | Both 14.1 and 14.2 land with ruff + mypy clean across all 53 source files at every sub-task commit. New fields are typed (`claude_timeout_seconds: int \| None`, `email_use_ssl: bool`, `attempt_number: int`, `use_ssl: bool`); the `smtp: smtplib.SMTP` annotation on the local var inside `_send` lets mypy resolve the union since `SMTP_SSL` is a subclass of `SMTP`. Test count climbs 1153 → 1160 (+7) with both new branches covered, retry-loop attempt-number propagation locked end-to-end, and cross-protection on the SMTP_SSL transport-selection invariant. No `# noqa` / `# type: ignore` added. |

### Constraints

| ID | Constraint | Status | Evidence |
|----|------------|--------|----------|
| CON-003 | User approval for technique adoption | ✅ Complete (preserved) | No Phase 14 sub-task touches the technique-promotion path. `FeedbackLoop.approve` / `reject` continue to be the only way `experimental/` strategies move to `active`. |

## Phase-Adjacent Requirements Touched (No New Coverage Added)

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| NFR-012 | Live Trading Confirmation / Awareness | ✅ Complete (preserved) | 14.2 doesn't extend Phase 13.4's three-channel push redundancy (Slack + Telegram + Email) — it makes the email channel reachable for operators on port-465-only providers. The redundancy invariant (any two of three down, the third still delivers) is unchanged; the addressable-operator surface widens. |
| FR-001 / FR-002 / FR-003 | Strategy framework input contract | ✅ Complete (preserved) | 14.1's `claude_timeout_seconds` is a per-strategy frontmatter field on `TechniqueInfo`; the `BaseStrategy` / `ClaudeCLI` boundary is unchanged. Existing strategies that don't set the field remain on `Settings.claude_cli_timeout_seconds` — the lazy `ClaudeCLI()` constructor preserves Phase 12.3 semantics bytewise. |

## Test Summary

- **Phase 14 tests at phase completion**:
  - 14.1: 5 new tests across `tests/test_ai_claude.py` +
    `tests/test_ai_exceptions.py` + `tests/test_strategy_base.py` +
    `tests/test_strategy_loader.py` + `tests/test_proposal_engine.py`
    (1153 → 1158).
  - 14.2: 2 new tests in `tests/test_proposal_notification.py`
    (1158 → 1160).
- **Full suite at phase completion**: **1160 passing, 0 failing**.
- **Lint/format**: `ruff check` clean across all Phase 14 source.
  `mypy src` clean (53 source files — preserved from Phase 12.2's
  29 → 0 baseline; no regression introduced by any Phase 14 sub-task).

## Gaps

None blocking. Both sub-tasks shipped with passing tests and clean
lint/type baselines on touched files.

Two soft items worth flagging — neither is a gap against the
requirements mapping table, both are intentional choices documented
in their respective session logs:

1. **240s × 1.5 = 360s worst case ties up the Fly worker for a full
   cycle on the failing path** (14.1) — engine's monitor interval is
   60s default, so a chasulang cycle that hits both attempts and
   times out at 360s blocks 6 monitor ticks. Acceptable at this
   leash; if chasulang continues to fail at 240s, the right next move
   is prompt slimming or scoping chasulang off BTC scan, not bumping
   the override further. Live verification still owed — operator
   needs to redeploy Fly and re-grep `chasulang_ict_smc` +
   `LLM_TIMEOUT` post-redeploy.
2. **Cross-protection in 14.2's tests catches wrong-constructor at
   the call site, not a regression where the SSL path accidentally
   also calls `starttls()`** — `_FakeSMTP.starttls()` is a no-op flag
   flip; against a real SMTP_SSL server, calling `starttls()` on an
   already-encrypted connection raises `SMTPNotSupportedError`. The
   `assert fake.starttls_called is False` check tests the *intent*
   but not the *runtime constraint*. Acceptable: the intent is
   load-bearing and the unit test pins it.

## Risks Carried Forward

1. **Live verification of 14.1 chasulang 240s override still owed**
   — Phase 14.1 deployed the per-strategy override but the operator
   still needs to redeploy Fly and verify the override eliminates
   timeouts in production. If `attempt_number == 2` still appears in
   `LLM_TIMEOUT` events post-redeploy, the prompt itself is the
   bottleneck — escalate to prompt-slimming or scope chasulang off
   BTC scan. Operator action.
2. **Body parity invariant is by-hand across three push backends**
   (12.4 + 13.4 + 14.2 carry) — `_build_email_body` delegates to
   `_build_telegram_text`; Slack uses the same content via its own
   path. No mechanism enforces the in-sync invariant across all
   three; if a future Telegram-only tweak lands, email + Slack would
   silently diverge. Low priority; only worth a `_build_push_payload`
   helper if a deliberate divergence is proposed.
3. **Per-TF RSI baselines deployed but not measured** — Phase 9.4
   shipped `rsi_4h` + `rsi_15m` but their relative performance vs
   `rsi_universal` has not been measured. `python -m
   scripts.backtest_baselines` (public-API clean since 13.3) would
   surface the comparison. Operator action.
4. **Bot token + chat id are both credentials** (12.4 carry) +
   **SMTP password is a credential** (13.4 carry) — three push
   backends now hold secrets in `Settings`. `__repr__` masks the
   secret in each (URL for Slack; both token and chat id for
   Telegram; password for email). Operators must know not to commit
   `.env` or paste any of these values into PRs.
5. **No live-engine smoke run in production yet** (10.1
   carry-forward) — the live wiring landed but the operator still
   needs to redeploy Fly with the live-mode env vars and walk the
   9-step checklist in `docs/deployment.md` with a $100 balance
   before flipping production to live mode at real sizing. Now
   particularly relevant: Phase 12.1's cross-cycle cap, Phase 12.3's
   LLM timeout retry, Phase 14.1's per-strategy timeout override,
   Phase 12.4's Telegram push, and Phase 13.4 + 14.2's email push
   are all production-ready and should be exercised together.
6. **3-channel push test trade — operator action** — send a test
   proposal through the system to verify Slack + Telegram + Email
   all deliver. Manual verification only — no automated test
   possible without real webhooks / SMTP credentials. Should be part
   of the live-mode smoke checklist.
7. **Long+short same-symbol cap is a hard cap, not soft** (12.1
   carry) — the synthetic-hedge prevention invariant blocks
   outright with no "scale down the second position" smoothing.
   Acceptable; safer default.
8. **Multi-inheritance `ClaudeTimeoutError` is subtle** (12.3 carry,
   reinforced by 14.1's `attempt_number` extension) — future callers
   writing `except ClaudeError` might be surprised that a catch on
   `StrategyError` also fires. The MRO is documented and test-locked.

## DEBT Closure Summary

- **DEBT-012 SMTP_SSL alternative for port 465 SMTP providers**
  (Low, Phase 13.4 carry) ✅ resolved by Phase 14.2 (`email_use_ssl`
  Settings flag + `EmailNotifier` send-time branch between
  `smtplib.SMTP`+STARTTLS and `smtplib.SMTP_SSL`).

Net DEBT: 1 resolved (DEBT-012), 0 added. **Active count goes from
1 → 0. The TECH-DEBT tracker is empty for the first time since
Phase 10.5 logged DEBT-001.**

## Recommendations for Phase 15 (or follow-up)

With the TECH-DEBT tracker empty, the next phase's shaping is driven
by the session-log "Follow-up Work" sections and the cross-check
itself rather than carry-forward debt. Candidates:

1. **Operator: redeploy Fly to verify 14.1 chasulang 240s override
   eliminates timeouts** — if `attempt_number == 2` still appears in
   `LLM_TIMEOUT` events post-redeploy, prompt slimming or scoping
   chasulang off BTC scan is the escalation path. Highest-priority
   carry-forward action; live verification still owed.
2. **Operator runs (still standing — neither yet executed in
   production)**:
   - `python -m scripts.backtest_baselines` (Phase 10.3 leftover —
     fills `docs/baselines.md` reference numbers, currently `_TBD_`;
     public API end-to-end since 13.3; cheap, unblocks "is the LLM
     beating the baselines?" measurement and "are the per-TF RSI
     baselines from 9.4 outperforming the universal RSI?" measurement).
   - `python -m src.tools.purge_proposals` (Phase 11.4 — manual
     lever for ad-hoc retention windows that differ from the
     configured value; only worth running once proposal volume
     grows).
3. **3-channel push test trade — operator action** — send a test
   proposal through the system (e.g. via a $100 paper-mode cycle)
   to verify Slack + Telegram + Email all deliver. Manual
   verification only — no automated test possible without real
   webhooks / SMTP credentials. Should be part of the live-mode
   smoke checklist (10.1 carry-forward).
4. **Per-TF RSI baseline measurement (Phase 9.4 follow-up)** —
   `rsi_4h` and `rsi_15m` are deployed but have not been measured
   against `rsi_universal`. Operator-runnable now via
   `scripts.backtest_baselines`. If results show one TF dominates,
   that informs which baseline to keep front-and-center in
   `docs/baselines.md`.
5. **Live-mode smoke checklist execution** (10.1 carry-forward) —
   walk the 9-step checklist in `docs/deployment.md` with a $100
   balance before flipping production to live mode at real sizing.
   Now particularly relevant: Phase 12.1's cross-cycle cap, Phase
   12.3's LLM timeout retry, Phase 14.1's per-strategy timeout
   override, Phase 12.4's Telegram push, and Phase 13.4 + 14.2's
   email push are all production-ready and should be exercised
   together.
6. **Body parity enforcement across three push backends** (12.4 +
   13.4 + 14.2 soft item) — if a deliberate divergence is ever
   warranted (Telegram-only Markdown deeplink, etc.), the spec
   invariant should be re-asserted explicitly in each builder. No
   mechanism enforces the in-sync invariant today; a single
   `_build_push_payload` helper feeding all three backends would
   close it. Low priority; only worth if a divergence is proposed.
7. **Periodic-in-loop `purge_old`** vs the current startup-only
   hook (Phase 11.4 carry) — still relevant if proposal volume
   grows enough that monthly records pile up between deploys /
   restarts.

## Cross-Check Result

- ✅ Complete: 5 requirements (2 FR + 1 NFR + 1 CON + 1
  phase-adjacent preserved)
- ⚠️ Partial: 0 requirements
- ❌ Gap: 0 requirements

**Phase 14 closes. The development plan's Current Status table now
shows every Phase 14 row as ✅ Complete. The mainline has no
non-deferred unchecked items. Carried-forward deferrals: 7.5 Tapbit
(longstanding). The TECH-DEBT tracker is empty for the first time
since Phase 10.5. Recommended Phase 15 shaping above the line:
operator live verification of the 14.1 chasulang 240s override
(real-money relevance — strategy was consistently dropping out of
cycles on prod, the override is in place but unverified live);
operator runs of the now-ready baselines + purge tooling;
3-channel push test trade verification; per-TF RSI baseline
measurement; live-mode smoke checklist execution against the
production-ready cross-cycle cap + LLM retry + per-strategy
timeout override + three-channel push stack.**
