# Chart-Based Strategy Autopsy

Use this reference when `strategy-improvement` must explain why each strategy
made good or bad chart decisions, or when chart evidence may drive retuning,
pausing, or strategy logic changes.

## Evidence Contract

Start from the deployed Fly `/data` snapshot. Join proposal, trade,
performance, portfolio, runtime activity, and account policy by
`(sub_account_id, strategy_id, trade_id, proposal_id)` where available.

Treat OHLCV as a separate read-only evidence artifact:

- fetch or load candles after the Fly snapshot has been captured
- store the fetched candle windows outside the repo or under an explicit
  analysis output path
- record exchange, symbol, timeframe, since, limit, first/last candle,
  expected bars, fetched bars, and missing gaps
- never infer chart behavior from missing candles

Prefer existing code surfaces before inventing new ones:

- `src/strategy/trade_autopsy.py`
- `src/proposal/replay.py`
- `src/exchange/base.py`
- `src/backtest/validator.py`
- `src/dashboard/pages/autopsy.py`

## Sampling

For every material strategy family, sample enough trades to cover both outcome
and failure modes:

- largest realized losers
- largest realized winners
- stop-loss closes
- take-profit closes
- long holds and stale/open-risk rows
- near-threshold rejected proposals when proposal tuning is in scope

Do not overstate small samples. Keep the base sample labels:

- `<5`: exploratory
- `5-14`: weak evidence
- `15-29`: usable but not fully comparable
- `30+`: comparable

Open, stale, synthetic, reconciliation-close, missing-SL/TP, missing
`performance_record_id`, or incomplete-exit rows may be reviewed for runtime
risk, but they are not clean strategy-edge evidence.

## Candle Windows

Default window per sampled trade:

- primary timeframe: 100 bars before entry
- trade window: entry through exit
- post-exit: 50 bars after exit

Add higher timeframe context when it affects the strategy:

- 15m strategy: add 1h and 4h
- 1h strategy: add 4h and 1d
- 4h strategy: add 1d

Entry-cause analysis may use only candles closed before proposal/trade
decision time. Entry/exit candles are intrabar ambiguous unless the data source
contains fill sequencing. Post-entry and post-exit candles are outcome
diagnostics, not entry-rule evidence.

## Metrics

Compute or report:

- MFE %, MAE %, realized PnL %, realized R
- MFE_R, MAE_R, final_R against entry-stop risk
- bars to MFE, bars to MAE, bars held
- post-exit follow-through in trade direction
- stop distance and target distance in ATR
- entry distance to VWAP, SMA/EMA, Bollinger bands, or declared strategy level
- ATR percentile and whether volatility expanded after entry
- entry candle body/range ratio and wick ratio
- entry volume percentile and candle range percentile
- TP touched before exit, SL touched before exit, and same-candle ambiguity
- local regime, higher-timeframe regime, and market-regime gate result when
  available
- duplicate exposure or correlated same-symbol/same-side context

## Mistake Taxonomy

Use a controlled taxonomy so reports are comparable. Prefer one primary label
and optional secondary labels, each with confidence.

- `runtime_artifact`: stale quote, stale open, missing SL/TP, missing
  performance link, bad mark, cap artifact, or reconciliation state
- `chart_data_unavailable`: missing, unsorted, insufficient, or non-overlapping
  candles
- `late_entry_chase`: entry occurred after the favorable move was already
  mostly exhausted
- `counter_regime_entry`: trade fought dominant local or higher-timeframe
  regime
- `false_breakout`: breakout failed or closed back inside the broken range
  within the expected confirmation window
- `mean_reversion_into_trend`: fade entered into strengthening trend or
  volatility expansion
- `volatility_expansion_after_entry`: ATR/range expanded against the position
  shortly after entry
- `stop_too_tight`: price modestly exceeded stop before later reaching the
  thesis area or target zone
- `stop_too_wide`: adverse excursion was too large relative to thesis, ATR, or
  risk budget
- `target_too_far`: repeated MFE reached a practical partial target but not the
  configured take-profit
- `premature_exit`: exit occurred before strong continuation in the original
  direction
- `time_stop_mismatch`: holding period outlived the observable setup edge
- `mtf_conflict`: lower-timeframe signal conflicted with higher-timeframe
  trend or regime
- `low_liquidity_noise`: abnormal low volume, wide spread proxy, or noisy wick
  drove the signal
- `duplicate_exposure`: correlated or same-symbol exposure dominated the
  outcome
- `unknown_insufficient_chart`: chart exists but does not support a confident
  diagnosis

## Hypothesis Gate

A chart label is not a strategy action by itself. Turn it into an implementation
hypothesis only when:

- the same primary mistake repeats in at least 3 trades or at least 30% of the
  relevant losing sample
- at least one counterexample was checked
- runtime artifacts were separated from strategy-edge mistakes
- the hypothesis can be replayed or backtested without look-ahead
- the parameter search space is declared and bounded

Prefer one hypothesis per strategy family per cycle. Examples:

- "VWAP mean reversion needs an ATR expansion filter before fading."
- "Breakout entries need a volume percentile floor and close-confirmation."
- "RSI entries should scout only when higher-timeframe regime is not strongly
  against the signal."
- "Stop distance should be widened only if MFE_R shows recurring stop-runs
  followed by target-zone reaches."

## Report Template

For each strategy family, report:

- sample count and confidence label
- OHLCV source and coverage
- representative winners and losers
- repeated primary/secondary mistake labels
- metrics summary: MFE/MAE/R, ATR/VWAP/regime, stop/target realism
- runtime artifacts excluded from strategy-edge evidence
- one hypothesis or "no chart-backed hypothesis"
- required replay/backtest/OOS verification before implementation
