# voice/audio_input.py

import pyaudio
import struct

class AudioInput:
    def __init__(self, sample_rate, frame_length):
        self.sample_rate = sample_rate
        self.frame_length = frame_length
        self.pa = pyaudio.PyAudio()
        self.stream = None

    def start(self):
        self.stream = self.pa.open(
            rate=self.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.frame_length
        )

    def read(self):
        pcm = self.stream.read(
            self.frame_length,
            exception_on_overflow=False
        )
        return struct.unpack_from(
            "h" * self.frame_length,
            pcm
        )

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pa.terminate()
