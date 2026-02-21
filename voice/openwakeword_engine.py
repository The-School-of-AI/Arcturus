# voice/openwakeword_engine.py

import numpy as np
from openwakeword.model import Model

class OpenWakeWordEngine:
    def __init__(self, model_path, threshold=0.6):
        self.model = Model(
            wakeword_models=[model_path]
        )
        self.threshold = threshold
        self.wakeword_name = self.model.wakeword_names[0]

        # OpenWakeWord expects 16kHz mono int16
        self.sample_rate = 16000
        self.frame_length = 512  # safe default

    def process(self, pcm):
        """
        pcm: tuple/list of int16 samples
        """
        audio = np.array(pcm, dtype=np.int16)
        scores = self.model.predict(audio)

        return scores[self.wakeword_name] >= self.threshold

    def close(self):
        pass
