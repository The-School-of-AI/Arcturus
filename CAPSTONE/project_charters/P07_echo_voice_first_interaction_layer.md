# PROJECT 7: "Echo" — Voice-First Interaction Layer


> **Inspired by:** OpenClaw (Voice Wake, Talk Mode, ElevenLabs integration)
> **Team:** Voice & Audio Engineering · **Priority:** P1 · **Duration:** 4 weeks

### Objective
Add **always-on voice interaction** to Arcturus so users can speak to their agent hands-free, with natural voice responses — making Arcturus usable while driving, cooking, or walking.

### Detailed Features

#### 7.1 Voice Wake (Hotword Detection)
- **Wake word:** Configurable wake phrase (default: "Hey Arcturus")
- **On-device detection:** Use Porcupine (Picovoice) or OpenWakeWord for low-latency, privacy-preserving wake detection
- **Continuous listening:** Background audio monitoring with minimal CPU/battery impact
- **Visual indicator:** Subtle UI indicator showing listening state

#### 7.2 Speech-to-Text (STT)
- **Streaming transcription:** Real-time speech transcription using Whisper (local) or Deepgram (cloud)
- **Multi-language:** Support for 50+ languages with auto-detection
- **Noise robustness:** Noise cancellation preprocessing for real-world environments
- **Punctuation & formatting:** Auto-punctuation and number formatting

#### 7.3 Text-to-Speech (TTS)
- **Natural voice output:** ElevenLabs (primary), Azure Speech (fallback), local TTS (Piper) for offline
- **Voice personas:** Multiple voice styles (professional, casual, energetic) — user configurable
- **Streaming TTS:** Start speaking before full response is generated for low perceived latency
- **SSML support:** Rich speech markup for emphasis, pauses, prosody control

#### 7.4 Talk Mode (Continuous Conversation)
- **Hands-free flow:** Wake → speak → get voice response → continue naturally (no re-wake needed for 30s)
- **Interruption handling:** User can interrupt agent mid-response, agent stops and re-listens
- **Conversation context:** Voice sessions maintain full conversation history like text sessions
- **Background audio:** Optional ambient sound/music while awaiting next command

#### 7.5 Voice Actions
- **Voice-triggered skills:** "Hey Arcturus, check my email" → triggers email skill
- **Voice-controlled navigation:** "Show me the dashboard" → navigate UI
- **Dictation mode:** Long-form speech → document input

#### 7.6 Deliverables
- `voice/wake.py` — hotword detection engine
- `voice/stt.py` — speech-to-text pipeline (streaming)
- `voice/tts.py` — text-to-speech pipeline (streaming)
- `voice/talk_mode.py` — continuous conversation orchestrator
- Frontend: `features/voice/` — voice UI overlay, waveform visualizer, mute/unmute controls
- Mobile/Desktop: mic access, background audio permissions

### Strategy
- Start with browser-based Web Audio API for STT/TTS, then native APIs for desktop/mobile
- Whisper for STT quality, ElevenLabs for TTS quality — both with local fallbacks for privacy mode
- Integrate voice as just another "channel" in Project 1 (Nexus) — voice messages flow through the same pipeline

---

## 20-Day Execution Addendum

### Team Split
- Single owner: Voice pipeline, wake/command flow, and UX hooks.

### Day Plan
- Days 1-5: STT/TTS baseline and command intents.
- Days 6-10: Wake mode, interruption handling, response streaming.
- Days 11-15: Device action hooks and privacy controls.
- Days 16-20: Robustness and noisy-environment testing.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p07_echo/test_voice_command_roundtrip.py`
- Integration: `tests/integration/test_echo_with_gateway_and_agentloop.py`
- CI required check: `p07-echo-voice`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Voice roundtrip must support wake, command, interruption, and mute/privacy controls with deterministic fallback to text when audio path fails.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Echo flows through Nexus routing and can trigger agent actions with trace visibility.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p07-echo-voice must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P07_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 1.2s partial transcript emission.
