# Arcturus WhatsApp Bridge

A thin Node.js sidecar that runs a [Baileys](https://github.com/WhiskeySockets/Baileys) WhatsApp Web session and exposes a minimal HTTP API so the Arcturus Python backend can send and receive WhatsApp messages.

## Architecture

```
User's WhatsApp phone
  ↕ (WhatsApp Web protocol via Baileys)
whatsapp_bridge/index.js   ← This sidecar
  ↕ POST /send              ↕ POST /api/nexus/whatsapp/inbound
channels/whatsapp.py        routers/nexus.py
          ↕
   gateway/bus.py  (Nexus MessageBus)
```

## Prerequisites

- Node.js **≥ 18**
- A WhatsApp account (personal or Business)
- Arcturus FastAPI backend running on `http://localhost:8000`

## Setup

```bash
cd whatsapp_bridge
npm install
```

## First Run (QR code scan)

```bash
npm start
```

On first launch, a QR code is printed in the terminal. Open WhatsApp on your phone → **Linked Devices** → **Link a Device** → scan the QR code.

The session is saved to `./session/` and automatically reused on subsequent starts — no re-scan needed.

## Subsequent Runs

```bash
npm start
```

The bridge reconnects using the saved session. If the session expires or is logged out, delete `./session/` and re-run to re-scan.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BRIDGE_PORT` | `3001` | HTTP port this server listens on |
| `FASTAPI_BASE_URL` | `http://localhost:8000` | Arcturus FastAPI server base URL |
| `WHATSAPP_BRIDGE_SECRET` | *(empty)* | Shared HMAC-SHA256 secret for request auth. Set the same value in FastAPI's env as `WHATSAPP_BRIDGE_SECRET`. Leaving empty disables signature checks (dev only). |
| `WA_SESSION_DIR` | `./session` | Directory to persist Baileys auth files |
| `LOG_LEVEL` | `info` | Pino log level (`debug`, `info`, `warn`, `error`) |

## FastAPI Environment Variables

Set these in your `.env` (see `.env.example`):

```bash
WHATSAPP_BRIDGE_URL=http://localhost:3001
WHATSAPP_BRIDGE_SECRET=<same value as bridge's WHATSAPP_BRIDGE_SECRET>
```

## API

### `POST /send`

Send a text message to a WhatsApp number.

**Request:**
```json
{ "recipient_id": "15551234567", "text": "Hello from Arcturus!" }
```
`recipient_id` can be a bare phone number (digits only) or a full JID (`15551234567@s.whatsapp.net` or `123456789@g.us` for groups).

**Response (success):**
```json
{ "ok": true, "message_id": "ABCDEF123456", "timestamp": "2026-02-23T10:00:00.000Z" }
```

**Response (failure):**
```json
{ "ok": false, "error": "WhatsApp session not connected", "state": "disconnected" }
```

### `GET /health`

Returns the current session status.

```json
{ "status": "open", "connected": true, "session_dir": "/path/to/session" }
```

## Known Limitations

- Only one WhatsApp Web session per account can be active at a time.
- Baileys uses the unofficial WhatsApp Web protocol — it may break on WhatsApp client updates.
- Media messages (images, videos) without a caption are not forwarded (text-only for now).
