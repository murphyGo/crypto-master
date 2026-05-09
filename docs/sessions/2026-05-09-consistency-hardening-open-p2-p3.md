# Session: consistency-hardening CH-11..CH-18 and CH-20..CH-25

## Unit

- `consistency-hardening`
- Primary owner units: `ai-feedback-loop`, `proposal-runtime`,
  `persistence-data-integrity`, `backtesting-validation`,
  `exchange-integration`, `dashboard-operator-ui`, `trading-core`

## Summary

Closed the requested open P2/P3 backlog slices from
`aidlc-docs/construction/consistency-hardening/functional-design/spec.md`.

- CH-11: markdown generations always require the prompt runtime Output
  Contract, even when frontmatter claims `technique_type: code`.
- CH-12: `ProposalHistory.load` now accepts `sub_account_id` and rejects
  ambiguous id-only lookups.
- CH-13: JSONL rotator appends are instance-synchronized and skipped malformed
  lines are counted.
- CH-14: activity and audit records now carry `schema_version=1` while legacy
  records without the field still load.
- CH-15: baseline result serialization reuses the backtest serializer and
  baseline/report writes are atomic.
- CH-16: regime validation skips when fewer than two regimes are evaluable.
- CH-17: Bybit CCXT client typing now matches the Binance protocol surface.
- CH-18: command-center drillthrough rows carry active `mode` and `scope`.
- CH-20: duplicated dashboard query-param helpers moved to
  `src/dashboard/query_params.py`.
- CH-21: correlation strategy lookup is cached per cycle and invalidated after
  attaching newly opened trades.
- CH-22: shared `ema` and `atr` indicators replace duplicated strategy helpers.
- CH-23: Claude CLI subprocesses receive an allowlisted environment only.
- CH-24: equity curves no longer mark unrealized PnL on the entry bar.
- CH-25: listed anchors were verified as active contracts after CH-06/CH-28
  rather than removable dead code.

## Tests

- `uv run pytest tests/test_ai_improver.py tests/test_proposal_interaction.py tests/test_jsonl_rotator.py -q`
- `uv run pytest tests/test_runtime_activity_log.py tests/test_feedback_audit.py tests/test_ai_improver.py tests/test_proposal_interaction.py tests/test_jsonl_rotator.py -q`
- `uv run pytest tests/test_backtest_analyzer.py tests/test_scripts_backtest_baselines.py tests/test_backtest_validator.py -q`
- `uv run pytest tests/test_exchange_binance.py tests/test_exchange_bybit.py tests/test_dashboard_app.py -q`
- `uv run pytest tests/test_dashboard_autopsy.py tests/test_dashboard_feedback.py tests/test_dashboard_ops.py tests/test_dashboard_trading.py tests/test_dashboard_engine.py tests/test_runtime_engine.py -q`
- `uv run pytest tests/test_strategy_indicators.py tests/test_baseline_strategies.py tests/test_ai_claude.py -q`
- `uv run pytest tests/test_backtest_engine.py tests/test_live_trading.py tests/test_paper_trading.py -q`

## Decisions

- CH-25 was not treated as a deletion pass because the anchored live fill,
  paper testnet, and auto-confirm functions are now intentional runtime
  contracts covered by tests.
- The Claude CLI allowlist keeps only process basics such as `PATH` and `HOME`;
  ambient API-key variables are not inherited.

## Risks

- Full `uv run pytest` was not run during this session; targeted coverage was
  used because the slice touched many independent modules.
