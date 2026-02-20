# voice/voice_wake_service.py

import threading
import time
from datetime import datetime

from voice.audio_input import AudioInput
from voice.wake_engine import create_wake_engine
from voice.config import VOICE_CONFIG

class VoiceWakeService:
    def __init__(self, on_wake_callback):
        self.engine = create_wake_engine()

        self.audio = AudioInput(
            self.engine.sample_rate,
            self.engine.frame_length
        )

        self.on_wake = on_wake_callback
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self.audio.start()

        self._thread = threading.Thread(
            target=self._loop,
            daemon=True
        )
        self._thread.start()

    def _loop(self):
        while self._running:
            pcm = self.audio.read()

            if self.engine.process(pcm):
                self.on_wake({
                    "type": "VOICE_WAKE",
                    "timestamp": datetime.now().isoformat(),
                    "wake_word": VOICE_CONFIG["wake_word"]
                })
                time.sleep(1)  # debounce

    def stop(self):
        self._running = False
        time.sleep(0.1)
        self.audio.stop()
        self.engine.close()
