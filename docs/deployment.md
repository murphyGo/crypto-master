# Deploying Crypto Master to Fly.io

Phase 8.3 — first-deploy guide for the paper-only production runtime.

## Architecture in one paragraph

A single Fly Machine runs one container that hosts both processes:
the trading engine (`python -m src.main`) and the Streamlit dashboard
(`streamlit run src/dashboard/app.py`). They share `/data`, mounted
from a Fly volume, so the dashboard reads the proposals, trades,
audit log, activity log, and portfolio snapshots that the engine
writes. `start.sh` (the container's CMD) launches both processes;
when either dies the script exits and Fly restarts the machine.

## Prerequisites

- [`flyctl`](https://fly.io/docs/hands-on/install-flyctl/) installed
  and authenticated (`fly auth login`).
- A Fly account with billing enabled (paper-only deploys are
  cheap — see *Cost* below — but Fly requires a card on file).
- Exchange testnet API keys for at least one of Binance or Bybit.
  Get them from
  [testnet.binance.vision](https://testnet.binance.vision/) or
  [testnet.bybit.com](https://testnet.bybit.com/).
- Claude auth — pick **one** of the two paths:
  - **Recommended for personal use: Claude Code subscription**
    via `CLAUDE_CODE_OAUTH_TOKEN`. Generate the token locally
    (where Claude Code is already logged in) with
    `claude setup-token` — it prints a long-lived OAuth token
    starting with `sk-ant-oat01-...`. This routes `claude -p`
    calls through your Pro / Max subscription rather than the
    metered API.
  - **Anthropic API key** via `ANTHROPIC_API_KEY`. Per-request
    billing through console.anthropic.com. Use this if you don't
    have a Claude Code subscription, or if you want to keep the
    runtime's spend separate from your interactive Claude Code
    usage.
- A Cloudflare account if you want auth on the dashboard (recommended,
  see *Dashboard auth* below).

## First-time setup

```bash
# 1. Bootstrap the Fly app config (creates a NEW fly.toml override
#    with a unique app name; rename app in our committed fly.toml
#    after launch if desired).
fly launch --no-deploy --copy-config

# 2. Create the persistent volume for /data. 1 GiB is plenty —
#    proposals/trades/audit/activity logs are tiny JSON.
fly volumes create data --region nrt --size 1

# 3. Push secrets. Live keys are deliberately omitted; first deploy
#    is paper-only.
#
# Pick ONE of the two Claude auth paths:
#
#   (a) Claude Code subscription (recommended for personal use):
fly secrets set \
    CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...    \
    BINANCE_TESTNET_API_KEY=...                 \
    BINANCE_TESTNET_API_SECRET=...              \
    TRADING_MODE=paper                          \
    LOG_LEVEL=INFO                              \
    PAPER_INITIAL_BALANCE=10000

#   (b) Anthropic API key (per-request billing):
fly secrets set \
    ANTHROPIC_API_KEY=sk-ant-...                \
    BINANCE_TESTNET_API_KEY=...                 \
    BINANCE_TESTNET_API_SECRET=...              \
    TRADING_MODE=paper                          \
    LOG_LEVEL=INFO                              \
    PAPER_INITIAL_BALANCE=10000

# 4. (Optional but recommended) Override engine defaults via secrets
#    or env. EngineConfig defaults are: cycle_interval_seconds=300,
#    auto_approve_threshold=1.0, altcoin_top_k=3.
#    These are not yet wired through Settings — they live on
#    EngineConfig only — so changing them today means editing
#    src/main.py. Track this as a follow-up.
```

## Deploy

```bash
fly deploy
```

First deploy takes ~5 minutes (image build + Claude CLI install +
Python deps). Subsequent deploys are faster thanks to layer caching
on requirements.txt + pyproject.toml.

To watch logs:

```bash
fly logs                # streaming
fly logs --no-tail      # historical only
```

To check container state:

```bash
fly status
fly machine status <id>
```

To open a shell in the running machine:

```bash
fly ssh console
# In the shell, the activity log is at:
#   tail -f /data/runtime/activity.jsonl
```

## Dashboard auth (Cloudflare Access)

Streamlit has no built-in auth and the dashboard exposes positions,
P&L, and proposal decisions. **Do not deploy without an auth gate
in front.** The simplest and free option is Cloudflare Access:

1. **Custom domain on Fly.** Map the dashboard to a domain you own:

   ```bash
   fly certs create dashboard.example.com
   # Add the CNAME / A records Fly prints in your DNS.
   ```

2. **Move DNS to Cloudflare.** Update the domain's nameservers to
   Cloudflare. This is free.

3. **Create a Zero Trust Access Application:**

   - Go to Cloudflare Zero Trust → Access → Applications → Add an
     application → Self-hosted.
   - Application domain: `dashboard.example.com`.
   - Identity: One-time PIN to your email (free; no extra IdP needed).
   - Policy: allow `your.email@gmail.com`.

4. **Test:** visit the domain → Cloudflare prompts for the PIN →
   email arrives → Streamlit dashboard loads.

Without DNS migration: Tailscale serve is the next-cheapest option
(`tailscale serve` from inside the container) and is private to your
tailnet. Adds one apt package and a sidecar, omitted here for
simplicity.

## Region pick

The committed `fly.toml` uses `nrt` (Tokyo) because Binance + Bybit
both have low latency from there. Other reasonable choices:

| Region | Code | Notes |
|--------|------|-------|
| Tokyo  | nrt  | Default. Good for Binance / Bybit / OKX. |
| Hong Kong | hkg | Even closer to some Asian exchanges; sometimes pricier. |
| Frankfurt | fra | If you're in Europe and crypto-region latency doesn't matter (paper). |
| US East  | iad | Cheap, fine if you're US-based and not chasing latency. |

Switch by editing `primary_region` in `fly.toml` and re-running
`fly deploy`. The volume can be migrated with `fly volumes fork`.

## Cost (steady state, single machine)

| Item | Monthly |
|------|---------|
| `shared-cpu-1x` 1 GB always-on | ~$3.20 |
| 1 GB volume | ~$0.15 |
| Egress (mostly outbound to exchange APIs) | $0 (under 100 GB free) |
| Cloudflare Access (free tier) | $0 |
| **Total** | **~$3-4 USD / month** |

Cost goes up if you bump memory (2 GB ~$5.70), add a second region,
or run live alongside paper.

## Rollout / rollback

- **Update**: `fly deploy`. Fly does a rolling restart by default;
  combined with `start.sh` exiting cleanly on SIGTERM, the engine
  has a chance to flush its activity log before going down.
- **Rollback**: Fly keeps the last few image releases. List with
  `fly releases`, restore with `fly releases rollback <version>`.
- **Suspend**: `fly scale count 0` stops the trader and dashboard
  without deleting state. `fly scale count 1` resumes.

## Live trading (deferred)

The committed config is paper-only. To switch to live trading later:

1. Add live keys to secrets (`BINANCE_API_KEY`, `BINANCE_API_SECRET`
   — without the `_TESTNET_` infix).
2. Set `TRADING_MODE=live`.
3. Update `src/main.py` to instantiate `LiveTrader` instead of
   `PaperTrader` when `Settings.trading_mode == "live"`. This is a
   small follow-up sub-task; the auto-approve loop has the same
   shape either way.
4. Lower `auto_approve_threshold` cautiously and **set notification
   `min_score` higher than the auto-approve threshold** so you get
   pinged on every accepted live proposal.

## Risks to keep in mind

1. **`fly deploy` redeploys both processes simultaneously.** A bad
   trader change still kills the dashboard for the duration of the
   deploy (~30 seconds of unavailability). Acceptable for personal
   use; if it becomes painful, split into two Fly apps with state
   in Tigris (Fly's S3-equivalent).

2. **One machine = single point of failure.** Fly machines are
   reliable (~99.9%) but not redundant. For paper trading, the
   acceptable trade-off; for live trading, consider a hot standby
   in a second region.

3. **State persists across deploys** thanks to the volume — but
   destroying the volume (`fly volumes destroy data`) is
   irreversible. Test recovery by occasionally copying
   `/data/runtime/activity.jsonl` and `/data/audit/feedback.jsonl`
   off-box (e.g., into a private S3 bucket).

4. **Claude CLI auth churn.** If Anthropic changes the headless
   auth path (env var name, OAuth requirement), `claude -p` calls
   inside the container will start failing silently — check engine
   activity log for `cycle_errored` events containing Claude-related
   strings.

## Appendix: minimal `.env.example` for local mirror

To match the production environment locally, create a `.env` from
`.env.example` with the same keys. The container reads env directly
from Fly secrets; locally, `python-dotenv` reads `.env` via
`Settings`.
