# Crypto Master - Technical Debt Tracker

## Overview

This document tracks technical debt items identified during development. Items are prioritized and have escalation thresholds.

## Priority Levels & Escalation Thresholds

| Priority | Description | Escalation Threshold |
|----------|-------------|---------------------|
| **Critical** | Blocks development or causes failures | Immediate |
| **High** | Significant impact on quality/maintainability | 14 days |
| **Medium** | Moderate impact, should be addressed | 21 days |
| **Low** | Minor issues, address when convenient | 30 days |

## Active Debt Items

<!--
Template for new items:

### DEBT-XXX: [Title]

| Field | Value |
|-------|-------|
| **Priority** | Critical/High/Medium/Low |
| **Created** | YYYY-MM-DD |
| **Phase** | Phase N.M |
| **Component** | Component name |

**Description:**
[Detailed description of the debt item]

**Impact:**
[What is affected by this debt]

**Suggested Resolution:**
[How to resolve this debt]

**Related:**
- Issue/PR links
- Related DEBT items
-->

### DEBT-003: EngineConfig Remaining Fields Not Env-Overridable

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 10.2 |
| **Component** | `src/config.py` (`Settings`), `src/runtime/engine.py` (`EngineConfig`), `src/main.py` (`build_engine`) |

**Description:**
Phase 10.2 promoted four operationally-impactful `EngineConfig` fields to env vars (`engine_cycle_interval`, `engine_auto_approve_threshold`, `engine_symbols`, `engine_balance`). Four other `EngineConfig` fields remain hardcoded:

- `monitor_interval_seconds` — how often the engine's monitor loop polls open positions for SL/TP hits.
- `bitcoin_symbol` — the symbol used for `propose_bitcoin` (defaults to `"BTCUSDT"`).
- `altcoin_top_k` — the K in `propose_altcoins`'s top-K return.
- `actor` — the string recorded as the activity-log actor.

**Impact:**
- These are tunables operators rarely need to change. The judgement during 10.2 was that promoting them inflates the `Settings` surface for marginal gain.
- If an operator does hit one of these four needs in production (e.g. wants to tune `altcoin_top_k` or rename the activity-log actor), they have to do a code edit + redeploy — the same pre-10.2 friction.

**Suggested Resolution:**
- Repeat the Phase 10.2 pattern for whichever of the four fields actually needs operator-tunability in practice. Don't ship all four speculatively; wait until at least one operator request lands.
- The `engine_symbols` `NoDecode` + `field_validator(mode="before")` pattern is the template if a list field ever needs to be added.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-10.2-engineconfig-env-override.md`
- Predecessor: Phase 10.2 EngineConfig Env Override (4 of 8 fields shipped).

### DEBT-004: Baseline Backtest Script Follow-ups

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 10.3 |
| **Component** | `scripts/backtest_baselines.py`, `src/exchange/base.py` (`BaseExchange.get_ohlcv`) |

**Description:**
Phase 10.3 shipped `scripts/backtest_baselines.py` as the operator tooling that populates `docs/baselines.md`'s reference-numbers table. Two minor follow-ups surfaced from QA review:

1. **mypy nit at `scripts/backtest_baselines.py:241,248`** — `seen: set[int]` vs `seen.add(candle[0])` where `candle[0]` is typed `float`. One-line fix (`seen.add(int(ts))` or retype). Cosmetic; runtime behaviour correct because ccxt returns int ms — the type system just doesn't know that.

2. **`BaseExchange.get_ohlcv` doesn't accept `since`** — the script paginates by reaching into `BinanceExchange._client` to access the underlying ccxt client directly. This is gated to actually-needed cases (2160 candles for 3mo×1h, 2880 for 1mo×15m, both exceed the ~1500 cap), but it bypasses the framework abstraction. If a future phase extends `BaseExchange.get_ohlcv` to accept a `since` parameter, the script should drop the reach-around.

**Impact:**
- The mypy nit is cosmetic — runtime is correct, only the type system is unhappy.
- The `_client` reach-around is operationally fine (script is operator-invoked, not in any production path) but is a soft coupling between the script and `BinanceExchange`'s internal ccxt client. If the binance integration ever swaps clients, the script breaks.

**Suggested Resolution:**
- Fix the mypy nit in passing during the next cycle that touches the script (one-line change).
- Extend `BaseExchange.get_ohlcv` with an optional `since: int | None = None` parameter in a future framework cycle, then drop the reach-around. Don't ship the framework change speculatively — wait until a second use case appears.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-10.3-baseline-reference-numbers.md`
- Predecessor: Phase 10.3 Baseline Reference Numbers (operator tooling).

### DEBT-005: ccxt typing in `src/exchange/binance.py`

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 11.1 |
| **Component** | `src/exchange/binance.py` |

**Description:**
11 mypy errors in `src/exchange/binance.py` (mix of `attr-defined`, `valid-type`, and `no-any-return`) blocked on missing ccxt type stubs. ccxt does not ship `py.typed`, so attribute access on the client and type annotations referencing ccxt classes both fail mypy's checks.

Dev's note (verbatim): "11 mypy errors (attr-defined / valid-type / no-any-return) blocked on missing ccxt type stubs. Recommended fix: hand-rolled Protocol covering the 8+ ccxt methods used."

**Impact:**
- The errors do not affect runtime — ccxt is correctly used and tests pass.
- They prevent `mypy src/exchange/binance.py` from gating cleanly, weakening the post-11.1 baseline-clean contract for this one module.
- Cosmetic but recurrent: every cycle touching `binance.py` has to triage these as pre-existing.

**Suggested Resolution:**
- Hand-rolled Protocol covering the 8+ ccxt methods actually used by `BinanceExchange` (`fetch_balance`, `fetch_ohlcv`, `create_order`, `fetch_order`, `cancel_order`, `fetch_open_orders`, `fetch_my_trades`, `set_sandbox_mode`, etc.). Type the `_client` attribute as the Protocol; mypy then resolves attribute access without ccxt stubs.
- Alternative (cheaper): scoped `# type: ignore[attr-defined]` per call site. Phase 11.1 deliberately avoided this — Protocol is the cleaner fix.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-11.1-lint-type-sweep.md`
- Out-of-scope per Phase 11.1 spec.

### DEBT-006: `src/exchange/factory.py` shape drift

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 11.1 |
| **Component** | `src/exchange/factory.py` |

**Description:**
3 mypy errors in `src/exchange/factory.py`:

- Line 22 — untyped def.
- Line 91 — config kwarg type mismatch.
- Line 110 — return-value mismatch.

Looks like genuine API-shape drift between the factory's signatures and the exchange constructors / config it composes, not a typing-hygiene nit.

**Impact:**
- Runtime behaviour appears correct (existing tests pass) but the type-system says the contracts no longer line up with the call sites. If true, a real bug is one refactor away.
- Phase 11.1 deliberately did not touch these without a quant-trader-expert review — fixing the types blindly could mask a genuine API drift.

**Suggested Resolution:**
- Quant-trader-expert review of the three call sites first to determine whether the drift is a typing-hygiene gap or a real signature mismatch.
- Then either tighten the factory's annotations to match the call sites (if hygiene), or update the call sites to match the constructors (if drift). Don't pick one without the review.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-11.1-lint-type-sweep.md`
- Out-of-scope per Phase 11.1 spec.

### DEBT-007: Dashboard Streamlit type errors

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 11.1 |
| **Component** | `src/dashboard/{theme,app,pages/trading,pages/engine}.py` |

**Description:**
~13 mypy errors clustered across `src/dashboard/theme.py`, `src/dashboard/app.py`, `src/dashboard/pages/trading.py`, and `src/dashboard/pages/engine.py`. Mostly missing local annotations / casts on Streamlit / pandas-derived values where mypy cannot infer the narrowed type.

**Impact:**
- No runtime impact — Streamlit pages render correctly.
- Bundling them into one mini-sweep cycle is cheaper than fixing them one-at-a-time across four phases.

**Suggested Resolution:**
- One focused mini-sweep cycle covering the four files. Add the missing annotations / casts in a single PR. Same shape as DEBT-001's resolution but scoped to the dashboard.
- No functional change; pure typing hygiene.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-11.1-lint-type-sweep.md`
- Out-of-scope per Phase 11.1 spec.

### DEBT-008: `src/main.py:220` lambda annotation

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 11.1 |
| **Component** | `src/main.py` |

**Description:**
Single mypy error at `src/main.py:220` — `Cannot infer type of lambda`.

**Impact:**
- Cosmetic. One line.

**Suggested Resolution:**
- One-line fix candidate: replace the lambda with a typed `def`, or annotate the lambda's parameter via an assigned `Callable` annotation.
- Pick up in passing during the next cycle that touches `src/main.py`.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-11.1-lint-type-sweep.md`
- Out-of-scope per Phase 11.1 spec.

### DEBT-009: `scripts/lint.sh --fix` unsafe for CI

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 11.1 |
| **Component** | `scripts/lint.sh` |

**Description:**
QA flagged that `scripts/lint.sh:6` uses `ruff check src tests --fix`. The `--fix` flag silently rewrites source on lintable regressions instead of reporting them — fine for local dev convenience, unsafe for a CI gate (a CI run would mutate the working tree and pass green when the source had drifted).

**Impact:**
- No runtime impact; the script is operator/dev-invoked today.
- If the script is ever wired to CI as-is, regressions get auto-fixed in CI's checkout and never surface as failures, defeating the gate.

**Suggested Resolution:**
- Drop `--fix` for CI use, or split into two scripts: `lint.sh` (CI: report-only, no `--fix`) and `lint-fix.sh` (dev: with `--fix`).
- Document the contract in the script header so the next operator knows which is which.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-11.1-lint-type-sweep.md`
- QA verdict: 🟡 minor on Phase 11.1.

### DEBT-010: Long+Short Same-Symbol Test Gap

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 12.1 |
| **Component** | `tests/test_runtime_engine.py` |

**Description:**
Phase 12.1 shipped the cross-cycle position cap (`EngineConfig.max_open_positions_per_symbol`, default 1). Quant's review verbatim: the cap correctly blocks the long+short same-symbol case (cap counts trades regardless of side, which is the safe behaviour preventing accidental synthetic hedge), but the test suite does not explicitly cover that path.

The 5 tests added in Phase 12.1 cover default value, env wiring, cap-hit rejection, cap-not-reached execution, and other-symbol-doesn't-block. The long+short same-symbol path is a separate invariant (cap counts both sides toward the same denominator) that the current tests do not pin down.

**Impact:**
- Implementation is correct — long+short on the same symbol both count toward the cap, which is the safe behaviour (prevents an accidental synthetic hedge from a long arriving while a short is still open, or vice versa).
- Absence of an explicit test means a future refactor that splits the count by side could regress the protection without anything failing red. The cap would still pass its other tests but quietly let through the synthetic-hedge case.
- Risk envelope is unaffected today; the gap is purely defensive against future regression.

**Suggested Resolution:**
- Add `test_cap_blocks_opposite_side_same_symbol` in a follow-up cycle. Setup: existing open long position on `BTCUSDT`; proposal arrives for short on `BTCUSDT` with cap=1. Assert: cap-hit rejection fires (composite-accept passed but cap blocks; `proposals_rejected` increments; `PROPOSAL_REJECTED` logged with the symbol-cap reason; no `trader.open_position` call).
- Mirror the existing cap-hit test's shape; only difference is the side of the existing position vs the proposal's side.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-12.1-cross-cycle-position-cap.md`
- Quant verdict: 🟡 ship with note on Phase 12.1.

---

## Resolved Debt Items

<!--
Move resolved items here with resolution date and notes.

### DEBT-XXX: [Title] ✅

| Field | Value |
|-------|-------|
| **Priority** | [Original priority] |
| **Created** | YYYY-MM-DD |
| **Resolved** | YYYY-MM-DD |
| **Resolution** | [Brief description] |
-->

### DEBT-001: Pre-Existing Lint/Type Sweep ✅

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 11.1 cleared all 18 ruff + 12 in-scope mypy errors; ruff config migrated to `[tool.ruff.lint]`; `types-PyYAML` added. |

### DEBT-002: OHLCV Per-Technique Refetch in Multi-Technique Scan ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 11.2 added per-call (symbol, tf) cache; verified 3-symbol × 4-technique example drops from 12 → 3 fetches. |

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Active | 8 |
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 8 |
| Resolved (All Time) | 2 |

---

## Change History

| Date | Action | Item |
|------|--------|------|
| 2026-04-05 | Created | Initial TECH-DEBT tracker |
| 2026-04-28 | Added | DEBT-001 Pre-Existing Lint/Type Sweep (Medium) — surfaced during Phase 10.5 |
| 2026-04-28 | Added | DEBT-002 OHLCV Per-Technique Refetch in Multi-Technique Scan (Low) — surfaced during Phase 10.6 |
| 2026-04-28 | Added | DEBT-003 EngineConfig Remaining Fields Not Env-Overridable (Low) — surfaced during Phase 10.2 |
| 2026-04-28 | Added | DEBT-004 Baseline Backtest Script Follow-ups (Low) — surfaced during Phase 10.3 |
| 2026-04-28 | Resolved | DEBT-001 Pre-Existing Lint/Type Sweep — Phase 11.1 cleared all in-scope ruff + mypy errors |
| 2026-04-28 | Added | DEBT-005 ccxt typing in `src/exchange/binance.py` (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Added | DEBT-006 `src/exchange/factory.py` shape drift (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Added | DEBT-007 Dashboard Streamlit type errors (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Added | DEBT-008 `src/main.py:220` lambda annotation (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Added | DEBT-009 `scripts/lint.sh --fix` unsafe for CI (Low) — surfaced during Phase 11.1 |
| 2026-04-28 | Resolved | DEBT-002 OHLCV Per-Technique Refetch in Multi-Technique Scan — Phase 11.2 added per-call (symbol, tf) cache |
| 2026-04-28 | Added | DEBT-010 Long+Short Same-Symbol Test Gap (Low) — surfaced during Phase 12.1 |
