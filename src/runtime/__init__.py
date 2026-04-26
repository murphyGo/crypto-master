"""Production runtime for the trading service (Phase 8).

Wraps the existing components — `ProposalEngine`, `ProposalInteraction`,
`PaperTrader`, `NotificationDispatcher` — into a long-running headless
``TradingEngine`` that auto-decides proposals based on score and surfaces
every cycle event through an append-only activity log.

The dashboard reads the activity log to give operators visibility into
what the engine is doing without coupling the engine to Streamlit.
"""
