#!/usr/bin/env bash
# Container entrypoint that runs the trader and Streamlit dashboard
# in the same Fly machine so they share the /data volume.
#
# Why one container instead of two Fly processes:
#   Fly volumes are tied to a single machine — they cannot be
#   mounted by two process groups. The dashboard reads what the
#   trader writes (proposals, trades, audit log, activity log,
#   portfolio snapshots), so they must share local disk. Running
#   both inside one container is the cheapest correct solution.
#
# Supervision strategy:
#   - Both processes are launched in the background.
#   - `wait -n` blocks until either exits.
#   - When one exits we kill the other and exit the script;
#     Fly's machine restart policy then recycles the whole VM.
#     Restart latency is one machine boot (~10-15s), which is
#     acceptable for a paper-trading deployment.
#
# Signal handling:
#   - tini (PID 1, set in the Dockerfile) forwards SIGTERM/SIGINT
#     here. The trap below propagates them to both children for a
#     clean shutdown (the engine flips its asyncio stop event;
#     Streamlit responds to SIGTERM gracefully).

set -euo pipefail

# Make sure the volume directories exist on first boot — the engine
# and dashboard create them lazily when they first write, but having
# them ready avoids confusing first-run "directory not found" logs.
mkdir -p "${DATA_DIR:-/data}/runtime" "${DATA_DIR:-/data}/logs"

echo "[start.sh] Launching trader: python -m src.main"
python -m src.main &
TRADER_PID=$!

echo "[start.sh] Launching dashboard: streamlit run src/dashboard/app.py"
streamlit run src/dashboard/app.py \
    --server.port 8080 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false &
DASHBOARD_PID=$!

cleanup() {
    echo "[start.sh] Received signal — shutting down children..."
    kill -TERM "$TRADER_PID" "$DASHBOARD_PID" 2>/dev/null || true
    wait "$TRADER_PID" "$DASHBOARD_PID" 2>/dev/null || true
    exit 0
}
trap cleanup TERM INT

# Wait for either child to exit; surface its exit code.
wait -n
EXIT_CODE=$?
echo "[start.sh] A child exited with code ${EXIT_CODE}; tearing down peer."
kill -TERM "$TRADER_PID" "$DASHBOARD_PID" 2>/dev/null || true
wait "$TRADER_PID" "$DASHBOARD_PID" 2>/dev/null || true
exit "$EXIT_CODE"
