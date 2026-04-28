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

_(none — all tracked items resolved)_

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

### DEBT-005: ccxt typing in `src/exchange/binance.py` ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 12.2 added `CCXTClient` Protocol covering 10 ccxt methods used (`load_markets`, `close`, `fetch_ohlcv`, `fetch_ticker`, `fetch_balance`, `create_market_order`, `create_limit_order`, `cancel_order`, `fetch_order`, `fetch_open_orders`); `_client` typed as `CCXTClient \| None`. mypy: 11 errors → 0. |

### DEBT-006: `src/exchange/factory.py` shape drift ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 12.2 investigated — NOT a behavioural mismatch. Registry's `type[BaseExchange]` widens away subclass `__init__` params. Resolved with tightly-scoped `cast(Any, exchange_class)(...)` + comment explaining the typing gap. mypy: 3 errors → 0. |

### DEBT-007: Dashboard Streamlit type errors ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 12.2 added `Literal` types for theme constants, `StreamlitPage` import for navigation, `cast(...)` on `st.metric` numeric values. mypy: 13 errors → 0. |

### DEBT-008: `src/main.py` lambda annotation ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 12.2 added targeted `# type: ignore[misc]` (canonical case for asyncio signal-handler callback shape mismatch). mypy: 1 error → 0. |

### DEBT-009: `scripts/lint.sh --fix` unsafe for CI ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.1 split `scripts/lint.sh` into CI-safe (no `--fix`) + dev-only `scripts/lint-fix.sh`. |

### DEBT-010: Long+Short Same-Symbol Test Gap ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.1 added `test_cap_blocks_opposite_side_same_symbol`; verifies long+short same-symbol cap path matches single-side cap behaviour. |

### DEBT-011: Dashboard `dict[str, object]` casts ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.1 introduced per-page TypedDicts (`TradingSummaryMetrics`, `EngineSummaryMetrics`) replacing `dict[str, object]`; `cast()` calls dropped. |

### DEBT-003: EngineConfig Remaining Fields Not Env-Overridable ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.2 added `engine_monitor_interval` / `engine_bitcoin_symbol` / `engine_altcoin_top_k` / `engine_actor` Settings fields with env override; `build_engine` wires all 4 to `EngineConfig`. |

### DEBT-004: Baseline Backtest Script Follow-ups ✅

| Field | Value |
|-------|-------|
| **Priority** | Low |
| **Created** | 2026-04-28 |
| **Resolved** | 2026-04-28 |
| **Resolution** | Phase 13.3 added `since: int | None = None` to `BaseExchange.get_ohlcv` ABC; Binance + Bybit forward to ccxt; `scripts/backtest_baselines.py` drops the `_client` reach-around. |

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Active | 0 |
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |
| Resolved (All Time) | 11 |

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
| 2026-04-28 | Resolved | DEBT-005 ccxt typing in `src/exchange/binance.py` — Phase 12.2 added `CCXTClient` Protocol (10 methods) |
| 2026-04-28 | Resolved | DEBT-006 `src/exchange/factory.py` shape drift — Phase 12.2 confirmed typing-system gap (not behavioural); `cast(Any, ...)` + comment |
| 2026-04-28 | Resolved | DEBT-007 Dashboard Streamlit type errors — Phase 12.2 `Literal` types + `StreamlitPage` + numeric casts |
| 2026-04-28 | Resolved | DEBT-008 `src/main.py` lambda annotation — Phase 12.2 targeted `# type: ignore[misc]` |
| 2026-04-28 | Added | DEBT-011 Dashboard `dict[str, object]` casts (Low) — surfaced during Phase 12.2 |
| 2026-04-28 | Resolved | DEBT-009 `scripts/lint.sh --fix` unsafe for CI — Phase 13.1 split into CI-safe lint.sh (no `--fix`) + dev-only lint-fix.sh |
| 2026-04-28 | Resolved | DEBT-010 Long+Short Same-Symbol Test Gap — Phase 13.1 added `test_cap_blocks_opposite_side_same_symbol` |
| 2026-04-28 | Resolved | DEBT-011 Dashboard `dict[str, object]` casts — Phase 13.1 introduced per-page TypedDicts (TradingSummaryMetrics, EngineSummaryMetrics); `cast()` calls dropped |
| 2026-04-28 | Resolved | DEBT-003 EngineConfig Remaining Fields Not Env-Overridable — Phase 13.2 added `engine_monitor_interval` / `engine_bitcoin_symbol` / `engine_altcoin_top_k` / `engine_actor` Settings fields; `build_engine` wires all 4 |
| 2026-04-28 | Resolved | DEBT-004 Baseline Backtest Script Follow-ups — Phase 13.3 added `since: int | None = None` to `BaseExchange.get_ohlcv` ABC; Binance + Bybit forward to ccxt; `scripts/backtest_baselines.py` drops the `_client` reach-around |
