# Slack Channel Setup for Arcturus

Connect Arcturus to Slack so users can message the agent in any channel or DM.

---

## Prerequisites

- Arcturus backend running locally (port 8000)
- A Slack workspace where you have permission to install apps
- Python environment set up (`uv sync --python 3.11`)
- A public tunnel running (see [Tunnel Options](../channels_setup_readme.md#tunnel-options))

---

## Step 1: Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Enter an app name (e.g. `Arcturus`) and select your workspace → **Create App**

---

## Step 2: Configure Bot Permissions

1. In the left sidebar, click **OAuth & Permissions**
2. Scroll to **Scopes → Bot Token Scopes** and add:
   - `chat:write` — send messages
   - `channels:history` — read channel messages
   - `groups:history` — read private channel messages
   - `im:history` — read DM messages
   - `mpim:history` — read group DM messages
3. Scroll up and click **Install to Workspace** → **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

---

## Step 3: Get the Signing Secret

1. In the left sidebar, click **Basic Information**
2. Scroll to **App Credentials**
3. Copy the **Signing Secret**

---

## Step 4: Set Environment Variables

Open `.env` in the project root and add:

```
SLACK_BOT_TOKEN=xoxb-<your-bot-token>
SLACK_SIGNING_SECRET=<your-signing-secret>
```

---

## Step 5: Start a Public Tunnel

Slack requires a publicly accessible HTTPS URL. Start one of:

```bash
# localtunnel (no account)
npx localtunnel --port 8000

# OR cloudflared (no account)
cloudflared tunnel --url http://localhost:8000
```

Copy the HTTPS URL shown (e.g. `https://abc123.loca.lt`).

---

## Step 6: Enable Events API

1. In your Slack app, click **Event Subscriptions** in the sidebar
2. Toggle **Enable Events** to On
3. In **Request URL**, enter: `https://<your-tunnel-url>/api/nexus/slack/events`
4. Wait for Slack to verify the URL (it sends a `url_verification` challenge — the backend handles this automatically)
5. Under **Subscribe to bot events**, add:
   - `message.channels`
   - `message.groups`
   - `message.im`
   - `message.mpim`
6. Click **Save Changes**

---

## Step 7: Reinstall the App

After adding event subscriptions, Slack requires a reinstall:

1. Click **OAuth & Permissions** → **Reinstall to Workspace**
2. Click **Allow**

---

## Step 8: Add the Bot to a Channel

In your Slack workspace:
- Type `/invite @Arcturus` in any channel to add the bot
- Or open a DM: click **+** next to **Direct Messages** → search for the bot name

---

## Step 9: Test

Send a message in the channel or DM:

```
hello, what can you help me with?
```

The bot will reply after the agent processes the message (typically 10–30 seconds). Slack will show the response in the same channel/DM.

> **Note:** The bot always returns HTTP 200 immediately (fire-and-forget), then posts the reply asynchronously. This prevents Slack from retrying the request.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Request URL not verified | Backend not running or tunnel down | Start backend, restart tunnel |
| No reply from bot | `SLACK_BOT_TOKEN` wrong | Check `.env`, restart backend |
| Bot sends multiple replies | Old Slack retry arriving | Tunnel was slow; fire-and-forget fix handles this |
| `403 Invalid Slack signature` | `SLACK_SIGNING_SECRET` wrong | Check `.env` |
| Bot not in channel | Bot not invited | Run `/invite @<botname>` in the channel |
