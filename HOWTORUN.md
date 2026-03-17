cd platform-frontend
npm run dev
npm run dev:all for frontend and backend

uv run Arcturus/app.py

to run RAG (index files)
uv run Arcturus/mcp_servers/server_rag.py

npm run electron:dev:all

## Echo Voice System (Local-First)

All voice services run locally — zero cloud API keys needed.

### Prerequisites

```bash
# Voice STT (Moonshine — 5x faster than Whisper, streaming)
pip install moonshine-voice

# Voice TTS (Kokoro — 82M params, 36x real-time, high quality)
pip install kokoro-onnx
brew install espeak-ng   # Required by Kokoro for phonemization (macOS)

# Kokoro model files (auto-downloaded to voice/kokoro_models/ during setup)
# If missing, download manually:
#   curl -L -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
#   curl -L -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
#   Place both files in voice/kokoro_models/

# Intent classification (Ollama + Gemma 3)
ollama pull gemma3:4b

# Optional: noise reduction for STT
pip install noisereduce
```

### Voice Stack

| Component | Provider | Notes |
|-----------|----------|-------|
| Wake Word | OpenWakeWord | Local, no API key |
| STT | Moonshine | Local, streaming, 5x faster than Whisper |
| TTS | Kokoro ONNX | Local, 82M params, 60+ voices |
| Intent Gate | Ollama Gemma 3 | Local, falls back to rule-based |

Config: `voice/config.py` — change `stt_provider`, `tts_provider`, `engine` to switch providers.