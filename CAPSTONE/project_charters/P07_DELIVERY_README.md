# P07 Delivery README — Project Echo (Voice Pipeline)

## 1. Scope Delivered

- **Wake word detection** via Porcupine (primary) and OpenWakeWord (alternate)
- **30-second follow-up window**: No wake word required for 30 seconds after agent response
- Configurable engine selection through `voice/config.py`
- Always-on microphone listener with threaded audio processing
- Placeholder hook for STT pipeline trigger on wake word detection
- Modular `voice/` package with clean separation of concerns

---

## 2. Architecture Changes

The Arcturus Voice Architecture is a state-driven pipeline designed for low-latency, interruptible interactions. It is integrated directly into the FastAPI backend to leverage shared resources (like the Agent Loop) while maintaining a dedicated service for audio processing.


### 2.1 End-to-End Pipeline

```
┌──────────┐
│  Mic In  │
└────┬─────┘
     ↓
┌──────────────┐
│ Wake Word    │  (always on)
│ Detector     │
└────┬─────────┘
     │ detected
     ↓
┌──────────────┐
│ Audio Stream │───────────────┐
└────┬─────────┘               │
     ↓                         │ interrupt
┌──────────────┐               │
│ Streaming    │               │
│ STT          │◄──────────────┘
└────┬─────────┘
     ↓ partial/final text
┌──────────────┐
│ Agent        │  (ONE agent)
└────┬─────────┘
     ↓ response tokens
┌──────────────┐
│ Streaming    │
│ TTS          │
└────┬─────────┘
     ↓
  🔊 Speaker
```

The system follows a synchronous state-machine pattern:
1. **Orchestration**: The `Orchestrator` manages the lifecycle of a voice interaction. It transitions between `IDLE`, `LISTENING` (transcribing), and `SPEAKING` (synthesizing) states, ensuring that only one phase is active at a time while allowing for immediate cancellation/preemption.
2. **Perception**:
    - **Wake Word**: The `VoiceWakeService` (Porcupine-based) listens for the "Hey Arcturus" trigger.
    - **STT**: Once triggered, the `STTService` captures the live audio stream and converts it to text.
3. **Reasoning**: The `Orchestrator` passes the transcribed text to the `AgentLoop4` (the core agentic engine), which processes the query using its planning and tool-calling capabilities.
4. **Action**: The agent's text output is piped to the `TTSService` for audio synthesis and playback.

### 2.2 Design Principles

| Principle | Detail |
|---|---|
| **Always-on detection** | Wake word detector runs in a dedicated daemon thread, consuming minimal CPU |
| **Separation of concerns** | Each pipeline stage (wake → STT → Agent → TTS) is an independent module |
| **Interruptibility** | Audio stream supports barge-in; a new wake word can interrupt ongoing TTS |
| **Engine-agnostic** | Factory pattern (`create_wake_engine()`) allows swapping between Porcupine and OpenWakeWord via config |
| **Offline-first** | Wake word detection is fully offline; STT and TTS are designed for local-first with cloud fallback |

### 2.3 Module Breakdown

```
voice/
├── config.py                  # Centralized configuration (engine selection, paths, thresholds)
├── audio_input.py             # Microphone capture (PyAudio, 16kHz mono PCM)
├── wake_engine.py             # Factory: create_wake_engine() → engine instance
├── porcupine_engine.py        # Porcupine wake word engine + STT trigger placeholder
├── openwakeword_engine.py     # OpenWakeWord engine (alternate, TFLite-based)
├── voice_wake_service.py      # Orchestrator: ties audio → engine → callback in a thread
├── keywords/
│   └── hey_arcturus.ppn       # Custom Porcupine wake word model
└── models/
    └── hey_jarvis_v0.1.tflite # OpenWakeWord model (alternate)-- to be finished
```

### 2.4 Data Flow (Current Implementation)

```
main.py
  └─► VoiceWakeService(on_wake_callback)
        ├─► create_wake_engine()          # Returns PorcupineWakeEngine or OpenWakeWordEngine
        ├─► AudioInput(sample_rate, frame_length)  # Opens mic stream
        └─► _loop() [daemon thread]
              ├─► audio.read()            # Read PCM frame from mic
              ├─► engine.process(pcm)     # Check for wake word
              │     └─► on_wake_detected()  # 🎙️ STT trigger placeholder
              └─► on_wake(event_dict)     # Fire callback with wake event
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

### 2.6 STT — Speech-to-Text (🔲 placeholder)

- **Choice:** `faster-whisper` (tiny or small model)
- **Config:** `vad_filter=True`, streaming chunks (200–300ms), CPU first
- **Hard rule:** STT is NOT agentic. It streams text → that's it.

### 2.7 TTS — Text-to-Speech (🔲 placeholder)

- **Choice:** Azure Speech  | `piper-tts` (local), fallback: Coqui TTS
- **Rule:** TTS must obey hard stop within <50ms on interrupt.

### 2.8 Agent (🔲 placeholder)

- **Choice:** One LLM-backed agent with fixed prompt
- No tools. No memory. No planning.
- Skills: "Explain X", "Summarise", "Answer concisely"

---

## 3. API And UI Changes

- **FastAPI Integration**: The voice pipeline is now part of the central API. It is initialized in the `lifespan` event of `api.py`.
- **Voice Router**: Added `/api/voice/start` (POST) to allow triggering the voice listening state via the web UI or external events.
- **Shared State**: The `Orchestrator` uses the same `AgentLoop4` instance as the REST API, ensuring consistent memory and context across voice and text interfaces.

---

## 4. Mandatory Test Gate Definition

- Acceptance file: `tests/acceptance/p07_echo/test_voice_command_roundtrip.py`
- Integration file: `tests/integration/test_echo_with_gateway_and_agentloop.py`
- CI check: `p07-echo-voice`

---

## 5. Test Evidence

- ✅ Wake word detection tested manually (`uv run wake_word.py`)
- ✅ "Hey Arcturus" wake event fires with correct event payload
- 🔲 STT → Agent → TTS roundtrip (pending pipeline integration)

---

## 6. Existing Baseline Regression Status

- Command: `scripts/test_all.sh quick`
- No regressions expected — voice module is additive, no existing modules modified

---

## 7. Security And Safety Impact

- Microphone access requires user consent (OS-level permission)
- Porcupine requires `PICOVOICE_ACCESS_KEY` stored in `.env` (not committed)
- No audio data leaves the device during wake word detection (offline)
- Future STT: local-first by default (faster-whisper), no cloud dependency

---

## 8. Known Gaps

| Gap | Status | Notes |
|---|---|---|
| STT pipeline | 🔲 Placeholder | `on_wake_detected()` in `porcupine_engine.py` |
| TTS pipeline | 🔲 Not started | Needs piper-tts integration |
| Agent integration | 🔲 Not started | Wire transcribed text → agent → TTS |
| Barge-in / interrupt | 🔲 Design only | Wake word during TTS should cancel playback |
| `tflite-runtime` on Windows/Py3.13 | ⚠️ Blocked | OpenWakeWord requires `tflite-runtime` which is unavailable for Python 3.13 on Windows. Use Porcupine engine or switch `inference_framework="onnx"` |

---

## 9. Rollback Plan

- Remove `voice/` directory
- Remove voice-related dependencies from `pyproject.toml` (`pvporcupine`, `openwakeword`, `pyaudio`, `sounddevice`)
- No other modules are affected

---

## 10. Demo Steps

1. Ensure `PICOVOICE_ACCESS_KEY` is set in `voice/.env`
2. Run: `uv run wake_word.py`
3. Say **"Hey Arcturus"**
4. Observe wake event in terminal:
   ```
   🔥 WAKE EVENT: {'type': 'VOICE_WAKE', 'timestamp': '...', 'wake_word': 'Hey Arcturus'}
   ```
5. Press Enter to stop
