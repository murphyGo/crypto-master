# Session: strategy-tuning Slice 2 — INITIAL-ACTION SEEDING FOR NAMED STRATEGY FAMILIES (DEBT-069(b))

Date: 2026-05-28
Units: `strategy-tuning` / `dashboard-operator-ui`
Stage: Code Generation
Related debt: DEBT-069(b) — initial-action seeding for named strategy families (spec §"Initial Actions").
Related requirements: FR-036, FR-037, FR-038, NFR-007, NFR-008

> SECOND cycle on DEBT-069 today. The earlier (a)+(d) cycle (dashboard Applied/Recommended view +
> `STRATEGY_ACTION_APPLIED` emitter) already shipped and committed as `45d9b1f` — its log is
> `docs/sessions/2026-05-28-strategy-tuning-slice-2-dashboard-a-d.md`. This log covers the distinct (b)
> initial-action seeding cycle that builds directly on the now-shipped (a) dashboard view: (a) made the
> Recommended column live but unseeded on day one; (b) populates that column with a static per-strategy
> seed map used as a FALLBACK ONLY. Sibling to the Slice 1 (2026-05-13) state-machine log and the
> Slice 2(e) true-profit-factor log (2026-05-24).

## Scope

DEBT-069(b) adds a static per-strategy seed map (spec §"Initial Actions") that populates the dashboard
Recommended column on day one, before live evidence is sufficient for the real `recommend_action`
recommender to fire. The seed is a **Recommended-column FALLBACK ONLY**: it never changes Applied
state, never gates trades, and once live evidence is sufficient the real `recommend_action` output
supersedes the seed. This is the natural bundle with the (a) dashboard view shipped earlier today.

This was a full team cycle: quant-trader-expert validated the seed mapping against the 2026-05-13 Fly
evidence snapshot; senior-developer implemented; qa-reviewer returned 🟢 Ship.

## Changes — DEBT-069(b) initial-action seeding (Recommended-column FALLBACK ONLY)

In `src/strategy/tuning_recommender.py`:

- New `STRATEGY_SEED_ACTIONS` dict + `SEED_DEFAULT_ACTION = RETUNE` catch-all + `seed_action_for(name)`
  helper.
- Keys are registered technique NAMES (not filenames). Two name-traps to record: `rsi.py` →
  `rsi_universal`; `bollinger_bands.py` → `bollinger_band_reversion`.
- The seed map (quant-validated against the 2026-05-13 Fly snapshot per
  `aidlc-docs/construction/strategy-tuning/functional-design/spec.md` §"Initial Actions"):
  - **SCOUT** = `rsi_universal` / `rsi_4h` / `rsi_15m` / `raschke_holy_grail` / `ma_crossover`
  - **PAUSE** = `momentum_pinball_orb` / `vwap_mean_reversion` / `bollinger_band_reversion` /
    `turtle_soup_reclaim`
  - **RETUNE** = `vcp_breakout` / `session_vwap_pullback` / `tsmom_vol_breakout` /
    `weinstein_stage2_filter`
  - **catch-all** (incl. deprecated/unnamed e.g. `chasulang_ict_smc`) = RETUNE via `SEED_DEFAULT_ACTION`.

In `src/dashboard/pages/strategies.py`:

- `build_strategy_tuning_rows` now computes `recommended = recommend_action(...) or
  seed_action_for(strategy.name)` — the live recommendation always supersedes the seed; the seed only
  fills in when `recommend_action` returns `None`.
- The now-dead `INSUFFICIENT_EVIDENCE` sentinel was removed cleanly: every row now gets a non-None
  recommendation via the catch-all, so the "—" / thin-evidence path no longer exists.

## Quant classification notes (worth recording for audit)

- `counter_trend: True` → mean-reversion family → PAUSE: `bollinger_band_reversion`,
  `turtle_soup_reclaim`, `vwap_mean_reversion`.
- trend/breakout non-counter-trend & unnamed → RETUNE: `tsmom_vol_breakout`, `weinstein_stage2_filter`.
- `vcp_breakout` / `session_vwap_pullback` carry a conditional in the spec ("keep if PF≥1.3 else
  retune"); under thin / undefined-PF day-one evidence this resolves to RETUNE.

## Review

### QA 🟢 Ship

qa-reviewer returned 🟢 Ship and independently confirmed the test deltas (see Verification), the
seed-as-fallback semantics (live recommendation supersedes seed), and the clean removal of the
`INSUFFICIENT_EVIDENCE` sentinel.

### Quant validation (upfront, not escalation)

quant-trader-expert validated the seed mapping against the 2026-05-13 Fly evidence snapshot before
implementation. No quant escalation DURING the cycle was required — no trade-gating / backtest /
strategy-math was touched; the seed map is a static Recommended-column fallback only.

## Files Changed

- **Created**:
  - `tests/test_strategy_tuning_recommender.py` — 4 new recommender tests (13-family parametrize,
    name-traps, catch-all, case-sensitivity). (File extended if it pre-existed; the (b) tests are new.)
- **Modified**:
  - `src/strategy/tuning_recommender.py` — `STRATEGY_SEED_ACTIONS` dict + `SEED_DEFAULT_ACTION = RETUNE`
    catch-all + `seed_action_for(name)` helper.
  - `src/dashboard/pages/strategies.py` — `build_strategy_tuning_rows` now `recommended =
    recommend_action(...) or seed_action_for(strategy.name)`; dead `INSUFFICIENT_EVIDENCE` sentinel
    removed.
  - `tests/test_dashboard_strategies.py` — seed-fallback test replaces the old thin-evidence-dash test;
    added seeded-PAUSE-yaml + live-recommendation-supersedes-seed tests.

## Key Decisions

| Decision | Rationale |
|---|---|
| Seed map is a Recommended-column FALLBACK ONLY | Never changes Applied state, never gates trades; once live evidence is sufficient the real `recommend_action` output supersedes it. Keeps the seed an observability convenience, not a control path. |
| Keys are registered technique NAMES, not filenames | Two name-traps: `rsi.py` → `rsi_universal`, `bollinger_bands.py` → `bollinger_band_reversion`. Matching on `strategy.name` is the stable contract; filenames are not. |
| `SEED_DEFAULT_ACTION = RETUNE` catch-all | Deprecated / unnamed strategies (e.g. `chasulang_ict_smc`) get a safe non-None recommendation; nothing falls through to `None` anymore. |
| `vcp_breakout` / `session_vwap_pullback` resolve to RETUNE | Spec conditional is "keep if PF≥1.3 else retune"; under thin / undefined-PF day-one evidence the else-branch (RETUNE) is the honest seed. |
| Remove the `INSUFFICIENT_EVIDENCE` sentinel | With the catch-all every row now gets a non-None recommendation, so the sentinel and its "—" render path are dead code; removed cleanly rather than left dangling. |
| `recommend_action(...) or seed_action_for(...)` ordering | Live evidence always wins; the seed only fills the day-one gap. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Verification

- Full suite: **2235 passed**, 0 failed (was 2217 from the (a)/(d) baseline; net **+18** = 4 new
  recommender tests in `tests/test_strategy_tuning_recommender.py` — 13-family parametrize, name-traps,
  catch-all, case-sensitivity — plus updated dashboard tests in `tests/test_dashboard_strategies.py`:
  seed-fallback replaces the old thin-evidence-dash test, seeded-PAUSE-yaml, and
  live-recommendation-supersedes-seed).
- `ruff check src tests`: clean.
- `mypy src`: clean (90 source files).
- No quant escalation beyond the upfront mapping validation (no trade-gating / backtest / strategy-math
  touched).

## Potential Risks

- **The seed map is a static snapshot of 2026-05-13 Fly evidence; it can drift from reality.** Because
  the seed is hand-validated against a point-in-time snapshot, a strategy whose live behaviour has
  shifted since 2026-05-13 will show a stale seed until enough live evidence accumulates for
  `recommend_action` to supersede it. This is bounded — the seed is fallback-only and never gates
  trades — but an operator reading the Recommended column on day one is reading a 2026-05-13 opinion,
  not live truth. The seed should be revisited when (g) threshold calibration lands.

- **Name-trap regressions are silent.** The keys are registered technique names, and two of them
  diverge from their filenames (`rsi.py` → `rsi_universal`, `bollinger_bands.py` →
  `bollinger_band_reversion`). A future rename of a technique's `name` that isn't mirrored in
  `STRATEGY_SEED_ACTIONS` would silently fall through to the RETUNE catch-all rather than erroring —
  the strategy would still get a recommendation, just the wrong (default) one. The name-trap tests
  guard the current mapping; future renames must update both.

## TECH-DEBT Items

DEBT-069(b) marked **SHIPPED 2026-05-28**. No NEW debt filed. After this cycle the DEBT-069 umbrella
has **(c), (f), (g), (i)** remaining open; (a), (b), (d), (e), and the (h)-comment are shipped.

## Remaining Work

DEBT-069 umbrella remains Active for (c) observation store, (f) pause-reason split, (g) threshold
calibration, and (i) funnel unit-test coverage gaps. Suggested next cycle: (c) observation store would
let the dashboard render recommendation trends without re-running the recommender at every page load;
(g) threshold calibration after the first 2 weeks of paper evidence is the natural moment to also
re-validate the (b) seed map against fresh evidence.

No ADR needed — (b) is a static seed map used as a Recommended-column fallback only. It introduces no
new component boundary, gates no trades, and the live recommender already supersedes it; it does not
lock in a constraint future work must respect (the seed is explicitly revisable at calibration time).
The one classification rationale (counter-trend → PAUSE, conditional-PF → RETUNE under thin evidence)
is recorded above in the quant classification notes — the session log is its right home.
