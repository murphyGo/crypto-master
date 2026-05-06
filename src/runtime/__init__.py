"""Production runtime for the trading service (Phase 8).

Wraps the existing components — `ProposalEngine`, `ProposalInteraction`,
`PaperTrader`, `NotificationDispatcher` — into a long-running headless
``TradingEngine`` that auto-decides proposals based on score and surfaces
every cycle event through an append-only activity log.

The dashboard reads the activity log to give operators visibility into
what the engine is doing without coupling the engine to Streamlit.
"""

from src.runtime.correlation_governor import (
    CorrelationExposure,
    CorrelationExposureSource,
    CorrelationGateConfig,
    CorrelationGateDecision,
    CorrelationInputSet,
    CorrelationWarning,
    CorrelationWarningPolicy,
    CorrelationWarningType,
    compute_duplicate_exposure_warnings,
    evaluate_correlation_gate,
)
from src.runtime.safety_score import (
    RuntimeSafetyBand,
    RuntimeSafetyInputs,
    RuntimeSafetyPolicy,
    RuntimeSafetyScore,
    compute_runtime_safety_score,
    inputs_from_activity_events,
    inputs_from_recent_activity_events,
    recent_activity_events,
)

__all__ = [
    "CorrelationExposure",
    "CorrelationExposureSource",
    "CorrelationGateConfig",
    "CorrelationGateDecision",
    "CorrelationInputSet",
    "CorrelationWarning",
    "CorrelationWarningPolicy",
    "CorrelationWarningType",
    "compute_duplicate_exposure_warnings",
    "evaluate_correlation_gate",
    "RuntimeSafetyBand",
    "RuntimeSafetyInputs",
    "RuntimeSafetyPolicy",
    "RuntimeSafetyScore",
    "compute_runtime_safety_score",
    "inputs_from_activity_events",
    "inputs_from_recent_activity_events",
    "recent_activity_events",
]
