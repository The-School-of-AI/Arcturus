"""Nexus gateway router.

Exposes the Unified Message Bus over HTTP so the WebChat widget (and future
channel adapters) can send/receive messages through the Arcturus agent core.

Endpoints
---------
POST /api/nexus/webchat/inbound
    Receive an inbound WebChat message, route it through the bus (agent
    processing + outbound delivery to the session outbox).

GET  /api/nexus/webchat/messages/{session_id}
    Poll for queued outbound messages for a WebChat session. Each call drains
    and returns all pending messages (fire-and-forget delivery model).
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

_logger = logging.getLogger(__name__)

from gateway.envelope import MessageEnvelope

router = APIRouter(prefix="/nexus", tags=["Nexus"])

# Lazy reference to the shared MessageBus singleton.
# We defer import so that this module can be imported safely at startup
# before gateway components are fully initialized.
_bus = None


def _get_bus():
    global _bus
    if _bus is None:
        from shared.state import get_message_bus
        _bus = get_message_bus()
    return _bus


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class WebChatInboundRequest(BaseModel):
    """Inbound WebChat message from the widget."""

    session_id: str
    sender_id: str
    sender_name: str
    text: str
    message_id: str | None = None


class MobileInboundRequest(BaseModel):
    """Inbound context from the mobile app."""

    session_id: str
    sender_id: str
    sender_name: str
    text: str
    device_type: str = "mobile"
    message_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/webchat/inbound")
async def webchat_inbound(req: WebChatInboundRequest, bg: BackgroundTasks):
    """Receive a message from the WebChat widget.

    Builds a ``MessageEnvelope`` and kicks off bus processing as a
    background task so the HTTP 200 returns immediately.  The agent reply
    is enqueued in the session outbox once processing completes; the widget
    picks it up via GET ``/api/nexus/webchat/messages/{session_id}``.
    """
    envelope = MessageEnvelope.from_webchat(
        session_id=req.session_id,
        sender_id=req.sender_id,
        sender_name=req.sender_name,
        text=req.text,
        message_id=req.message_id or str(uuid.uuid4()),
    )

    async def _run_roundtrip():
        try:
            await _get_bus().roundtrip(envelope)
        except Exception as exc:
            _logger.exception(
                "Background roundtrip failed for session %s: %s",
                req.session_id, exc,
            )

    bg.add_task(_run_roundtrip)
    return {"ok": True, "session_id": req.session_id, "status": "accepted"}


@router.get("/webchat/messages/{session_id}")
async def webchat_poll(session_id: str):
    """Poll for pending outbound messages for a WebChat session.

    Drains the session outbox — each message is returned exactly once.
    Returns an empty list if no messages are queued.
    """
    bus = _get_bus()
    adapter = bus.adapters.get("webchat")
    raw = adapter.drain_outbox(session_id) if adapter else []
    # Normalise: frontend polls for `m.text`; outbox stores `content`.
    messages = [{**m, "text": m.get("text") or m.get("content", "")} for m in raw]
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }


@router.get("/webchat/stream/{session_id}")
async def webchat_stream(session_id: str, request: Request):
    """SSE push stream for a WebChat session.

    The client connects once; replies are pushed as ``event: message`` events
    the instant the agent delivers them — no polling required.  A ``ping``
    keepalive is sent every 15 seconds to prevent proxy timeouts.

    The polling endpoint (``/webchat/messages/{session_id}``) remains available
    as a fallback for clients that do not support SSE.
    """
    bus = _get_bus()
    adapter = bus.adapters.get("webchat")
    q = adapter.subscribe_sse(session_id) if adapter else asyncio.Queue()

    async def _generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield {"event": "message", "data": json.dumps(msg)}
                except TimeoutError:
                    # Send a keepalive ping so the connection is not dropped by
                    # proxies / load balancers that time out idle streams.
                    yield {"event": "ping", "data": ""}
        finally:
            if adapter:
                adapter.unsubscribe_sse(session_id, q)

    return EventSourceResponse(_generator())


# ---------------------------------------------------------------------------
# Slack Events API
# ---------------------------------------------------------------------------


@router.post("/slack/events")
async def slack_events(request: Request) -> dict[str, Any]:
    """Receive Slack Events API webhook.

    Handles two Slack event types:

    * ``url_verification`` — initial handshake when the Slack app is configured;
      returns the ``challenge`` token so Slack confirms ownership of the URL.
    * ``event_callback`` with ``message`` sub-type — routes the message through
      the Nexus bus (ingest → mock agent → deliver reply back to the channel).

    Signature verification is performed when ``SLACK_SIGNING_SECRET`` is set
    on the adapter (via env var or config).  Requests with an invalid signature
    are rejected with HTTP 403.  Signature checking is skipped in dev/test mode
    (when the secret is empty).
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 1. url_verification handshake (Slack app setup / re-verification).
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # 2. Optional signature verification.
    bus = _get_bus()
    adapter = bus.adapters.get("slack")
    signing_secret: str = getattr(adapter, "signing_secret", "") if adapter else ""
    if signing_secret:
        ts = request.headers.get("X-Slack-Request-Timestamp", "")
        sig = request.headers.get("X-Slack-Signature", "")
        from channels.slack import SlackAdapter as _SlackAdapter
        if not _SlackAdapter.verify_signature(body, ts, sig, signing_secret):
            raise HTTPException(status_code=403, detail="Invalid Slack signature")

    # 3. Route message events through the bus.
    event = payload.get("event", {})
    _text = MessageEnvelope.normalize_text(event.get("text", ""))
    _subtype = event.get("subtype", "")
    if (
        event.get("type") == "message"
        and not event.get("bot_id")
        and not _subtype  # skip message_changed, message_deleted, etc.
        and _text  # skip empty/whitespace-only messages (prevents ValueError in envelope)
    ):
        envelope = MessageEnvelope.from_slack(
            channel_id=event.get("channel", "unknown"),
            sender_id=event.get("user", "unknown"),
            sender_name=event.get("user", "unknown"),
            text=_text,
            message_id=event.get("ts", str(uuid.uuid4())),
            thread_ts=event.get("thread_ts"),
        )
        # Fire-and-forget: return 200 OK immediately so Slack doesn't retry.
        asyncio.create_task(bus.roundtrip(envelope))

    # Slack requires a 200 OK with any body to acknowledge receipt.
    return {"ok": True}


# ---------------------------------------------------------------------------
# Discord Interactions / Gateway webhook
# ---------------------------------------------------------------------------


@router.post("/discord/events")
async def discord_events(request: Request) -> dict[str, Any]:
    """Receive Discord webhook events (Interactions endpoint or Gateway relay).

    Handles two Discord payload types:

    * ``PING`` (type 1) — initial handshake when the Interactions endpoint is
      first configured in the Discord Developer Portal; returns ``{"type": 1}``
      so Discord confirms ownership.
    * ``APPLICATION_COMMAND`` / message event (type 2 / custom relay) — routes
      the message through the Nexus bus (ingest → mock agent → deliver reply).

    Signature verification is performed using Ed25519 when ``DISCORD_PUBLIC_KEY``
    is set on the adapter.  Requests with an invalid signature are rejected with
    HTTP 401 (Discord's required status for failed signature checks).
    Signature checking is skipped in dev/test mode (when the key is empty).
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 1. Optional Ed25519 signature verification.
    bus = _get_bus()
    adapter = bus.adapters.get("discord")
    public_key: str = getattr(adapter, "public_key", "") if adapter else ""
    if public_key:
        timestamp = request.headers.get("X-Signature-Timestamp", "")
        signature = request.headers.get("X-Signature-Ed25519", "")
        from channels.discord import DiscordAdapter as _DiscordAdapter
        if not _DiscordAdapter.verify_signature(body, timestamp, signature, public_key):
            raise HTTPException(status_code=401, detail="Invalid Discord signature")

    # DEBUG: log full payload to diagnose routing
    print(f"[DISCORD DEBUG] payload type={payload.get('type')} keys={list(payload.keys())}")

    # 2. PING handshake (Discord requires type=1 response).
    if payload.get("type") == 1:
        return {"type": 1}

    # 3. Route message events through the bus.
    #    Supports both Interactions (type 2 APPLICATION_COMMAND) and
    #    a simple relay format: {"type": "message", "channel_id": ..., ...}
    event_type = payload.get("type")
    if event_type == 2:
        # Slash command / application command interaction
        data = payload.get("data", {})
        interaction_id = str(payload.get("id", uuid.uuid4()))
        guild_id = str(payload.get("guild_id", "unknown"))
        channel_id = str(payload.get("channel_id", "unknown"))
        member = payload.get("member", {})
        user = member.get("user", payload.get("user", {}))
        sender_id = str(user.get("id", "unknown"))
        sender_name = user.get("username", "unknown")
        # For slash commands the text is the command name + options joined
        options = data.get("options", [])
        text_parts = [data.get("name", "")]
        for opt in options:
            text_parts.append(str(opt.get("value", "")))
        text = " ".join(filter(None, text_parts)) or "command"

        envelope = MessageEnvelope.from_discord(
            guild_id=guild_id,
            channel_id=channel_id,
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            message_id=interaction_id,
        )
        interaction_token = payload.get("token", "")
        application_id = payload.get("application_id", "")

        async def _run_and_reply():
            # Remove hash so the dedup guard doesn't skip this as a duplicate
            if envelope.message_hash:
                bus._seen_hashes.discard(envelope.message_hash)
            result = await bus.ingest(envelope)
            print(f"[DISCORD] ingest success={result.success} agent_response={result.agent_response}")
            reply = ""
            if result.agent_response:
                reply = result.agent_response.get("reply", "")
            print(f"[DISCORD] reply ({len(reply)} chars): {reply[:80]}")
            if not reply:
                reply = "The agent could not complete your request."
            # Truncate to Discord's 2000-char limit
            if len(reply) > 2000:
                reply = reply[:1997] + "..."
            import httpx
            follow_up_url = f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}/messages/@original"
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.patch(follow_up_url, json={"content": reply})

        asyncio.create_task(_run_and_reply())
        # Return deferred acknowledgement immediately so Discord doesn't time out
        return {"type": 5}  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE

    elif event_type == "message" or payload.get("channel_id"):
        # Simple relay format used by tests and gateway relay bots
        guild_id = str(payload.get("guild_id", "unknown"))
        channel_id = str(payload.get("channel_id", "unknown"))
        sender_id = str(payload.get("author", {}).get("id", payload.get("sender_id", "unknown")))
        sender_name = payload.get("author", {}).get("username", payload.get("sender_name", "unknown"))
        text = payload.get("content", payload.get("text", ""))
        message_id = str(payload.get("id", payload.get("message_id", str(uuid.uuid4()))))
        is_bot = payload.get("author", {}).get("bot", False)

        if not is_bot and text:
            envelope = MessageEnvelope.from_discord(
                guild_id=guild_id,
                channel_id=channel_id,
                sender_id=sender_id,
                sender_name=sender_name,
                text=text,
                message_id=message_id,
            )
            await bus.roundtrip(envelope)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Microsoft Teams inbound
# ---------------------------------------------------------------------------


@router.post("/teams/events")
async def teams_events(request: Request) -> dict[str, Any]:
    """Receive an inbound Bot Framework Activity from Microsoft Teams.

    Microsoft Teams posts a Bot Framework Activity JSON payload when
    a user sends a message to the bot:

        {
          "type":          "message",
          "id":            "activity-id",
          "text":          "Hello Arcturus",
          "from":          {"id": "29:...", "name": "Alice", "role": "user"},
          "conversation":  {"id": "a:...", "isGroup": false},
          "channelData":   {"teamsChannelId": "19:...", "team": {"id": "..."}},
          "serviceUrl":    "https://smba.trafficmanager.net/apis"
        }

    The ``Authorization: Bearer {token}`` header carries an optional
    credential.  Verification is skipped when ``TEAMS_APP_PASSWORD`` is
    empty (dev mode).

    Non-message activities (typing, installationUpdate, etc.) are skipped.
    Bot-sent messages (``from.role == "bot"``) are skipped to prevent loops.
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 1. Optional Bearer token verification.
    bus = _get_bus()
    adapter = bus.adapters.get("teams")
    app_password: str = getattr(adapter, "app_password", "") if adapter else ""
    if app_password:
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        from channels.teams import TeamsAdapter as _TeamsAdapter
        if not _TeamsAdapter.verify_token(token, app_password):
            raise HTTPException(status_code=403, detail="Invalid Teams Authorization token")

    # 2. Only handle message activities.
    activity_type = payload.get("type", "")
    if activity_type != "message":
        return {"ok": True, "skipped": True, "reason": f"activity_type={activity_type}"}

    # 3. Skip messages from bots to prevent loops.
    sender = payload.get("from", {})
    if sender.get("role", "").lower() == "bot":
        return {"ok": True, "skipped": True, "reason": "fromBot"}

    # 4. Extract fields from the Bot Framework Activity.
    message_id = payload.get("id") or str(uuid.uuid4())
    text = (payload.get("text") or "").strip()

    # Guard: skip empty text (card actions, attachments without text, etc.)
    if not text:
        return {"ok": True, "skipped": True, "reason": "empty_text"}

    channel_data = payload.get("channelData", {})
    team_id = (channel_data.get("team") or {}).get("id", "")
    teams_channel_id = channel_data.get("teamsChannelId", "")

    # For DMs, team_id may be absent; fall back to conversation.id
    conversation = payload.get("conversation", {})
    if not team_id:
        team_id = conversation.get("id", "dm")
    if not teams_channel_id:
        teams_channel_id = conversation.get("id", "")

    sender_id = sender.get("aadObjectId") or sender.get("id", "unknown")
    sender_name = sender.get("name", sender_id)
    service_url = payload.get("serviceUrl", "")
    thread_id_in = payload.get("replyToId")  # set for threaded replies

    # 5. Build envelope and roundtrip through the bus.
    envelope = MessageEnvelope.from_teams(
        team_id=team_id,
        channel_id=teams_channel_id,
        sender_id=sender_id,
        sender_name=sender_name,
        text=text,
        message_id=message_id,
        thread_id_in=thread_id_in,
        service_url=service_url,
    )
    await bus.roundtrip(envelope)

    return {"ok": True}


# ---------------------------------------------------------------------------
# WhatsApp (Baileys bridge inbound)
# ---------------------------------------------------------------------------


@router.get("/whatsapp/inbound")
async def whatsapp_challenge(request: Request) -> dict[str, Any]:
    """WhatsApp hub.challenge handshake (GET).

    When the Baileys bridge (or an external system) verifies the webhook URL,
    it can send:
      GET /api/nexus/whatsapp/inbound?hub.mode=subscribe&hub.challenge=TOKEN&hub.verify_token=SECRET

    We echo back the challenge token to confirm ownership.  This mirrors the
    WhatsApp Cloud API verification pattern, making the endpoint compatible
    with future migration away from Baileys.

    Query params:
        hub.mode:         Must be ``"subscribe"``.
        hub.challenge:    Arbitrary token to echo back.
        hub.verify_token: Must match ``WHATSAPP_BRIDGE_SECRET`` (or be empty in dev mode).
    """
    mode = request.query_params.get("hub.mode", "")
    challenge = request.query_params.get("hub.challenge", "")
    verify_token = request.query_params.get("hub.verify_token", "")

    bus = _get_bus()
    adapter = bus.adapters.get("whatsapp")
    expected_secret: str = getattr(adapter, "bridge_secret", "") if adapter else ""

    # In dev mode (no secret), accept any verify_token.
    # In production, verify_token must match the bridge secret.
    if expected_secret and verify_token != expected_secret:
        raise HTTPException(status_code=403, detail="hub.verify_token mismatch")

    if mode == "subscribe" and challenge:
        return {"hub.challenge": challenge}

    raise HTTPException(status_code=400, detail="Invalid hub.mode or missing hub.challenge")


@router.post("/whatsapp/inbound")
async def whatsapp_inbound(request: Request) -> dict[str, Any]:
    """Receive an inbound WhatsApp message from the Baileys bridge.

    The bridge POSTs a JSON payload with these fields:
        message_id    (str)  — Baileys key.id (globally unique)
        phone_number  (str)  — sender's normalized phone number (digits only)
        contact_name  (str)  — sender's WhatsApp push name
        text          (str)  — message text
        is_group      (bool) — True for group chat messages
        group_id      (str|null) — group JID when is_group=True
        timestamp     (str)  — ISO 8601

    The bridge sets ``X-WA-Secret`` header (HMAC-SHA256 over raw JSON body).
    Signature verification is skipped when ``WHATSAPP_BRIDGE_SECRET`` is empty.

    ``fromMe=True`` messages are filtered at the bridge before being forwarded;
    this endpoint also guards against empty text as a defence-in-depth measure.
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 1. Optional HMAC-SHA256 signature verification.
    bus = _get_bus()
    adapter = bus.adapters.get("whatsapp")
    bridge_secret: str = getattr(adapter, "bridge_secret", "") if adapter else ""
    if bridge_secret:
        sig = request.headers.get("X-WA-Secret", "")
        from channels.whatsapp import WhatsAppAdapter as _WhatsAppAdapter
        if not _WhatsAppAdapter.verify_signature(body, sig, bridge_secret):
            raise HTTPException(status_code=403, detail="Invalid WhatsApp bridge signature")

    # 2. Extract fields.
    phone_number = payload.get("phone_number", "")
    contact_name = payload.get("contact_name", phone_number)
    text = payload.get("text", "")
    message_id = payload.get("message_id") or str(uuid.uuid4())
    is_group = bool(payload.get("is_group", False))
    group_id = payload.get("group_id")

    # 3. Guard: skip empty text (also catches any fromMe slip-through).
    if not text:
        return {"ok": True, "skipped": True, "reason": "empty_text"}

    # 4. Build envelope and roundtrip through the bus.
    envelope = MessageEnvelope.from_whatsapp(
        phone_number=phone_number,
        contact_name=contact_name,
        text=text,
        message_id=message_id,
        is_group=is_group,
        group_id=group_id,
    )
    await bus.roundtrip(envelope)

    # Bridge expects a simple 200 OK acknowledgement.
    return {"ok": True}


# ---------------------------------------------------------------------------
# Google Chat Events API
# ---------------------------------------------------------------------------


@router.post("/googlechat/events")
async def googlechat_events(request: Request) -> dict[str, Any]:
    """Receive Google Chat events (space messages and bot mentions).

    Google Chat POSTs event objects to this endpoint when the bot receives
    a message in a Space it has been added to, or when a user @-mentions it.

    Event types handled:
    * ``MESSAGE`` — user sends a message or @-mentions the bot in a Space.
    * ``ADDED_TO_SPACE`` — bot was added to a Space (acknowledged silently).
    * ``REMOVED_FROM_SPACE`` — bot was removed (acknowledged silently).

    Optional token verification:
        If ``GOOGLE_CHAT_VERIFICATION_TOKEN`` is set on the adapter, the
        ``token`` field in the JSON body is compared against it.  Requests
        with an invalid token are rejected with HTTP 403.

    The reply is delivered back to Google Chat via the adapter's
    ``send_message()`` (webhook or service-account mode, whichever is
    configured).

    Reference:
        https://developers.google.com/chat/how-tos/bots-develop
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 1. Optional token verification.
    bus = _get_bus()
    adapter = bus.adapters.get("googlechat")
    verification_token: str = getattr(adapter, "verification_token", "") if adapter else ""
    if verification_token:
        token_in_payload = payload.get("token", "")
        from channels.googlechat import GoogleChatAdapter as _GoogleChatAdapter
        if not _GoogleChatAdapter.verify_signature(body, token_in_payload, verification_token):
            raise HTTPException(status_code=403, detail="Invalid Google Chat verification token")

    event_type = payload.get("type", "")

    # 2. Silently acknowledge lifecycle events.
    if event_type in ("ADDED_TO_SPACE", "REMOVED_FROM_SPACE"):
        return {"text": ""}

    # 3. Route MESSAGE events through the bus.
    if event_type == "MESSAGE":
        message = payload.get("message", {})
        sender = message.get("sender", {})
        space = payload.get("space", {})

        space_name = space.get("name", "spaces/unknown")
        sender_id = sender.get("name", sender.get("email", "unknown"))
        sender_name = sender.get("displayName", sender.get("name", "unknown"))
        text = message.get("argumentText", message.get("text", "")).strip()
        message_name = message.get("name", str(uuid.uuid4()))
        thread_name = message.get("thread", {}).get("name")
        is_bot = sender.get("type") == "BOT"

        if not text or is_bot:
            return {"text": ""}

        envelope = MessageEnvelope.from_googlechat(
            space_name=space_name,
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            message_name=message_name,
            is_bot=is_bot,
            thread_name=thread_name,
        )
        await bus.roundtrip(envelope)

    # Google Chat expects a 200 OK with a (possibly empty) JSON body.
    return {"text": ""}


# ---------------------------------------------------------------------------
# iMessage / BlueBubbles inbound
# ---------------------------------------------------------------------------


@router.post("/imessage/inbound")
async def imessage_inbound(request: Request) -> dict[str, Any]:
    """Receive an inbound iMessage from the BlueBubbles server webhook.

    BlueBubbles POSTs a JSON payload when a new iMessage arrives:

        {
          "type": "new-message",
          "data": {
            "guid":          "...",          // message GUID
            "text":          "hello",
            "chats":         [{"guid": "iMessage;+;+15551234567", ...}],
            "handle":        {"address": "+15551234567", "firstName": "Alice", ...},
            "isFromMe":      false,
            "dateCreated":   1234567890000,
            "isGroupMessage": false
          }
        }

    The ``X-BB-Secret`` header carries an optional HMAC-SHA256 signature over
    the raw body.  Verification is skipped when ``BLUEBUBBLES_WEBHOOK_SECRET``
    is empty (dev mode).

    Messages sent by the bot itself (``isFromMe: true``) are skipped to
    prevent reply loops.
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 1. Optional HMAC-SHA256 signature verification.
    bus = _get_bus()
    adapter = bus.adapters.get("imessage")
    webhook_secret: str = getattr(adapter, "webhook_secret", "") if adapter else ""
    if webhook_secret:
        sig = request.headers.get("X-BB-Secret", "")
        from channels.imessage import iMessageAdapter as _iMessageAdapter
        if not _iMessageAdapter.verify_signature(body, sig, webhook_secret):
            raise HTTPException(status_code=403, detail="Invalid BlueBubbles webhook signature")

    # 2. Only handle new-message events.
    event_type = payload.get("type", "")
    if event_type != "new-message":
        return {"ok": True, "skipped": True, "reason": f"event_type={event_type}"}

    data = payload.get("data", {})

    # 3. Skip messages from the bot itself.
    if data.get("isFromMe", False):
        return {"ok": True, "skipped": True, "reason": "fromMe"}

    # 4. Extract fields from the BlueBubbles payload.
    message_guid = data.get("guid") or str(uuid.uuid4())
    text = data.get("text", "").strip()

    # Guard: skip empty text (media without caption, tapbacks, etc.)
    if not text:
        return {"ok": True, "skipped": True, "reason": "empty_text"}

    # Chat GUID comes from the first chat entry
    chats = data.get("chats", [])
    chat_guid = chats[0].get("guid", "iMessage;+;unknown") if chats else "iMessage;+;unknown"

    handle = data.get("handle", {})
    sender_id = handle.get("address", "unknown")
    # Build a human-readable name from firstName + lastName if available
    first = handle.get("firstName", "")
    last = handle.get("lastName", "")
    sender_name = f"{first} {last}".strip() or sender_id

    is_group = bool(data.get("isGroupMessage", False))

    # 5. Build envelope and roundtrip through the bus.
    envelope = MessageEnvelope.from_imessage(
        chat_guid=chat_guid,
        sender_id=sender_id,
        sender_name=sender_name,
        text=text,
        message_guid=message_guid,
        is_group=is_group,
    )
    await bus.roundtrip(envelope)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Signal inbound
# ---------------------------------------------------------------------------


@router.post("/signal/inbound")
async def signal_inbound(request: Request) -> dict[str, Any]:
    """Receive an inbound Signal message forwarded by the signal-cli bridge.

    The signal_bridge/app.py sidecar polls signal-cli every 2 seconds and
    POSTs new messages with the following JSON body:

        {
          "message_id":  "1740650000000",
          "phone_number": "+15551234567",
          "sender_name":  "Alice",
          "text":         "hello",
          "is_group":     false,
          "group_id":     null,
          "timestamp":    "2026-02-28T10:00:00Z"
        }

    The ``X-Signal-Secret`` header carries an optional HMAC-SHA256 signature
    over the raw body.  Verification is skipped when ``SIGNAL_BRIDGE_SECRET``
    is empty (dev mode).
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 1. Optional HMAC-SHA256 signature verification.
    bus = _get_bus()
    adapter = bus.adapters.get("signal")
    bridge_secret: str = getattr(adapter, "bridge_secret", "") if adapter else ""
    if bridge_secret:
        sig = request.headers.get("X-Signal-Secret", "")
        from channels.signal import SignalAdapter as _SignalAdapter
        if not _SignalAdapter.verify_signature(body, sig, bridge_secret):
            raise HTTPException(status_code=403, detail="Invalid Signal bridge signature")

    # 2. Extract fields.
    message_id = payload.get("message_id") or str(uuid.uuid4())
    text = (payload.get("text") or "").strip()

    # Guard: skip empty text (reactions, receipts, etc.)
    if not text:
        return {"ok": True, "skipped": True, "reason": "empty_text"}

    phone_number = payload.get("phone_number", "unknown")
    sender_name = payload.get("sender_name") or phone_number
    is_group = bool(payload.get("is_group", False))
    group_id = payload.get("group_id")

    # 3. Build envelope and roundtrip through the bus.
    envelope = MessageEnvelope.from_signal(
        phone_number=phone_number,
        sender_name=sender_name,
        text=text,
        message_id=message_id,
        is_group=is_group,
        group_id=group_id,
    )
    await bus.roundtrip(envelope)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Mobile inbound (P13 Orbit)
# ---------------------------------------------------------------------------


@router.post("/mobile/inbound")
async def mobile_inbound(req: MobileInboundRequest):
    """Receive a message from the mobile app.

    Routes a ``MessageEnvelope`` through the bus with mobile channel identity.
    """
    envelope = MessageEnvelope.from_mobile(
        session_id=req.session_id,
        sender_id=req.sender_id,
        sender_name=req.sender_name,
        text=req.text,
        message_id=req.message_id or str(uuid.uuid4()),
        device_type=req.device_type,
    )
    result = await _get_bus().roundtrip(envelope)
    return result.to_dict()


@router.get("/mobile/messages/{session_id}")
async def mobile_poll(session_id: str):
    """Poll for pending outbound messages for a mobile session."""
    bus = _get_bus()
    adapter = bus.adapters.get("mobile")
    # If no specialized mobile adapter, fallback to webchat for now
    if not adapter:
        adapter = bus.adapters.get("webchat")

    messages = adapter.drain_outbox(session_id) if adapter else []
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }
