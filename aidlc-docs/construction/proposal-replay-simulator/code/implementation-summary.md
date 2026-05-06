# Implementation Summary: proposal-replay-simulator

Registered as a new product unit.

First code generation step adds `src/proposal/replay.py`, a deterministic
input contract that pairs `ProposalRecord` history entries with explicit
`OHLCV` candle windows. The model validates sorted candles, requires each
proposal to have a window with data at or after proposal creation, supports
loading from `ProposalHistory`, and exposes lookup by proposal id.
