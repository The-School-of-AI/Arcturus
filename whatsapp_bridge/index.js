/**
 * Arcturus WhatsApp Bridge
 *
 * Maintains a Baileys WhatsApp Web session and exposes a minimal HTTP API
 * so the Python FastAPI backend can send and receive WhatsApp messages.
 *
 * Outbound (FastAPI → Bridge):
 *   POST /send        { recipient_id, text }  → sends via Baileys
 *   GET  /health                              → session status
 *
 * Inbound (Bridge → FastAPI):
 *   On every new WhatsApp message, POSTs to:
 *   POST FASTAPI_BASE_URL/api/nexus/whatsapp/inbound
 *   with X-WA-Secret header (HMAC-SHA256 over body) for authentication.
 *
 * Environment variables:
 *   BRIDGE_PORT          HTTP port this server listens on (default: 3001)
 *   FASTAPI_BASE_URL     Base URL of the Arcturus FastAPI server (default: http://localhost:8000)
 *   WHATSAPP_BRIDGE_SECRET  Shared secret for HMAC-SHA256 auth (optional but recommended)
 *   WA_SESSION_DIR       Directory to persist Baileys session files (default: ./session)
 *   LOG_LEVEL            Pino log level (default: info)
 */

// Load .env from this directory before reading any process.env vars
require("dotenv").config({ path: require("path").join(__dirname, ".env") });

const {
  default: makeWASocket,
  DisconnectReason,
  useMultiFileAuthState,
  isJidGroup,
  fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");
const axios = require("axios");
const express = require("express");
const qrcode = require("qrcode-terminal");
const pino = require("pino");
const crypto = require("crypto");
const path = require("path");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const PORT = parseInt(process.env.BRIDGE_PORT || "3001", 10);
const FASTAPI_BASE_URL = (process.env.FASTAPI_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const INBOUND_PATH = "/api/nexus/whatsapp/inbound";
const BRIDGE_SECRET = process.env.WHATSAPP_BRIDGE_SECRET || "";
const SESSION_DIR = process.env.WA_SESSION_DIR || path.join(__dirname, "session");

const logger = pino({ level: process.env.LOG_LEVEL || "info" });

// ---------------------------------------------------------------------------
// Baileys session state
// ---------------------------------------------------------------------------

let sock = null;
let connectionState = "disconnected"; // "connecting" | "open" | "disconnected"

/**
 * Start (or restart) the Baileys WhatsApp session.
 * Called once on startup and again after unexpected disconnects.
 */
async function startBaileys() {
  connectionState = "connecting";

  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);

  // Fetch the latest WhatsApp Web version from WA servers to avoid 405 failures
  // caused by the bundled version becoming outdated after WhatsApp updates.
  const { version } = await fetchLatestBaileysVersion();
  logger.info({ version }, "Using WhatsApp Web version");

  sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false, // We handle QR ourselves via qrcode-terminal
    logger: pino({ level: "silent" }), // Suppress Baileys internal logs
  });

  // ── Connection lifecycle ──────────────────────────────────────────────────
  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      logger.info("Scan QR code with WhatsApp mobile to connect:");
      qrcode.generate(qr, { small: true });
    }

    if (connection === "open") {
      connectionState = "open";
      logger.info("WhatsApp session connected");
    }

    if (connection === "close") {
      connectionState = "disconnected";
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = statusCode === DisconnectReason.loggedOut;
      logger.warn({ statusCode, loggedOut }, "WhatsApp connection closed");

      if (!loggedOut) {
        // Reconnect after 5 s backoff (don't loop on explicit logout)
        logger.info("Reconnecting in 5 s…");
        setTimeout(startBaileys, 5000);
      } else {
        logger.error("Session logged out — delete ./session and restart to re-scan QR");
      }
    }
  });

  // ── Persist updated credentials ───────────────────────────────────────────
  sock.ev.on("creds.update", saveCreds);

  // ── Forward inbound messages to FastAPI ───────────────────────────────────
  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    // "notify" = real new messages; "append" = historical (on reconnect) — skip append
    if (type !== "notify") return;

    for (const msg of messages) {
      // Skip messages sent by the bot itself
      if (msg.key.fromMe) continue;

      // Skip WhatsApp status broadcasts
      if (msg.key.remoteJid === "status@broadcast") continue;

      const jid = msg.key.remoteJid;
      const isGroup = isJidGroup(jid);

      // For group messages, msg.key.participant holds the sender's JID
      const senderJid = isGroup ? (msg.key.participant || "") : jid;
      const phoneNumber = senderJid.replace(/@[a-z.]+$/, ""); // Strip @s.whatsapp.net etc.
      const groupId = isGroup ? jid : null;

      // Display name: push name or fall back to phone number
      const contactName = msg.pushName || phoneNumber;

      // Extract text from various message types
      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        msg.message?.videoMessage?.caption ||
        "";

      // Skip non-text messages (media without caption, stickers, etc.)
      if (!text) continue;

      const payload = {
        message_id: msg.key.id,
        phone_number: phoneNumber,
        contact_name: contactName,
        text,
        is_group: isGroup,
        group_id: groupId,
        timestamp: msg.messageTimestamp
          ? new Date(Number(msg.messageTimestamp) * 1000).toISOString()
          : new Date().toISOString(),
      };

      // Compute HMAC-SHA256 signature over the serialised body
      const bodyStr = JSON.stringify(payload);
      const sig = BRIDGE_SECRET
        ? crypto.createHmac("sha256", BRIDGE_SECRET).update(bodyStr).digest("hex")
        : "";

      try {
        await axios.post(`${FASTAPI_BASE_URL}${INBOUND_PATH}`, payload, {
          headers: {
            "Content-Type": "application/json",
            ...(sig ? { "X-WA-Secret": sig } : {}),
          },
          timeout: 10000,
        });
        logger.debug({ message_id: msg.key.id }, "Forwarded inbound message to FastAPI");
      } catch (err) {
        logger.error(
          { err: err.message, message_id: msg.key.id },
          "Failed to forward inbound message to FastAPI"
        );
      }
    }
  });
}

// ---------------------------------------------------------------------------
// HTTP server
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json());

/**
 * Middleware: verify that outbound requests FROM FastAPI TO the bridge
 * carry a valid X-WA-Secret header.  Skipped when BRIDGE_SECRET is empty.
 */
function verifyBridgeSecret(req, res, next) {
  if (!BRIDGE_SECRET) return next(); // Dev mode — no secret configured

  const sig = req.headers["x-wa-secret"];
  if (!sig) {
    return res.status(401).json({ ok: false, error: "Missing X-WA-Secret header" });
  }

  const bodyStr = JSON.stringify(req.body);
  const expected = crypto
    .createHmac("sha256", BRIDGE_SECRET)
    .update(bodyStr)
    .digest("hex");

  // Constant-time comparison to prevent timing attacks
  try {
    if (!crypto.timingSafeEqual(Buffer.from(sig, "utf8"), Buffer.from(expected, "utf8"))) {
      return res.status(403).json({ ok: false, error: "Invalid X-WA-Secret signature" });
    }
  } catch (_) {
    return res.status(403).json({ ok: false, error: "Invalid X-WA-Secret signature" });
  }

  next();
}

/**
 * POST /send
 * Body: { recipient_id: string, text: string }
 * Sends a text message to the given WhatsApp phone number or JID.
 */
app.post("/send", verifyBridgeSecret, async (req, res) => {
  const { recipient_id, text } = req.body;

  if (!recipient_id || !text) {
    return res.status(400).json({ ok: false, error: "recipient_id and text are required" });
  }

  if (connectionState !== "open" || !sock) {
    return res.status(503).json({
      ok: false,
      error: "WhatsApp session not connected",
      state: connectionState,
    });
  }

  // Normalise JID: bare phone numbers get @s.whatsapp.net; group JIDs pass through
  const jid = recipient_id.includes("@") ? recipient_id : `${recipient_id}@s.whatsapp.net`;

  try {
    const result = await sock.sendMessage(jid, { text });
    logger.info({ jid, message_id: result?.key?.id }, "Outbound message sent");
    return res.json({
      ok: true,
      message_id: result?.key?.id || null,
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    logger.error({ err: err.message, jid }, "Failed to send outbound message");
    return res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * GET /health
 * Returns the current session status.
 */
app.get("/health", (_req, res) => {
  res.json({
    status: connectionState,
    connected: connectionState === "open",
    session_dir: SESSION_DIR,
  });
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

app.listen(PORT, () => {
  logger.info({ port: PORT, fastapi: FASTAPI_BASE_URL }, "WhatsApp bridge started");
  startBaileys().catch((err) => {
    logger.error({ err: err.message }, "Baileys startup failed");
    process.exit(1);
  });
});
