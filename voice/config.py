# voice/config.py

import os

_VOICE_DIR = os.path.dirname(os.path.abspath(__file__))

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
        "keyword_path": os.path.join(_VOICE_DIR, "keywords", "hey_arcturus.ppn"),

        # Sensitivity: 0.0 (least sensitive) → 1.0 (most sensitive)
        # Higher = fewer missed detections, but more false positives.
        # 0.75 is a good balance for real-world noisy environments.
        "sensitivity": 0.75,
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
    # TTS configuration (Azure Speech)
    # -----------------------------
    # Credentials loaded from env: AZURE_SPEECH_KEY, AZURE_SPEECH_REGION
    "tts": {
        "voice_name": "en-US-JennyNeural",   # default (overridden by active persona)

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
}
