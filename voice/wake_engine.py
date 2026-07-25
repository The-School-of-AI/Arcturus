# voice/wake_engine.py

from voice.config import VOICE_CONFIG


def create_wake_engine(on_wake_detected=None):
    engine = VOICE_CONFIG.get("engine", "openwakeword")

    try:
        if engine == "porcupine":
            from voice.porcupine_engine import PorcupineWakeEngine
            cfg = VOICE_CONFIG["porcupine"]
            return PorcupineWakeEngine(
                keyword_path=cfg["keyword_path"],
                sensitivity=cfg["sensitivity"],
                on_wake_detected=on_wake_detected,
            )

        elif engine == "pocketsphinx":
            from voice.pocketsphinx_engine import PocketSphinxWakeEngine
            cfg = VOICE_CONFIG["pocketsphinx"]
            return PocketSphinxWakeEngine(
                keyphrase=cfg.get("keyphrase", "HeyArcturus"),
                kws_threshold=cfg.get("kws_threshold", 1e-20),
                hmm_path=cfg.get("hmm_path"),
                dict_path=cfg.get("dict_path"),
                on_wake_detected=on_wake_detected,
            )

        else:
            # openwakeword (default)
            from voice.openwakeword_engine import OpenWakeWordEngine
            cfg = VOICE_CONFIG["openwakeword"]
            return OpenWakeWordEngine(
                model_path=cfg.get("model_path"),
                threshold=cfg.get("threshold", 0.6),
                on_wake_detected=on_wake_detected,
            )
    except Exception as e:
        raise ValueError(f"wake engine failed: {e}")
