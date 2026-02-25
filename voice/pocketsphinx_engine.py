# voice/pocketsphinx_engine.py

"""
PocketSphinx wake word engine — fully offline, no API key required.
Uses CMU PocketSphinx keyphrase detection for always-on wake word listening.
Fallback option when Porcupine access key is unavailable.
"""

import os
import numpy as np
from pathlib import Path

try:
    from pocketsphinx import Decoder
    _HAS_POCKETSPHINX = True
except ImportError:
    _HAS_POCKETSPHINX = False
    print("⚠️ [PocketSphinx] pocketsphinx not installed. "
          "Install with: pip install pocketsphinx")

_VOICE_DIR = Path(__file__).resolve().parent

class PocketSphinxWakeEngine:
    """
    Keyphrase-spotting wake word engine using CMU PocketSphinx.
    Fully offline, no API keys needed — uses acoustic model bundled
    with the pocketsphinx package.

    Implements the same interface as PorcupineWakeEngine:
      - sample_rate (property)
      - frame_length (property)
      - process(pcm) → bool
      - close()
    """

    def __init__(
        self,
        keyphrase: str = "HeyArcturus",
        kws_threshold: float = 1e-20,
        hmm_path: str = None,
        dict_path: str = None,
        on_wake_detected=None,
    ):
        if not _HAS_POCKETSPHINX:
            raise ImportError("pocketsphinx is not installed.")

        self.on_wake_detected_cb = on_wake_detected
        self._sample_rate = 16000
        self._frame_length = 1024
        LOG_FILE = _VOICE_DIR / "pocketsphinx_init.log"
        # Configure decoder
        config = Decoder.default_config()
        # HMM and dictionary paths — use bundled defaults if not specified
        config.set_string('-hmm', hmm_path)
        config.set_string('-dict', dict_path)   

        # 🔴 Disable competing decoders (CRITICAL)
        config.set_string('-lm', None)
        config.set_string('-jsgf', None)
        config.set_string('-fsg', None)
        # config.set_string('-allphone', None)
        # config.set_string('-lmctl', None)

        # Keyphrase spotting mode
        keyphrase = keyphrase.lower()
        config.set_string('-keyphrase', keyphrase)
        config.set_float('-kws_threshold', kws_threshold)

        # Suppress verbose PocketSphinx logs
        config.set_string('-logfn', str(LOG_FILE))
        config.set_int('-samprate', 16000)    
        self._decoder = Decoder(config)
        self._decoder.start_utt()

        print(f"✅ [PocketSphinx] Engine ready — keyphrase: \"{keyphrase}\" "
              f"(threshold: {kws_threshold})")

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def frame_length(self):
        return self._frame_length

    def process(self, pcm):
        """
        pcm: tuple/list of int16 samples (same contract as Porcupine).
        Returns True if wake word detected.
        """
        # Convert to int16 bytes for PocketSphinx
        audio = np.array(pcm, dtype=np.int16)
        self._decoder.process_raw(audio.tobytes(), False, False)

        if self._decoder.hyp() is not None:
            # Wake word detected — reset utterance for next detection
            self._decoder.end_utt()
            self._decoder.start_utt()

            if self.on_wake_detected_cb:
                self.on_wake_detected_cb()
            return True

        return False

    def close(self):
        """Clean up the decoder."""
        try:
            self._decoder.end_utt()
        except Exception:
            pass