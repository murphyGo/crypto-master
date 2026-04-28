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

# 4. (Optional) Override engine tunables via secrets. As of Phase 13.2
#    every EngineConfig field is env-driven through Settings; defaults
#    match EngineConfig's pre-10.2 hardcoded values, so leaving them
#    unset preserves existing behaviour.
fly secrets set \
    ENGINE_CYCLE_INTERVAL=300                              \
    ENGINE_AUTO_APPROVE_THRESHOLD=1.0                      \
    ENGINE_SYMBOLS=ETH/USDT,SOL/USDT,BNB/USDT,ADA/USDT,AVAX/USDT \
    ENGINE_BALANCE=10000                                   \
    ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL=1                 \
    ENGINE_MONITOR_INTERVAL=60                             \
    ENGINE_BITCOIN_SYMBOL=BTC/USDT                         \
    ENGINE_ALTCOIN_TOP_K=3                                 \
    ENGINE_ACTOR=auto-engine
#
#    - ENGINE_CYCLE_INTERVAL (int seconds, ge=10): time between cycles.
#    - ENGINE_AUTO_APPROVE_THRESHOLD (float, ge=0.0): composite-score
#      cutoff above which proposals are auto-accepted (and notified).
#    - ENGINE_SYMBOLS (comma-separated list): altcoin symbols scanned
#      each cycle. BTC/USDT is fixed separately as the bitcoin scan.
#    - ENGINE_BALANCE (Decimal): notional balance used for proposal
#      sizing. Independent of PAPER_INITIAL_BALANCE (which the
#      PaperTrader uses for its virtual wallet).
#    - ENGINE_MAX_OPEN_POSITIONS_PER_SYMBOL (int, ge=1): HARD cap on
#      open positions per symbol applied at the engine execution
#      gate (Phase 12.1). Prevents accumulation of multiple positions
#      on the same pair across cycles — Phase 10.6's per-cycle dedup
#      doesn't catch the cross-cycle case. Default 1 is the
#      recommended live-trading value; raise only for intentional
#      pyramiding. Cap-rejected proposals are still recorded as
#      PROPOSAL_REJECTED in the activity log with a
#      "symbol <pair> cap <N> reached" reason.
#    - ENGINE_MONITOR_INTERVAL (int seconds, ge=10): SL/TP monitor
#      poll interval inside one cycle. Default 60.
#    - ENGINE_BITCOIN_SYMBOL (str): symbol for the per-cycle Bitcoin
#      scan. Default BTC/USDT.
#    - ENGINE_ALTCOIN_TOP_K (int, ge=1): cap on altcoin proposals
#      retained per cycle (composite-score ranked, then truncated).
#      Default 3.
#    - ENGINE_ACTOR (str): actor name stamped onto auto-decided
#      proposals + activity log events. Default "auto-engine".
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

## Live trading

Phase 10.1 wired live mode end-to-end. Both modes share the same
`Trader` protocol so the engine is mode-agnostic — flip the
`TRADING_MODE` secret and provide live API keys to switch.

**Live-mode checklist** — read this before you flip the switch.
Live trading puts real money on the line; the cost of a misconfigured
deploy is real losses, not test-data garbage.

1. **Live keys**. Set `BINANCE_API_KEY` / `BINANCE_API_SECRET` (or
   `BYBIT_API_KEY` / `BYBIT_API_SECRET`) — note: **without the
   `_TESTNET_` infix**. Verify on the exchange dashboard that the
   keys have only the permissions you need (futures trading; nothing
   like withdrawal). Rotate after deploy if the keys ever transit a
   non-encrypted channel:

   ```bash
   fly secrets set BINANCE_API_KEY=... BINANCE_API_SECRET=... TRADING_MODE=live
   ```

2. **`auto_approve_threshold`**. The same threshold gates both paper
   and live execution; in live, every proposal that scores ≥ this
   number is opened with **no second prompt**. Start conservative
   (e.g. 1.5–2.0 vs the paper default of 1.0) and ratchet down only
   after observing live proposal scores.

3. **`paper_initial_balance` is meaningless in live mode.** Sizing
   in live comes from real exchange balances and the configured
   `risk_percent` / `leverage` per proposal. Verify that
   `Settings.max_leverage` and `default_stop_loss_pct` are set
   appropriately for your account and risk tolerance.

4. **Notifications**. Set `NotificationDispatcher`'s `min_score`
   *higher than* the auto-approve threshold so every accepted live
   proposal pages you. Console + File backends are always on; three
   push backends are opt-in (Phase 11.3, Phase 12.4, Phase 13.4):
   Slack via `SLACK_WEBHOOK_URL`, Telegram via the pair
   `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`, and Email via the SMTP
   sextet (`EMAIL_SMTP_HOST` / `EMAIL_SMTP_PORT` / `EMAIL_SMTP_USER`
   / `EMAIL_SMTP_PASSWORD` / `EMAIL_FROM` / `EMAIL_TO`). The
   dashboard's Engine page also surfaces every accepted proposal in
   real time.

   **Slack setup (optional).** Create an incoming webhook at
   <https://api.slack.com/messaging/webhooks>: pick the workspace +
   channel, hit **Add New Webhook to Workspace**, copy the URL it
   prints (`https://hooks.slack.com/services/T.../B.../...`). Push
   it into Fly secrets:

   ```bash
   fly secrets set SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
   ```

   Treat the URL like an API key — anyone with it can post in your
   channel. Rotate by deleting the webhook in Slack and creating a
   new one. The runtime never logs the URL; HTTP failures (timeout,
   500) are logged and swallowed by the dispatcher's per-channel
   isolation so a flaky Slack endpoint cannot stall the cycle. Unset
   the secret to disable.

   **Telegram setup (optional).** Create a bot through
   [@BotFather](https://t.me/BotFather): `/newbot` → choose a name
   and username → copy the token it prints
   (`123456789:AAH...XYZ`). Then obtain the destination chat id:
   send any message to the bot from the chat you want alerts in
   (DM, group, or channel — for groups/channels add the bot first),
   then read `message.chat.id` from
   `https://api.telegram.org/bot<TOKEN>/getUpdates`. Push both into
   Fly secrets:

   ```bash
   fly secrets set \
       TELEGRAM_BOT_TOKEN=123456789:AAH...XYZ \
       TELEGRAM_CHAT_ID=-1001234567890
   ```

   Both the token and the chat id are sensitive — the token
   authenticates the bot (anyone who has it can drive it) and the
   chat id reveals the alert destination. The runtime never logs
   either value, and `__repr__` on the notifier masks both. Both
   secrets must be set for the backend to register; with only one
   set the dispatcher silently skips Telegram. HTTP failures
   (timeout, 500) are logged and swallowed by the dispatcher's
   per-channel isolation, same as Slack. Unset either secret to
   disable.

   **Email setup (optional).** Pick an SMTP provider you already use
   (Gmail with an App Password, Mailgun, SendGrid, your company's
   relay — anything that speaks STARTTLS on port 587). Then push the
   six secrets:

   ```bash
   fly secrets set \
       EMAIL_SMTP_HOST=smtp.gmail.com \
       EMAIL_SMTP_PORT=587 \
       EMAIL_SMTP_USER=you@gmail.com \
       EMAIL_SMTP_PASSWORD=your_app_password_here \
       'EMAIL_FROM=Crypto Master <you@gmail.com>' \
       EMAIL_TO=alerts@example.com
   ```

   The password is the only secret here, but treat all six as
   sensitive — knowing the relay + sender lets an attacker spoof
   alerts. The runtime never logs the password and `__repr__` on the
   notifier masks it. ALL six fields must be set for the backend to
   register; with any field missing the dispatcher silently skips
   email. STARTTLS is the default (port 587); SMTP-over-SSL providers
   should use the documented SSL port. SMTP failures (connection
   refused, auth rejected, 5xx) are logged and swallowed by the
   dispatcher's per-channel isolation, same as Slack and Telegram.
   Unset any field to disable.

5. **Start small**. Send a small balance to the exchange (e.g.
   $100–$500) and watch the first day of live trades on the
   dashboard before scaling up. The runtime is paper-tested
   thoroughly but the real exchange is the only place to validate
   slippage and fee assumptions on your symbols.

6. **Confirmation policy**. `LiveTrader` calls a confirmation
   callback before submitting orders. In the production deploy,
   `src/main.py` wires this to an *auto-confirm* function because
   the engine's threshold gate has already authorized the
   proposal — there is no operator at the keyboard to answer. If
   you launch `python -m src.main` interactively (TTY attached),
   swap the callback to `default_confirmation` for stdin prompts
   per NFR-012.

7. **Per-trade exits skip the callback.** When SL/TP fire, the
   engine calls `LiveTrader.close_position(trade_id, exit_price,
   reason="stop_loss"|"take_profit")` and `LiveTrader` deliberately
   does *not* call the callback for those reasons — the user
   pre-authorized those bounds at open time. Manual closes
   (`reason="manual"`) still go through the callback.

8. **Monitoring**. After the first live deploy, watch:
   - `data/runtime/activity.jsonl` (cycle / proposal / position
     events; every event the dashboard timeline shows)
   - `data/trades/live/` (every fill)
   - The engine page's cycle-time chart for sudden spikes
     (rate-limit thrash, etc.)
   - The Trading page's equity curve for unexpected drawdowns

9. **Rollback to paper mode** is a `fly secrets set TRADING_MODE=paper`
   away — but **does not auto-close any open live positions**.
   Manually close them on the exchange first if needed.

## Operator tools

### Proposal-history retention

Long-running deploys accumulate one JSON file per generated proposal
under `data/proposals/`. `Settings.log_retention_months` (default
`12`) controls how long a record stays at the top level before it is
moved to `data/proposals/archive/<YYYY-MM>/`.

**Always-on path** (Phase 11.4): `src/main.py::run` invokes
`ProposalHistory.purge_old(retention_months=...)` once per process
boot, before the engine starts cycling. No operator action required.
The runtime logs a single INFO line when records were archived; the
"nothing to purge" case is silent so daily restarts don't generate
noise.

**Manual lever**: the same purge is exposed as a CLI for ad-hoc
windows that differ from the configured retention (e.g. tighter
cleanup before a disk-pressure event):

```bash
# Use the configured retention window:
python -m src.tools.purge_proposals

# One-off override:
python -m src.tools.purge_proposals --retention-months 6
```

The command is idempotent — re-running with the same retention is a
no-op because archived files live under a subdirectory the top-level
glob skips. Output is a single summary line in either direction
("Purged N proposal record(s) older than X months." or "No proposal
records older than X months; nothing to purge.").

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
