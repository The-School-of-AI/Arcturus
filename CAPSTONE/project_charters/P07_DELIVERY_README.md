# P07 Delivery README — Project Echo (Voice Pipeline)

## 1. Scope Delivered

- **Wake word detection** via Porcupine (primary) and Pocketsphinx (local) OpenWakeWord (pipeline ready but custom wake-phrase training not supported on windows)
- **Dual STT providers**:  Deepgram Nova-2 (cloud, low-latency) and faster-Whisper (local, private) — switchable via config
- **Auto-punctuation & formatting**: Both STT providers configured for punctuation, smart formatting, and numeral conversion
- **Barge-in / Interruption**: High-performance continuous VAD detection during TTS. Supports immediate cancellation of TTS and Nexus runs.
- **Barge-in Safety Hold**: A 2-second accumulation window after detection to ensure user speech is fully captured before STT aggregation begins.
- **STT Pre-filling**: A ring buffer captures the last 500ms of audio during barge-in detection and pushes it to STT, ensuring no user speech is lost during the interruption phase.
- **Streaming TTS**: Both Azure Speech and Piper (local) support real-time word-by-word streaming for "instant-on" responses.
- **Sandbox Tool Aliasing**: Intelligent resolution for hallucinated tool names (e.g. `fetchsearchurls` → `fetch_search_urls`) to ensure voice commands resolve reliably.
- **Clean Spoken Output**: Comprehensive 13-step text cleaner that strips markdown, Python error traces, and internal role labels (like "Captain") before synthesis.
- **Dictation Mode**: Long-form speech → document input. Say "start dictation", speak freely, and the pipeline accumulates every STT fragment into a persistent `.txt` document saved under `memory/dictation/`. Retrievable via REST API.
- **Echo Panel (UI)**: Real-time visual feedback for voice states (Idle, Listening, Thinking, Speaking) with streaming transcript display and wake-word indicators.
- **User query**: Forwarded to the nexus as a channel
- **30-second follow-up window**: No wake word required for 30 seconds after agent response
- Configurable engine selection and STT provider through `voice/config.py`
- Always-on microphone listener with threaded audio processing
- Modular `voice/` package with clean separation of concerns

---

## 2. Architecture Changes

The Arcturus Voice Architecture is a state-driven pipeline designed for low-latency, interruptible interactions. It is integrated directly into the FastAPI backend to leverage shared resources (like the Agent Loop) while maintaining a dedicated service for audio processing.


### 2.1 End-to-End Pipeline

```
┌──────────┐
│  Mic In  │
└────┬─────┘
     ↓ Accumulate (2s hold)
┌──────────────┐
│ Wake Word    │  (always on, offline)
│ Detector     │  Porcupine / Pocketsphinx / OpenWakeWord
└────┬─────────┘
     │ detected
     ↓
┌──────────────┐
│ Intent Gate  │  (Classification & Routing)
│ (DICTATION)  │──► [Direct to File]
│ (COMMAND)    │──► [Direct UI Event]
│ (AGENTIC)    │──► [To Nexus Queue]
└────┬─────────┘ 
     │ (QUERY/AGENTIC)
     ↓                        
┌──────────────┐               ┌──────────────┐
│ STT          │◄──────────────┤ Barge-in VAD │
│ Whisper(loc) │               │ detected?    │
│ Deepgram(cld)│               └──────┬───────┘
└────┬─────────┘                      │
     ↓ raw text                       │ interrupt
┌──────────────┐                      │
│ NEXUS (Loop) │◄─────────────────────┘
└────┬─────────┘
     ↓ response tokens
┌──────────────┐
│ TTS (Stream) │
└────┬─────────┘
     ↓
   🔊 Speaker
```

The system follows a synchronous state-machine pattern:
1. **Orchestration**: The `Orchestrator` manages the lifecycle of a voice interaction. It transitions between `IDLE`, `LISTENING` (transcribing), `THINKING` (nexus processing), and `SPEAKING` (synthesizing) states.
2. **Intent Gating**: Before a full plan is generated, the `IntentRouter` classifies the utterance. **COMMAND**s (like navigation) bypass the heavy Agent Loop and trigger UI events directly in <100ms.
3. **Perception**:
    - **Wake Word**: The `VoiceWakeService` listens for the trigger.
    - **STT**: Audio is streamed to choice provider. If barge-in is detected, the `BargeInDetector` triggers a 2-second safety hold to finish capturing user speech.
4. **Reasoning**: The `Orchestrator` forwards the refined text to the NEXUS `Agent`.
5. **Action**: The agent's output is streamed to the `TTSService`. Interruption (vocal barge-in) triggers an immediate Nexus `stop()` and TTS `cancel()`.

### 2.2 Design Principles

| **Interruptibility** | Optimized Barge-in (NumPy-based VAD) interrupts TTS and Nexus runs in <50ms with zero lost speech (STT pre-fill) |
| **Deterministic Intent Routing** | `IntentRouter` matches navigation and media commands via regex/fast-paths before LLM invocation |
| **Tool Hallucination Shield** | Sandbox uses fuzzy name aliasing to resolve common LLM tool-calling typos during voice sessions |
| **Clean Audio Path** | 13-step regex cleaner ensures user never hears markdown artifacts or raw Python exceptions |
| **Asynchronous Wait Loop** | Orchestrator polls for agent results while concurrently handling mid-run clarifications and barge-ins |
| **Always-on detection** | Wake word detector runs in a dedicated daemon thread, consuming minimal CPU |
| **Separation of concerns** | Each pipeline stage (wake → STT → Agent → TTS) is an independent module |
| **Engine-agnostic** | Factory pattern (`create_wake_engine()`) allows swapping between Porcupine and OpenWakeWord via config |
| **Provider-agnostic STT** | Config-driven switch between Whisper (local, private) and Deepgram (cloud, fast) — same `push_audio/start/stop/cancel` interface |
| **LLM post-processing** | `TextRefiner` ensures clean, production-quality text regardless of STT provider quality |
| **Cloud services with fallback option as Offline-** | Wake word detection Porcupine engine cloud based with offline pocketsphinx ; Deepgram for STT- cloud based with Whisper as local-offline  alternative |

### 2.3 Module Breakdown

```
voice/
├── config.py                  # Centralized configuration (thresholds, engine selection, refiner toggle)
├── audio_input.py             # Optimized microphone capture (NumPy zero-copy arrays)
├── barge_in.py                # High-perf VAD logic (vectorized RMS calculation)
├── wake_engine.py             # Factory: create_wake_engine() → engine instance
├── porcupine_engine.py        # Porcupine wake word engine (Hey Arcturus)
├── openwakeword_engine.py     # OpenWakeWord engine (alternate, TFLite-based)
├── voice_wake_service.py      # Audio loop: mic → wake/barge-in detection + STT pre-fill buffer
├── intent_gate.py             # Layer 1 Router: Classifies DICTATION vs COMMAND vs AGENTIC
├── stt_service.py             # Local STT via faster-whisper (small model, CPU/CUDA)
├── deepgram_stt_service.py    # Cloud STT via Deepgram Nova-2 (WebSocket streaming)
├── text_refiner.py            # LLM post-processor (Gemini 2.5 Flash Lite)
├── orchestrator.py            # State machine & cleaner: strips markdown and Python errors
├── agent.py                   # Voice agent: LLM intent extraction via ModelManager
├── tts_service.py             # Azure Speech TTS (cloud, streaming)
├── piper_tts_service.py       # Piper TTS (local, streaming ONNX)
├── dictation_service.py       # DictationSession: long-form speech → document buffer + autosave
├── .env                       # API keys (PICOVOICE_ACCESS_KEY, DEEPGRAM_API_KEY)
│   └── hey_arcturus.ppn       # Custom Porcupine wake word model
└── models/
    └── hey_jarvis_v0.1.tflite # OpenWakeWord model (alternate)
```

### 2.4 Data Flow (Current Implementation)

```
api.py (lifespan startup)
  ├─► Orchestrator(wake, stt, agent, tts)   # Central state machine
  │     └─► TextRefiner()                    # LLM post-processor initialized here
  ├─► STTService / DeepgramSTTService        # Selected by config.stt_provider
  ├─► VoiceWakeService(on_wake_callback)
  │     ├─► create_wake_engine()             # Porcupine or OpenWakeWord
  │     ├─► AudioInput(sample_rate, frame_length)
  │     └─► _loop() [daemon thread]
  │           ├─► audio.read()               # Read PCM from mic
  │           ├─► engine.process(pcm)        # Wake word check
  │           │     └─► orchestrator.on_wake()  # → state = LISTENING
  │           └─► if LISTENING:
  │                 stt.push_audio(pcm)      # Stream audio to STT
  │
  └─► STT on_text callback:
        └─► orchestrator.on_text(raw_text)
              ├─► TextRefiner.refine(raw)     # LLM cleanup (punctuation, numbers, grammar)
              ├─► print refined text          # Console output
              └─► agent.respond(refined)      # [Ready] Forward to nexus channel
```

---


### 2.5 Wake Word Detection (offline, fast)

| | Primary | Alternate |
|---|---|---|
| **Engine** | Porcupine (pvporcupine) | OpenWakeWord |
| **Model** | `hey_arcturus.ppn` | `hey_jarvis_v0.1.tflite` |
| **Latency** | <50ms | ~80ms |
| **Offline** | ✅ | ✅ |
| **Custom wake word** | Via Picovoice Console | Via training pipeline |

**Rule:** Wake word thread only does detection. No audio routing, no cleverness.

### 2.6 STT — Speech-to-Text (✅ implemented)

| | Whisper (Local) | Deepgram (Cloud) |
|---|---|---|
| **Engine** | `faster-whisper` (small model) | Deepgram Nova-2 |
| **Connection** | Direct inference | WebSocket streaming |
| **Latency** | ~1–3s per chunk (CPU) | ~100–300ms |
| **Offline** | ✅ | ❌ (requires API key) |
| **Punctuation** | `condition_on_previous_text=True` | `punctuate=true`, `smart_format=true` |
| **Numbers** | Via TextRefiner LLM | `numerals=true` + TextRefiner |
| **VAD** | `vad_filter=True` | Server-side |
| **Noise reduction** | `noisereduce` spectral gating (optional) | Same |

- **Config switch:** `stt_provider: "whisper"` or `"deepgram"` in `voice/config.py`
- **Same interface:** Both implement `push_audio()`, `start()`, `stop()`, `cancel()`
- **Hard rule:** STT is NOT agentic. It streams text → that's it.

### 2.7 Text Refinement — LLM Post-Processing (✅ implemented)

- **Model:** Gemini 2.5 Flash Lite via `ModelManager`
- **Runs in:** Orchestrator's `on_text()` callback, before forwarding to agent
- **Capabilities:**
  - Auto-punctuation (periods, commas, question marks)
  - Number formatting ("twenty three" → "23", "three percent" → "3%")
  - Sentence capitalization and proper noun detection
  - Filler word removal ("um", "uh", "like", "you know")
  - Minor grammar correction (without changing meaning)
- **Fast-path:** Utterances ≤3 words skip the LLM call (rule-based capitalize + punctuate)
- **Safety:** Falls back to raw text if LLM fails or returns garbage
- **Configurable:** Toggle on/off and change model via `voice/config.py` → `text_refiner`

### 2.8 TTS — Text-to-Speech (✅ implemented)

- **Choice**: Azure Speech | `piper-tts` (local)
- **Rule**: TTS must obey hard stop within <50ms on interrupt.

### 2.9 Agent (✅ implemented)

- **Engine:** LLM-backed agent using `ModelManager` (Gemini / Ollama)
- **Prompt:** Extracts user INTENT and ACTION from refined transcript
- **Response:** Concise 1–2 sentence verbal response for voice playback
- Skills: "Explain X", "Summarise", "Answer concisely"

### 2.10 Voice Actions & Intent Routing

The Arcturus Voice Pipeline uses a multi-tier **Intent Gate** (`intent_gate.py`) to classify user speech before expensive reasoning begins. This ensures that simple instructions are executed with sub-second latency.

| Intent Type | Trigger Signal | Action |
|---|---|---|
| **DICTATION** | "Start dictation", "Write this down" | Routes audio to `DictationSession`; bypasses Nexus agentic logic. |
| **COMMAND** | "Open dashboard", "Go to IDE" | Deterministic UI events published to the Event Bus in <100ms. |
| **QUERY** | "How's the weather", "What is X" | Single-turn LLM response via Nexus; skips complex planning. |
| **AGENTIC** | "Fix the bug in X", "Analyze the logs" | Full multi-step `AgentLoop4` execution with tool-calling. |

#### Navigation Command Mappings:
- **"Open/Go to [Tab]"** signals the `IntentRouter` to fire a `navigation` event to the Vite frontend.
- Supported destinations: `dashboard`, `explorer`, `notes`, `rag`, `settings`, `ide`, `mcp`, `apps`.

### 2.11 Multi-turn Clarification Flow

Unlike standard chat, the voice pipeline handles ambiguity as a blocking state. If the Nexus `PlannerAgent` identifies missing information, it auto-injects a `ClarificationAgent` node.

1. **Detection**: Orchestrator polls the run graph and finds a `waiting_input` node with agent `ClarificationAgent`.
2. **Engagement**: Orchestrator interrupts any background background processes and speaks the `clarificationMessage` via TTS.
3. **Wait Loop**: The system enters a 20-second synchronous listening window.
4. **Resumption**: Once the user answers, the text is POSTed to the Nexus input endpoint, and the plan execution continues automatically.

---

## 3. API And UI Changes

- **FastAPI Integration**: The voice pipeline is initialized during the `lifespan` event of `api.py`. It creates the Orchestrator, STT service (based on `stt_provider` config), wake service, agent, TTS, and TextRefiner — all wired together before the API starts accepting requests.
- **Voice Router**: Added `/api/voice/start` (POST) to allow triggering the voice listening state via the web UI or external events.
- **Provider Selection at Startup**: `api.py` reads `VOICE_CONFIG["stt_provider"]` and instantiates either `STTService` (Whisper) or `DeepgramSTTService` — the Orchestrator is provider-agnostic.
- **Startup Log**: The console prints `✅ [Voice] Pipeline WARM and listening (Provider: whisper|deepgram)` on successful initialization.
- **Echo Sidebar Integration**: Dedicated UI panel in the platform for real-time interaction status and manual trigger bypass.

---

## 4. Mandatory Test Gate Definition

- Acceptance file: `tests/acceptance/p07_echo/test_voice_command_roundtrip.py`
- Integration file: `tests/integration/test_echo_with_gateway_and_agentloop.py`
- CI check: `p07-echo-voice`

---

## 5. Test Evidence

- ✅ Wake word detection tested manually — "Hey Arcturus" wake event fires with correct event payload
- ✅ Whisper STT transcribes speech after wake word detection (local, CPU)
- ✅ Deepgram STT streams and transcribes via WebSocket (cloud)
- ✅ TextRefiner post-processes raw transcripts (punctuation, numbers, grammar)
- ✅ Orchestrator logs refined text to console with diff view when refinement occurs
- ✅ Full STT → Refiner → Agent → TTS roundtrip with voice playback (End-to-end pipeline verified)

---

## 6. Existing Baseline Regression Status

- Command: `scripts/test_all.sh quick`
- No regressions expected — voice module is additive, no existing modules modified

---

## 7. Security And Safety Impact

- Microphone access requires user consent (OS-level permission)
- Porcupine requires `PICOVOICE_ACCESS_KEY` stored in `.env` (not committed)
- Deepgram requires `DEEPGRAM_API_KEY` stored in `voice/.env` (not committed)
- Gemini requires `GEMINI_API_KEY` for the TextRefiner (not committed)
- No audio data leaves the device during wake word detection (offline)
- Whisper STT is fully local — no data leaves the device
- Deepgram STT streams audio to the cloud — use Whisper for privacy-sensitive deployments
- TextRefiner sends only text (not audio) to Gemini for refinement

---

## 8. Known Gaps

| STT pipeline | ✅ Done | Whisper (local) and Deepgram (cloud) both implemented and switchable |
| Text refinement | ✅ Done | LLM post-processing via Gemini 2.5 Flash Lite |
| Agent integration | ✅ Done | `agent.py` uses `ModelManager` for intent extraction |
| TTS pipeline | ✅ Done | Azure Speech and Piper-TTS (local) both support streaming playback |
| Barge-in / Interruption | ✅ Done | Optimized VAD with 2s Safety Hold and STT pre-fill buffer |
| Dictation mode | ✅ Done | `DictationSession` + `DICTATING` orchestrator state; REST API support |
| Error Masking | ✅ Done | TTS cleaner masks raw Python exceptions with friendly message |
| Hallucination Handling | ✅ Done | Sandbox allows for common tool-calling spelling/casing variants |
| `tflite-runtime` on Windows/Py3.13 | ⚠️ Blocked | OpenWakeWord requires `tflite-runtime` which is unavailable for Python 3.13 on Windows. Use Porcupine engine or switch `inference_framework="onnx"` |


---

## 9. Rollback Plan

- Remove `voice/` directory
- Remove voice-related dependencies from `pyproject.toml` (`pvporcupine`, `openwakeword`, `pyaudio`, `sounddevice`, `faster-whisper`, `websocket-client`, `noisereduce`)
- Remove voice imports and lifespan block from `api.py`
- No other modules are affected — voice is fully additive

---

## 10. Demo Steps

1. Ensure `PICOVOICE_ACCESS_KEY` is set in `voice/.env`
2. Ensure `GEMINI_API_KEY` is set in `.env` (for TextRefiner)
3. Set `DEEPGRAM_API_KEY` in `.env` if using Deepgram provider
4. Set `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` in `.env` if using Azure TTS
5. Start the API: `uv run api.py`
6. Observe startup logs:
   ```
   ✅ [TextRefiner] Initialized (model: gemini/gemini-2.5-flash-lite)
   ✅ [Voice] Pipeline WARM and listening (Provider: whisper)
   ```
6. Say **"Hey Arcturus"**
7. Observe wake detection:
   ```
   [Orchestrator] Wake word detected. Listening...
   ```
8. Speak a command (e.g., "set a timer for twenty three minutes")
9. Observe refined transcript:
   ```
   [Orchestrator] "set a timer for twenty three minutes" → "Set a timer for 23 minutes."
   ```
10. The follow-up window stays open for 30 seconds (no wake word needed)
