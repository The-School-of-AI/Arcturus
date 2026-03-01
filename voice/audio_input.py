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
        self._running = False

    def _callback(self, indata, frames, time, status):
        if self._running:
            pcm = (indata[:, 0] * 32767).astype(np.int16)
            self.q.put(pcm)

    def start(self):
        self._running = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.frame_length,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()

    def read(self, timeout: float = 0.5):
        """
        Returns one frame of PCM audio as a tuple of int16 samples.

        Uses a timeout so the calling thread remains responsive to
        signals (Ctrl+C / KeyboardInterrupt).  Returns None if no
        audio arrived within the timeout window — callers should
        treat None as a no-op and loop again.
        """
        try:
            pcm = self.q.get(timeout=timeout)
            return tuple(pcm.tolist())
        except queue.Empty:
            return None

    def stop(self):
        self._running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        # Drain any remaining items so threads unblock immediately
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break