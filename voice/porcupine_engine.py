# voice/porcupine_engine.py

import pvporcupine
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from voice/ dir AND project root to ensure keys are found
_VOICE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _VOICE_DIR.parent
load_dotenv(_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

class PorcupineWakeEngine:
    def __init__(self, keyword_path, sensitivity, on_wake_detected=None):
        self.on_wake_detected_cb = on_wake_detected
        access_key = os.getenv("PICOVOICE_ACCESS_KEY")
        if not access_key:
            raise ValueError(
                "❌ PICOVOICE_ACCESS_KEY not found in environment. "
                "Set it in voice/.env or the project root .env"
            )

        if not os.path.exists(keyword_path):
            raise FileNotFoundError(
                f"❌ Wake word keyword file not found: {keyword_path}"
            )

        self.porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[keyword_path],
            sensitivities=[sensitivity]
        )

    @property
    def sample_rate(self):
        return self.porcupine.sample_rate

    @property
    def frame_length(self):
        return self.porcupine.frame_length

    def process(self, pcm):
        detected = self.porcupine.process(pcm) >= 0
        if detected and self.on_wake_detected_cb:
            self.on_wake_detected_cb()
        return detected

    def close(self):
        self.porcupine.delete()
