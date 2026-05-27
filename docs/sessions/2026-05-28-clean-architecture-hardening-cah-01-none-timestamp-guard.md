# Session: clean-architecture-hardening CAH-01 — EXCHANGE `None`-TIMESTAMP GUARD (BUGFIX)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-01 (Tier 0 bugfix; the only real bug in the clean-code-architecture review).

> FIRST unit shipped from the `clean-architecture-hardening` plan (created 2026-05-28 from the guide-driven
> clean-code-architecture review). CAH-01 is the standalone Tier 0 bugfix, shipped ahead of the Tier 1
> quick wins. CAH-02…CAH-15 remain planned. This is a trading-domain unit, so it carried a
> quant-trader-expert review in addition to qa-reviewer.

## Scope

CAH-01 closes the exchange `None`-timestamp guard. `from_unix_ms(None)` raised a `TypeError` that escaped
the adapters' `RateLimitExceeded` / `CCXTExchangeError` ladders, violating `BaseExchange`'s
`ExchangeAPIError`-only contract (ccxt returns `None` timestamps on some venues, notably Bybit tickers).
Two surfaces were affected — `Order.created_at` and `Ticker.timestamp` — and they were treated
differently because their downstream consumers differ.

## Changes — CAH-01 `None`-timestamp guard

**`Order.created_at`** (required non-nullable `datetime`, `src/models.py`): a missing / `None` raw
timestamp now falls back to `now_utc()` with a `logger.warning`. The quant confirmed this is sound — there
is no age / time-stop / stale / reconciliation consumer of `Order.created_at`; those all key off
`Trade.entry_time` (derived from candle timestamps). `Order.created_at` is metadata only, so a `now_utc()`
fallback fabricates nothing that any decision path reads.

**`Ticker.timestamp`**: a first cut also used `now_utc()` here, but the quant flagged it 🔴 — that defeated
the stale-quote gate. A stale tape with a missing timestamp would have laundered into age ≈ 0 "fresh",
silently disabling the DEBT-033 stale-quote protection. The rework: `Ticker.timestamp` is now
`datetime | None` (`src/models.py`); both adapters pass `timestamp=None` + a warning when the raw
timestamp is missing; `_stale_quote_gate` (`src/runtime/engine.py` ~L4022) gained a `None` branch that
mirrors the existing over-age branch — WARN + fall-through when `reject_if_stale_quote=False`, HARD-REJECT
(`reason="stale_quote_no_live_data"`, `detail="ticker_timestamp_missing"`) when `True`. The fail-closed
switch is preserved and no freshness is fabricated.

Both adapters (`src/exchange/binance.py`, `src/exchange/bybit.py`) were fixed identically; CAH-11 will
later de-dup them into a shared `CcxtExchange` base.

## Process / verdicts

senior-developer implemented → quant-trader-expert 🔴 (ticker hazard) → senior-developer reworked →
quant-trader-expert 🟢 → qa-reviewer 🟢.

### Quant escalation — first pass 🔴 (ticker hazard)

The quant caught that fabricating `Ticker.timestamp = now_utc()` on a missing raw timestamp defeats the
stale-quote gate: a stale tape with no timestamp would be measured as age ≈ 0 and pass as fresh, disabling
the DEBT-033 protection. This is the load-bearing finding of the cycle — the `Order.created_at`
`now_utc()` fallback was fine precisely because nothing measures age off it, but the same move on
`Ticker.timestamp` was a silent correctness hole.

### Quant re-review — 🟢 (hazard closed)

After the rework to `datetime | None` + the gate `None` branch, the quant returned 🟢. Consumer audit:
the stale-quote gate is the ONLY `Ticker.timestamp` arithmetic consumer; the `Order.created_at`
`now_utc()` fallback is sound (metadata only, no age/time-stop/stale/reconciliation consumer).

### QA 🟢

qa-reviewer returned 🟢: 2245 passed, ruff + mypy clean. The `datetime | None` model change is type-safe
repo-wide; both gate branches (None + over-age) are tested; scope is clean.

## Files Changed

- **Modified**:
  - `src/models.py` — `Ticker.timestamp` widened to `datetime | None`; `Order.created_at` `now_utc()`
    fallback on missing/None.
  - `src/exchange/binance.py` — pass `timestamp=None` + warning on a missing raw ticker timestamp; order
    `created_at` fallback path.
  - `src/exchange/bybit.py` — same fix as binance (identical; CAH-11 will de-dup).
  - `src/runtime/engine.py` — `_stale_quote_gate` (~L4022) gained a `None` branch mirroring the over-age
    branch: WARN + fall-through when `reject_if_stale_quote=False`, HARD-REJECT
    (`reason="stale_quote_no_live_data"`, `detail="ticker_timestamp_missing"`) when `True`.
  - `tests/test_exchange_binance.py` — ticker None-timestamp (is None + warning) + order None-timestamp
    (now_utc + warning) + numeric-regression.
  - `tests/test_exchange_bybit.py` — same coverage as binance.
  - `tests/test_runtime_engine.py` — 2 stale-quote-gate None-branch tests.

## Key Decisions

| Decision | Rationale |
|---|---|
| `Order.created_at` → `now_utc()` fallback on missing/None | Metadata only; quant confirmed no age/time-stop/stale/reconciliation consumer reads it (those key off `Trade.entry_time` from candle timestamps). A fabricated created_at misleads no decision path. |
| `Ticker.timestamp` → `datetime \| None` (NOT a `now_utc()` fallback) | The quant 🔴: a `now_utc()` fallback laundered a stale tape into age ≈ 0 "fresh" and silently disabled the DEBT-033 stale-quote protection. Widening to nullable preserves the truth (timestamp genuinely missing) so the gate can decide. |
| `_stale_quote_gate` None branch mirrors the over-age branch | Fail-closed switch preserved end to end: WARN + fall-through when `reject_if_stale_quote=False`, HARD-REJECT when `True`. No fabricated freshness; a missing timestamp is treated exactly as conservatively as an over-age one. |
| `detail="ticker_timestamp_missing"` discriminator on the hard-reject | Distinguishes a missing-timestamp rejection from an over-age rejection within the shared `reason="stale_quote_no_live_data"` for diagnosis. |
| Both adapters fixed identically (no shared helper yet) | De-dup is explicitly CAH-11's scope (`CcxtExchange` base). Fixing both inline keeps CAH-01 a focused bugfix and avoids pulling the refactor forward. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2245 passed**, 0 failed (+10 from the 2235 baseline at the start of
  `clean-architecture-hardening`). New tests: ticker None-timestamp (is None + warning) × 2 adapters,
  order None-timestamp (now_utc + warning) × 2 adapters, numeric-regression × 2, + 2 stale-quote-gate
  None-branch tests in `tests/test_runtime_engine.py`.
- `ruff check`: clean.
- `mypy`: clean — the `datetime | None` model change is type-safe repo-wide.

## Potential Risks

- **The `Ticker.timestamp = datetime | None` widening is a repo-wide model change.** Any future
  consumer that does timestamp arithmetic on `Ticker.timestamp` without a None-guard will now hit a
  type error rather than a silent age ≈ 0. mypy currently confirms the stale-quote gate is the ONLY
  arithmetic consumer and it is guarded — but the nullable contract must be respected by any new reader.
  This is the intended, safe direction (truthful nullability over a fabricated value), but it is a
  contract that future work must honour.

- **Both adapters carry the fix as duplicated code until CAH-11.** A future change to one adapter's
  timestamp handling that is not mirrored to the other would drift the two venues' behaviour silently.
  The duplication is deliberate (CAH-11 de-dups) and tested identically on both sides, but it is live
  duplication in the interim.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-01. A Change-History row dated 2026-05-28
was added to `docs/TECH-DEBT.md` because the stale-quote None-timestamp bug is a real correctness fix
worth the audit trail.

Non-blocking follow-up (quant, optional): a distinct `error_type` tag (e.g. `stale_ticker_no_timestamp`)
for venue-health monitoring separation — the missing-timestamp hard-reject currently shares
`error_type=stale_ticker`, discriminated only by `detail`. Monitoring ergonomics, not correctness; not
filed as DEBT, recorded here for the next monitoring pass.

## Remaining Work

CAH-02…CAH-15 remain planned in `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`.
Next action: **CAH-02 (order-side helpers)**, the first of the Tier 1 quick wins.

No ADR needed — CAH-01 is a focused Tier 0 bugfix. The `Ticker.timestamp` widening to `datetime | None`
is a nullability correction to an existing model field driven by a real consumer hazard, not a new
component boundary or a choice between competing long-term designs; the gate's None branch mirrors the
existing over-age branch rather than introducing a new abstraction. The decision rationale is recorded
in the Key Decisions table above, which is the right home for it.
</content>
</invoke>
