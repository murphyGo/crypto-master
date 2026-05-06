# Cross-Check: Runtime Safety Score Contract

## Scope

Verify that Runtime Safety Score has a stable input/output contract and status
bands before event extraction is implemented.

## Requirements Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Safety input model exists | Complete | `RuntimeSafetyInputs` defines bounded counters and drawdown input. |
| Status bands exist | Complete | `RuntimeSafetyBand` defines safe/degraded/risky/pause-recommended states. |
| Score thresholds are validated | Complete | `RuntimeSafetyPolicy` rejects non-descending threshold configuration. |
| Score output shape exists | Complete | `RuntimeSafetyScore` carries score, band, inputs, and explanatory factors. |
| Activity events aggregate into inputs | Complete | Test counts cycle errors, notification failures, LLM timeouts, stale-quote rejection, liquidation, and cold-start events. |
| Score computation applies penalties | Complete | Tests cover safe no-penalty score, risky mixed penalties, and pause-recommended liquidation penalties. |
| Engine dashboard surfaces score | Complete | `build_runtime_safety_score` feeds the Engine page Runtime Safety section. |
| Notification summaries can surface score | Complete | Slack, Telegram, and email builders include the optional compact safety summary when `Notification.safety_score` is present. |
| Runtime notifications receive score | Complete | `TradingEngine` computes the current safety score and passes it to `notify_proposal`. |
| Concentration signal feeds score | Complete | `correlation_warning` activity events increment safety score correlation warnings. |

## Implementation Evidence

- `src/runtime/safety_score.py`
- `src/runtime/__init__.py`
- `src/proposal/notification.py`
- `tests/test_runtime_safety_score.py`
- `tests/test_proposal_notification.py`

## Test Evidence

- `uv run pytest tests/test_runtime_safety_score.py -q`
- `uv run pytest tests/test_dashboard_engine.py tests/test_runtime_safety_score.py -q`
- `uv run ruff check src/runtime/safety_score.py src/runtime/__init__.py tests/test_runtime_safety_score.py`
- `uv run ruff check src/dashboard/pages/engine.py tests/test_dashboard_engine.py`
- `uv run black --check src/runtime/safety_score.py src/runtime/__init__.py tests/test_runtime_safety_score.py`
- `uv run black --check src/dashboard/pages/engine.py tests/test_dashboard_engine.py`
- `uv run pytest tests/test_proposal_notification.py tests/test_runtime_safety_score.py -q`
- `uv run ruff check src/proposal/notification.py src/runtime/safety_score.py tests/test_proposal_notification.py tests/test_runtime_safety_score.py`
- `uv run black --check src/proposal/notification.py src/runtime/safety_score.py tests/test_proposal_notification.py tests/test_runtime_safety_score.py`
- `uv run pytest tests/test_runtime_correlation_governor.py tests/test_runtime_safety_score.py tests/test_runtime_engine.py::test_notification_receives_runtime_safety_score tests/test_runtime_engine.py::test_correlation_warning_is_advisory_by_default tests/test_runtime_engine.py::test_correlation_gate_rejects_when_enabled -q`

## Gaps and Risks

- Runtime safety score remains advisory; it does not pause cycles by itself.

## Unit Mapping

- **Primary Unit**: `runtime-safety-score`
- **Related Units**: `proposal-runtime`, `dashboard-operator-ui`, `notifications-ops`
