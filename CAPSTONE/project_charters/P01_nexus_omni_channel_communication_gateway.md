# PROJECT 1: "Nexus" — Omni-Channel Communication Gateway


> **Inspired by:** OpenClaw (multi-channel inbox, channel routing, group messaging)
> **Team:** Platform Engineering · **Priority:** P0 · **Duration:** 3 weeks

### Objective
Build a unified incoming/outgoing message gateway that lets Arcturus respond through **any channel the user already uses** — WhatsApp, Telegram, Slack, Discord, Microsoft Teams, Signal, iMessage, Matrix, WebChat — from a single agent instance.

### Detailed Features

#### 1.1 Channel Adapters
- **WhatsApp** via Baileys (unofficial WhatsApp Web API) — full message send/receive, media, group support
- **Telegram** via grammY framework — inline keyboards, bot commands, group activation by mention
- **Slack** via Bolt SDK — threaded replies, reactions, file sharing, Slack App manifest
- **Discord** via discord.js — slash commands, embeds, voice channel awareness, role-based gating
- **Microsoft Teams** via Bot Framework SDK — adaptive cards, proactive messaging, Teams-specific threading
- **Signal** via signal-cli — encrypted messaging, group support, disappearing messages compliance
- **iMessage/BlueBubbles** via BlueBubbles REST API — Apple ecosystem bridging, tapback reactions
- **Matrix** via matrix-bot-sdk — federated messaging, end-to-end encryption support
- **Google Chat** via Chat API — spaces, cards, webhooks
- **WebChat** built-in — embeddable widget served from the Arcturus gateway itself

#### 1.2 Unified Message Bus
- Single `MessageEnvelope` schema: `{channel, sender, thread_id, content, media[], metadata}`
- Normalize all inbound messages into the envelope before routing to the agent core
- Outbound: format agent responses per channel (Markdown → Slack mrkdwn, Discord embeds, Teams adaptive cards)
- Media handling: auto-transcode images/video/audio to per-channel optimal formats

#### 1.3 Session & Routing Layer
- **Multi-agent routing:** Route different channels/contacts to isolated agent instances with separate memory contexts
- **Group activation modes:** `mention-only` vs `always-on` per group/channel
- **DM security policy:** Pairing-code flow for unknown senders (allowlist model)
- **Queue modes:** Serial processing vs parallel processing per session
- **Presence & typing indicators:** Real-time status propagation across channels

#### 1.4 Deliverables
- `channels/` directory with adapter modules per platform
- `gateway/router.py` — incoming message router with session affinity
- `gateway/formatter.py` — outbound message formatter per channel
- Config schema: `config/channels.yaml` with per-channel credentials, policies, routing rules
- Integration test suite per channel with mock servers

### Strategy
- Start with WebChat (already partially exists) and Telegram (simplest API) as proof of concept
- Add Telegram, WhatsApp and Slack in week 1
- Discord, Teams, Signal, iMessage in week 2
- Matrix, Google Chat in week 3

---

## 20-Day Execution Addendum

### Team Split
- Student A: Channel adapters and gateway backend.
- Student B: Session routing, frontend inbox/outbox, integration harness.

### Day Plan
- Days 1-5: Implement `MessageEnvelope`, WebChat + Telegram adapters, router skeleton.
- Days 6-10: Add Slack + WhatsApp adapters, session affinity, retry and dedupe.
- Days 11-15: Group activation policies, formatter matrix, failure recovery.
- Days 16-20: Hardening, docs, demo and full integration tests.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p01_nexus/test_multichannel_roundtrip.py`
- Integration: `tests/integration/test_nexus_session_affinity.py`
- CI required check: `p01-nexus-gateway`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. At least three channel adapters must pass roundtrip tests including text plus one media payload, and session affinity must remain stable across reconnects.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Nexus works with Aegis policy enforcement and memory-backed session routing without message loss.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p01-nexus-gateway must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P01_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 2.5s message processing latency.
