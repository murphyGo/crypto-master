# Session: cross-account-risk-policy KILL-SWITCH → RUNTIME-SAFETY-SCORE INTEGRATION (DEBT-068(h))

Date: 2026-05-25
Units: `cross-account-risk-policy` / `runtime-safety-score`
Stage: Code Generation
Related debt: DEBT-068(h) — `runtime-safety-score` kill-switch integration.
**This log COMPLETES the DEBT-068 umbrella SUBSTANCE** — with (h) shipped, every
substantive sub-task (a, b, c, c-arb, d, e, f, g, h) is now done; only minor
ride-along follow-up NOTES remain (see TECH-DEBT Items / Remaining Work below).
Related requirements: FR-036, FR-037, FR-038, FR-044, NFR-007, NFR-008, NFR-012

> Same-unit sibling to the ten preceding runtime/policy/dashboard
> `cross-account-risk-policy` logs (DEBT-068(b) opt-in caps, (c-1)/(c-2) kill
> switches, (c-arb) cap arbitration, (d) operator-freeze runtime read side, (e)
> stale actions, (g) risk event types, (f-1) read-only panel, (f-2) operator-freeze
> toggle write side). The (g) slice gave kill-switch trips their own dedicated
> `RISK_KILL_SWITCH_TRIPPED` event type; this log consumes that event type — it
> feeds LIVE kill-switch trips into the operator-facing runtime-safety-score so a
> portfolio kill-switch trip visibly degrades the score band. Uncommitted on `main`
> at the time of writing; committed immediately after.

## Scope

DEBT-068(h) wires LIVE kill-switch trips into the runtime-safety-score signal so
the operator-facing score reflects when a money-safety gate has actually fired.
Concretely: a new `RuntimeSafetyInputs.kill_switch_conditions` field, a
`_count_kill_switch_conditions` extractor that counts the DISTINCT kill-switch
CONDITIONS in the cycle's activity events, and a new per-condition penalty in
`compute_runtime_safety_score`. The penalty is calibrated so that ONE live
kill-switch condition lands the score at 75 = DEGRADED — satisfying the spec
line-367 mandate that a portfolio kill-switch trip bumps the band to at least
degraded — two conditions → 50 = RISKY, with the penalty capped at 60.

Scope is kill switches ONLY. The two other candidate stale/safety signals were
deliberately EXCLUDED: stale-position `auto_close` (the (e) `STALE_POSITION_AUTO_CLOSED`
event) is correct-behaviour housekeeping, not a money-safety failure, so it must
not depress the score; operator-freeze (`OPERATOR_FREEZE_ENGAGED`) is the manual
analogue of the existing `pause_recommended` signal and is already represented in
the operator surface, so folding it into the score would double-count. The (e)/(g)
follow-up notes that named "feed runtime-safety-score inputs" are satisfied for the
kill-switch half only; the stale-event surfacing remains a dashboard concern, not a
score input, by design.

## Changes — DEBT-068(h) kill-switch → runtime-safety-score integration

All in `src/runtime/safety_score.py`:

- **`RuntimeSafetyInputs.kill_switch_conditions: int`** (`Field(default=0, ge=0)`)
  — the new input field carrying the distinct live-condition count.
- **`_count_kill_switch_conditions(events)`** — the extractor. Counts DISTINCT
  `(cycle_id, gate_reason, sub_account_id)` tuples among `RISK_KILL_SWITCH_TRIPPED`
  events. NON-advisory only: events with truthy `details.advisory` (paper-mode
  kill-switch advisories) are EXCLUDED, because the score measures live
  money-safety health and paper kill switches do not halt the lab. `cycle_id` is
  read from the event's top-level field with a `details` fallback for robustness;
  a missing/None `sub_account_id` normalizes to `"__global__"`, so a portfolio-level
  gate counts ONCE per cycle rather than once per proposal. The dedup is what makes
  the band math meaningful — one tripped condition can fire on every proposal in a
  cycle, and raw event counts would massively overstate severity.
- **Penalty in `compute_runtime_safety_score`** — `min(kill_switch_conditions * 25,
  60)`, applied via the existing `_apply_penalty` factor mechanism (factor string
  `f"kill-switch conditions={inputs.kill_switch_conditions}"`). Per-condition 25,
  cap 60. Band math from the 100 baseline: 1 condition → 75 = DEGRADED (≥70
  threshold), 2 → 50 = RISKY, ≥3 capped at 60 penalty (40 floor) so the kill-switch
  signal alone never collapses the whole score to 0.
- **Wiring** — `kill_switch_conditions=_count_kill_switch_conditions(events)` added
  to the `RuntimeSafetyInputs` assembly in the activity-aggregation path.

## Review

### The over-count bug — quant gate working (🔴 → 🟢)

quant-trader-expert's FIRST pass returned 🔴. The two GLOBAL/portfolio kill-switch
gates (`_global_kill_switch_gate` and `_portfolio_daily_loss_check`, gate_reasons
`portfolio_kill_switch` / `portfolio_daily_loss_kill_switch`) emit their event with
the PROPOSING account's `sub_account_id` spread in via `_proposal_summary`. Because
`_count_kill_switch_conditions` keys distinctness on `sub_account_id`, ONE portfolio
condition was counted ONCE PER DISTINCT PROPOSER per cycle — so a portfolio trip seen
across 3 proposing accounts in one cycle produced 3 conditions → 75 became 0/RISKY-or-worse
instead of the intended single condition → 25 penalty → 75/DEGRADED. As a second-order
consequence the `"__global__"` normalization branch was effectively DEAD: a portfolio
event always carried a real proposer `sub_account_id`, so the `or "__global__"`
fallback never fired.

**Fix (Option A, engine-side).** In `src/runtime/engine.py`, the two portfolio gate
emit sites now `details.pop("sub_account_id", None)` AFTER the `_proposal_summary`
spread, for the two portfolio gate_reasons only. With the proposer account id removed,
the extractor's `or "__global__"` branch fires and a single portfolio trip across N
proposers collapses to ONE condition (75/DEGRADED), as intended; the previously-dead
normalization branch is now live. Account-level gates were left untouched — they carry
a stable literal account id and their distinct conditions still (correctly) count
separately.

This ALSO fixed an unrelated f-1 dashboard mis-attribution: a portfolio trip no longer
lights up the *proposer's* per-account kill-switch state in the (f-1) panel, which now
renders `"—"` for that account. **Subtlety worth recording**: the pop must REMOVE the
key, not null it — the f-1 dataframe relies on `.get(..., "—")` defaulting to render the
empty cell, so a present-but-`None` value would not produce the `"—"` placeholder.

**Re-review after fix: 🟢.** quant confirmed both portfolio emit sites drop the key,
there is no third global emission path, account-level gates are unaffected, there is no
f-1 regression, and the band math is correct (1 → 75 DEGRADED, 2 → 50 RISKY, cap 60).

### QA

qa-reviewer 🟢 on the ORIGINAL (pre-fix) submission, full suite 2191. NOTE FOR THE
RECORD: qa's fixtures did not exercise the multi-proposer global-trip path, so QA did
NOT catch the over-count — the quant gate did. This is a clean example of why the quant
pass is not redundant with QA: QA verified the per-event behaviour and the band
thresholds in isolation, but the cross-cycle, multi-proposer aggregation semantics are a
trading-math concern that the quant owns.

## Verification

- Full suite: **2195 passed**, 0 failed (was 2181; net **+14** = 10 original tests + 4
  regression tests added for the over-count fix).
- `ruff check src tests`: clean.
- `mypy src`: clean.

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | ✅ |
| Resource Management | ✅ |
| Security | ✅ |
| Type Hints | ✅ |
| Tests | ✅ |

## Potential Risks

- **The multi-proposer global-trip over-count (CAUGHT AND FIXED pre-ship).** As
  detailed above, the first pass counted one portfolio condition once per distinct
  proposer per cycle. Fixed engine-side by dropping `sub_account_id` at the two
  portfolio emit sites; +4 regression tests pin the collapse-to-one behaviour. The
  residual risk is that a FUTURE third portfolio-kill-switch emission path could
  reintroduce the over-count if it forgets the `details.pop`; the regression tests and
  the in-code DEBT-068(h) comments at both emit sites are the guard. No third path
  exists today.

- **`details.pop` interaction with the f-1 panel is load-bearing.** The pop must REMOVE
  the `sub_account_id` key rather than set it to `None`, because the f-1 dataframe relies
  on `dict.get(..., "—")` defaulting. A future refactor that "tidies" the pop into an
  explicit `details["sub_account_id"] = None` would silently break the f-1 `"—"`
  placeholder for portfolio trips. Documented in-code; noted here for the audit trail.

- **Penalty cap interaction.** The kill-switch penalty caps at 60, so even ≥3 distinct
  live conditions in one cycle leave a 40 floor from this signal alone; the score can
  still fall lower once the other penalties compose. This is intended (the kill-switch
  signal should dominate toward DEGRADED/RISKY without single-handedly zeroing the
  score), but threshold/cap calibration is a candidate for the runtime-safety-score
  unit's future threshold-calibration work if live evidence suggests the bands are mis-set.

## TECH-DEBT Items

DEBT-068(h) is marked **SHIPPED**. **This COMPLETES the DEBT-068 umbrella SUBSTANCE** —
(a), (b), (c) [(c-1)+(c-2)], (c-arb), (d), (e), (f) [(f-1)+(f-2)], (g), and (h) are all
shipped. No NEW debt items were filed by this cycle. The umbrella's residue is now ONLY
the six minor ride-along follow-up NOTES carried from earlier slices:
(c-2-note-fee-timing), (e-note-close-stale-quote), (f-1-note-snapshot-event),
(c-arb-note-overshoot-units), (f-2-note-test-gap), (f-2-note-broad-except). None are
blocking and none are money-safety defects.

**Recommendation surfaced to the lead** (status only — not actioned here): with the
core scope done and only minor notes remaining, the lead should decide whether the
DEBT-068 umbrella's top-level Statistics status flips from Active to Resolved. Either
(a) flip to Resolved and re-file the six residual notes as their own small DEBT items,
or (b) keep the umbrella Active but SLIMMED to just the notes. The substance is
unambiguously complete; the choice is a bookkeeping preference for the lead/user.

## Remaining Work

No remaining DEBT-068 SUBSTANCE. The six minor follow-up notes above ride along to be
addressed opportunistically. No new follow-ups from this cycle.

No ADR needed — this slice consumes the already-decided `RISK_KILL_SWITCH_TRIPPED` event
type ((g)) and feeds it into the established runtime-safety-score `RuntimeSafetyInputs` /
`_apply_penalty` pattern. It introduces no new component boundary; the only design choice
(distinct-condition counting via `(cycle_id, gate_reason, sub_account_id)` dedup with
portfolio gates collapsing to `"__global__"`) is an implementation detail of an existing
signal rather than a long-term constraint future work must respect. The kill-switch-only
scope decision (excluding stale-close housekeeping and operator-freeze) is recorded here
in the session log, which is the right home for it.
