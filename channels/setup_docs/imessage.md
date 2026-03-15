# iMessage Channel Setup for Arcturus

Connect Arcturus to iMessage via the BlueBubbles bridge — an open-source server that exposes iMessage as a REST API.

---

## Prerequisites

- A **Mac** running macOS (iMessage only works on Apple hardware)
- Arcturus backend running on the same Mac (port 8000)
- BlueBubbles server installed on the Mac
- Python environment set up (`uv sync --python 3.11`)
- Messages.app signed into your Apple ID on the Mac

> **No tunnel needed for local testing.** BlueBubbles and Arcturus can talk on localhost.

---

## How It Works

```
iMessage ↔ Mac Messages.app ↔ BlueBubbles server (local REST API)
                                        │  POST /api/nexus/imessage/inbound
                                        ▼
                                  Arcturus backend
                                        │  reply text
                                        ▼
                                  BlueBubbles server → iMessage → recipient
```

---

## Known Limitation: Private API Required for Real-Time Webhooks

BlueBubbles webhooks for new incoming messages **only fire reliably when the Private API helper is enabled**. Without it, BlueBubbles polls the iMessage database but does not trigger webhooks on new messages.

Enabling Private API requires **disabling SIP (System Integrity Protection)** — a macOS security feature. This is a significant step and optional for a demo/capstone context.

**Without Private API:** The Arcturus inbound endpoint (`/api/nexus/imessage/inbound`) works correctly and can be verified via `curl` simulation. Outbound replies via BlueBubbles REST API work without Private API.

**With Private API:** Full real-time end-to-end flow works. Requires SIP off (recoverable).

---

## Step 1: Install BlueBubbles Server

1. Download BlueBubbles from [bluebubbles.app](https://bluebubbles.app)
2. macOS will warn "cannot be verified" — go to **System Settings → Privacy & Security** → click **Open Anyway**
3. Install and open the app
4. Set a **server password** — copy it (you will need it for `.env`)
5. Note the server URL: by default `http://localhost:1234`

### Required macOS Permissions

BlueBubbles needs **both** of these to function:

- **System Settings → Privacy & Security → Full Disk Access** → add BlueBubbles and toggle ON
- **System Settings → Privacy & Security → Accessibility** → add BlueBubbles and toggle ON

After granting permissions, **fully quit and reopen BlueBubbles**.

---

## Step 2: Configure a Webhook in BlueBubbles

1. Open BlueBubbles → **Settings** → **Webhooks**
2. Click **Add Webhook**
3. Set URL: `http://localhost:8000/api/nexus/imessage/inbound`
4. Select event type: **New Message**
5. Leave webhook secret blank (or set one and add to `.env`)
6. Click **Save**

---

## Step 3: Set Environment Variables

Open `.env` in the project root:

```
BLUEBUBBLES_URL=http://localhost:1234
BLUEBUBBLES_PASSWORD=<your-bluebubbles-server-password>
BLUEBUBBLES_WEBHOOK_SECRET=
```

> **Password note:** The password must be copied exactly from BlueBubbles Settings. If it contains special characters like `@`, do not URL-encode it in `.env` — `httpx` handles encoding automatically.

---

## Step 4: Verify `config/channels.yaml`

```yaml
imessage:
  enabled: true
  bluebubbles_url_env: BLUEBUBBLES_URL
  password_env: BLUEBUBBLES_PASSWORD
  webhook_secret_env: BLUEBUBBLES_WEBHOOK_SECRET
  parse_mode: plain
  policies:
    group_activation: always-on
    dm_allowlist: []
    max_retries: 3
    retry_backoff_seconds: 1.0
```

---

## Step 5: Restart the Arcturus Backend

```bash
lsof -ti:8000 | xargs kill -9
uv run uvicorn api:app --port 8000
```

---

## Step 6: Verify BlueBubbles Connection

```bash
curl "http://localhost:1234/api/v1/ping?password=YOUR_PASSWORD"
# Expected: {"status":200,"message":"Ping received!","data":"pong"}
```

---

## Step 7: Test

> **Important:** Send from a **different Apple ID** than the one signed into the Mac. Messages sent from the same Apple ID appear as `isFromMe: true` and are skipped to prevent reply loops.

Send an iMessage to the Apple ID shown in BlueBubbles dashboard (e.g. `yourname@icloud.com`) from another device or Apple ID. The bot will reply after agent processing (typically 10–30 seconds).

To verify the inbound handler works independently of BlueBubbles webhooks:

```bash
curl -X POST http://localhost:8000/api/nexus/imessage/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "type": "new-message",
    "data": {
      "guid": "test-001",
      "text": "Hello from iMessage",
      "chats": [{"guid": "iMessage;+;+15551234567"}],
      "handle": {"address": "+15551234567", "firstName": "Test"},
      "isFromMe": false,
      "dateCreated": 1700000000000,
      "isGroupMessage": false
    }
  }'
# Expected: {"ok":true}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Webhook never fires on new messages | Private API not enabled | Enable Private API in BlueBubbles (requires SIP off) |
| `401` from BlueBubbles API | Wrong password | Copy exact password from BlueBubbles Settings |
| `403` from Arcturus | Webhook secret mismatch | Check `BLUEBUBBLES_WEBHOOK_SECRET` in `.env` |
| Outbound reply fails | `BLUEBUBBLES_PASSWORD` wrong | Check password in BlueBubbles settings |
| Message sent from iPhone not triggering webhook | Same Apple ID — `isFromMe: true` | Send from a different Apple ID |
| No iMessage chats in BlueBubbles | Full Disk Access not granted | System Settings → Privacy & Security → Full Disk Access → add BlueBubbles |
| BlueBubbles not detecting new messages | Accessibility not granted | System Settings → Privacy & Security → Accessibility → add BlueBubbles |
| Bot not responding | Backend not running | Run `uv run uvicorn api:app --port 8000` |
