# Session: DEBT-065 synthetic-row leak into live-promotion gating fix

## Unit

- `proposal-runtime` (primary — promotion-gating consumer-site switch)
- Secondary unit: `runtime-reconciliation` (upstream source of synthetic
  `reconciliation_close` markers on `PerformanceRecord` that DEBT-065 was
  designed to fence off from CON-003 promotion gating)

## Related Requirements

- FR-013: Generate trading proposals — closest match for the
  `_score.sample_size` derivation that feeds `sample_factor` into the
  proposal scoring formula.
- FR-014: Store proposal history and outcomes — closest match for the
  `TechniquePerformance` aggregate over `PerformanceRecord` that this fix
  re-bases on a real-only sub-count.
- FR-029: Live-promotion safety gating — closest match for
  `ProposalEngine._cold_start_blocks_live` (the canonical CON-003
  cold-start gate) whose payload now reports real-only counts.
- NFR-007: Trading history storage integrity — synthetic markers exist to
  preserve the ledger shape while excluding rows from gating; this fix
  honours the original contract at `src/strategy/performance.py:214`.

## Scope

Closed DEBT-065 with option (b) from its suggested-resolution list — the
smaller-diff path. New `TechniquePerformance.real_trade_count` property
(`total_trades - synthetic_count`) added on `src/strategy/performance.py`
with a docstring citing DEBT-065; the 2 promotion-gating consumer sites
in `ProposalEngine` (`_cold_start_blocks_live` + `_score.sample_size`)
switched to read it. `total_trades` semantics intentionally preserved
for the operator-facing display surfaces (dashboard "Total Trades"
column at `src/dashboard/pages/strategies.py:118` + improver prompt
rendering at `src/ai/improver.py:667`) per the design intent that
operator counts should match what the underlying ledger holds. Filed
DEBT-070 (Low) for the ranking-side `total_trades` reads at
`src/proposal/engine.py:996, 1010, 1014, 1132` flagged by dev and
confirmed by QA — explicitly out of scope for DEBT-065 (gating-only).

## Changes

- `src/strategy/performance.py` — new `real_trade_count: int` property on
  `TechniquePerformance` defined as `total_trades - synthetic_count`;
  docstring cites DEBT-065.
- `src/proposal/engine.py` — 2 promotion-gating consumer sites switched
  from `perf.total_trades` to `perf.real_trade_count`:
  - `_cold_start_blocks_live` (~lines 1062-1068) — including the
    activity-log payload (`per_technique_trades`, `max_trades_observed`)
    which now reports real-only counts.
  - `_score`'s `sample_size` derivation (~lines 1199-1209) — flows into
    `sample_factor` blend.
- `tests/test_strategy_performance.py` — +3 tests pinning
  `real_trade_count` property arithmetic.
- `tests/test_proposal_engine.py` — +4 tests: canonical DEBT-065 defect
  scenario (9 real + 2 synthetic at threshold 10 now correctly blocks at
  `_cold_start_blocks_live`); boundary at 10 real + 5 synthetic admits;
  `_score` 8 real + 3 synthetic `sample_size` reflects real-only; all-
  synthetic record set collapses to cold-start.
- `docs/TECH-DEBT.md` — moved DEBT-065 from Active to Resolved; filed
  DEBT-070 in Active; Statistics Medium 5→4, Low 3→4, Resolved 57→58
  (Total Active unchanged at 8); two Change History rows.
- `aidlc-docs/aidlc-state.md` — appended DEBT-065 closeout note to the
  `runtime-reconciliation` row.

## QA Verdict

🟢 — clean fix, scoped exactly to the 2 gating sites named in DEBT-065's
suggested resolution. QA confirmed dev's flag of 4 additional ranking-
side `total_trades` reads at `src/proposal/engine.py:996, 1010, 1014,
1132` (QA corrected dev's :1128 mis-cite to :1132); these affect
strategy-selection ranking — not promotion gating — and DEBT-065 scope
was explicitly the 2 gating sites, so dev correctly stayed in scope.
Filed as DEBT-070 (Low) for a separate ranking-side sweep.

## Verification

- `pytest -q`
  - Result: 2054 passed (was 2047; net +7, zero regressions).
- `ruff check src tests`
  - Result: fully clean.
- `mypy src/strategy/performance.py src/proposal/engine.py`
  - Result: clean.

## Risks

- **Ranking-side `total_trades` reads (DEBT-070) remain unfixed** — the
  4 reads at `src/proposal/engine.py:996, 1010, 1014, 1132` in
  `_select_best_technique` / `_select_all_techniques` still treat
  synthetic rows as history. Mild operator-experience distortion: a
  synthetic-heavy strategy can win the "best technique" ranking on a
  per-(symbol, sub-account) cycle over a genuine cold-start strategy,
  though composite/edge dominates the actual scoring formula so the
  blast radius is bounded. **No money-safety impact** — promotion gating
  is correctly fenced by DEBT-065's fix; only the ranking-order surface
  is affected. Tracked in DEBT-070.
- **Display sites intentionally untouched** — `src/dashboard/pages/strategies.py:118`
  "Total Trades" column and `src/ai/improver.py:667` improver prompt
  continue to render synthetic-inclusive counts. This is by design:
  operator-facing counts should match what the underlying ledger holds,
  and the improver prompt's interpretation of sample size is decoupled
  from the gating contract. If a future cycle ever migrates these, it
  should be a deliberate operator-UX decision (not recommended).

## Future Work (not filed as new DEBT beyond DEBT-070)

- **DEBT-070 ranking sweep** — same pattern as this fix, applied to the
  4 reads in `_select_best_technique` / `_select_all_techniques`, plus
  regression tests pinning that a synthetic-heavy strategy does NOT win
  ranking over a real-history strategy at equal composite.
- **Display-site migration** — whether `src/dashboard/pages/strategies.py:118`
  and `src/ai/improver.py:667` should ever migrate to `real_trade_count`.
  Not recommended — operator counts should match the ledger — but worth
  reconsidering if operator feedback ever surfaces confusion about why
  a strategy "has 11 trades" but is still gated as cold-start.
