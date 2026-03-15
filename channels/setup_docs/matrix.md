# Matrix Channel Setup for Arcturus

Connect Arcturus to the Matrix protocol. Arcturus polls the Matrix Client-Server API directly — no sidecar needed. Works with any Matrix homeserver (matrix.org, Element, self-hosted Synapse, etc.).

---

## Prerequisites

- Arcturus backend running locally (port 8000)
- A Matrix account for the bot (separate from your personal account)
- Python environment set up (`uv sync --python 3.11`)

> **No tunnel needed.** Arcturus polls the Matrix sync API internally every 2 seconds. No public webhook URL is required.

---

## How It Works

```
Matrix users ↔ Matrix homeserver ↔ Matrix CS API (sync)
                                          │  Arcturus polls GET /_matrix/client/v3/sync
                                          ▼
                                    Arcturus backend (gateway/matrix adapter)
                                          │  reply via PUT /_matrix/client/v3/rooms/{room}/send
                                          ▼
                                    Matrix homeserver → users
```

---

## Step 1: Create a Bot Account

Create a dedicated Matrix account for the bot (do NOT use your personal account):

### Option A: matrix.org (free)

1. Go to [app.element.io](https://app.element.io) → **Create account**
2. Select homeserver: `matrix.org`
3. Register with a username like `arcturus-bot`
4. Note the full user ID: `@arcturus-bot:matrix.org`

### Option B: Self-hosted Synapse

Register the account via the admin API or via the registration endpoint on your homeserver.

---

## Step 2: Get an Access Token

The access token authenticates Arcturus to the Matrix API.

**Using curl:**

```bash
curl -s -X POST "https://matrix.org/_matrix/client/v3/login" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "m.login.password",
    "user": "@arcturus-bot:matrix.org",
    "password": "<your-bot-password>"
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('Token:', d.get('access_token'))"
```

Copy the `access_token` value.

---

## Step 3: Set Environment Variables

Open `.env` in the project root:

```
MATRIX_HOMESERVER_URL=https://matrix.org
MATRIX_USER_ID=@arcturus-bot:matrix.org
MATRIX_ACCESS_TOKEN=<your-access-token>
```

---

## Step 4: Verify `config/channels.yaml`

```yaml
matrix:
  enabled: true
  homeserver_url_env: MATRIX_HOMESERVER_URL
  user_id_env: MATRIX_USER_ID
  access_token_env: MATRIX_ACCESS_TOKEN
  sync_interval_seconds: 2.0
  parse_mode: plain
  policies:
    group_activation: mention-only
    dm_allowlist: []
    max_retries: 3
    retry_backoff_seconds: 1.0
```

> `group_activation: mention-only` means the bot only responds in rooms when @mentioned. DMs always respond.

---

## Step 5: Restart the Arcturus Backend

```bash
lsof -ti:8000 | xargs kill -9
uv run uvicorn api:app --port 8000
```

The Matrix sync loop starts automatically. You will see polling activity in the logs.

---

## Step 6: Create a Room and Invite the Bot

> **Important:** Create a room with **encryption disabled**. The Arcturus adapter does not support E2EE (Olm/Megolm). If you create an encrypted room, all messages will show as "Unable to decrypt message."

1. Open Element → click **+** next to Rooms → **New room**
2. Enter a name (e.g. `Arcturus-Test`)
3. Click **More options** → **uncheck "Enable end-to-end encryption"**
4. Click **Create room**
5. Invite the bot: click the room name → **Invite people** → search `@arcturus-bot:matrix.org`
6. The bot accepts the invite automatically on the next sync cycle (within 2 seconds)

---

## Step 7: Test

In the room, type:

```
@arcturus-bot hello, what can you help me with?
```

The bot replies after agent processing (typically 10–30 seconds).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Unable to decrypt message" | Room has E2EE enabled | Create a new room with encryption disabled |
| `M_UNKNOWN_TOKEN` in logs | Access token expired or wrong | Re-run login curl command and update `.env` |
| Bot not joining room | Invite not sent or sync not running | Check `MATRIX_USER_ID`, restart backend |
| No response to messages | `mention-only` policy | Include `@arcturus-bot` in message, or set `group_activation: always-on` in `channels.yaml` |
| Nothing appears in backend logs | Bot not in room or wrong account credentials | Verify `MATRIX_USER_ID` and `MATRIX_ACCESS_TOKEN` match the bot account, not personal account |
| `MATRIX_HOMESERVER_URL` 404 | Wrong homeserver URL | Use base URL without trailing slash, e.g. `https://matrix.org` |
| High latency | `sync_interval_seconds` too high | Lower to `1.0` in `channels.yaml` |
