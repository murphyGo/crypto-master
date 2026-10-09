# Crypto Master — production container (Phase 8.3).
#
# One container runs both the trading engine and the Streamlit
# dashboard via start.sh. They share /data (a Fly volume) so the
# dashboard reads what the engine writes.
#
# Auth:
# - Codex uses its own ChatGPT auth cache on the persistent /data volume.
# - Claude remains installed for an explicit rollback; no API fallback.
# - Exchange testnet keys come in the same way (BINANCE_API_KEY etc).

# Keep Node and Python on the same Debian release. Pin these upstream
# inputs; review future updates through the same compatibility build gate.
FROM node:24.21.0-trixie-slim@sha256:173f125896c3b47ddf056734c7ea789d04595a6a08769a8f78e0df642781fb66 AS node-runtime
FROM python:3.13.16-slim-trixie@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c

# Copy only Node/npm so the Python image's /usr/local stays intact.
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm/ /usr/local/lib/node_modules/npm/

# System dependencies:
# - libstdc++6 / libatomic1: Node's shared libraries, including ARM support.
# - ca-certificates: HTTPS to Anthropic + exchange APIs.
# - curl: convenience for in-container debugging.
# - tini: PID 1 init that reaps zombies and forwards signals to
#   start.sh (which propagates SIGTERM to both children).
# Claude CLI 2.1.295 requires Node >=22; Node 24 LTS meets that requirement.
# Keep the deployed CLI version while changing its runtime. engine-strict
# turns future engine incompatibilities into build failures.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libstdc++6 \
        libatomic1 \
        tini \
 && ln -s node /usr/local/bin/nodejs \
 && ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && node --version \
 && npm --version \
 && npx --version \
 && npm install --global --engine-strict @anthropic-ai/claude-code@2.1.295 \
 && node -e 'const assert = require("node:assert/strict"); \
       const p = require("/usr/local/lib/node_modules/@anthropic-ai/claude-code/package.json"); \
       assert.equal(process.versions.node.split(".")[0], "24"); \
       assert.equal(p.version, "2.1.295"); \
       assert.equal(p.engines.node, ">=22.0.0"); \
       console.log(JSON.stringify({node: process.version, cli: p.version, requiredNode: p.engines.node}));' \
 && claude --version \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Qualified native CLI; the transport rejects any other version at runtime.
RUN test "$(uname -m)" = x86_64 \
 && curl --fail --location --silent --show-error --max-time 120 \
      https://github.com/openai/codex/releases/download/rust-v0.153.4/codex-x86_64-unknown-linux-musl.tar.gz \
      -o /tmp/codex.tar.gz \
 && echo 'f479424eca092484dc40d87ae28c44f4cc40234a60045d6131e493800d814a30  /tmp/codex.tar.gz' | sha256sum --check \
 && tar -xzf /tmp/codex.tar.gz -C /tmp codex-x86_64-unknown-linux-musl \
 && install -m 0755 /tmp/codex-x86_64-unknown-linux-musl /usr/local/bin/codex \
 && rm /tmp/codex.tar.gz /tmp/codex-x86_64-unknown-linux-musl

# Install Python deps first so layer cache survives source edits.
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source. Tests, docs, .venv etc are excluded via
# .dockerignore so the build context stays small.
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY strategies/ ./strategies/
COPY trading_profiles/ ./trading_profiles/
COPY docs/research/strategies/ ./docs/research/strategies/
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
