# Discord Channel Setup for Arcturus

This guide walks you through connecting Arcturus to Discord so users can message the agent via a slash command.

---

## Prerequisites

- Arcturus backend running locally (port 8000)
- A Discord account
- Python environment set up (`uv sync --python 3.11`)

---

## Step 1: Create a Discord Application and Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → give it a name (e.g. `arcturus-bot`) → **Create**
3. Go to the **Bot** tab
4. Click **Reset Token** → copy the token (you will need it shortly)
5. Under **Privileged Gateway Intents**, enable **Message Content Intent**
6. Save changes

---

## Step 2: Get Your Public Key

1. Go to **General Information** tab of your app
2. Copy the **Public Key** — you will need it for `.env`

---

## Step 3: Set Environment Variables

Open `.env` in the project root and add:

```
DISCORD_BOT_TOKEN=<your-bot-token>
DISCORD_PUBLIC_KEY=<your-public-key>
```

---

## Step 4: Install Required Dependency

Discord uses Ed25519 signature verification. Install the required library:

```bash
uv add PyNaCl
```

> Without this, all incoming Discord requests will be rejected with 401.

---

## Step 5: Enable always-on Routing for Discord

Open `config/channels.yaml` and make sure Discord's `group_activation` is set to `always-on`:

```yaml
discord:
  enabled: true
  policies:
    group_activation: always-on
```

> The default is `mention-only`, which silently drops all messages that don't contain `@arcturus`.

---

## Step 6: Generate an Invite URL and Add Bot to Your Server

1. In the Developer Portal, go to **OAuth2 → URL Generator**
2. Under **Scopes**, select:
   - `bot`
   - `applications.commands`
3. Under **Bot Permissions**, select:
   - `Send Messages`
4. Copy the generated URL and open it in your browser
5. Select your Discord server → **Authorize**

> If you don't have a server, open Discord → click **+** in the sidebar → **Create My Own** → **For me and my friends**.

---

## Step 7: Set Up a Public Tunnel

Discord requires a publicly accessible HTTPS URL to send interactions to. Choose one of the following options:

### Option A: ngrok (requires free account)

1. Sign up at [dashboard.ngrok.com/signup](https://dashboard.ngrok.com/signup)
2. Get your authtoken from [dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Run:
```bash
ngrok config add-authtoken <your-authtoken>
ngrok http 8000
```
4. Copy the `https://....ngrok-free.app` URL shown in the output

### Option B: localtunnel (no account needed)

```bash
npx localtunnel --port 8000
```

Copy the `https://....loca.lt` URL shown in the output.

### Option C: cloudflared (no account needed)

```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:8000
```

Copy the `https://....trycloudflare.com` URL shown in the output.

> Keep this terminal open — closing it will break the connection to Discord.

---

## Step 8: Set the Interactions Endpoint URL

1. Make sure the Arcturus backend is running on port 8000
2. In the Discord Developer Portal → your app → **General Information**
3. Scroll to **Interactions Endpoint URL**
4. Paste: `https://<your-tunnel-url>/api/nexus/discord/events`
5. Click **Save Changes**

Discord will immediately send a PING to verify the endpoint. The backend must be running for this to succeed.

> If you see "The specified interactions endpoint url could not be verified", check that:
> - The backend is running
> - The tunnel is active
> - `PyNaCl` is installed

---

## Step 9: Register the `/ask` Slash Command

Run this once to register the slash command globally:

```bash
curl -X POST "https://discord.com/api/v10/applications/<YOUR_APP_ID>/commands" \
  -H "Authorization: Bot <YOUR_BOT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ask",
    "description": "Ask the Arcturus agent a question",
    "options": [{
      "name": "message",
      "description": "Your message",
      "type": 3,
      "required": true
    }]
  }'
```

To find your `APP_ID`, run:

```bash
curl -s -H "Authorization: Bot <YOUR_BOT_TOKEN>" \
  "https://discord.com/api/v10/users/@me" | python3 -c "import sys,json; d=json.load(sys.stdin); print('App ID:', d.get('id'))"
```

> Slash commands can take up to **1 hour** to propagate globally. For instant registration to a specific server, use the guild-specific endpoint:
> `https://discord.com/api/v10/applications/<APP_ID>/guilds/<GUILD_ID>/commands`

---

## Step 10: Test

In your Discord server, type:

```
/ask message:hello
```

The bot will show "thinking..." and reply after the agent completes (typically 10–30 seconds).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "The specified interactions endpoint url could not be verified" | Backend not running or PyNaCl missing | Start backend, run `uv add PyNaCl` |
| Bot responds with "The agent could not complete your request" | Skill error or no agent output | Check backend terminal for `[NEXUS]` logs |
| `/ask` command not showing in Discord | Slash command not yet propagated | Wait up to 1 hour, or use guild-specific registration |
| "dino-bot didn't respond in time" | Tunnel disconnected | Restart tunnel, update Interactions Endpoint URL |
| All messages trigger wrong skill | Skill intent triggers too broad | Check `config/channels.yaml` and skill `intent_triggers` |
| "Invalid Discord signature" | PyNaCl not installed | Run `uv add PyNaCl` and restart backend |
