# voice/wake_engine.py

from voice.config import VOICE_CONFIG
from voice.porcupine_engine import PorcupineWakeEngine
from voice.openwakeword_engine import OpenWakeWordEngine
from voice.pocketsphinx_engine import PocketSphinxWakeEngine

def create_wake_engine(on_wake_detected=None):
    engine = VOICE_CONFIG.get("engine", "pocketsphinx")

    try:
        if engine == "porcupine":
            cfg = VOICE_CONFIG["porcupine"]
            return PorcupineWakeEngine(
                keyword_path=cfg["keyword_path"],
                sensitivity=cfg["sensitivity"],
                on_wake_detected=on_wake_detected,
            )

        elif engine == "pocketsphinx":
            cfg = VOICE_CONFIG["pocketsphinx"]
            return PocketSphinxWakeEngine(
                keyphrase=cfg.get("keyphrase", "HeyArcturus"),
                kws_threshold=cfg.get("kws_threshold", 1e-20),
                hmm_path=cfg.get("hmm_path"),
                dict_path=cfg.get("dict_path"),
                on_wake_detected=on_wake_detected,
            )

        else:
            # openwakeword (default fallback)
            cfg = VOICE_CONFIG["openwakeword"]
            return OpenWakeWordEngine(
                model_path=cfg["model_path"],
                threshold=cfg["threshold"]
            )
    except Exception as e:
        raise ValueError(f"wake engine failed: {e}")
