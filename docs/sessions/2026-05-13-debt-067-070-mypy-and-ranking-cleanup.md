# Session: DEBT-067 + DEBT-070 close-out — `mypy src` repo-wide clean + ranking-side `real_trade_count` sweep

## Unit

- `proposal-runtime` (primary — ranking-side `total_trades` →
  `real_trade_count` sweep in `_select_best_technique` /
  `_select_all_techniques`)
- Secondary unit: `dashboard-operator-ui` (mypy cleanup on
  `src/dashboard/app.py` — `DashboardMode` literal-default reorder +
  `Sequence` covariant widening on `render_command_center_links`)
- Secondary unit: `quality-governance` (`mypy src` repo-wide-clean
  milestone — first time this session, 88 source files zero issues)

## Related Requirements

- NFR-003: Type integrity — closest match for the `mypy src` repo-wide
  clean milestone delivered by DEBT-067; the 3 pre-existing
  `src/dashboard/app.py` errors had been a QA-noise filter across the
  past 4 unit cycles (DEBT-061, market-regime, runtime-reconciliation,
  proposal-funnel-audit) and now no longer mask future regressions.
- FR-013: Generate trading proposals — closest match for the
  `_select_best_technique` / `_select_all_techniques` ranking selection
  paths that DEBT-070 corrects so synthetic-only history no longer wins
  selection over genuine cold-start strategies.
- FR-014: Store proposal history and outcomes — same `TechniquePerformance`
  aggregate over `PerformanceRecord` that the DEBT-065 close-out
  re-based on real-only counts; DEBT-070 extends that contract to the
  ranking-side reads.
- FR-029: Live-promotion safety gating — adjacent to the DEBT-065
  gating-side fix; DEBT-070 closes the ranking-side residue so the
  `real_trade_count` contract holds end-to-end across both gating and
  selection surfaces (display sites intentionally remain on
  `total_trades`).

## Scope

Bundled DEBT-067 + DEBT-070 — both filed 2026-05-13 as Low-priority
mechanical close-outs (DEBT-067 surfaced as a QA observation across the
past 4 unit cycles; DEBT-070 surfaced from QA during DEBT-065 close-out
as a scope-split ranking-side residue). Both items independently
shipped the suggested-resolution verbatim:

- **DEBT-070 (ranking-side sweep)** — the same pattern as the DEBT-065
  gating-side fix, applied to the 4 ranking-side reads in
  `ProposalEngine`. `_select_best_technique` (`src/proposal/engine.py`)
  switched 3 `perf.total_trades` reads — `any_history` detection
  (`L996`), tie-breaker sort key (`L1010`), return-perf gate (`L1014`) —
  to `perf.real_trade_count`. `_select_all_techniques`
  (`src/proposal/engine.py:1132`) switched its return-perf gate the
  same way. Inline `# DEBT-070:` comments at each site. Display sites
  at `src/dashboard/pages/strategies.py:118` ("Total Trades" column)
  and `src/ai/improver.py:667` (improver prompt rendering)
  intentionally remain on `total_trades` per the DEBT-065 design
  intent — operator-facing record counts should match what the
  underlying ledger holds, and improver prompts should see the same
  shape the operator sees.
- **DEBT-067 (mypy repo-wide cleanup)** — `DashboardMode` type alias
  reordered before `COMMAND_CENTER_DEFAULT_MODE` at
  `src/dashboard/app.py:285`; the constant is now annotated
  `: DashboardMode = "paper"` to carry the literal type (clears the
  Literal-default error). `render_command_center_links` parameter
  (`src/dashboard/app.py:869, 882`) widened from `list[...]` to
  `Sequence[...]` (covariant read-only over the parameter — function
  body never mutates it), and `Sequence` added to the existing
  `collections.abc` import. The result: `mypy src` now reports
  `Success: no issues found in 88 source files` repo-wide — the first
  time during this session this has been true.

## Changes

- `src/proposal/engine.py` — 4 ranking-side `perf.total_trades` reads
  switched to `perf.real_trade_count` with inline `# DEBT-070:`
  comments at each site: `any_history` detection (`L996`), tie-breaker
  sort key (`L1010`), `_select_best_technique` return-perf gate
  (`L1014`), `_select_all_techniques` return-perf gate (`L1132`).
- `src/dashboard/app.py` — `DashboardMode` type alias reordered before
  `COMMAND_CENTER_DEFAULT_MODE` at line 285 (constant now annotated
  `: DashboardMode = "paper"`); `render_command_center_links`
  parameter (lines 869, 882) widened from `list[...]` to
  `Sequence[...]`; `Sequence` added to the existing `collections.abc`
  import.
- `tests/test_proposal_engine.py` — +2 tests pinning DEBT-070:
  `test_select_best_technique_tiebreaks_on_real_trade_count`
  (canonical defect scenario: equal `avg_pnl`, A=10 synthetic/0 real,
  B=0 synthetic/5 real → B wins; pre-fix A would have won via the
  `-perf.total_trades` tie-breaker), and
  `test_select_best_technique_any_history_ignores_synthetic_only`
  (synthetic-only beta does NOT register as "has history" → falls
  back to lex-first cold-start, alpha wins).
- `docs/TECH-DEBT.md` — moved DEBT-067 and DEBT-070 from Active to
  Resolved; Statistics Active 6 → 4, Low 4 → 2, Resolved 60 → 62;
  two Change History rows.
- `aidlc-docs/aidlc-state.md` — appended DEBT-070 closeout note to the
  `proposal-runtime` row and the `mypy src` repo-wide-clean milestone
  note to the `quality-governance` row.

## QA Verdict

🟢 + repo-wide mypy-clean milestone confirmed. Both items shipped the
suggested-resolution verbatim — no scope creep, no unrelated edits.
DEBT-070 is a 4-site mechanical sweep following the DEBT-065 pattern
with regression tests pinning the canonical defect and the
`any_history` short-circuit. DEBT-067 is the 2-line + 2-line
mechanical fix originally specified in its suggested-resolution
(literal-default + covariant Sequence). The bundled `mypy src` result
of `Success: no issues found in 88 source files` is the explicit
milestone — the 3 errors had been a recurring QA-noise filter across
the past 4 unit cycles.

## Verification

- `pytest -q`
  - Result: 2061 passed (was 2059; net +2, zero regressions).
- `ruff check src tests`
  - Result: fully clean.
- `mypy src`
  - Result: `Success: no issues found in 88 source files` — **first
    time during this session that `mypy src` is fully clean
    repo-wide.**

## Risks

- **None — both fixes are minimal and well-tested.** DEBT-070 is a
  4-site mechanical pattern-match on the DEBT-065 fix (whose contract
  has been in production since same-day close-out) with 2 dedicated
  regression tests pinning the canonical defect (synthetic-heavy
  tie-breaker) and the `any_history` short-circuit. DEBT-067 is a pure
  type-system fix — no runtime behaviour change (`DashboardMode` is a
  type alias only; `Sequence` is structurally covariant over the
  parameter without changing call-site argument shapes).

## Milestone Note

`mypy src` is now fully clean repo-wide for the first time during
this session: `Success: no issues found in 88 source files`. The 3
pre-existing `src/dashboard/app.py` errors closed by DEBT-067 had been
a recurring QA-noise filter across the past 4 unit cycles (DEBT-061,
market-regime, runtime-reconciliation, proposal-funnel-audit) and now
no longer mask future regressions on the next diff.

## Future Work (not filed as new DEBT)

- **Optional CI gate to lock the repo-wide-clean mypy baseline.** With
  `mypy src` now clean at 88 source files, a CI gate (or
  pre-commit hook) would prevent regressions from creeping back in.
  **Explicitly NOT filed as DEBT in this cycle** — introducing a new
  mypy-regression-blocking CI gate is a project-policy decision that
  requires explicit user approval; flagged here only as a candidate
  follow-up so a future cycle's planner has the signal. Project has no
  `.github/workflows/` or `.pre-commit-config.yaml` yet (per the
  DEBT-042 close-out note from Phase 26.5 — black gate is enforceable
  but still manual), so this would also be the first CI infrastructure
  in the repo.
- **Active TECH-DEBT queue now down to 4 items** — 2 Low informational
  (DEBT-064 runtime-reconciliation taxonomy gaps; DEBT-066 in-memory
  mark-price cache for cap-blocker `unrealized_pnl_percent`) + 2
  Medium Slice 2 umbrellas (DEBT-068 `cross-account-risk-policy`
  Slice 2; DEBT-069 `strategy-tuning` Slice 2). No High / Critical
  open items.
