---
name: strategy-improvement
description: Analyze deployed Fly /data strategy performance via verified subagent fan-out, then file improvement points as action-item units (strategy add/modify, bug, or code improvement) in docs/TECH-DEBT.md, with optional chart-based trade autopsy.
---

# Crypto Master Strategy Improvement Skill

Analyze deployed paper-lab strategy performance, derive improvement points
through subagent fan-out plus lead verification, and convert each verified
finding into an action-item unit (or a bounded change).

This skill is for requests like:

- "analyze current strategy performance"
- "improve profitability"
- "modify weak strategies or create a better one"
- "use subagents to review strategy performance"
- "strategy tuning from Fly paper results"
- "analyze why each strategy made bad chart decisions"
- "find improvement points and file them as action items / units"
- "spawn subagents to analyze and verify each before acting"

## What This Skill Produces

1. A verified evidence bundle and fair per-strategy metrics from deployed Fly
   `/data`.
2. A list of **lead-verified** improvement points (rejected/unverified findings
   are dropped, not actioned).
3. **Action-item units** for every verified finding that needs follow-up work,
   filed as `DEBT-XXX` entries in `docs/TECH-DEBT.md` and mapped to an AI-DLC
   unit in `aidlc-docs/inception/units/debt-unit-map.md`. Each unit is tagged as
   one of: `strategy-add`, `strategy-modify`, `bug`, or `code-improvement`.
4. Optionally, a bounded implementation of the highest-priority unit when the
   request is in `implementation` mode and evidence + hypothesis are clear.

Downstream, `/dev-crypto <unit>`, `/team-lead "resolve DEBT-NNN"`, and
`/tech-debt promote DEBT-NNN` consume these units to execute the work.

## Non-Negotiable Data Rule

For deployed strategy performance, use the Fly app's mounted `/data` volume.
Do not infer current performance from repo-local `data/`, backtest outputs, or
old copied snapshots unless the user explicitly asks for local/backtest-only
analysis.

**Preflight (fail loudly, do not dead-end silently).** Before snapshotting,
confirm Fly is reachable and the app is serving:

```bash
flyctl auth whoami
flyctl status --app crypto-master
flyctl ssh console --app crypto-master -C "sh -lc 'printenv DATA_DIR; find /data -maxdepth 2 -type d | sort | sed -n \"1,160p\"'"
```

If `flyctl` is unauthenticated, the app is stopped/scaled-to-zero, or you lack
access, STOP and surface the exact failure to the user. Then offer the
documented fallback (analyze repo-local `data/` or backtest outputs) as an
explicit, user-confirmed choice — never silently fall back, and never present an
empty/failed pull as an empty dataset.

**The lead captures exactly one snapshot** (do not let fan-out lanes each
re-snapshot — concurrent `flyctl ssh` pulls hit rate limits and return
inconsistent live state). Stamp the filename with a real timestamp and capture
the resolved path to hand to every lane:

```bash
mkdir -p /private/tmp/crypto-master-strategy-snapshots
SNAP="/private/tmp/crypto-master-strategy-snapshots/fly-data-$(date +%Y%m%d-%H%M%S).tgz"
flyctl ssh console --app crypto-master -C "sh -lc 'tar -C /data -czf - trades performance portfolio proposals runtime audit feedback notifications .subaccounts_migrated_v19_1 .performance_migrated_v19_2'" > "$SNAP"
test -s "$SNAP" || { echo "EMPTY SNAPSHOT — treat as hard failure, do not proceed"; }
SNAPDIR="${SNAP%.tgz}" && mkdir -p "$SNAPDIR" && tar -C "$SNAPDIR" -xzf "$SNAP"
echo "Shared read-only evidence dir for all lanes: $SNAPDIR"
```

The `tar` no longer swallows errors with `2>/dev/null`; an empty or failed
archive (`test -s`) is a hard failure, not an empty dataset. Extract once into
`$SNAPDIR` and pass that single absolute path to every subagent.

Never run repair, backfill, force-close, migration, or deletion tooling during
the analysis phase. Old `/private/tmp` snapshots may be reused if fresh enough;
record which snapshot a run used so re-runs are traceable.

## Required Context

Read the relevant subset before acting (read those that exist; skip-and-note any
that have been renamed or removed rather than stalling):

1. `AGENTS.md`
2. `config/sub_accounts.yaml`
3. `aidlc-docs/aidlc-state.md`
4. `aidlc-docs/construction/plans/strategy-tuning-code-generation-plan.md`
5. `aidlc-docs/construction/strategy-tuning/functional-design/spec.md`
6. `aidlc-docs/inception/units/unit-of-work.md`
7. `aidlc-docs/inception/units/debt-unit-map.md`
8. `docs/TECH-DEBT.md`
9. `docs/sessions/2026-05-13-fly-strategy-analysis-units.md`
10. `docs/sessions/2026-05-13-strategy-tuning-slice-1-shipped.md`

For code changes, also inspect:

- `src/strategy/base.py`
- `src/strategy/loader.py`
- `src/strategy/indicators.py`
- `src/strategy/performance.py`
- `src/strategy/trade_autopsy.py`
- `src/strategy/tuning.py`
- `src/strategy/tuning_recommender.py`
- `src/proposal/interaction.py`
- `src/proposal/replay.py`
- `src/exchange/base.py`
- `src/backtest/validator.py`
- `src/dashboard/pages/autopsy.py`
- representative strategy files under `strategies/`

For detailed chart-autopsy procedures, load
`references/chart-autopsy.md` only when the request asks for chart-based trade
autopsy, strategy mistake diagnosis, or strategy logic changes based on trade
charts.

## Workflow

**How this skill runs.** The fan-out + lead-verification pattern in §7 is the
*execution engine*, not a late step. §§2-6 define **what each lane computes and
the rubric the lead verifies against**; §7 defines **who runs them and how
findings are validated**; §§8-9 turn verified findings into decisions and
action-item units. Read §7 before dispatching: the lead captures the shared
snapshot, fans out lanes that perform the §§2-6 analyses, runs the §7
verification gate, then proceeds 6 → 8 → 9. Do not execute §§2-6 single-threaded
*and then* redo them as lanes.

### 1. State The Mode

Classify the request as one of:

- `analysis-only`: produce findings and a plan; do not edit files.
- `planning`: produce an implementation plan or AI-DLC construction slice; do
  not edit strategy/runtime code.
- `implementation`: make a bounded change after evidence and plan are clear.

If the user says "analysis and plan first", stay in `analysis-only` or
`planning`.

### 2. Build The Evidence Bundle

Use the Fly snapshot to build a joined `(sub_account_id, strategy_id)` evidence
model. Preserve sub-account boundaries; do not flatten strategy-lab accounts.

Load and reconcile, when present:

- `/data/trades/paper/<sub_account>/trades.json`
- `/data/portfolio/paper/<sub_account>/snapshots.json`
- `/data/performance/<sub_account>/<strategy>/records.json`
- `/data/performance/<sub_account>/<strategy>/summary.json`
- `/data/performance/<sub_account>/<strategy>/fail_closed.json`
- `/data/proposals/<sub_account>/*.json`
- legacy root `/data/proposals/*.json`, de-duplicated by proposal id
- `/data/runtime/activity*.jsonl`
- `/data/audit/*.jsonl`
- migration marker files under `/data/`

Report snapshot timestamp, Fly app, machine/release if available, included
paths, parse failures, and data freshness before recommendations.

### 3. Compute Fair Strategy Metrics

Do not rank from `summary.json` alone. Compute or report:

- closed real trades, excluding `synthetic=true` reconciliation records
- win rate, gross win, gross loss, true profit factor
- expectancy per trade, median PnL, closed PnL in USDT
- closed PnL as percent of one **canonical base — account equity** (report
  notional-based returns separately and labeled; never mix bases across
  strategies in a ranking)
- realized fee drag **and realized + estimated funding cost** over the holding
  period for perpetual positions
- **risk-adjusted return: per-strategy Sharpe and Sortino**, stating the
  sampling basis (per-trade vs per-day) and `rf = 0`; use the same Sharpe basis
  as the §10 OOS robustness gate so analysis and gate measure the same thing
- max drawdown and return over max drawdown
- average risk per trade and PnL per 1 percent account risk when available
- **trades per period and mean/median holding period** (capacity / fee exposure
  differ even at equal per-trade expectancy)
- realized leverage per strategy (so a high return % that is just leverage is
  visible, not rewarded)
- **per-regime (bull/bear/sideways/unknown) expectancy and win rate**
- stop-loss hit rate and take-profit hit rate
- open count, open notional, fresh mark-to-market PnL, stale-open count
- missing SL/TP, missing `performance_record_id`, malformed closed rows
- proposal generated, score accepted, trade opened, outcome linked
- gate rejection breakdown, fail-closed rate, emission rate
- coverage window, latest snapshot age, data-quality confidence

Handle degenerate cases — these silently invert rankings on small samples:

- profit factor is **undefined / ∞ when gross loss = 0** (early winning streak);
  report it as such and never let ∞ drive a `keep`/`promote`
- expectancy and PF are dominated by a single outlier in the `<30`-trade regime;
  report a confidence interval (bootstrap or t-based) or the
  largest-trade-removed expectancy, and rank on the **lower CI bound**, not the
  point estimate
- return-over-max-drawdown inflates to meaninglessness when MDD is below a noise
  floor (e.g. `< 1-2` trades' worth of risk); cap or flag it

Use sample-size labels (necessary but not sufficient — pair every tier with a
confidence interval and a minimum loser count; PF from 30 trades with 2 losers
is not robust):

- `<5` closed real trades: exploratory
- `5-14`: weak evidence
- `15-29`: usable but not fully comparable
- `30+`: minimum for comparison, still wide CI on heavy-tailed crypto PnL — not
  "settled"

Also gate on **calendar coverage, not just trade count**: 30 trades compressed
into 2 days of one regime is not comparable to 30 trades over months across
regimes. Downgrade the label when trade count is high but calendar span / regime
diversity is low, and forbid `keep`/`promote` when all positive expectancy comes
from a single regime bucket (regime-confounded → max action `scout`).

Never let a `2/2` strategy outrank a larger sample without a low-sample label.
Do not multiply PnL by leverage again. Treat missing mark prices as unknown,
not zero. Flag any strategy whose positive expectancy is smaller than its
omitted funding estimate as "edge unconfirmed."

### 4. Run Chart-Based Trade Autopsies

When the request asks why strategies misjudged trades, when strategy code
changes are being considered, or when material losers/winners need diagnosis,
perform chart-based autopsy before recommending entry/exit logic changes.

Use read-only OHLCV evidence. Prefer existing project surfaces:

- `TradeAutopsy` and `TradeAutopsy.with_candle_window()` in
  `src/strategy/trade_autopsy.py`
- proposal/candle replay contracts in `src/proposal/replay.py`
- exchange `get_ohlcv(..., since=...)` APIs in `src/exchange/base.py`
- robustness/OOS validation in `src/backtest/validator.py`

For each sampled `(sub_account_id, strategy_id)` trade:

- join proposal, trade, performance record, and portfolio context
- inspect at least 100 primary-timeframe bars before entry, the entry-to-exit
  window, and 50 bars after exit when data is available
- include higher-timeframe context when relevant, for example 15m -> 1h/4h or
  1h -> 4h/1d
- compute MFE/MAE, realized R, bars to MFE/MAE, ATR/VWAP/SMA distance,
  stop/target distance versus realized volatility, post-exit follow-through,
  entry volume/range percentile, and same-candle TP/SL ambiguity
- any feature/percentile/indicator used to **judge or modify entry logic**
  (ATR percentile, VWAP, SMA distance, volume/range percentile) must be computed
  from the **pre-decision candle subset only**; post-entry candles are for
  outcome metrics (MFE/MAE, follow-through) exclusively — see Guardrails
- classify chart mistakes with the controlled taxonomy from
  `references/chart-autopsy.md`
- report OHLCV source, exchange, timeframe, since/limit, expected versus
  fetched bars, missing gaps, and timestamp alignment assumptions

Do not treat chart fetch failures, missing windows, stale open rows,
`synthetic=true` records, missing SL/TP, or missing `performance_record_id` as
strategy-edge evidence. Classify those as `runtime-artifact` or
`chart_data_unavailable` and route to runtime/funnel work first.

Tail sampling is for **hypothesis generation only**. Drawing the largest
winners/losers / SL-closes / TP-closes is an outcome-stratified, biased sample;
do not compute mistake *rates*, effect sizes, or average-R from it. Re-measure
any rate that gates a logic change on a representative (or full) loser sample.

Strategy logic changes require a replay/backtestable hypothesis. The
"`≥3 trades or ≥30% of relevant losers`" trigger is a multiple-comparisons trap
across the ~13 taxonomy labels — with few losers some label clears 30% by
chance. Therefore do not modify logic unless **all** hold:

- the mistake label was **predeclared** before scanning (hypothesis-first), or a
  multiplicity correction is applied across the taxonomy;
- the label's rate among losers is materially higher than its rate among winners
  (base-rate differential, not a single cherry-picked counterexample);
- the absolute floor is raised above 3 when the relevant loser sample is itself
  `<15` (the threshold is meaningless on an "exploratory/weak" sample);
- at least one counterexample was reviewed.

### 5. Separate Runtime Problems From Strategy Edge

Before changing strategy logic, decide whether poor results are caused by:

- unreconciled runtime state
- missing SL/TP or missing performance links
- stale open positions or cash-only portfolio snapshots
- proposal score thresholds
- stale quote, cap, correlation, market-regime, or risk-budget gates
- account policy configuration
- strategy signal quality

If runtime or funnel state is invalid, route the work to
`runtime-reconciliation`, `proposal-funnel-audit`, or `cross-account-risk-policy`
before strategy code changes.

### 6. Synthesize Actions

Map each strategy family to one action. Bind each to a **quantitative** gate so
a losing family is not `kept` on noise and a good family is not `paused` on one
adverse regime:

- `pause`: a hard safety breach (caps/risk) **or** loss that survives a regime +
  sample-size check (do not pause a family whose only losses are one adverse
  regime — that is `shadow`/`scout`)
- `shadow`: keep measuring signals but block opens
- `scout`: promising but under-sampled; reduce size
- `retune`: mediocre or regime-misaligned; hypothesis needed
- `keep`: `≥15` trades and lower-CI expectancy `≥ 0`
- `promote`: `30+` trades (or higher per the wide-CI note in §3), positive
  lower-CI expectancy, all four §10 robustness sub-gates passed, and no
  single-regime confound

Each action maps to a concrete **outcome** (see §9): `pause` / `shadow` /
`scout` / `keep` are account-policy states realized as a `config/sub_accounts.yaml`
YAML diff in the report (not a `DEBT-XXX` unit); `retune` becomes a
`strategy-modify` unit; `promote` is governed by the §10 gates, not a unit; a
new family from §8 step 5 becomes a `strategy-add` unit.

**Cross-strategy selection guard.** Promoting the best of N families evaluated on
one shared paper window is itself a multiple-comparison over strategies; the
per-strategy OOS gate does not correct for the winner being selected from N.
Raise the OOS/Sharpe bar with the number of candidates considered
(deflated-Sharpe or Bonferroni), and require the promoted family's OOS to come
from a window not used to select it among peers.

Paper performance may recommend an action. It must not directly rewrite logic
without a hypothesis, replay/backtest plan, and verification gate.

### 7. Subagent-Driven Analysis With Lead Verification

This is the execution engine for §§2-6. The parent assistant is the **lead**
(the top-level agent — only it can spawn subagents): it captures the shared
snapshot, sizes the fan-out, dispatches subagents that perform the §§2-6
analyses, then verifies every finding before anything becomes an action item.
Subagents discover and argue; the lead decides what is true. A subagent **cannot
spawn its own subagents** — when a lane's output reveals a deeper question, it
*reports that question* and the lead spawns the follow-up lane.

**Size the fan-out to the evidence surface, within a budget.** One lane per
coherent investigation; do not spawn redundant lanes that read the same slice.
Default to **≤6-8 concurrent lanes for a first pass**. A thin snapshot (one
sub-account, `<15` closed trades) may need only 3-4. If the evidence surface
justifies `≥10` lanes, or a recursive follow-up depth `>1`, **confirm the
fan-out size / budget with the user before dispatching** rather than ballooning
into dozens of agents. Bound chart autopsy to a sampled N trades per strategy,
not every loser. Stop condition: every strategy family has a verdict and no
high-severity finding is left unverified.

Use the project agents where they fit: prefer `Explore` (read-only, no
Edit/Write) for evidence custody and data parsing; use `quant-trader-expert` for
any strategy-logic, risk-math, or chart-autopsy lane; `general-purpose` only
when a lane genuinely needs broader tools.

**Every subagent prompt must embed a read-only + scope contract**, because
analysis lanes run in separate contexts the lead-facing Data Rule does not
reach:

- the single shared extracted snapshot path (`$SNAPDIR`) to read; "analyze only
  files under this path, read-only";
- "do NOT call flyctl or re-snapshot; do NOT Edit/Write; do NOT run
  repair/backfill/migrate/force-close/delete tooling; do not modify the snapshot
  or repo `data/`";
- the current `mode` (`analysis-only` / `planning` / `implementation`) — lanes
  must refuse file edits, test runs, or commits when `mode != implementation`;
- the structured-finding return contract below.

Typical lanes (extend or collapse as the snapshot demands; each executes the
correspondingly-numbered §§2-6 analysis):

1. Evidence custody: Fly health, release, snapshot, `/data` layout.
2. Runtime reconciliation: orphan trades, SL/TP, links, stale state.
3. Closed-trade PnL: realized return, PF, win rate, fees, outliers.
4. Open exposure: mark-to-market, concentration, stale age, risk.
5. Strategy cohort: RSI, mean reversion, breakout, trend, default/LLM.
6. Proposal funnel: generated to opened conversion and gate breakdown.
7. Risk policy: sizing, caps, same-symbol/side exposure, drawdown pause.
8. Market regime: bull/bear/sideways/unknown match and allowed regimes.
9. Chart autopsy: representative winners/losers/open-risk samples, OHLCV
   custody, MFE/MAE/R, ATR/VWAP/regime checks, mistake taxonomy, and
   replay/backtestable hypotheses.
10. Code/bug audit: defects in strategy/runtime/funnel code surfaced by the
    data (e.g. miscomputed PF, mis-wired gate, look-ahead in a signal).
11. Planning synthesis: AI-DLC unit mapping and ordered action plan.

Require each analysis subagent to return a **structured finding list**, where
every finding carries: claim, evidence pointers (exact snapshot paths, trade
ids, `(sub_account, strategy)`, candle window), sample-size label, proposed
classification (one of `strategy-add` / `strategy-modify` / `bug` /
`code-improvement` / `runtime-artifact` / `chart_data_unavailable` /
`no-action`), and a confidence. Findings without evidence pointers are not
findings.

#### Lead verification gate (mandatory)

No finding becomes an action item until the lead has verified it. For each
candidate finding the lead:

- re-checks the cited evidence against the snapshot itself (open the file/trade,
  do not trust the subagent's summary);
- applies the sample-size and `synthetic`/stale/missing-link rules from steps
  3-5 — reject anything resting on `<5` trades, `synthetic=true` rows, missing
  SL/TP, missing `performance_record_id`, or a chart fetch failure as
  strategy-edge evidence (reclassify as `runtime-artifact`);
- for any strategy-logic claim, confirms the chart-mistake-repetition threshold
  from step 4 (≥3 trades or ≥30% of relevant losers, with ≥1 counterexample);
- for any bug/code claim, reads the cited source lines to confirm the defect is
  real and not a misread;
- runs a quick adversarial check — can this finding be explained by a benign
  cause (regime, fees, small sample, runtime state)? If plausibly yes and the
  subagent did not rule it out, **re-dispatch the lane** (spawn a fresh agent
  with the specific counter-hypothesis, or `SendMessage` the existing one to
  continue with its context) — at most **1-2 rounds**. If still unverified after
  the second pass, drop it as unverified; do not loop further.

When two subagents disagree, or evidence supports competing trading
interpretations, do not average them — spawn one tie-breaker lane or escalate to
the user (see Guardrails). Record, per finding, a verdict of
`verified` / `reclassified` / `rejected` and the reason:

- `verified` findings flow on through §6 (per-family action) → §8
  (modify-vs-create) → §9 (file the unit). Verification does not skip §6/§8.
- `reclassified` to `runtime-artifact` / `chart_data_unavailable`: not
  strategy-edge work, but if the artifact is itself a defect it becomes a `bug`
  / `code-improvement` unit routed to runtime/funnel units in §9.
- `no-action` (verified-but-benign, e.g. regime-explained) and `rejected`:
  record in the report's verification log; they produce no unit.

### 8. Decide Modify Existing Vs Create New

§8 and the implementation half of §9 execute **only in `implementation` mode**.
In `analysis-only` / `planning` mode this step produces the *recommended*
modify-vs-create decision as text, not file edits.

Prefer the smallest action supported by evidence:

1. Data invalid: fix observability/reconciliation first.
2. Strategy bad only because gates are wrong: tune runtime/policy, not entry
   logic.
3. Strategy has a clear parameter hypothesis: retune existing strategy.
4. Strategy family is structurally mismatched to regime: pause/shadow or add
   regime gating before rewriting.
5. Existing family has no salvageable edge and a tested hypothesis exists:
   create a new deterministic OHLCV-only strategy.

New strategy files should be `.py` `BaseStrategy` subclasses under
`strategies/` with `TECHNIQUE_INFO`. Prefer shared indicators from
`src/strategy/indicators.py`. Avoid prompt `.md` strategies unless the user
explicitly asks for Claude-in-the-loop strategy generation.

### 9. Create Action-Item Units

Every `verified` finding that needs follow-up work becomes an **action-item
unit** — a `DEBT-XXX` entry in `docs/TECH-DEBT.md` mapped to an AI-DLC unit.
This is the durable hand-off; `/dev-crypto`, `/team-lead`, and `/tech-debt`
consume it. Do not leave verified improvement points only in the chat report.

Classify each finding into exactly one action-item type:

| Type | When | Default primary unit |
|------|------|----------------------|
| `strategy-add` | A tested OHLCV-only hypothesis with no salvageable existing home | `strategy-framework` |
| `strategy-modify` | Parameter/logic/regime-gating change to an existing family with a replay/backtestable hypothesis | `strategy-tuning` (params/gates) or `strategy-framework` (logic) |
| `bug` | A real defect in strategy/runtime/funnel/risk code confirmed against source | unit that owns the first code change |
| `code-improvement` | Correctness-preserving clarity/structure/observability fix | unit that owns the file |

Routing rules:

- `verified` strategy findings map to a `strategy-add` / `strategy-modify` /
  `bug` / `code-improvement` unit (§6 action mapping: `retune` → `strategy-modify`,
  new family → `strategy-add`).
- `runtime-artifact` / `chart_data_unavailable` findings are **not strategy-edge
  work**. They become a unit *only if the artifact is itself a defect worth
  fixing*; in that case file a `bug` / `code-improvement` unit routed to
  `runtime-reconciliation`, `proposal-funnel-audit`, or `cross-account-risk-policy`.
  A transient data gap with no underlying defect produces no unit.
- `no-action` and `rejected` findings produce **no unit** — record them in the
  report's verification log only.
- A pure account-policy/threshold change with no code edit (a `pause` / `shadow`
  / `scout` / `keep` action) is a config action, not a unit; record it as a
  `config/sub_accounts.yaml` YAML diff in the report instead of a `DEBT-XXX`.
- Map every unit to its AI-DLC unit via the path-ownership table in
  `aidlc-docs/inception/units/unit-of-work.md`; pick the unit owning the first
  code change as primary and list spillover units as secondary.

For each action-item unit, write a `docs/TECH-DEBT.md` entry using the template
at the top of that file. In the `Description`, include the finding's evidence
pointers (snapshot path, `(sub_account, strategy)`, trade ids / candle window),
the verification verdict, the sample-size label, and — for `strategy-modify` /
`strategy-add` — the predeclared hypothesis and the replay/backtest plan that
must pass before promotion. Set `Priority` from impact (loss-causing or unsafe →
High/Critical; mediocre/cosmetic → Medium/Low) and stamp `Component` with the
affected unit(s).

Then update `aidlc-docs/inception/units/debt-unit-map.md`: add a row under
"Active Debt by Unit" and a row in the "Debt Details" table with the suggested
next action. Per that file's own rule, update `docs/TECH-DEBT.md` first, then
refresh the map in the same change.

Number new entries by **allocating the whole id block up front**: read the
current max once (parse the numeric prefix only — `DEBT-069` has lettered
sub-rows like `DEBT-069(a)`, so grep the number, not the suffix) and reserve
`DEBT-(max+1 .. max+k)` for the k verified findings, then write them
**sequentially in one pass**. Never delegate unit-writing to concurrent
subagents — that is how two findings collide on the same id. Before writing,
grep `docs/TECH-DEBT.md` and `debt-unit-map.md` for an existing entry covering
the same `(sub_account, strategy)` finding and **update it instead of
duplicating**.

In `analysis-only` / `planning` mode, present the proposed units (id, type,
unit, priority, one-line action) in the report and ask before writing them
unless the user said to file them automatically. In `implementation` mode, write
the units, then optionally pick up the top one via the Decide-Modify-vs-Create
path above.

### 10. Guardrails

- No live promotion from paper evidence alone.
- No mainnet sizing, credential, or deployment changes without explicit user
  intent.
- No promotion without operator approval.
- No parameter search without a predeclared hypothesis and bounded search
  space.
- No repeated tuning against the same Fly paper window without a fresh OOS or
  forward observation period.
- A plain full-history backtest is not enough; use chronological OOS,
  walk-forward, regime split, and parameter sensitivity where promotion is at
  stake.
- Replay threshold, approval, exit, SL/TP, or filter changes against proposal
  history before implementation or promotion decisions.
- No chart-driven strategy edits from implicit live fetches alone; persist fixed
  candle-window artifacts and record data gaps before replay/autopsy.
- No look-ahead bias: entry-cause analysis may use only candles closed before
  proposal/trade decision time; post-entry candles are for outcome diagnostics
  and hypothesis testing only. This applies to **derived features too** — any
  ATR/VWAP/SMA/percentile used to judge or modify entry logic must be computed
  from the pre-decision candle subset, never across a window that includes
  post-entry bars.
- No promoting the best of N strategies on a shared window without a
  selection-bias correction (deflated-Sharpe / Bonferroni) and an OOS window not
  used for the among-peers selection.
- Stop and ask when evidence supports competing trading interpretations.

## Implementation Targets

For `strategy-tuning` work, update only the relevant subset:

- `src/strategy/performance.py`
- `src/strategy/tuning.py`
- `src/strategy/tuning_recommender.py`
- `src/runtime/engine.py`
- `src/proposal/funnel.py`
- `src/trading/sub_account.py`
- `src/dashboard/pages/strategies.py` or current dashboard strategy surface
- `config/sub_accounts.yaml` and examples when account policy changes

For strategy code:

- `strategies/<name>.py`
- `tests/test_baseline_strategies.py`
- `tests/test_strategy_loader.py`
- strategy-specific tests when present

For chart-autopsy implementation work:

- `src/strategy/trade_autopsy.py`
- `src/strategy/chart_autopsy.py` when pre/post-entry chart features or mistake
  taxonomy need a new module
- `src/tools/` or `scripts/` for read-only candle-window report generation
- `src/dashboard/pages/autopsy.py` for operator chart-autopsy visibility
- `tests/test_strategy_trade_autopsy.py`
- `tests/test_strategy_chart_autopsy.py`
- `tests/test_proposal_replay.py`

Avoid unrelated refactors and do not modify repo-local runtime data.

## Verification

Pick tests based on touched surfaces:

```bash
uv run pytest tests/test_baseline_strategies.py tests/test_strategy_loader.py -q
uv run pytest tests/test_strategy_performance.py tests/test_strategy_tuning_recommender.py -q
uv run pytest tests/test_runtime_engine.py tests/test_proposal_funnel.py tests/test_proposal_replay.py -q
uv run pytest tests/test_trading_sub_account.py tests/test_trading_sub_account_registry.py -q
uv run pytest tests/test_backtest_validator.py tests/test_scripts_backtest_baselines.py -q
uv run pytest tests/test_dashboard_strategies.py tests/test_dashboard_trading.py -q
uv run pytest tests/test_strategy_trade_autopsy.py tests/test_proposal_replay.py -q
uv run black src tests scripts strategies
```

For broader or cross-unit changes, run `uv run pytest` when practical. Record
any skipped checks and why.

## Documentation And AI-DLC Updates

For substantial implementation, update the relevant files narrowly:

- `aidlc-docs/construction/plans/strategy-tuning-code-generation-plan.md`
- `aidlc-docs/aidlc-state.md`
- `docs/TECH-DEBT.md`
- `aidlc-docs/inception/units/debt-unit-map.md` only when debt changes
- `docs/sessions/YYYY-MM-DD-strategy-tuning-<task>.md`
- `docs/cross-checks/YYYY-MM-DD-strategy-tuning-<task>.md` after completed
  unit-level change

Do not churn `docs/development-plan.md`, `docs/legacy/development-plan.md`,
`DESIGN.md`, or broad requirements docs unless the task explicitly changes
architecture, requirements, or legacy phase interpretation.

## Report Format

End with:

- Fly evidence source and snapshot path
- strategy ranking with confidence labels
- subagent fan-out used (lanes + agent types) and, per finding, the lead
  verification verdict (`verified` / `reclassified` / `rejected`) with reason
- runtime/funnel/data-quality blockers
- chart autopsy coverage, OHLCV source, missing candle gaps, and timestamp
  assumptions
- repeated chart mistake taxonomy and per-strategy hypothesis
- recommended action per strategy family
- **action-item units emitted or proposed**: `DEBT-NNN`, type
  (`strategy-add` / `strategy-modify` / `bug` / `code-improvement`), primary
  unit, priority, one-line next action
- implementation plan or changed files
- verification run or not run
- remaining risks and operator decisions needed
