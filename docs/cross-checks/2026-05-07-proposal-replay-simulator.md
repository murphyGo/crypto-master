# Cross-Check: Proposal Replay Simulator

## Scope

Verify that Proposal Replay Simulator has a deterministic input contract,
scenario comparison, and operator-readable report output.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Replay input pairs proposal history with candles | Complete | `ProposalReplayInput.from_records` and `from_history` build cases from `ProposalRecord` plus explicit `OHLCV` windows. |
| Candle windows are deterministic | Complete | Tests reject missing, unsorted, and pre-proposal-only candle windows. |
| Threshold comparison exists | Complete | `ProposalReplayScenario.min_score` filters proposals below an alternate approval threshold. |
| Exit assumptions are explicit | Complete | Same-candle TP/SL ambiguity is resolved by `stop_first` or `take_profit_first`. |
| Operator report is emitted | Complete | `render_replay_report` produces Markdown summary, recommendation, and outcome detail tables. |
| CLI entrypoint is wired | Complete | `src.tools.proposal_replay` loads `ProposalReplayInput` JSON, builds scenario grids, and writes Markdown to stdout or a file. |

## Implementation Evidence

- `src/proposal/replay.py`
- `src/proposal/__init__.py`
- `src/tools/proposal_replay.py`
- `tests/test_proposal_replay.py`
- `tests/test_tools_proposal_replay.py`

## Test Evidence

- `uv run pytest tests/test_proposal_replay.py -q`
- `uv run pytest tests/test_tools_proposal_replay.py tests/test_proposal_replay.py -q`
- `uv run ruff check src/proposal/replay.py src/proposal/__init__.py tests/test_proposal_replay.py`
- `uv run ruff check src/tools/proposal_replay.py tests/test_tools_proposal_replay.py`
- `uv run black --check src/proposal/replay.py src/proposal/__init__.py tests/test_proposal_replay.py`
- `uv run black --check src/tools/proposal_replay.py tests/test_tools_proposal_replay.py`
- `uv run mypy src`
- `uv run pytest -q`

## Gaps and Risks

- No dashboard entrypoint is wired yet; current operator tooling is the
  file-based CLI plus reusable Markdown renderer.

## Unit Mapping

- **Primary Unit**: `proposal-replay-simulator`
- **Related Units**: `proposal-runtime`, `backtesting-validation`, `dashboard-operator-ui`
