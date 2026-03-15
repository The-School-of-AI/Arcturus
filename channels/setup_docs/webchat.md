# WebChat Channel Setup for Arcturus

WebChat is the built-in chat widget in the Arcturus Electron frontend. No external accounts, no tunnels, no configuration required.

---

## Prerequisites

- Arcturus backend running (port 8000)
- Arcturus Electron frontend running

---

## Setup

No setup needed. WebChat is enabled by default and runs entirely within the Arcturus app.

```yaml
# config/channels.yaml (default — no changes needed)
webchat:
  enabled: true
  policies:
    group_activation: always-on
    max_retries: 2
    retry_backoff_seconds: 0.5
```

---

## How to Access the Chat Widget

1. Start the Electron app: `cd platform-frontend && npm run electron:dev:all`
2. Go to the **Apps** tab
3. Drag the **AI Chat** card onto the canvas
4. Type a message and press Enter

The widget posts to `POST /api/nexus/webchat/inbound` and polls `GET /api/nexus/webchat/messages/{session_id}` for replies. An SSE stream is also available at `GET /api/nexus/webchat/stream/{session_id}` for push delivery.

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/nexus/webchat/inbound` | Send a message from the widget |
| `GET` | `/api/nexus/webchat/messages/{session_id}` | Poll for pending replies |
| `GET` | `/api/nexus/webchat/stream/{session_id}` | SSE stream for push delivery |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Widget not visible | Apps tab not open or card not placed | Open Apps tab → drag AI Chat card to canvas |
| No reply from agent | Backend not running | Start backend on port 8000 |
| "session expired" | Session ID mismatch | Refresh the widget or reload the frontend |
