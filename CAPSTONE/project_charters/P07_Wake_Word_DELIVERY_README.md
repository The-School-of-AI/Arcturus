## Final Architecture for Project Echo
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


  ## Techstack

  1️⃣ Wake Word

Porcupine | Openwakeword -unable to access tflite models(openwakeword native) on Windows

Rule:
Wake word thread only does detection.
No audio routing, no agents.

2️⃣ STT (streaming, cancellable, no agent logic)

faster-whisper (tiny or small)

Config (important):

vad_filter=True

Streaming chunks (200–300 ms)

CPU first (GPU optional)

STT is NOT agentic.
It streams text → that’s it.

3️⃣ TTS (fast + interruptible)

Azure Speech | piper-tts (local)


TTS must obey hard stop within <50 ms on interrupt.

4️⃣ Agent (single, deterministic, impressive)

One LLM-backed agent with fixed prompt which reads intent and triggers voice action

