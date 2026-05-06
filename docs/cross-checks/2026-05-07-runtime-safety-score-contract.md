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

## Implementation Evidence

- `src/runtime/safety_score.py`
- `src/runtime/__init__.py`
- `tests/test_runtime_safety_score.py`

## Test Evidence

- `uv run pytest tests/test_runtime_safety_score.py -q`
- `uv run ruff check src/runtime/safety_score.py src/runtime/__init__.py tests/test_runtime_safety_score.py`
- `uv run black --check src/runtime/safety_score.py src/runtime/__init__.py tests/test_runtime_safety_score.py`

## Gaps and Risks

- Dashboard and notification surfacing are not implemented yet.

## Unit Mapping

- **Primary Unit**: `runtime-safety-score`
- **Related Units**: `proposal-runtime`, `dashboard-operator-ui`, `notifications-ops`
