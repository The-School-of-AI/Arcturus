# PROJECT 13: "Orbit" — Mobile & Cross-Platform Experience


> **Inspired by:** OpenClaw (iOS/Android nodes, macOS menu bar app), existing scaling plan (Project "Gemini-Mobile")
> **Team:** Mobile Engineering · **Priority:** P1 · **Duration:** 4 weeks

### Objective
Build native **iOS and Android apps** plus a **macOS menu bar companion** that bring the full power of Arcturus to mobile devices with voice-first interaction, push notifications, and device-local capabilities.

### Detailed Features

#### 13.1 Mobile App (React Native / Expo)
- **Chat interface:** Full-featured mobile chat with Markdown rendering, code highlighting, media support
- **Voice mode:** Push-to-talk and continuous listening with Voice Wake (Project 7)
- **Camera integration:** Take photos/scan documents → send to agent for analysis
- **Screen capture:** Share screen recordings with agent for debugging/help
- **Push notifications:** Agent-initiated notifications (task complete, scheduled reminder, alert)
- **Offline mode:** Queue messages when offline, sync on reconnect
- **Widget:** Home screen widget showing latest agent response or quick actions

#### 13.2 macOS Menu Bar App
- **System tray presence:** Always-available quick access to Arcturus
- **Global hotkey:** Cmd+Shift+A → instant agent input overlay
- **Quick actions:** Quick commands without opening full UI (set timer, quick search, clipboard analysis)
- **Status indicator:** Show agent status (idle, thinking, error) in menu bar icon
- **Screen recording:** Agent can request screen recording permission for visual context

#### 13.3 Device Node Protocol
- **Node capabilities:** Each device advertises its capabilities (camera, GPS, files, notifications)
- **Remote control:** Gateway can invoke device capabilities via `node.invoke`
- **Bonjour/mDNS discovery:** Automatic device discovery on local network
- **Secure pairing:** Device pairing via QR code or pairing code

#### 13.4 Cross-Platform Sync
- **Session continuity:** Start conversation on desktop, continue on mobile seamlessly
- **Memory sync:** Shared episodic memory across devices (Project 11 integration)
- **Settings sync:** Preferences, skills, and configurations synced via cloud

#### 13.5 Deliverables
- `mobile/` — React Native (Expo) app with chat, voice, camera, notifications
- `desktop/menubar/` — macOS menu bar app (Electron or Swift)
- `nodes/protocol.py` — device node protocol handler
- `nodes/discovery.py` — Bonjour/mDNS device discovery
- Platform-specific builds: iOS App Store, Google Play Store, macOS DMG

### Strategy
- Start with mobile web (PWA) for immediate cross-platform reach
- Then React Native for native experience (iOS first given user's macOS ecosystem)
- macOS menu bar app as lightweight companion to existing Electron desktop app

---

## 20-Day Execution Addendum

### Team Split
- Single owner: mobile shell, sync hooks, and desktop quick-access node.

### Day Plan
- Days 1-5: Mobile app shell and auth/session sync.
- Days 6-10: Voice/camera/screen feature integration.
- Days 11-15: Menu bar quick command app and hotkey flow.
- Days 16-20: Offline resilience and device-node stability.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p13_orbit/test_mobile_sync_and_action.py`
- Integration: `tests/integration/test_orbit_with_nexus_echo_mnemo.py`
- CI required check: `p13-orbit-mobile`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Cross-device session continuity, offline queue replay, and at least one device action (camera/screenshot) must pass end-to-end tests.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Orbit syncs with Nexus channels, Echo voice actions, and Mnemo memory updates without divergence.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p13-orbit-mobile must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P13_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 2.0s sync propagation latency.
