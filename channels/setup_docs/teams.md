# Microsoft Teams Channel Setup for Arcturus

Connect Arcturus to Microsoft Teams via the Azure Bot Service. Users can DM the bot or add it to a team channel.

> **Known Blocker (2026-03-14):** Azure Bot registration requires a Microsoft personal account with its own Azure tenant/directory. Attempting to register with an account associated with an existing tenant (e.g., a Microsoft-managed or corporate tenant) results in:
> `"Selected user account does not exist in tenant 'Microsoft Services' and cannot access the application..."`
> The backend adapter and inbound handler are fully implemented and tested via curl simulation. Live end-to-end requires resolving Azure account access.

---

## Prerequisites

- Arcturus backend running locally (port 8000)
- A **personal** Microsoft account (Outlook/Hotmail/Live) with its own Azure directory — **not** a work/school account or Microsoft-managed tenant
- Python environment set up (`uv sync --python 3.11`)
- A public tunnel running (see [Tunnel Options](../channels_setup_readme.md#tunnel-options))

---

## Step 1: Register a Bot in Azure

1. Go to [portal.azure.com](https://portal.azure.com)
2. Search for **Azure Bot** → **Create**
3. Fill in:
   - **Bot handle**: `arcturus-bot`
   - **Subscription / Resource Group**: use existing or create new
   - **Type of App**: Multi-tenant
4. Click **Review + Create** → **Create**
5. After creation, go to the resource → **Configuration** tab
6. Copy the **Microsoft App ID** — this is your `TEAMS_APP_ID`
7. Click **Manage Password** (next to App ID) → **New client secret** → copy the secret — this is your `TEAMS_APP_PASSWORD`

---

## Step 2: Set the Messaging Endpoint

1. In the Azure Bot resource → **Configuration** tab
2. Set **Messaging endpoint**: `https://<your-tunnel-url>/api/nexus/teams/events`
3. Click **Apply**

---

## Step 3: Enable the Teams Channel

1. In the Azure Bot resource → **Channels** tab
2. Click **Microsoft Teams** → **Save**

---

## Step 4: Set Environment Variables

Open `.env` in the project root:

```
TEAMS_APP_ID=<your-microsoft-app-id>
TEAMS_APP_PASSWORD=<your-client-secret>
TEAMS_SERVICE_URL=https://smba.trafficmanager.net/apis
```

> `TEAMS_SERVICE_URL` is the default Bot Framework service URL. Teams sends this per-message; the value here is used for proactive messages.

---

## Step 5: Verify `config/channels.yaml`

```yaml
teams:
  enabled: true
  app_id_env: TEAMS_APP_ID
  app_password_env: TEAMS_APP_PASSWORD
  service_url_env: TEAMS_SERVICE_URL
  parse_mode: markdown
  policies:
    group_activation: mention-only
    dm_allowlist: []
    max_retries: 3
    retry_backoff_seconds: 1.0
```

> `group_activation: mention-only` means the bot responds in channels only when @mentioned. DMs always respond.

---

## Step 6: Restart the Backend

```bash
lsof -ti:8000 | xargs kill -9
uv run uvicorn api:app --port 8000
```

---

## Step 7: Test the Bot in Teams

1. Open Microsoft Teams
2. Click **...** in the left sidebar → **Apps** → search for your bot by handle
3. Click **Add** to install it → click **Open** to DM it

Or add to a team channel:
1. Go to any channel → **+** (Add a tab/app) → search for your bot → **Add to a team**
2. In the channel, type `@Arcturus hello`

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bot not receiving messages | Messaging endpoint wrong or tunnel down | Update endpoint in Azure Portal, restart tunnel |
| `403 Invalid Teams Authorization token` | App password wrong | Check `TEAMS_APP_PASSWORD` in `.env` |
| Bot in channel but not responding | `mention-only` policy | Include `@Arcturus` in message |
| Reply not delivered to Teams | `TEAMS_SERVICE_URL` wrong | Check value; Teams sends it per-message in Activity payload |
| Bot not appearing in Teams app catalog | App not approved / channel not enabled | Enable Teams channel in Azure Bot → Channels |
