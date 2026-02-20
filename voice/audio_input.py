# voice/audio_input.py

import sounddevice as sd
import numpy as np
import queue


class AudioInput:
    def __init__(self, sample_rate, frame_length):
        self.sample_rate = sample_rate
        self.frame_length = frame_length
        self.q = queue.Queue()
        self.stream = None

    def _callback(self, indata, frames, time, status):
        if status:
            # You may want to log this
            pass
        # indata is float32 [-1, 1], convert to int16-like scale if needed
        pcm = (indata[:, 0] * 32767).astype(np.int16)
        self.q.put(pcm)

    def start(self):
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.frame_length,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()

    def read(self):
        """
        Returns: tuple[int] of length frame_length (like your PyAudio version)
        """
        pcm = self.q.get()
        return tuple(pcm.tolist())

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None