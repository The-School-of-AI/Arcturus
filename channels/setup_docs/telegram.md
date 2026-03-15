# Telegram Channel Setup for Arcturus

Connect Arcturus to Telegram so users can message the agent directly via DM or in groups.

---

## Prerequisites

- Arcturus backend running locally (port 8000)
- A Telegram account
- Python environment set up (`uv sync --python 3.11`)

> **No tunnel needed.** Telegram uses long-polling — Arcturus polls the Bot API every 2 seconds. No public URL is required.

---

## Step 1: Create a Bot via BotFather

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Enter a display name (e.g. `Arcturus Bot`)
4. Enter a username ending in `bot` (e.g. `arcturus_agent_bot`)
5. BotFather replies with your **Bot Token** — copy it

---

## Step 2: Set Environment Variable

Open `.env` in the project root and add:

```
TELEGRAM_TOKEN=<your-bot-token>
```

---

## Step 3: Verify `config/channels.yaml`

Confirm the Telegram channel entry looks like this (defaults are correct):

```yaml
telegram:
  enabled: true
  token_env: TELEGRAM_TOKEN
  parse_mode: plain
  policies:
    group_activation: always-on
    dm_allowlist: []
    max_retries: 3
    retry_backoff_seconds: 1.0
```

The `group_activation: always-on` means the bot responds to every message in DMs and groups (no `@mention` required).

---

## Step 4: Restart the Backend

```bash
# Kill the running backend (Ctrl+C or kill port)
lsof -ti:8000 | xargs kill -9

# Start fresh
uv run uvicorn api:app --port 8000
```

The Telegram poll loop starts automatically on startup. You will see:

```
[Telegram] Poll loop started for token ...
```

---

## Step 5: Test

1. Open Telegram and find your bot (search for its username)
2. Send `/start` or any message (e.g. `hello`)
3. The bot will reply after the agent processes the message (typically 10–30 seconds)

For group testing: add the bot to a group. It responds to all messages (always-on) or only `@mentions` if you change `group_activation` to `mention-only`.

---

## Group Chat — Mention-Only Mode (Optional)

If you want the bot to respond only when explicitly mentioned in a group:

```yaml
telegram:
  policies:
    group_activation: mention-only
```

Users must include `@arcturus` in their message. DMs always work regardless of this setting.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No response from bot | `TELEGRAM_TOKEN` not set or wrong | Check `.env` and restart backend |
| `[Telegram] Poll loop error` in logs | Invalid token | Verify token from BotFather |
| Bot responds but with wrong content | Skill error | Check `[NEXUS]` logs in backend terminal |
| Bot added to group but not responding | `group_activation: mention-only` set | Change to `always-on` or send `@<botname> hello` |
