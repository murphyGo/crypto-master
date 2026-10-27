# Existing availability UI

Keep the current Streamlit section rendering and one watcher per page render.
Active recovery reports existing rebuild_pending with the original progress
signal; it does not invoke the terminal retry callback. Final exhaustion uses
existing stale/unavailable warning and explicit Refresh. Details/attempt counts
stay in bounded diagnostics, not trading/operator flows. No layout redesign.
