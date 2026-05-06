# Implementation Summary: trade-quality-autopsy

Initial code generation adds `TradeAutopsy`, a normalized evidence model for
closed runtime and backtest trades. It captures side, mode, sub-account,
entry/exit details, fees, PnL, close reason, holding time, and outcome bucket.

Autopsies can now be enriched with candle-window metrics via
`with_candle_window`, which computes MFE, MAE, drawdown-before-exit, and records
the window size as evidence.
