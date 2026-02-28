# Arcturus Signal Bridge

A thin Python sidecar that wraps the [signal-cli](https://github.com/AsamK/signal-cli) HTTP REST
server and exposes a minimal API so the Arcturus Python backend can send and receive Signal messages.

## Architecture

```
User's Signal phone
  ↕ (Signal protocol via signal-cli)
signal_bridge/app.py   ← This sidecar (polls signal-cli every 2s)
  ↕ POST /send              ↕ POST /api/nexus/signal/inbound
channels/signal.py          routers/nexus.py
          ↕
   gateway/bus.py  (Nexus MessageBus)
```

## Prerequisites

- **signal-cli** ≥ 0.13 with `--http` daemon mode
  - Download: https://github.com/AsamK/signal-cli/releases
  - Requires Java 17+
- A Signal account (personal phone number)
- Arcturus FastAPI backend running on `http://localhost:8000`

## Setup

### 1. Install signal-cli

```bash
# macOS (Homebrew)
brew install signal-cli

# Linux / manual
wget https://github.com/AsamK/signal-cli/releases/latest/download/signal-cli-*.tar.gz
tar xf signal-cli-*.tar.gz
sudo mv signal-cli-*/bin/signal-cli /usr/local/bin/
```

### 2. Register or link your number

**Option A — Register a new number** (uses the number as the bot's identity):
```bash
signal-cli -a +15551234567 register
signal-cli -a +15551234567 verify 123456   # enter SMS code
```

**Option B — Link an existing Signal account** (non-primary device):
```bash
signal-cli link -n "Arcturus Bot"
# Scan the displayed QR code with your Signal mobile app:
# Signal → Settings → Linked Devices → Link New Device
```

### 3. Start signal-cli in HTTP daemon mode

```bash
signal-cli -a +15551234567 daemon --http
# Listens on http://localhost:8080 by default
```

### 4. Configure environment variables

Copy `.env.example` and set:
```bash
SIGNAL_PHONE_NUMBER=+15551234567   # The number registered above
SIGNAL_CLI_URL=http://localhost:8080
SIGNAL_BRIDGE_URL=http://localhost:3002
SIGNAL_BRIDGE_SECRET=your-secret   # Optional; leave empty for dev mode
```

### 5. Start the bridge

```bash
cd signal_bridge
pip install fastapi uvicorn httpx
python app.py
# Bridge starts on http://localhost:3002
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SIGNAL_CLI_URL` | `http://localhost:8080` | signal-cli HTTP daemon URL |
| `SIGNAL_PHONE_NUMBER` | *(required)* | E.164 phone number registered with signal-cli |
| `SIGNAL_BRIDGE_PORT` | `3002` | HTTP port this bridge listens on |
| `FASTAPI_BASE_URL` | `http://localhost:8000` | Arcturus FastAPI server base URL |
| `SIGNAL_BRIDGE_SECRET` | *(empty)* | Shared HMAC-SHA256 secret for request auth |
| `POLL_INTERVAL_S` | `2` | Seconds between signal-cli receive polls |
| `LOG_LEVEL` | `INFO` | Python logging level |

## FastAPI Environment Variables

Set these in your `.env` (see `.env.example`):

```bash
SIGNAL_BRIDGE_URL=http://localhost:3002
SIGNAL_BRIDGE_SECRET=<same value as bridge's SIGNAL_BRIDGE_SECRET>
```

## API

### `POST /send`

Send a text message to a Signal number or group.

**Request:**
```json
{ "recipient_id": "+15551234567", "text": "Hello from Arcturus!" }
```
`recipient_id` is an E.164 phone number or a Signal group ID.

**Response (success):**
```json
{ "ok": true, "message_id": "1740650000000", "timestamp": "2026-02-28T10:00:00Z" }
```

**Response (failure):**
```json
{ "ok": false, "error": "signal-cli not reachable" }
```

### `GET /health`

Returns the current bridge and signal-cli status.

```json
{ "status": "ok", "connected": true, "phone_number": "+15551234567" }
```

## Disappearing Messages

Signal's disappearing message timer is a **client-side setting** configured per conversation
in the Signal mobile app. The Arcturus bridge does not set or modify this timer — it honours
whatever the user has configured. Messages sent by the bot will expire according to that setting.

## Known Limitations

- Polling-based inbound (2s interval) — not true push. Latency: 0–2s per inbound message.
- Text messages only — media attachments are not forwarded (text-only for now).
- One Signal account per bridge instance.
- signal-cli must be running as a separate process before starting the bridge.
