# voice/openwakeword_engine.py

import numpy as np
import openwakeword
from openwakeword.model import Model


class OpenWakeWordEngine:
    def __init__(self, model_path=None, threshold=0.6, on_wake_detected=None):
        self._on_wake_detected = on_wake_detected

        # Use bundled ONNX model if no custom path given, or if the given path
        # is a .tflite file (tflite-runtime unavailable on macOS ARM64 + Py3.11)
        if model_path is None or model_path.endswith(".tflite"):
            onnx_paths = openwakeword.get_pretrained_model_paths("onnx")
            jarvis = [p for p in onnx_paths if "hey_jarvis" in p]
            if jarvis:
                model_path = jarvis[0]
            else:
                model_path = onnx_paths[0] if onnx_paths else model_path

        inference_framework = "onnx" if model_path.endswith(".onnx") else "tflite"

        self.model = Model(
            wakeword_models=[model_path],
            inference_framework=inference_framework,
        )
        self.threshold = threshold
        self.wakeword_name = list(self.model.models.keys())[0]

        # OpenWakeWord expects 16kHz mono int16
        self.sample_rate = 16000
        self.frame_length = 1280  # ~80ms at 16kHz (OpenWakeWord needs >=1280 samples)

    def process(self, pcm):
        """
        pcm: tuple/list of int16 samples.
        Returns True if wake word detected.
        """
        audio = np.array(pcm, dtype=np.int16)
        scores = self.model.predict(audio)
        detected = scores[self.wakeword_name] >= self.threshold

        if detected and self._on_wake_detected:
            self._on_wake_detected()

        return detected

    def close(self):
        pass
