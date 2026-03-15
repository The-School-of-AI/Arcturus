"""Arcturus Signal Bridge

A thin Python sidecar that wraps the signal-cli HTTP REST server and exposes
a minimal API so the Arcturus FastAPI backend can send and receive Signal messages.

Outbound (FastAPI → Bridge):
  POST /send        { recipient_id, text }  → proxied to signal-cli
  GET  /health                              → session status

Inbound (Bridge → FastAPI):
  Background poller calls signal-cli POST /v1/receive every POLL_INTERVAL_S seconds.
  For each new message, POSTs to:
    POST FASTAPI_BASE_URL/api/nexus/signal/inbound
  with X-Signal-Secret header (HMAC-SHA256 over body) for authentication.

Environment variables:
  SIGNAL_CLI_URL        Base URL of the signal-cli HTTP server (default: http://localhost:8080)
  SIGNAL_PHONE_NUMBER   E.164 phone number registered with signal-cli (e.g. +15551234567)
  SIGNAL_BRIDGE_PORT    HTTP port this server listens on (default: 3002)
  FASTAPI_BASE_URL      Base URL of the Arcturus FastAPI server (default: http://localhost:8000)
  SIGNAL_BRIDGE_SECRET  Shared HMAC-SHA256 secret for bridge ↔ FastAPI auth (optional)
  POLL_INTERVAL_S       Polling interval in seconds (default: 2)
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SIGNAL_CLI_URL = os.getenv("SIGNAL_CLI_URL", "http://localhost:8080").rstrip("/")
SIGNAL_PHONE_NUMBER = os.getenv("SIGNAL_PHONE_NUMBER", "")
BRIDGE_PORT = int(os.getenv("SIGNAL_BRIDGE_PORT", "3002"))
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000").rstrip("/")
INBOUND_PATH = "/api/nexus/signal/inbound"
BRIDGE_SECRET = os.getenv("SIGNAL_BRIDGE_SECRET", "")
POLL_INTERVAL_S = float(os.getenv("POLL_INTERVAL_S", "2"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("signal_bridge")

app = FastAPI(title="Arcturus Signal Bridge")
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=15.0)
    return _http_client


def _sign(body_str: str) -> str:
    """Compute HMAC-SHA256 hex digest of body_str using BRIDGE_SECRET."""
    return hmac.new(
        BRIDGE_SECRET.encode("utf-8"),
        body_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _verify_secret(req_secret: str, body_str: str) -> bool:
    """Constant-time comparison of inbound X-Signal-Secret header."""
    if not BRIDGE_SECRET:
        return True
    expected = _sign(body_str)
    try:
        return hmac.compare_digest(req_secret, expected)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Outbound: POST /send
# ---------------------------------------------------------------------------


@app.post("/send")
async def send_message(request: Request) -> JSONResponse:
    """Send a Signal message via signal-cli.

    Request body: { "recipient_id": "+15551234567", "text": "Hello!" }
    Optionally authenticated via X-Signal-Secret header.
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    # Verify inbound secret from FastAPI if configured
    if BRIDGE_SECRET:
        sig = request.headers.get("X-Signal-Secret", "")
        if not _verify_secret(sig, body_str):
            raise HTTPException(status_code=401, detail="Invalid X-Signal-Secret")

    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    recipient_id = payload.get("recipient_id", "").strip()
    text = payload.get("text", "").strip()

    if not recipient_id or not text:
        raise HTTPException(status_code=400, detail="recipient_id and text are required")

    if not SIGNAL_PHONE_NUMBER:
        raise HTTPException(status_code=503, detail="SIGNAL_PHONE_NUMBER not configured")

    # signal-cli v1 send endpoint
    cli_payload = {
        "number": SIGNAL_PHONE_NUMBER,
        "recipients": [recipient_id],
        "message": text,
    }

    client = _get_client()
    try:
        resp = await client.post(f"{SIGNAL_CLI_URL}/v1/send", json=cli_payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            timestamp = data.get("timestamp") or datetime.utcnow().isoformat()
            return JSONResponse({
                "ok": True,
                "message_id": str(timestamp),
                "timestamp": datetime.utcnow().isoformat(),
            })
        else:
            try:
                err = resp.json()
            except Exception:
                err = {"error": f"HTTP {resp.status_code}"}
            return JSONResponse(
                {"ok": False, "error": err.get("error", f"HTTP {resp.status_code}")},
                status_code=resp.status_code,
            )
    except httpx.RequestError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


# ---------------------------------------------------------------------------
# Health: GET /health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> JSONResponse:
    """Return bridge and signal-cli connection status."""
    client = _get_client()
    try:
        resp = await client.get(f"{SIGNAL_CLI_URL}/v1/health")
        cli_ok = resp.status_code == 200
    except Exception:
        cli_ok = False

    return JSONResponse({
        "status": "ok" if cli_ok else "signal_cli_unavailable",
        "connected": cli_ok,
        "phone_number": SIGNAL_PHONE_NUMBER,
    })


# ---------------------------------------------------------------------------
# Inbound poller: polls signal-cli /v1/receive and forwards to FastAPI
# ---------------------------------------------------------------------------


async def _poll_loop() -> None:
    """Background task: poll signal-cli for new messages every POLL_INTERVAL_S seconds."""
    if not SIGNAL_PHONE_NUMBER:
        logger.warning("SIGNAL_PHONE_NUMBER not set — inbound polling disabled")
        return

    logger.info(
        "Signal inbound poller started (interval=%.1fs, number=%s)",
        POLL_INTERVAL_S,
        SIGNAL_PHONE_NUMBER,
    )
    client = _get_client()

    while True:
        try:
            resp = await client.get(
                f"{SIGNAL_CLI_URL}/v1/receive/{SIGNAL_PHONE_NUMBER}",
                timeout=10.0,
            )
            if resp.status_code == 200:
                messages = resp.json()
                for msg in messages or []:
                    await _forward_message(client, msg)
        except Exception as exc:
            logger.debug("Poll error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL_S)


async def _forward_message(client: httpx.AsyncClient, msg: dict) -> None:
    """Parse a signal-cli receive envelope and POST it to FastAPI."""
    envelope = msg.get("envelope", {})

    # Skip messages sent by ourselves
    if envelope.get("source") == SIGNAL_PHONE_NUMBER:
        return

    data_message = envelope.get("dataMessage", {})
    sync_message = envelope.get("syncMessage", {})

    # Try dataMessage first, then syncMessage.sentMessage
    if data_message:
        text = data_message.get("message", "")
        group_info = data_message.get("groupInfo", {})
        timestamp = data_message.get("timestamp")
    elif sync_message:
        sent = sync_message.get("sentMessage", {})
        text = sent.get("message", "")
        group_info = sent.get("groupInfo", {})
        timestamp = sent.get("timestamp")
    else:
        return  # Not a data message (typing indicator, receipt, etc.)

    if not text:
        return  # Skip non-text messages

    is_group = bool(group_info)
    group_id = group_info.get("groupId", "") if is_group else None
    sender_number = envelope.get("source", "unknown")
    sender_name = envelope.get("sourceName") or sender_number
    message_id = str(timestamp or datetime.utcnow().timestamp())

    payload = {
        "message_id": message_id,
        "phone_number": sender_number,
        "sender_name": sender_name,
        "text": text,
        "is_group": is_group,
        "group_id": group_id,
        "timestamp": datetime.utcnow().isoformat(),
    }

    body_str = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    if BRIDGE_SECRET:
        headers["X-Signal-Secret"] = _sign(body_str)

    try:
        await client.post(
            f"{FASTAPI_BASE_URL}{INBOUND_PATH}",
            content=body_str,
            headers=headers,
            timeout=10.0,
        )
        logger.debug("Forwarded inbound message %s to FastAPI", message_id)
    except Exception as exc:
        logger.error("Failed to forward inbound message %s: %s", message_id, exc)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(_poll_loop())
    logger.info(
        "Signal bridge started on port %d (signal-cli: %s)",
        BRIDGE_PORT,
        SIGNAL_CLI_URL,
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=BRIDGE_PORT, reload=False)
