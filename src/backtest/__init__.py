"""Backtesting package for Crypto Master.

Simulates analysis techniques against historical OHLCV data so users
can validate a strategy before putting real funds behind it.

Related Requirements:
- FR-025: Backtesting Execution
- NFR-006: Backtesting Result Storage
- NFR-008: Asset/PnL History (mode separation — mode="backtest")
"""

from src.backtest.analyzer import PerformanceAnalyzer, PerformanceMetrics
from src.backtest.engine import (
    BacktestAbortedError,
    BacktestConfig,
    Backtester,
    BacktestError,
    BacktestResult,
    BacktestTrade,
)
from src.backtest.harness import BacktestHarness
from src.backtest.multi_account_report import MultiAccountReport
from src.backtest.reproducibility import ReplayIdentity
from src.backtest.snapshot_replay import ReplayCoverage, SnapshotReplaySource

__all__ = [
    "Backtester",
    "BacktestConfig",
    "BacktestResult",
    "BacktestTrade",
    "BacktestError",
    "BacktestAbortedError",
    "BacktestHarness",
    "MultiAccountReport",
    "PerformanceAnalyzer",
    "PerformanceMetrics",
    "ReplayCoverage",
    "ReplayIdentity",
    "SnapshotReplaySource",
]
