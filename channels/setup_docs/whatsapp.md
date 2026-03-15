# WhatsApp Channel Setup for Arcturus

Connect Arcturus to WhatsApp via the Baileys bridge — a Node.js sidecar that connects to WhatsApp Web and forwards messages to the Arcturus backend.

> **No public tunnel needed.** WhatsApp uses the bridge as a polling client; Arcturus never needs to be reachable from the internet.

---

## How It Works

```
WhatsApp (phone) ↔ WhatsApp Web ↔ Baileys bridge (Node.js, port 3001)
                                        │  POST /api/nexus/whatsapp/inbound
                                        │  (HMAC-SHA256 signed)
                                        ▼
                                  Arcturus backend (port 8000)
                                        │  agent reply
                                        ▼
                                  Baileys bridge → POST /send → WhatsApp
```

The Baileys bridge (`whatsapp_bridge/`) is a small Node.js server. It maintains the WhatsApp Web session, receives new messages, and forwards them to Arcturus. Arcturus replies are sent back through the bridge.

---

## Prerequisites

- Arcturus backend running locally (port 8000)
- Node.js 18+ installed (`node --version`)
- A WhatsApp account and phone (the phone number that will act as the bot)
- Python environment set up (`uv sync --python 3.11`)

---

## Step 1: Install Bridge Dependencies

```bash
cd whatsapp_bridge
npm install
```

This installs Baileys, Express, axios, dotenv, and other dependencies listed in `package.json`.

---

## Step 2: Create the Bridge `.env` File

Create `whatsapp_bridge/.env` (this file is **not** the root `.env`):

```
# Port the bridge HTTP server listens on
BRIDGE_PORT=3001

# Base URL of the Arcturus FastAPI server
FASTAPI_BASE_URL=http://localhost:8000

# Shared secret for HMAC-SHA256 request signing — pick any random string
WHATSAPP_BRIDGE_SECRET=your-random-secret-here
```

> **Important:** The bridge reads env vars from this file via `dotenv`. If this file is missing or the variable names are wrong, the secret will be empty and signature verification will fail with 403 errors.

---

## Step 3: Set Arcturus Environment Variables

Open `.env` in the **project root** (not the bridge directory) and add:

```
WHATSAPP_BRIDGE_URL=http://localhost:3001
WHATSAPP_BRIDGE_SECRET=your-random-secret-here
```

Both `.env` files must have **exactly the same** `WHATSAPP_BRIDGE_SECRET` value.

---

## Step 4: Verify `config/channels.yaml`

```yaml
whatsapp:
  enabled: true
  bridge_url_env: WHATSAPP_BRIDGE_URL
  bridge_secret_env: WHATSAPP_BRIDGE_SECRET
  parse_mode: plain
  policies:
    group_activation: mention-only
    dm_allowlist: []
    max_retries: 3
    retry_backoff_seconds: 1.0
```

> `group_activation: mention-only` means the bot responds in groups only when `@arcturus` is included in the message. DMs always respond.

---

## Step 5: Start the Arcturus Backend

```bash
lsof -ti:8000 | xargs kill -9
uv run uvicorn api:app --port 8000
```

---

## Step 6: Start the Baileys Bridge

Open a **separate terminal** and run:

```bash
cd whatsapp_bridge
npm start
```

On first run, a QR code is displayed in the terminal. Scan it with WhatsApp on your phone:

1. Open WhatsApp on your phone
2. Go to **Settings** → **Linked Devices** → **Link a Device**
3. Scan the QR code shown in the terminal

You will see:
```
{"msg":"WhatsApp session connected"}
```

The session is saved in `whatsapp_bridge/session/` — you will not need to scan again unless you log out or delete that folder.

> **Note:** The bridge logs in JSON format (pino). `"level":30` = info, `"level":40` = warn, `"level":50` = error.

---

## Step 7: Test

Send a WhatsApp message **to the phone number** that scanned the QR code (i.e. the linked device number). The bot will reply after agent processing, typically 10–30 seconds.

You should see in the backend terminal:
```
POST /api/nexus/whatsapp/inbound HTTP/1.1" 200 OK
[WA-SEND] POST http://localhost:3001/send recipient=<phone_number>
[WA-SEND] status=200 data={'ok': True, ...}
```

For group testing: add the linked phone number to a WhatsApp group and send `@arcturus hello`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| QR code not showing | Bridge not started | Run `npm start` in `whatsapp_bridge/` |
| `statusCode: 405` / immediate disconnect loop | Outdated Baileys — WA version mismatch | Already fixed in code (`fetchLatestBaileysVersion()`); if it recurs, run `npm install @whiskeysockets/baileys@6.17.16` |
| `403 Forbidden` on inbound | Bridge `.env` not loaded — `WHATSAPP_BRIDGE_SECRET` empty | Ensure `whatsapp_bridge/.env` exists with `WHATSAPP_BRIDGE_SECRET=...` matching root `.env` |
| Session expired after restart | WhatsApp logged out the linked device | Delete `whatsapp_bridge/session/` and rescan QR |
| No reply from bot | Bridge `/send` failing silently | Check backend logs for `[WA-SEND]` lines — look for `status=403` or `status=503` |
| `503 WhatsApp session not connected` | Bridge restarted but not yet connected | Wait for `"msg":"WhatsApp session connected"` in bridge terminal, then retry |
| Bot not responding in group | `mention-only` policy | Include `@arcturus` in your group message |
| Bridge starts but crashes immediately | Node version too old | Run `node --version` — must be 18+. Update with `nvm install 18` |

---

## How the Security Works

The bridge and Arcturus authenticate each other using HMAC-SHA256 over the JSON body:

- **Inbound** (bridge → Arcturus): bridge computes `HMAC(WHATSAPP_BRIDGE_SECRET, JSON.stringify(payload))` and sends it as the `X-WA-Secret` header. Arcturus verifies it.
- **Outbound** (Arcturus → bridge): Arcturus computes `HMAC(WHATSAPP_BRIDGE_SECRET, compact_json_body)` and sends it as `X-WA-Secret`. Bridge verifies it.

If either secret is missing or mismatched, the request is rejected with `403`.
