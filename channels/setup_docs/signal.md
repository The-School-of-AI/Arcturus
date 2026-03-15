# Signal Channel Setup for Arcturus

Connect Arcturus to Signal via signal-cli and the Arcturus signal bridge sidecar. Signal does not have an official bot API — this setup uses signal-cli to manage a dedicated Signal account.

---

## Prerequisites

- Arcturus backend running locally (port 8000)
- Java 17+ installed (`java --version`)
- A phone number to register with Signal (can be a VoIP number like Google Voice)
- Python environment set up (`uv sync --python 3.11`)

> **No tunnel needed.** The signal bridge polls signal-cli locally. Arcturus and the bridge communicate on localhost.

---

## How It Works

```
Signal (user's phone) ↔ Signal servers ↔ signal-cli (daemon)
                                                │  HTTP REST
                                                ▼
                                    signal_bridge/app.py (sidecar)
                                                │  POST /api/nexus/signal/inbound
                                                ▼
                                          Arcturus backend
                                                │  reply
                                                ▼
                                    signal_bridge → signal-cli → Signal
```

---

## Step 1: Install signal-cli

Download from [github.com/AsamK/signal-cli/releases](https://github.com/AsamK/signal-cli/releases):

```bash
# macOS example — adjust version
wget https://github.com/AsamK/signal-cli/releases/download/v0.13.0/signal-cli-0.13.0-Linux.tar.gz
tar -xf signal-cli-*.tar.gz
sudo mv signal-cli-*/bin/signal-cli /usr/local/bin/
```

Verify: `signal-cli --version`

---

## Step 2: Register a Signal Account

Use a phone number dedicated to the bot (not your personal Signal number):

```bash
# Request SMS verification code
signal-cli -a +1XXXXXXXXXX register

# Verify with code received by SMS
signal-cli -a +1XXXXXXXXXX verify <SMS-code>
```

---

## Step 3: Start signal-cli as a Daemon

```bash
signal-cli -a +1XXXXXXXXXX daemon --http --http-port 8080
```

This exposes signal-cli as an HTTP server on port 8080. Keep this terminal open.

---

## Step 4: Configure the Signal Bridge

The bridge is in `signal_bridge/`. Set environment variables (or create `signal_bridge/.env`):

```
# signal-cli daemon URL
SIGNAL_CLI_URL=http://localhost:8080

# Bot's phone number (E.164 format)
SIGNAL_ACCOUNT=+1XXXXXXXXXX

# Arcturus inbound endpoint
ARCTURUS_INBOUND_URL=http://localhost:8000/api/nexus/signal/inbound

# Shared secret for HMAC-SHA256 signing (optional but recommended)
BRIDGE_SECRET=<choose-a-random-secret>

# Poll interval in seconds
POLL_INTERVAL=2
```

---

## Step 5: Start the Signal Bridge

```bash
cd signal_bridge
uv run python app.py
```

You will see:
```
Signal bridge started. Polling signal-cli every 2s...
```

---

## Step 6: Set Arcturus Environment Variables

Open `.env` in the project root:

```
SIGNAL_BRIDGE_URL=http://localhost:8001   # bridge HTTP server port
SIGNAL_BRIDGE_SECRET=<same-secret-as-bridge>
```

---

## Step 7: Verify `config/channels.yaml`

```yaml
signal:
  enabled: true
  bridge_url_env: SIGNAL_BRIDGE_URL
  bridge_secret_env: SIGNAL_BRIDGE_SECRET
  parse_mode: plain
  policies:
    group_activation: mention-only
    dm_allowlist: []
    max_retries: 3
    retry_backoff_seconds: 1.0
```

---

## Step 8: Restart the Arcturus Backend

```bash
lsof -ti:8000 | xargs kill -9
uv run uvicorn api:app --port 8000
```

---

## Step 9: Test

Send a Signal message to the bot's phone number from your personal Signal account. The bot replies after agent processing (typically 10–30 seconds).

For group testing: create a Signal group, add the bot number, and include `@signal_account` or configure `group_activation: always-on`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `signal-cli: command not found` | Not in PATH | Move binary to `/usr/local/bin/` |
| Registration fails | Number already registered on Signal | Use a different number or unlink on existing device |
| Bridge not polling | signal-cli daemon not running | Run `signal-cli -a +E164 daemon --http` first |
| `403` from Arcturus | `BRIDGE_SECRET` mismatch | Ensure same secret in both `.env` files |
| No reply | signal-cli daemon stopped | Check daemon terminal for errors |
