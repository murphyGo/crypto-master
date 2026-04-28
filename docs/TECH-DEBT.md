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

### DEBT-001: Pre-Existing Lint/Type Sweep

| Field | Value |
|-------|-------|
| **Priority** | Medium |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 10.5 |
| **Component** | Cross-cutting (src/ai, src/strategy, src/feedback, src/trading, tests/, project tooling) |

**Description:**
Phase 10.5's touch-and-verify discipline surfaced lint/type errors that pre-exist this cycle but had not been recorded as debt. Two groups:

1. **18 pre-existing ruff errors:**
   - `B904` raise-from in `src/ai/claude.py`, `src/strategy/loader.py`, `src/feedback/loop.py`
   - `UP035` typing imports
   - `F841` / `F401` in tests

2. **24 pre-existing mypy errors:**
   - `src/trading/live.py` untyped object returns at lines 235, 244, 252, 438, 445
   - `src/ai/improver.py:280` arg-type
   - `types-PyYAML` missing from dev dependencies

**Impact:**
- The errors do not block development today (each module's tests still pass).
- They obscure new errors: future cycles that touch these files cannot rely on a "ruff/mypy clean" baseline as a gate signal — every cycle has to triage which errors are pre-existing vs newly introduced.
- The mypy `live.py` cluster in particular is on the live trading path; tightening those return types would surface real type-narrowing opportunities.

**Suggested Resolution:**
- One focused sweep cycle: fix all 18 ruff errors and the 24 mypy errors in a single PR. No functional change; pure typing/lint hygiene.
- Add `types-PyYAML` to `pyproject.toml`'s dev extras to drop the mypy import-untyped warning permanently.
- Once clean, consider adding a CI gate on ruff + mypy so future regressions are blocked at PR time rather than recorded as debt.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-10.5-volume-aware-default-paths.md`
- Dev report flagged these as suggested TECH-DEBT items; auditor judged groups 1 + 2 worth recording, group 3 (`DEFAULT_*_PATH` rename) skipped as not worth the noise.

### DEBT-002: OHLCV Per-Technique Refetch in Multi-Technique Scan

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Phase** | Surfaced during Phase 10.6 |
| **Component** | `src/proposal/engine.py` (`_propose_all_for_symbol`) |

**Description:**
Phase 10.6's multi-technique scan calls `_propose_all_for_symbol`, which re-fetches OHLCV per technique. This produces N×M `get_ohlcv` calls per symbol per cycle (N = techniques, M = timeframes), versus 1×M previously when only one technique ran per symbol.

Two concerns, both operational rather than correctness:

1. **Temporal-consistency drift** — technique A could see candle T while technique B sees T+δ if a candle rolls mid-cycle. Quant flagged this as 🟡 in post-review: "no look-ahead bias in strict sense (every fetch is now-relative)" but the per-technique candle skew is real.
2. **API rate-limit pressure at scale** — current envelope (5 symbols × 5 strategies × 4 timeframes = 100 calls/cycle) is fine for single-machine deployments. As `M` grows (more multi-TF strategies) or `N` grows (more baselines), the call count compounds.

**Impact:**
- No correctness defect today; the existing 100-calls/cycle envelope sits well inside Binance's rate limits.
- Will start to bite once a second multi-TF strategy lands (chasulang_ict_smc is currently the only one) or the symbol list grows beyond 5.
- The temporal drift is observable but not measurable in current production logs.

**Suggested Resolution:**
- Cache OHLCV per `(symbol, timeframe)` for the duration of one `propose_*` call. The cache lives only inside the public method's frame, so there is no global-state risk.
- Alternative: hoist the OHLCV fetch above the technique loop in `_propose_all_for_symbol` and pass the dict down. Same effect, simpler than a cache.

**Related:**
- Surfaced in: `docs/sessions/2026-04-28-phase-10.6-multi-technique-scan.md`
- Quant code review flagged as 🟡 in post-review (item 2: Look-ahead).

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

*No resolved items yet.*

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Active | 3 |
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 2 |
| Resolved (All Time) | 0 |

---

## Change History

| Date | Action | Item |
|------|--------|------|
| 2026-04-05 | Created | Initial TECH-DEBT tracker |
| 2026-04-28 | Added | DEBT-001 Pre-Existing Lint/Type Sweep (Medium) — surfaced during Phase 10.5 |
| 2026-04-28 | Added | DEBT-002 OHLCV Per-Technique Refetch in Multi-Technique Scan (Low) — surfaced during Phase 10.6 |
| 2026-04-28 | Added | DEBT-003 EngineConfig Remaining Fields Not Env-Overridable (Low) — surfaced during Phase 10.2 |
