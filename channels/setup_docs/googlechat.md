# Google Chat Channel Setup for Arcturus

Connect Arcturus to Google Chat via a Chat app (bot). Supports simple webhook mode and full service-account mode.

---

## Prerequisites

- Arcturus backend running locally (port 8000)
- A Google Workspace account (free Google accounts cannot create Chat apps)
- Python environment set up (`uv sync --python 3.11`)
- A public tunnel running (see [Tunnel Options](../channels_setup_readme.md#tunnel-options))

---

## Two Modes

| Mode | What you need | Limitations |
|------|--------------|-------------|
| **Simple (webhook)** | Just a webhook URL | Can only send to specific spaces; no DMs |
| **Full (service account)** | GCP project, service account JSON | Can message any space; full API access |

Start with **Simple** if you just want to test.

---

## Simple Mode: Incoming Webhook

### Step 1: Create a Webhook in Google Chat

1. Open [Google Chat](https://chat.google.com)
2. Open any Space (or create one)
3. Click the Space name at the top → **Apps & Integrations** → **Add webhooks**
4. Enter a name (e.g. `Arcturus`) and optional avatar URL
5. Click **Save** → copy the webhook URL

### Step 2: Set Environment Variable

```
GOOGLE_CHAT_WEBHOOK_URL=<your-webhook-url>
```

### Step 3: Configure the Inbound Endpoint

For the bot to *receive* messages in simple mode, you still need to create a Chat app with an HTTP endpoint (see Full Mode below for app creation). Simple webhook mode is outbound-only.

---

## Full Mode: Chat App with HTTP Endpoint

### Step 1: Create a GCP Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. `arcturus-chat`)
3. Enable the **Google Chat API**: APIs & Services → Library → search "Google Chat API" → Enable

### Step 2: Configure the Chat App

1. Go to APIs & Services → **Google Chat API** → **Configuration**
2. Set **App name**: `Arcturus`
3. Set **Avatar URL**: any image URL
4. Under **Functionality**, enable **Receive 1:1 messages** and **Join spaces and group conversations**
5. Under **Connection settings**, select **HTTP endpoint URL**
6. Enter: `https://<your-tunnel-url>/api/nexus/googlechat/events`
7. Under **Verification token**, copy the token shown (or set your own)
8. Click **Save**

### Step 3: Create a Service Account (for outbound replies)

1. Go to IAM & Admin → **Service Accounts** → **Create Service Account**
2. Name it `arcturus-chat-bot`
3. Click **Create and Continue** → skip role assignment → **Done**
4. Click the service account → **Keys** → **Add Key** → **JSON** → download the file
5. In Google Chat API Configuration, add this service account under **Service account**

### Step 4: Set Environment Variables

```
GOOGLE_CHAT_VERIFICATION_TOKEN=<token-from-step-2>
GOOGLE_CHAT_SERVICE_ACCOUNT_TOKEN=<contents-or-path-of-service-account-json>
```

---

## Verify `config/channels.yaml`

```yaml
google_chat:
  enabled: true
  webhook_url_env: GOOGLE_CHAT_WEBHOOK_URL
  service_account_token_env: GOOGLE_CHAT_SERVICE_ACCOUNT_TOKEN
  verification_token_env: GOOGLE_CHAT_VERIFICATION_TOKEN
  parse_mode: googlechat
  policies:
    group_activation: mention-only
```

---

## Restart and Test

```bash
lsof -ti:8000 | xargs kill -9
uv run uvicorn api:app --port 8000
```

In Google Chat, @mention the bot in a Space: `@Arcturus hello`

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bot not receiving messages | App endpoint URL wrong or tunnel down | Check URL in GCP Console, restart tunnel |
| `403` from backend | Verification token mismatch | Check `GOOGLE_CHAT_VERIFICATION_TOKEN` |
| Bot in space but not responding | `mention-only` policy | Include `@Arcturus` in message |
| Outbound reply fails | Service account not configured | Set `GOOGLE_CHAT_SERVICE_ACCOUNT_TOKEN` |
