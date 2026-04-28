# Session Log: 2026-04-28 - Priorities Investigation - Fly Zero-Trades Diagnosis

## Overview

- **Date**: 2026-04-28
- **Phase**: n/a — investigation triggered from `docs/team-priorities.md`
- **Sub-task**: "Fly 배포에 트레이딩이 0건. 원인 검증" (read-only diagnostic; user asked for a 1-page conclusion picking one of (a) normal no-trade, (b) bug, (c) configuration)

## Work Summary

Investigated why the Fly.io deployment of Crypto Master has executed zero trades since deploy. The user's brief required choosing among three explanations and producing a one-page diagnostic plus a follow-up sub-task suggestion if (b) or (c) was selected.

The conclusion is **(c) configuration with a structural twist**: at the engine's default settings, the cold-start composite score is mathematically capped at `0.5` while the auto-approve threshold is `1.0`. No proposal can clear the gate until the system has accumulated trade history — but the only way to accumulate history is to clear the gate. This is a chicken-and-egg lockout, and it is reproducible from the source defaults alone (no live runtime data was needed to identify it).

The fix path is the already-planned but unchecked **Phase 10.2 EngineConfig Env Override**. With env override in place an operator can drop `ENGINE_AUTO_APPROVE_THRESHOLD` to e.g. `0.3` to seed performance data, then ratchet it back up once warm-state proposals start producing `composite ≥ 1.0`. The investigation also surfaced a concrete recommendation to **change the threshold default from `1.0` → `0.3`** as part of 10.2, since the current default is unreachable from the cold-start branch of the same engine.

A secondary, separate finding: most runtime artifacts (`activity.jsonl`, `audit/feedback.jsonl`, `proposals/`, `notifications/`, `portfolio/`) are written through hardcoded *relative* paths that ignore `Settings.data_dir`. On Fly the volume is mounted at `/data` but the runtime writes to `/app/data/...` on the ephemeral container filesystem, so each machine recycle wipes the activity log. This is unrelated to the zero-trades issue (the activity log records the rejections; we just can't read them on the volume) but it is the reason the user, when looking at the volume, sees no `data/runtime/activity.jsonl` content.

This was a read-only investigation — no source files were edited and no tests were run. The artifact set is this session log plus the priorities-queue Done-section update.

## Files Changed

- **Created**:
  - `docs/sessions/2026-04-28-priorities-fly-zero-trades-diagnosis.md` — this file.

- **Modified**:
  - `docs/team-priorities.md` — flipped the Fly zero-trades item from Open to Done with the (c) outcome line and the recommended follow-up sub-task pointer.

- **Inspected (no edits)**:
  - `src/proposal/engine.py` — score formula (`_score`), selection (`_select_best_technique`).
  - `src/runtime/engine.py` — auto-decide gate (`_auto_decide`), `EngineConfig` defaults (`auto_approve_threshold=1.0`).
  - `src/main.py` — `build_engine` wires `EngineConfig()` with no env-driven overrides today.
  - `src/runtime/activity_log.py` — hardcoded `Path("data/runtime/activity.jsonl")`.
  - `src/strategy/loader.py` — `load_all_strategies` does not filter by `status`.
  - `src/strategy/performance.py` — `PerformanceTracker` correctly threads `Settings.data_dir`.
  - `src/config.py` — `Settings.data_dir` reads `DATA_DIR` env (set to `/data` in `Dockerfile`).
  - `strategies/{rsi,rsi_4h,rsi_15m,bollinger_bands,ma_crossover}.py`, `strategies/{sample_prompt,chasulang_ict_smc}.md` — every strategy has `status: experimental`.
  - `Dockerfile`, `start.sh`, `fly.toml`, `.env.example` — no `ENGINE_AUTO_APPROVE_THRESHOLD` Fly secret exists today.
  - Hardcoded relative paths also in `src/feedback/audit.py`, `src/feedback/loop.py`, `src/proposal/interaction.py`, `src/proposal/notification.py`, `src/trading/portfolio.py`.

## Diagnosis (verbatim from the developer report)

### Three constants that together produce the lockout

1. `EngineConfig.auto_approve_threshold` default = `1.0` — `src/runtime/engine.py:80`.
2. `ProposalEngineConfig.no_history_score_factor` default = `0.5` — `src/proposal/engine.py:166`.
3. Every shipped strategy has `status: experimental` and zero accumulated `PerformanceRecord` rows on a fresh deploy.

### Cold-start formula (`src/proposal/engine.py:444-487`)

```
if perf is None or perf.total_trades == 0:
    composite = confidence * no_history_score_factor   # = confidence * 0.5
else:
    composite = confidence * edge_factor * sample_factor
```

With `confidence=1.0` (max) and no history: `composite = 1.0 × 0.5 = 0.5`. Threshold = `1.0`. **`0.5 ≥ 1.0` is false** → every proposal is rejected with `"composite 0.5000 below threshold 1.0000"`. The activity log fills with `cycle_started → proposal_generated → proposal_rejected → cycle_completed`. `position_opened` / `position_closed` events never appear. Zero trades.

There is no escape path: the only way to populate `PerformanceTracker` with non-zero `total_trades` is to actually open trades, and the engine refuses to open any trade until the history exists.

### Why hypothesis (a) "normal no-trade" is ruled out

If markets simply hadn't crossed the threshold, we'd see proposal scores spread around the cutoff. Here every cold-start composite is bounded above by `0.5` and the cutoff is `1.0` — there is no market state that can clear the gate. The system is structurally locked, not market-dependent.

### Why hypothesis (b) "score / filter / order bug" is partially yes

The formula and the threshold are each individually defensible; they're incompatible together at the configured defaults. Categorising this as a bug vs a configuration issue is partly semantic. The investigation lands on (c) because the fix is "change the threshold value (and make it env-overridable)", not "rewrite the score logic".

## Key Decisions

| Decision | Rationale |
|---|---|
| Conclude (c) configuration rather than (b) bug | The score formula is correct trading-domain reasoning (cold-start should be more conservative). The threshold value is just too high relative to the cold-start ceiling. Both are configuration, not implementation defects. |
| Recommend Phase 10.2 (already planned) as the fix vehicle, with an additional default change | Phase 10.2 already exists in the dev plan as the env-override sub-task. The lockout is unblocked by env override. To prevent future fresh deploys from hitting the same lockout, the default should also drop from `1.0` to `0.3`. The quant review confirmed `0.3` is safe (`edge_factor` still gates negative-EV strategies to `composite=0`). |
| Surface the volume-path finding as a separate sub-task suggestion, not roll it in | The user's priorities item was scoped to the zero-trades question. The volume-paths finding is a different defect (data loss on machine recycle, not gate behaviour). Bundling would violate the "one sub-task per cycle" rule. |
| Read-only — no code edits, no test runs | The priorities item explicitly framed the work as "결론은 셋 중 하나여야 함" — investigation, not fix. The cycle's job was to produce the conclusion + a follow-up suggestion, not to ship the fix. |

## Code Review Results

| Category | Status |
|---|---|
| Error Handling | n/a — no code changed |
| Resource Management | n/a — no code changed |
| Security | n/a — no code changed |
| Type Hints | n/a — no code changed |
| Tests | n/a — no code changed |

## Verification

No test runs (read-only investigation). The diagnosis is reproducible by anyone reading the cited file:line locations:

- `src/proposal/engine.py:166` (`no_history_score_factor: float = Field(default=0.5, ...)`)
- `src/proposal/engine.py:471` (`composite=confidence * self.config.no_history_score_factor`)
- `src/runtime/engine.py:80` (`auto_approve_threshold: float = Field(default=1.0, ge=0.0)`)
- `src/runtime/engine.py:543-549` (`if composite >= threshold: ... else: rejected`)

## Potential Risks

- **Live runtime confirmation requires `fly logs` / `fly ssh` access**, which the team cannot run locally. The diagnosis is derived from source defaults; the user may want to confirm before treating it as final by running:
  - `fly logs -a crypto-master` and checking for `proposal_rejected` events with reason strings of the form `"composite X.XXXX below threshold 1.0000"`.
  - `fly ssh console -C 'tail -50 /app/data/runtime/activity.jsonl'` (note `/app/`, not `/data/` — see secondary finding below) to confirm the cycle pattern.
  - `fly ssh console -C 'ls /data/performance/'` to confirm the volume has no performance history yet.
  - If `fly logs` shows `cycle_errored` with API-key or claude-CLI failures instead, the conclusion would shift to a different configuration issue (keys not set / claude CLI auth) and the fix would differ.

- **The recommended default change `1.0 → 0.3`** is a behavioural change for any operator currently running with the implicit `1.0` default. Today there is exactly one such deployment (this Fly machine), and its current behaviour is "no trades", so the change is unambiguously an improvement. Worth calling out in the Phase 10.2 deployment doc.

- **Volume-path defect (secondary finding)**: `ActivityLog`, `AuditLog`, `ProposalHistory`, `Portfolio`, `Notification log`, and `FeedbackLoop` state directory all use hardcoded relative paths and ignore `Settings.data_dir`. On Fly with `WORKDIR=/app` and the volume at `/data`, these write to `/app/data/...` (ephemeral). Every machine recycle (auto-deploy, OOM, host migration) loses them. `PerformanceTracker` and `TradeHistoryTracker` are correctly volume-aware. Fix is a separate sub-task — see Follow-up Work.

## TECH-DEBT Items

None new. The defaults-incompatibility is in scope for Phase 10.2 (existing dev-plan item). The volume-paths finding is added to Follow-up Work below as a candidate sub-task; if the user approves, a planner cycle would add it to the dev plan.

## Follow-up Work

1. **Phase 10.2 EngineConfig Env Override (existing, unchecked)** — the natural next sub-task. When implementing, also change the default from `1.0` to `0.3` (quant-validated as safe) and document the cold-start ceiling in `.env.example` / `docs/deployment.md`.

2. **NEW candidate sub-task — Volume-aware default paths.** Route every `Default*Path` in `src/runtime/activity_log.py`, `src/feedback/audit.py`, `src/feedback/loop.py`, `src/proposal/interaction.py`, `src/proposal/notification.py`, and `src/trading/portfolio.py` through `Settings.data_dir` so that on Fly the activity / audit / proposal / portfolio history lands on the persistent volume rather than the ephemeral container root. Without this, even after Phase 10.2 unlocks trading, the activity log and the proposal history are wiped on every machine recycle and the dashboard timelines show holes. Suggested ID: **10.5 Volume-Aware Default Paths**. The user decides whether to add this to the dev plan now (planner cycle) or defer.

3. **Optional quant-side improvement** — introduce a "warm-up window" where the first N trades per technique use a lower threshold to bootstrap performance data, then snap to the configured threshold. More invasive than 10.2; only worth pursuing if the simpler env-override + lower default proves insufficient. Park as a candidate, not yet a sub-task.

---

## Runtime Verification Addendum — 2026-04-28 (post-cycle)

The user ran `fly logs -a crypto-master` against the running deployment after Cycle 1's report. **The actual log pattern overturns the original diagnosis's primary hypothesis.** Recording the correction here so the diagnostic record is honest about what was right and what was not.

### What the Fly logs actually show

100 most-recent log lines, ~2.5 hours of cycles:

- **One strategy only**: every cycle's per-symbol log line is `bollinger_band_reversion returned neutral on <SYMBOL>; no proposal`. No other strategy fires on any symbol. 91 of 100 lines match this exact pattern; the rest are Streamlit deprecation warnings and cycle-boundary entries.
- **No `proposal_rejected`, no `composite … below threshold` reason strings, no `cycle_errored`, no `scan_errored` events** — proposals never reach the threshold gate because they are filtered earlier by the `signal == "neutral"` short-circuit at `src/proposal/engine.py:357`.
- **Phase 9.4 strategies missing on Fly**: `ls /app/strategies/` returns `bollinger_bands.py`, `chasulang_ict_smc.md`, `experimental/`, `ma_crossover.py`, `rsi.py`, `sample_prompt.md`. Local has these plus `rsi_4h.py` and `rsi_15m.py`. The deployed image is from before Phase 9.4 (deployed ~11h before this addendum was written).
- **Volume confirmation (the secondary finding is correct)**: `/data/` is mounted with `runtime/`, `trades/`, `portfolio/`, `logs/` subdirs. `src/runtime/activity_log.py:34` defaults to `Path("data/runtime/activity.jsonl")` (relative). With `WORKDIR=/app` the file lands at `/app/data/runtime/activity.jsonl` (ephemeral), not `/data/runtime/activity.jsonl` (persistent volume). The user couldn't read the activity log on the volume because nothing was being written there.

### Corrected primary cause

The lockout is **not** at the threshold gate. It is at strategy selection:

1. `ProposalEngine._select_best_technique` (`src/proposal/engine.py:391`) returns **one** technique per symbol per cycle.
2. In cold-start (no performance history), the tiebreaker is **alphabetical by strategy name** (`applicable.sort(key=lambda s: s.name)`).
3. Alphabetic-first applicable strategy on Fly (without Phase 9.4): `bollinger_band_reversion`. (Locally with 9.4: still `bollinger_band_reversion` — alphabetic order is stable.)
4. `bollinger_bands.py`'s signal logic only fires when the close pierces the upper or lower band — a low-base-rate event. Most candles stay inside the bands → strategy returns `neutral` → engine logs the line we see → no proposal is created → score / threshold logic never runs.
5. Other strategies (`rsi`, `ma_crossover`, `chasulang_ict_smc`, `simple_trend_analysis`, `sample_prompt`) **never get to analyse anything**. They are loaded into `self.strategies` but `_select_best_technique` discards them.

The threshold-default story (`1.0` cap with cold-start ceiling `0.5`) **would** be the cause if proposals were being generated and rejected — but they're being filtered upstream. The cold-start ceiling math is still arithmetically correct; it just isn't what's blocking trades on this deployment.

### What this changes about the fix shape

- **Phase 10.2 EngineConfig Env Override is still valuable** — operators need to tune cycle interval, symbol list, balance, and threshold from Fly secrets. But the **threshold-default change `1.0 → 0.3` is no longer recommended**: lowering the threshold cannot help when no proposals reach it. Drop that part of the 10.2 brief.
- **New primary fix candidate: Phase 10.6 Multi-Technique Per-Symbol Scan.** Change `ProposalEngine` so each symbol cycle runs **every** applicable technique, not just the one alphabetically first. This restores the Phase 9.2 stated goal of "side-by-side LLM-vs-deterministic comparison + degraded-mode safety net" — currently broken because only one strategy is ever exercised. Backwards-compatible behaviour: the engine still returns ranked top-K proposals; it just generates more candidates to rank.
- **Alternative / complement: Phase 10.7 Cold-Start Selection.** Even if 10.6 doesn't land, swapping the cold-start tiebreaker from alphabetical-by-name to "highest historical fire-rate on the configured symbols" would let a more-active strategy (rsi / ma_crossover) win selection until performance data accumulates. Smaller patch than 10.6 but doesn't deliver the diversification benefit.
- **Phase 10.5 Volume-Aware Default Paths is confirmed.** The secondary finding is real and verified by the deployed file layout.
- **Phase 9.4 redeploy** is independent — once `rsi_4h.py` / `rsi_15m.py` ship, they would still need 10.6 to actually fire (alphabetic sort puts `bollinger_band_reversion` before any `rsi_*`).

### Cycle-1 retro

The team-lead's Cycle 1 hypothesis was a confidently-wrong inference from source-only inspection. The math was right; the upstream short-circuit was missed. Lesson for the orchestration: investigation cycles that conclude (b)/(c) should have a "grep the logs for the predicted reason string" step before treating the conclusion as final. Otherwise the team can produce internally-consistent diagnoses that actual runtime data refutes. Worth folding into the team-lead's role file as a stop condition: "for diagnostic cycles, do not declare a conclusion without a runtime artefact (log line / metric / state file) confirming the predicted symptom."
