# voice/wake_engine.py

from voice.config import VOICE_CONFIG
from voice.porcupine_engine import PorcupineWakeEngine
from voice.openwakeword_engine import OpenWakeWordEngine

def create_wake_engine():
    engine = VOICE_CONFIG["engine"]

    try:
        if engine == "porcupine":
            cfg = VOICE_CONFIG["porcupine"]
            return PorcupineWakeEngine(
                keyword_path=cfg["keyword_path"],
                sensitivity=cfg["sensitivity"]
            )

        else:
            engine = "openwakeword"
            cfg = VOICE_CONFIG["openwakeword"]
            return OpenWakeWordEngine(
                model_path=cfg["model_path"],
                threshold=cfg["threshold"]
            )
    except Exception as e       :
        raise ValueError(f"wake engine failed: {e}")
