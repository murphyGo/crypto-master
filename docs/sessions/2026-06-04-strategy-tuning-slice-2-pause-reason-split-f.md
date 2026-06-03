# Session: strategy-tuning Slice 2 (f) — pause-reason split (evidence vs gate-config)

Date: 2026-06-04
Unit: `proposal-runtime` + `dashboard-operator-ui` (DEBT-069 `strategy-tuning` Slice 2, sub-task (f))
Stage: Code Generation (trading-domain — quant design ruling first, code review after)
Related: DEBT-069(f) (quant Q5 follow-up); quant design ruling 2026-06-04.

## Scope

Split the strategy-tuning `pause` reason so the operator can tell an
evidence-corroborated pause (the live recommender also says pause) from a
gate-config-only pause (operator/seed config the current evidence no longer
supports — worth revisiting). Observability-only: never changes whether a pause
blocks.

## Quant design ruling (2026-06-04, pre-implementation)

- **Option (b), not the enum split.** `StrategyAction` is the durable
  operator-intent vocabulary (YAML / JSONL / seed map / recommender return).
  Evidence-vs-config is a *gate-time corroboration observation*, not two operator
  intents — it belongs in event `details`, not the action enum. Splitting the
  enum would ripple into the seed map, `applied_action_for`, the funnel terminal,
  and the YAML vocabulary for a runtime-only label.
- **Do NOT compute corroboration in the gate.** The engine holds **no**
  `PerformanceTracker` / `FailClosedMetricsTracker` on the gate path (it imports
  only `TradeHistory`). Computing corroboration there would mean threading both
  trackers into the engine **and** a new per-paused-proposal file-read +
  recommender call on the hot reject path — a self-inflicted violation of the
  "no new tracker call on the cycle path" invariant. The gate writes only the
  cheap structural fact it knows (`pause_reason="gate_config"`); the dashboard
  computes corroboration from the `applied` / live-`recommended` it already
  produces per `(sub_account, strategy)`.
- **Funnel terminal + `gate_reason` unchanged** — single
  `STRATEGY_ACTION_PAUSE` / `GATE_REJECTED_STRATEGY_ACTION_PAUSE`. A pause is a
  pause for capital-flow counting.
- **Product call (per quant):** `applied=PAUSE` + live recommender returns `None`
  (evidence too thin) → `gate_config_only` (the over-cautious case worth
  surfacing), not a third bucket.

## What shipped

**1. Engine gate (`src/runtime/engine.py`).** The `_strategy_action_gate` PAUSE
branch adds `"pause_reason": PAUSE_REASON_GATE_CONFIG` to the rejection event
`details`. The `record.reject(...)`, `GateOutcome(REJECTED, ...)`, `gate_reason`,
and terminal are untouched — the discriminator never feeds the block decision.
No tracker/exchange call added.

**2. Shared constant (`src/strategy/tuning.py`).** New
`PAUSE_REASON_GATE_CONFIG = "gate_config"` (added to `__all__`) so engine + tests
agree on the spelling. Lives in the durable tuning vocabulary module; no enum
change.

**3. Dashboard (`src/dashboard/pages/strategies.py`).**
- New module constants `PAUSE_TRIAGE_NONE` / `PAUSE_TRIAGE_EVIDENCE_CORROBORATED`
  (`"evidence_corroborated"`) / `PAUSE_TRIAGE_GATE_CONFIG_ONLY`
  (`"gate_config_only"`) + pure `_pause_triage_label(applied, live_recommendation)`.
- `build_strategy_tuning_rows` now captures the **raw live** `recommend_action`
  output (`live_recommendation`) BEFORE the seed fallback and passes it to the
  triage label — so a seeded pause (config guidance, not evidence) never counts
  as corroboration; thin evidence (`None`) → `gate_config_only`.
- New `StrategyTuningRow.pause_triage: str = ""` field + a `Pause Triage` column
  in `build_strategy_tuning_dataframe` (blank for non-pause rows).

## Trade-correctness invariants preserved

- Pause still hard-rejects regardless of `pause_reason` (discriminator is inside
  the `details` dict only; no branch keys off it).
- No new tracker/exchange call on the gate path — the gate writes a literal it
  already knows.
- Paper/live behaviour identical; the `enabled=False` no-op and all non-pause
  branches unchanged.
- Funnel accounting unchanged (single reason + terminal).
- Dashboard derives corroboration read-only from data it already loads; never
  mutates applied state or re-persists the event.

## Tests / checks

- Engine: `test_strategy_action_gate_pause_rejects_with_dedicated_terminal`
  extended with `details["pause_reason"] == "gate_config"`.
- Dashboard (`tests/test_dashboard_strategies.py`), 4 new + 1 column update:
  - `pause_triage_evidence_corroborated` — applied PAUSE + pause-band evidence →
    live recommends pause → `evidence_corroborated`.
  - `pause_triage_gate_config_only_when_recommender_disagrees` — applied PAUSE +
    keep-band evidence → `gate_config_only`.
  - `pause_triage_gate_config_only_on_thin_evidence` — applied PAUSE + thin
    evidence (live `None`, seed fills Recommended) → `gate_config_only`.
  - `pause_triage_blank_for_non_pause` — applied keep → `""`.
  - `test_tuning_dataframe_columns_and_empty` updated for the new `Pause Triage`
    column.
- Full suite: **2334 passed** (+4 from the 2330 (i) baseline), 0 failed; black +
  ruff + mypy clean (103 source files).

## Debt

DEBT-069(f) resolved. Remaining-open DEBT-069 sub-tasks: (c) observation store,
(g) post-evidence threshold calibration.
