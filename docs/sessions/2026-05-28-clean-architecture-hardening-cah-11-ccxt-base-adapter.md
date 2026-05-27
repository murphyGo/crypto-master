# Session: clean-architecture-hardening CAH-11 — TIER 4 `CcxtExchange` BASE ADAPTER DEDUP (EXCH-F1 + EXCH-F3 + EXCH-F5)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-11 (Tier 4 ports / typed contracts: `CcxtExchange` base adapter dedup [EXCH-F1] + bybit `_ensure_connected` annotation [EXCH-F3] + port `base.py` helper relocation [EXCH-F5]).

> ELEVENTH unit shipped from the `clean-architecture-hardening` plan, and the SECOND of the Tier 4 ports /
> typed-contracts units (after CAH-10's AI / feedback DIP cluster). It follows the standalone Tier 0 bugfix
> CAH-01, the three Tier 1 quick wins (CAH-02 order-side helpers / CAH-03 `build_engine` inlining / CAH-04
> dead-code-dedup sweep), the three Tier 2 method extractions (CAH-05 `_handle_proposal` finalize helpers /
> CAH-06 long-function splits / CAH-07 LSP uniform `analyze()` signatures), the two Tier 3 module splits
> (CAH-08 `performance.py` split + replay relocation / CAH-09 dashboard decomposition), and CAH-10 (the AI /
> feedback DIP cluster). Unlike CAH-10, CAH-11 IS trading-domain — it touches the live-order path's exchange
> adapters — so it carried a quant-trader-expert review in addition to qa-reviewer. It depends on CAH-01
> (already shipped): the `None`-timestamp guard CAH-01 had to apply identically to both adapters is the
> motivating duplication this unit removes. CAH-12…CAH-15 remain planned.

## Scope

CAH-11 is a behavior-preserving refactor that extracts a shared `CcxtExchange(BaseExchange)` base from the
~95%-identical `binance.py` / `bybit.py` adapter bodies. The two ccxt adapters had drifted into near-duplicate
implementations — the same client wiring, the same `TIMEFRAME_MAP`, the same exception ladders, the same
`_extract_ccxt_fee` / `_decimal_or_none` helpers, and — as CAH-01 made painfully concrete — the same
`None`-timestamp guards written out twice. CAH-11 collapses that duplication into one base, leaving the
subclasses thin. It serves NFR-009 (adding a new exchange should be a new thin adapter, not edits rippled
across the existing siblings).

### Sub-item 1 — EXCH-F1: `CcxtExchange` base adapter (dedup)

New `src/exchange/ccxt_base.py` holds the shared adapter substance: the `CCXTClient` Protocol, `TIMEFRAME_MAP`,
all shared methods (`create_order` / `_map_order` / `_map_order_status` / cancel / get / get_open / OHLCV
fetch, etc.), the exception ladders (`RateLimitExceeded` / `CCXTExchangeError` → `ExchangeAPIError`-only
contract), the CAH-01 `None`-timestamp guards now written ONCE, and the moved `_extract_ccxt_fee` /
`_decimal_or_none` helpers. The subclasses are now thin: they override only `_build_client()` plus the
per-venue knobs `OHLCV_LIMIT` (binance 1500 / bybit 200), name / URLs / logger, and the
`@register_exchange` decorator.

The divergence set — what intentionally STAYED per-subclass — is the load-bearing part of the refactor:

- **`_build_client()`** is the override hook. binance keeps its `binanceusdm` (futures) vs `binance` (spot)
  branch PLUS its options block; bybit keeps a single `ccxt.bybit` construction with **NO `defaultType` key**.
- **`OHLCV_LIMIT`** is a class attribute: binance `1500`, bybit `200` — the per-venue OHLCV cap is preserved.
- **name / URLs / logger / `@register_exchange`** stay per-subclass so the factory resolves each venue and
  per-venue logging / metadata is unchanged.

### Sub-item 2 — EXCH-F5: port `base.py` helper relocation

The `_extract_ccxt_fee` / `_decimal_or_none` helpers were moved OUT of the port `base.py` (which now is a pure
port + domain exceptions, with the now-unused imports dropped) and INTO `ccxt_base.py` where they belong with
the concrete ccxt adapter substance. This cleans the port boundary — `base.py` no longer carries ccxt-flavoured
implementation helpers.

### Sub-item 3 — EXCH-F3: bybit `_ensure_connected` annotation

The bybit `_ensure_connected` return annotation was collapsed to `-> CCXTClient` (matching the shared
Protocol type now living in `ccxt_base.py`).

## Process / verdicts

senior-developer implemented all three sub-items as one behavior-preserving commit → quant-trader-expert 🟢
(this is a trading-domain unit, live-order path) → qa-reviewer 🟢. The homogenization risk — that extracting a
shared base could accidentally flatten the per-venue `_build_client` differences (especially bybit's deliberate
ABSENCE of a `defaultType` key) — was explicitly avoided and verified by both reviewers.

### quant-trader-expert 🟢

Per-venue behavior is IDENTICAL on the live-order path: `create_order` / `_map_order` / `_map_order_status` /
cancel / get / get_open are byte-for-byte preserved; the OHLCV cap is preserved per venue (binance 1500 /
bybit 200 via the `OHLCV_LIMIT` class attribute). `_build_client` fidelity confirmed — binance keeps
`binanceusdm` / `binance` + its options block, bybit keeps a single `ccxt.bybit` with NO `defaultType` key
(the homogenization risk avoided). The exception ladders and the CAH-01 `None`-timestamp guard fire for both
venues. LSP intact; the factory resolves both adapters. **Cosmetic non-blocking note**: the CAH-01 warning
text is now derived from `self.name.capitalize()` (so it reads per-venue from the shared base rather than
being hand-written per adapter) — the asserted substrings are unchanged, so no test moved.

### qa-reviewer 🟢

Full suite **2289 passed** (+19 from the 2270 CAH-10 baseline); ruff + mypy clean across 99 files. The
behavior-preservation proof: `git diff` on the 3 existing exchange test files is **EMPTY** — the existing
adapter suites pass unchanged against the refactored code. The moved method bodies are byte-identical; the
EXCH-F5 helpers relocated cleanly with no broken importer; the patch targets still resolve via the kept
module-level `ccxt` import. The new toy-subclass extensibility test genuinely drives the base via only
`_build_client` + `OHLCV_LIMIT` — confirming the NFR-009 "new exchange = new thin adapter" extensibility claim
is real, not aspirational.

## Files Changed

- **Created**:
  - `src/exchange/ccxt_base.py` — NEW shared `CcxtExchange(BaseExchange)` base: the `CCXTClient` Protocol,
    `TIMEFRAME_MAP`, all shared adapter methods, the exception ladders, the CAH-01 `None`-timestamp guards
    (written ONCE here now), and the moved `_extract_ccxt_fee` / `_decimal_or_none` helpers.
  - `tests/test_exchange_ccxt_base.py` — base / extensibility tests, including the toy-subclass test that
    drives the shared base via only `_build_client` + `OHLCV_LIMIT` (the NFR-009 extensibility proof).
- **Modified**:
  - `src/exchange/binance.py` — now thin: overrides `_build_client()` (futures/spot branch + options block),
    `OHLCV_LIMIT = 1500`, name / URLs / logger, `@register_exchange`. Shared substance removed (now in
    `ccxt_base.py`).
  - `src/exchange/bybit.py` — now thin: overrides `_build_client()` (single `ccxt.bybit`, NO `defaultType`),
    `OHLCV_LIMIT = 200`, name / URLs / logger, `@register_exchange`; EXCH-F3 `_ensure_connected` annotation
    collapsed to `-> CCXTClient`.
  - `src/exchange/base.py` — EXCH-F5: `_extract_ccxt_fee` / `_decimal_or_none` helpers moved OUT to
    `ccxt_base.py`; `base.py` is now a pure port + domain exceptions with the now-unused imports dropped.

The changes are a behavior-preserving extraction on the exchange adapter layer; no trading-math, sizing, gate,
or signal path was touched.

## Key Decisions

| Decision | Rationale |
|---|---|
| Extract a shared `CcxtExchange(BaseExchange)` base into `src/exchange/ccxt_base.py`; make `binance.py` / `bybit.py` thin subclasses | The two adapters were ~95% identical; CAH-01 having to write the `None`-timestamp guard into BOTH was the concrete cost. One base means the shared substance (methods, exception ladders, guards, helpers) lives in one place, and a new exchange is a new thin adapter — directly serving NFR-009. |
| `_build_client()` is the only behavioral override hook (plus the `OHLCV_LIMIT` / name / URLs / logger / decorator knobs) | The genuine per-venue divergence is the client wiring: binance needs the futures/spot branch + options block, bybit needs a single `ccxt.bybit` with NO `defaultType`. Funneling exactly that divergence through one overridable method keeps the base shared while preserving each venue's construction byte-for-byte — the homogenization risk (flattening bybit's no-`defaultType` into a binance-style options block) is structurally avoided. |
| Keep `OHLCV_LIMIT` as a per-subclass class attribute (binance 1500 / bybit 200) | The OHLCV fetch cap is genuinely per-venue; expressing it as a class attribute the base reads keeps the cap correct without per-venue method overrides. |
| EXCH-F5: move `_extract_ccxt_fee` / `_decimal_or_none` out of port `base.py` into `ccxt_base.py` | These are ccxt-flavoured implementation helpers, not port concerns; relocating them leaves `base.py` a pure port + domain exceptions and co-locates the helpers with the concrete adapter substance that uses them. The now-unused imports were dropped from `base.py`. |
| Derive the CAH-01 warning text from `self.name.capitalize()` in the shared base | With the guard written once, the per-venue warning prefix must come from the instance rather than a hand-written literal per adapter. The asserted substrings are unchanged, so no test moved (quant's cosmetic non-blocking note). |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2289 passed**, 0 failed (+19 from the 2270 CAH-10 baseline — the new
  `tests/test_exchange_ccxt_base.py` base / extensibility suite).
- `ruff check`: clean.
- `mypy`: clean — 99 source files.
- Behavior-preservation proof: `git diff` on the 3 existing exchange test files is **EMPTY** — the existing
  Binance / Bybit adapter suites pass unchanged against the refactored code.
- Per-venue live-order path (`create_order` / `_map_order` / `_map_order_status` / cancel / get / get_open)
  byte-for-byte preserved; OHLCV cap preserved per venue (binance 1500 / bybit 200).
- `_build_client` fidelity: binance keeps `binanceusdm` / `binance` + options block; bybit keeps a single
  `ccxt.bybit` with NO `defaultType` key (homogenization risk avoided).
- Extensibility (NFR-009): the toy-subclass test drives the shared base via only `_build_client` +
  `OHLCV_LIMIT`.

## Potential Risks

- **The `_build_client()` override is the per-venue divergence seam, and bybit's ABSENCE of a `defaultType`
  key is load-bearing.** binance's futures/spot branch + options block and bybit's single `ccxt.bybit` with NO
  `defaultType` are deliberately different client constructions; if a future edit "tidies" `_build_client`
  toward a shared default (e.g. hoisting a `defaultType` into the base, or collapsing the binance branch), the
  per-venue connection semantics would silently change. The override hook plus the toy-subclass extensibility
  test are the guard, but the reason the two `_build_client` bodies differ is recorded here so a later reader
  understands the divergence is intentional, not an oversight.
- **The CAH-01 `None`-timestamp guard now fires from the shared base for both venues.** This is the win (one
  guard, not two), but it also means a regression in the base now affects BOTH adapters at once rather than
  one. The existing exchange suites (unchanged `git diff`) are the regression net.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-11. A Change-History row dated 2026-05-28 was
added to `docs/TECH-DEBT.md` for the audit trail (the second Tier 4 ports / typed-contracts unit: the
`CcxtExchange` base adapter dedup [EXCH-F1] + bybit `_ensure_connected` annotation [EXCH-F3] + port `base.py`
helper relocation [EXCH-F5], +19 tests, all gates green). The quant's `self.name.capitalize()` warning-text
observation is a cosmetic non-blocking note, not a defect — recorded here, not filed.

## Remaining Work

CAH-12…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-12 (Tier 4: funnel state derivation + `ProposalRecord` transition methods [PROP-F1 + PROP-F8])** —
trading-domain, so it gets a quant-trader-expert review.

No ADR needed — CAH-11 is the planned Tier 4 `CcxtExchange` base adapter dedup, a behavior-preserving
extraction delivered as routine planned work against the clean-architecture review's findings
(EXCH-F1/EXCH-F3/EXCH-F5). It is not a contested design decision with competing long-term options: the
`BaseExchange` port already existed (CAH-11 introduces an intermediate shared concrete base under it, not a
new abstraction boundary), and the `_build_client` override hook / `OHLCV_LIMIT` knob / helper-relocation
choices are local DIP / cohesion judgements recorded in the Key Decisions table. NFR-009 (new exchange = new
thin adapter) is served, not re-litigated. The audit value lives in this session log and the Change-History
row, not in an ADR.
