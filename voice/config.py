# voice/config.py

import os

_VOICE_DIR = os.path.dirname(os.path.abspath(__file__))

VOICE_CONFIG = {
    # Master switch
    "enabled": True,

    # Wake engine selection
    # Options: "porcupine", "openwakeword"
    "engine": "porcupine",
     "wake_word" :"Hey Arcturus",

    # -----------------------------
    # Porcupine configuration
    # -----------------------------
    "porcupine": {
        # Path to custom .ppn file (recommended)
        "keyword_path": os.path.join(_VOICE_DIR, "keywords", "hey_arcturus.ppn"),

        # Sensitivity: 0.0 (least sensitive) → 1.0 (most sensitive)
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
    # Shared wake behavior
    # -----------------------------
    "wake_behavior": {
        # Minimum seconds between wake events
        "debounce_seconds": 1.0,

        # Pause wake listening while agent is speaking
        "pause_while_speaking": True,
    },
}
