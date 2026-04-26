# Crypto Master — production container (Phase 8.3).
#
# One container runs both the trading engine and the Streamlit
# dashboard via start.sh. They share /data (a Fly volume) so the
# dashboard reads what the engine writes.
#
# Auth:
# - Claude CLI (NFR-002 mandates `claude -p`) is installed via npm.
#   Headless auth is `ANTHROPIC_API_KEY` set at runtime via Fly secrets.
# - Exchange testnet keys come in the same way (BINANCE_API_KEY etc).

FROM python:3.13-slim

# System dependencies:
# - nodejs / npm: required for `@anthropic-ai/claude-code` (the
#   CLI the project shells out to via `claude -p`). Debian Bookworm's
#   nodejs package is 18.x which satisfies Claude Code's Node 18+
#   requirement.
# - ca-certificates: HTTPS to Anthropic + exchange APIs.
# - curl: convenience for in-container debugging.
# - tini: PID 1 init that reaps zombies and forwards signals to
#   start.sh (which propagates SIGTERM to both children).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        nodejs \
        npm \
        tini \
 && npm install -g @anthropic-ai/claude-code \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so layer cache survives source edits.
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source. Tests, docs, .venv etc are excluded via
# .dockerignore so the build context stays small.
COPY src/ ./src/
COPY strategies/ ./strategies/
COPY trading_profiles/ ./trading_profiles/
COPY start.sh ./
RUN chmod +x start.sh

# Runtime config:
# - DATA_DIR points at the Fly volume mount (matches fly.toml).
# - PYTHONPATH=/app so `streamlit run src/dashboard/app.py` can resolve
#   `from src...` imports. `python -m src.main` already works because
#   `-m` puts the CWD on sys.path; streamlit puts only the script's
#   directory on sys.path, which would otherwise break the dashboard.
# - PYTHONUNBUFFERED so `fly logs` is live, not buffered.
# - PYTHONDONTWRITEBYTECODE because the volume is the only thing we
#   want to grow with state, not __pycache__ noise.
ENV DATA_DIR=/data \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Streamlit dashboard binds 8080. Trader has no port.
EXPOSE 8080

# tini handles signals + zombie reaping; start.sh runs trader +
# streamlit and exits when either one dies so Fly restarts the machine.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["./start.sh"]
