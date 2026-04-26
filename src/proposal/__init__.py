"""Trading proposal engine.

Phase 6.1 — given an exchange, a set of analysis techniques, and
historical performance data, produces ranked ``Proposal`` objects
that the user-interaction layer (Phase 6.2) and notification layer
(Phase 6.3) consume. The engine is headless: it returns data
structures, not user-facing output.

Related Requirements:
- FR-011: Bitcoin Trading Proposal
- FR-012: Altcoin Trading Proposal
- FR-005: Analysis Technique Performance Tracking (consumed)
"""

from src.proposal.engine import (
    Proposal,
    ProposalEngine,
    ProposalEngineConfig,
    ProposalEngineError,
    ProposalScore,
)

__all__ = [
    "Proposal",
    "ProposalEngine",
    "ProposalEngineConfig",
    "ProposalEngineError",
    "ProposalScore",
]
