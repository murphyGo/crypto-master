# Implementation Summary: proposal-replay-simulator

Registered as a new product unit.

First code generation step adds `src/proposal/replay.py`, a deterministic
input contract that pairs `ProposalRecord` history entries with explicit
`OHLCV` candle windows. The model validates sorted candles, requires each
proposal to have a window with data at or after proposal creation, supports
loading from `ProposalHistory`, and exposes lookup by proposal id.

Second code generation step adds replay scenario comparison. Operators can now
compare alternate `min_score` approval thresholds and same-candle exit
assumptions (`stop_first` versus `take_profit_first`). Replay outcomes include
approved/filtered state, exit reason, exit price/time, gross PnL, and price-move
PnL percent; scenario results aggregate approved count, total gross PnL, and
average PnL percent.

Final code generation step adds `render_replay_report`, a Markdown report for
operator threshold tuning. The report ranks scenarios by average PnL percent,
shows approved count and total gross PnL, calls out the recommended scenario,
and includes per-proposal outcome detail.
