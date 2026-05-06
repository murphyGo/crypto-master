# Implementation Summary: strategy-correlation-governor

Registered as a new product unit.

First code generation step adds `src/runtime/correlation_governor.py`, a shared
correlation input contract. `CorrelationExposure` normalizes backtest trades and
runtime `TradeHistory` records into common strategy/symbol/sub-account exposure
samples with side, timestamps, notional, and PnL. `CorrelationInputSet` builds
from backtest results or runtime trade history and exposes basic sub-account and
symbol filters for the next warning/gate steps.

Second code generation step adds advisory duplicate-exposure warnings.
`compute_duplicate_exposure_warnings` groups exposures across sub-accounts by
`symbol+side` and `strategy+symbol+side`, applies configurable thresholds, and
returns warnings with sub-account ids, exposure ids, total notional, and
operator-readable messages.
