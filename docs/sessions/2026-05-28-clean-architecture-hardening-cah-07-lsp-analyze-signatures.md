# Session: clean-architecture-hardening CAH-07 — LSP UNIFORM `analyze()` SIGNATURES (BEHAVIOR-PRESERVING SIGNATURE WIDENING)

Date: 2026-05-28
Unit: `clean-architecture-hardening`
Stage: Code Generation
Related plan: `aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md` — CAH-07 (Tier 2 LSP: uniform `analyze()` signatures across the baseline strategies).

> SEVENTH unit shipped from the `clean-architecture-hardening` plan, and the THIRD of the Tier 2 method
> extractions (after the standalone Tier 0 bugfix CAH-01, the three Tier 1 quick wins CAH-02 order-side
> helpers / CAH-03 `build_engine` inlining / CAH-04 dead-code-dedup sweep, and the two Tier 2 extractions
> CAH-05 `_handle_proposal` finalize helpers / CAH-06 long-function splits). This unit touches the strategy
> domain (`analyze()` signatures across the baseline strategies), so it carried a quant-trader-expert review
> in addition to qa-reviewer. CAH-08…CAH-15 remain planned.

## Scope

CAH-07 is a behavior-preserving Liskov-substitution fix: it widens truncated strategy `analyze()` signatures
so they match the `BaseStrategy.analyze` contract. The base declares two keyword-only parameters that several
baseline strategies had dropped from their overrides; a single-timeframe strategy mis-routed a multi-TF call
would have raised a `TypeError` instead of safely ignoring the extra kwargs. The fix makes the base contract
honest without changing any signal.

Added the keyword-only
`*, ohlcv_by_timeframe: dict[str, list[OHLCV]] | None = None, current_price: Decimal | None = None`
(matching `BaseStrategy.analyze`, `src/strategy/base.py:399-401`) to the truncated strategy `analyze`
signatures.

**The plan named 6 truncated strategies; verification found 10 truncated, and all 10 were widened.** The 10:

- `rsi`
- `ma_crossover`
- `momentum_pinball_orb`
- `turtle_soup_reclaim`
- `weinstein_stage2_filter`
- `raschke_holy_grail`
- `vcp_breakout`
- `session_vwap_pullback`
- `bollinger_bands`
- `vwap_mean_reversion`

`tsmom_vol_breakout` was already compliant and was left untouched. The added params are unused in every body —
pure signature widening, no indicator / signal / threshold / return touched (3 added lines per file, identical
across all 10).

2 new LSP contract tests in `tests/test_baseline_strategies.py`: a signature-inspection test (asserts the two
params exist and are `KEYWORD_ONLY` on every loaded strategy) and a callable-with-kwargs test (calls each
strategy with both kwargs supplied). Both iterate the LIVE `load_all_strategies()` registry rather than a
hardcoded subset, so a future strategy that re-drops the params is caught automatically.

## Process / verdicts

senior-developer implemented → quant-trader-expert 🟢 → qa-reviewer 🟢. Strategy-domain unit, so it carried
the quant review in addition to qa.

### Quant 🟢

quant-trader-expert returned 🟢: the diff is signature-only across all 10 strategies — 3 added lines each,
with no indicator / signal / threshold / return touched. The one hazard the quant inspected and cleared is the
`current_price` local-shadowing: in every one of the 10 files a local variable named `current_price` is
reassigned UNCONDITIONALLY (e.g. from the last close), and that reassignment PRECEDES any read in every file,
so the incoming `current_price` kwarg cannot alter signals — the shadowing is BENIGN today. All 10 strategies
are single-timeframe and correctly ignore `ohlcv_by_timeframe`.

### QA 🟢

qa-reviewer returned 🟢: **2258 passed (+2)**; ruff + mypy clean — the new annotations type-check against the
base across callers. All 10 diffs are identical 3-line additions. Completeness was confirmed via grep — 11
`async def analyze` definitions exist, the 10 widened plus the pre-compliant `tsmom_vol_breakout`. The contract
tests iterate the live `load_all_strategies()` registry (not a hardcoded subset) and assert `KEYWORD_ONLY`.

## Files Changed

- **Modified**:
  - `strategies/rsi.py` — `analyze()` widened with the two keyword-only kwargs (unused).
  - `strategies/ma_crossover.py` — same.
  - `strategies/momentum_pinball_orb.py` — same.
  - `strategies/turtle_soup_reclaim.py` — same.
  - `strategies/weinstein_stage2_filter.py` — same.
  - `strategies/raschke_holy_grail.py` — same.
  - `strategies/vcp_breakout.py` — same.
  - `strategies/session_vwap_pullback.py` — same.
  - `strategies/bollinger_bands.py` — same.
  - `strategies/vwap_mean_reversion.py` — same.
- **Created**:
  - (tests appended) `tests/test_baseline_strategies.py` — 2 new LSP contract tests (signature inspection
    asserting the two params are `KEYWORD_ONLY`; callable-with-kwargs over `load_all_strategies()`).

`tsmom_vol_breakout` was already compliant and was NOT modified. No `src/` code touched — the change is confined
to `strategies/*.py` override signatures and one test file.

## Key Decisions

| Decision | Rationale |
|---|---|
| Widen all 10 truncated strategies, not just the 6 the plan named | Verification found 10 `analyze()` overrides truncated (the plan undercounted at 6). Widening only the named 6 would leave 4 strategies still violating the base contract — the same `TypeError`-on-misrouted-multi-TF-call hazard the unit exists to close. The completeness was confirmed via grep (11 `async def analyze`, 10 truncated + pre-compliant `tsmom_vol_breakout`). |
| Pure signature widening — added params unused in every body | The base contract is what was dishonest; the strategies' single-TF signal logic is correct as-is. Touching any body would widen the quant surface for no behavioral gain. All 10 diffs are identical 3-line additions. |
| Match `BaseStrategy.analyze` exactly (`src/strategy/base.py:399-401`) | The keyword-only `*, ohlcv_by_timeframe: dict[str, list[OHLCV]] \| None = None, current_price: Decimal \| None = None` is copied from the base so the override is a true Liskov-compatible widening, not a near-match that mypy would still flag. |
| Leave `tsmom_vol_breakout` untouched | It already declared the params; re-touching it would add noise with no contract gain. |
| LSP contract tests iterate `load_all_strategies()`, not a hardcoded list | A registry-driven test catches any future strategy that re-drops the params; a hardcoded subset would silently miss new violators. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2258 passed (+2 from the 2256 CAH-06 baseline)**, 0 failed.
- `ruff check`: clean.
- `mypy`: clean — the new annotations type-check against `BaseStrategy.analyze` across callers.
- Completeness confirmed via grep: 11 `async def analyze` definitions, the 10 widened + the pre-compliant
  `tsmom_vol_breakout`.

## Potential Risks

- **`current_price` local-shadowing is a non-blocking WATCH-ITEM (not a DEBT item).** In all 10 widened
  strategies a local variable named `current_price` is reassigned UNCONDITIONALLY before any read, so the new
  incoming `current_price` kwarg is benign today (the local clobbers it before it can influence any signal).
  If a FUTURE edit wires one of these strategies to actually CONSUME the live `current_price` kwarg, the
  unconditional local reassignment would clobber the passed value — at that point the local should be renamed
  (e.g. `last_close`) so the kwarg and the derived last-close are distinct. This is a watch-item recorded here,
  deliberately NOT filed as a DEBT item: there is no defect to fix today, only a trap to remember if the kwarg
  is ever made load-bearing.
- **The contract tests are the regression boundary for the uniform signature.** They iterate
  `load_all_strategies()` and assert both params exist as `KEYWORD_ONLY`. A future strategy that drops the
  params, or makes them positional, will fail these tests rather than silently re-introducing the LSP gap.

## TECH-DEBT Items

No new DEBT item filed — the plan doc + unit-of-work track CAH-07. The `current_price` local-shadowing is
recorded above as a non-blocking WATCH-ITEM, deliberately NOT filed as DEBT (benign today; only relevant if a
future edit wires these strategies to consume the live `current_price` kwarg). A Change-History row dated
2026-05-28 was added to `docs/TECH-DEBT.md` for the audit trail (the third Tier 2 method extraction:
behavior-preserving LSP signature widening across 10 strategies, +2 tests).

## Remaining Work

CAH-08…CAH-15 remain planned in
`aidlc-docs/construction/plans/clean-architecture-hardening-code-generation-plan.md`. Next action:
**CAH-08 (Tier 3 module splits)** — `performance.py` → `performance.py` + `trade_history.py` [STRAT-F1]; move
the replay shared logic `tools` → `proposal/replay.py` [LAYER-F5]; pure file moves + re-export, low risk.

No ADR needed — CAH-07 is a focused Tier 2 LSP signature widening. It introduces no new component boundary
(the `BaseStrategy.analyze` contract already existed — the strategies are being brought back INTO conformance,
not a new abstraction), locks in no new constraint future work must respect beyond the pre-existing base
contract, and chooses between no competing long-term designs (the widen-all-10-not-6 and leave-bodies-untouched
calls are local conformance / behavior-preservation judgements recorded in the Key Decisions table). The audit
value lives in this session log and the Change-History row, not in an ADR.
</content>
</invoke>
