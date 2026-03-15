# Arcturus Nexus — Channel Setup Guide

All 10 messaging channels supported by the Arcturus Nexus gateway. Each channel has a dedicated step-by-step setup guide linked below.

---

## Prerequisites (All Channels)

Before setting up any channel:

1. **Python environment** — `uv sync --python 3.11`
2. **Backend running** — `uv run uvicorn api:app --port 8000` (or via Electron)
3. **`.env` file** — copy `.env.example` and fill in credentials for the channel you are enabling
4. **Public tunnel** (required for webhook-based channels) — see [Tunnel Options](#tunnel-options) below

---

## Channel Status

| Channel | Live-Tested | Inbound Endpoint | Setup Guide |
|---------|-------------|-----------------|-------------|
| WebChat | ✅ Live | Built-in (Electron frontend) | [setup_docs/webchat.md](setup_docs/webchat.md) |
| Telegram | ✅ Live | Polling (no tunnel needed) | [setup_docs/telegram.md](setup_docs/telegram.md) |
| Slack | ✅ Live | `POST /api/nexus/slack/events` | [setup_docs/slack.md](setup_docs/slack.md) |
| Discord | ✅ Live | `POST /api/nexus/discord/events` | [setup_docs/discord.md](setup_docs/discord.md) |
| WhatsApp | ✅ Live (2026-03-13) | `POST /api/nexus/whatsapp/inbound` | [setup_docs/whatsapp.md](setup_docs/whatsapp.md) |
| Matrix | ✅ Live (2026-03-13) | Polling (no tunnel needed) | [setup_docs/matrix.md](setup_docs/matrix.md) |
| iMessage | ⚠️ Partial (2026-03-14) | `POST /api/nexus/imessage/inbound` | [setup_docs/imessage.md](setup_docs/imessage.md) |
| Google Chat | 🚫 Blocked | `POST /api/nexus/googlechat/events` | [setup_docs/googlechat.md](setup_docs/googlechat.md) |
| Microsoft Teams | 🚫 Blocked | `POST /api/nexus/teams/events` | [setup_docs/teams.md](setup_docs/teams.md) |
| Signal | 🚫 Blocked | `POST /api/nexus/signal/inbound` | [setup_docs/signal.md](setup_docs/signal.md) |

**Legend:** ✅ Live-tested end-to-end | ⚠️ Partial (backend works, external dependency blocks full flow) | 🚫 Blocked (external platform access required) | 🔧 Code-complete, not yet live-tested

**Blocked channel notes:**
- **iMessage**: BlueBubbles bridge + Arcturus inbound handler work (curl-verified); real-time webhooks require BlueBubbles Private API, which requires disabling macOS SIP — not done for security.
- **Google Chat**: Requires Google Workspace account; personal Gmail accounts cannot create bots.
- **Microsoft Teams**: Requires Azure Bot registration; blocked by Azure tenant access issue (personal account in Microsoft-managed tenant).
- **Signal**: Requires Java 17+, signal-cli, and a dedicated phone number.

---

## General Setup Pattern

Every channel follows the same pattern:

```
1. Create bot / register app on the platform
2. Copy credentials into .env
3. Restart the Arcturus backend
4. (Webhook channels only) Start a public tunnel and register the endpoint URL
5. Send a test message
```

The channel configuration lives in `config/channels.yaml`. Each entry maps to env vars and policies (group activation, retry settings).

---

## Architecture: How Messages Flow

```
Platform (Slack/Discord/Telegram/...)
    │  POST webhook  OR  polling
    ▼
FastAPI router  (routers/nexus.py)
    │  MessageEnvelope
    ▼
MessageBus  (gateway/bus.py)
    │  route()
    ▼
MessageRouter  (gateway/router.py)
    │  RunsAgentAdapter → AgentLoop4
    ▼
Agent reply → MessageFormatter → Channel adapter → Platform
```

All channels share the same agent backend. Replies are formatted per-channel (MarkdownV2 for Telegram, mrkdwn for Slack, plain for Signal, etc.) by `gateway/formatter.py`.

---

## Tunnel Options

Webhook-based channels (Slack, Discord, WhatsApp, Google Chat, iMessage, Teams, Signal) require a publicly accessible HTTPS URL. Three options:

### Option A: ngrok (requires free account)
```bash
ngrok config add-authtoken <your-authtoken>
ngrok http 8000
# Copy the https://....ngrok-free.app URL
```

### Option B: localtunnel (no account needed)
```bash
npx localtunnel --port 8000
# Copy the https://....loca.lt URL
```

### Option C: cloudflared (no account needed)
```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:8000
# Copy the https://....trycloudflare.com URL
```

> Keep the tunnel terminal open. The URL changes each restart — you will need to update the webhook URL in the platform dashboard each time.

---

## Environment Variables Reference

All credentials are stored in `.env`. Never commit credentials to git.

| Channel | Required Env Vars |
|---------|-------------------|
| Telegram | `TELEGRAM_TOKEN` |
| Slack | `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` |
| Discord | `DISCORD_BOT_TOKEN`, `DISCORD_PUBLIC_KEY` |
| WhatsApp | `WHATSAPP_BRIDGE_URL`, `WHATSAPP_BRIDGE_SECRET` |
| Google Chat | `GOOGLE_CHAT_WEBHOOK_URL` (simple) or `GOOGLE_CHAT_SERVICE_ACCOUNT_TOKEN` (full) |
| iMessage | `BLUEBUBBLES_URL`, `BLUEBUBBLES_PASSWORD`, `BLUEBUBBLES_WEBHOOK_SECRET` |
| Teams | `TEAMS_APP_ID`, `TEAMS_APP_PASSWORD`, `TEAMS_SERVICE_URL` |
| Signal | `SIGNAL_BRIDGE_URL`, `SIGNAL_BRIDGE_SECRET` |
| Matrix | `MATRIX_HOMESERVER_URL`, `MATRIX_USER_ID`, `MATRIX_ACCESS_TOKEN` |

---

## Adding a New Channel

If you are adding a channel beyond the current 10:

1. Create `channels/<channel_name>.py` implementing `BaseChannelAdapter`
2. Add the channel entry to `config/channels.yaml`
3. Register the adapter in `shared/state.py` `initialize_message_bus()`
4. Add inbound route to `routers/nexus.py`
5. Add formatter in `gateway/formatter.py`
6. Write tests in `tests/` following the existing pattern
7. Add a setup guide in `channels/setup_docs/<channel_name>.md`
8. Add the channel to the table above
