# voice/config.py
#
# API keys are read from the PROJECT ROOT .env (the same file used by all
# other Arcturus modules).  Do NOT place a separate voice/.env file —
# keys defined there would shadow the global ones and cause confusion.
# Keys needed by voice modules:
#   PICOVOICE_ACCESS_KEY  — wake word detection (Porcupine)
#   DEEPGRAM_API_KEY      — cloud STT (Deepgram Nova-2)
#   AZURE_SPEECH_KEY      — TTS (Azure Neural Speech)
#   AZURE_SPEECH_REGION   — TTS region (e.g. "eastus")

import os
from pathlib import Path
from dotenv import load_dotenv

_VOICE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = Path(_VOICE_DIR).parent

# Load the project root .env once for the entire voice package.
# override=False means already-set env vars (e.g. from a shell export) win.
load_dotenv(_PROJECT_ROOT / ".env", override=False)

VOICE_CONFIG = {
    # Master switch
    "enabled": True,

    # Wake engine selection
    # Options: "porcupine", "openwakeword", "pocketsphinx"
    "engine": "porcupine",
    "wake_word": "Hey Arcturus",

    # -----------------------------
    # Porcupine configuration
    # -----------------------------
    "porcupine": {
        # Path to custom .ppn file (recommended)
        "keyword_path": os.path.join(_VOICE_DIR, "keywords", "Hey-Arcturus_en_windows_v4_0_0.ppn"),

        # Sensitivity: 0.0 (least sensitive) → 1.0 (most sensitive)
        # Higher = fewer missed detections, but more false positives.
        # 0.75 is a good balance for real-world noisy environments.
        "sensitivity": 0.6,
    },

    # -----------------------------
    # OpenWakeWord configuration
    # -----------------------------
    "openwakeword": {
        # Path to trained .tflite model
        "model_path": os.path.join(_VOICE_DIR, "models", "hey_jarvis_v0.1.tflite"),

        # Detection threshold (probability)
        # Higher = fewer false positives
        "threshold": 0.65,

        # OpenWakeWord expects 16kHz mono
        "sample_rate": 16000,

        # Audio chunk size (flexible)
        "frame_length": 512,
    },

    # -----------------------------
    # PocketSphinx configuration (offline fallback, no API key)
    # -----------------------------
    "pocketsphinx": {
        # Keyphrase to detect (must be pronounceable English words)
        "keyphrase": "HeyArcturus",

        # Detection threshold — lower = more sensitive, higher = fewer false positives
        # Typical range: 1e-30 (very sensitive) to 1e-5 (strict)
        "kws_threshold": 1e-20,

        # Optional: custom acoustic model / dictionary paths
        # Leave as None to use PocketSphinx bundled defaults
        "hmm_path": os.path.join(_VOICE_DIR,"model","en-us","en-us"),    
        "dict_path": os.path.join(_VOICE_DIR,"model","en-us", "cmudict-en-us.dict"),

        # PocketSphinx expects 16kHz mono
        "sample_rate": 16000,
        "frame_length": 1024,
    },

    # -----------------------------
    # Shared wake behavior
    # -----------------------------
    "wake_behavior": {
        # Minimum seconds between wake events
        "debounce_seconds": 1.0,

        # Pause wake listening while agent is speaking
        "pause_while_speaking": True,
    },

    # -----------------------------
    # Barge-in configuration (mic→TTS interruption)
    # -----------------------------
    # These thresholds intentionally bias toward *near-field* speech to avoid
    # distant talkers, background TV, or speaker echo triggering interruption.
    # Stricter values reduce self-interrupt when TTS is picked up by the mic.
    "barge_in": {
        # Suppress barge-in detection for this long after TTS starts.
        # Azure TTS has 200-600ms of synthesis latency before audio reaches the speaker,
        # so 1000ms was only ~400-800ms of real echo suppression. 1500ms is safer.
        "grace_ms": 1500,

        # Continuous speech required before interrupt.
        # 120ms = lower bound of the 120-200ms design band → fastest reliable detection.
        "min_speech_ms": 120,

        # Energy must be at least this multiple of ambient noise floor.
        "energy_ratio": 2.7,

        # Near-field gates (int16 RMS units).
        # 1100 provides a harder gate against speaker echo in quiet rooms where the
        # noise floor is very low (making the ratio gate easier to trip).
        "min_absolute_rms": 1100,
        "min_rms_above_noise": 250,
    },

    # -----------------------------
    # STT configuration
    # -----------------------------
    # Provider: "whisper" (local, private) or "deepgram" (cloud, faster)
    "stt_provider": "deepgram",

    "stt": {
        # Shared
        "sample_rate": 16000,
        "noise_reduce": True,

        # Whisper-specific (local)
        "whisper": {
            "model_size": "small",   # tiny, base, small, medium, large-v2
            "device": "cpu",         # cpu or cuda
            "language": "en",        # or None for auto-detect
        },

        # Deepgram-specific (cloud)
        "deepgram": {
            # API key loaded from env var DEEPGRAM_API_KEY
            "language": "en",        # or "multi" for auto-detect
        },
    },

    # -----------------------------
    # TTS configuration
    # -----------------------------
    # Provider selection: "azure" (cloud, premium) or "piper" (local, offline, streaming)
    "tts_provider": "azure",

    # Azure Speech credentials loaded from env: AZURE_SPEECH_KEY, AZURE_SPEECH_REGION
    "tts": {
        "voice_name": "en-US-JennyNeural",  
         # default (overridden by active persona)
        "streaming_enabled": True,
        # Active persona — must match a key in "personas" below
        "active_persona": "professional",

        # ── Voice Personas ─────────────────────────────────────
        # Each persona bundles an Azure Neural voice with prosody
        # controls so the agent's tone adapts to context or user
        # preference.  Users can switch at any time via the API.
        "personas": {
            "professional": {
                "voice_name": "en-US-JennyNeural",
                "rate": "1.0",
                "pitch": "+0Hz",
                "volume": "default",
                "description": "Clear, confident, and measured — great for work & productivity.",
            },
            "casual": {
                "voice_name": "en-US-AriaNeural",
                "rate": "1.05",
                "pitch": "+2Hz",
                "volume": "default",
                "description": "Warm, friendly, and conversational — ideal for everyday chat.",
            },
            "energetic": {
                "voice_name": "en-US-DavisNeural",
                "rate": "1.15",
                "pitch": "+4Hz",
                "volume": "loud",
                "description": "Upbeat, enthusiastic, and lively — perfect for motivation & hype.",
            },
        },
    },

    # -----------------------------
    # Piper TTS configuration (local, offline)
    # -----------------------------
    # Download models from: https://huggingface.co/rhasspy/piper-voices
    # Place .onnx + .onnx.json under voice/piper_models/
    "piper_tts": {
        # Path to the .onnx model file (relative paths resolved from voice/ dir)
        "model_path": os.path.join(_VOICE_DIR, "piper_models", "en_US-lessac-medium.onnx"),

        # Speech speed: 1.0 = normal, < 1.0 = faster, > 1.0 = slower
        "length_scale": 1.0,

        # Pause between sentences in seconds
        "sentence_silence": 0.15,

        # Speaker ID (for multi-speaker models, None for single-speaker)
        "speaker_id": None,

        # Enable streaming mode: start speaking as Nexus chunks arrive
        # instead of waiting for the full response
        "streaming_enabled": True,
    },
    # -----------------------------
    # Intent Gate configuration
    # -----------------------------
    "intent_gate": {
        "use_llm": True,  # When True, uses ModelManager to classify intents
        "fallback_to_rules": True, # If LLM fails, use regex-based classification
        "model": "gemini", # Model key from models.json
    },
}

