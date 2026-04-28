"""Operator-facing CLI tools for crypto-master (Phase 11.4).

Modules in this package are entry points operators run manually
(``python -m src.tools.<name>``). They live under ``src/`` rather
than ``scripts/`` because they import only project code (no external
network like ``scripts/backtest_baselines.py``) and benefit from the
same packaging/typing as the runtime.
"""
