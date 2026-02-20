# voice/porcupine_engine.py

import pvporcupine
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class PorcupineWakeEngine:
    def __init__(self, keyword_path, sensitivity):
        self.porcupine = pvporcupine.create(
            access_key=os.getenv("PICOVOICE_ACCESS_KEY"),
            keyword_paths=[keyword_path],
            sensitivities=[sensitivity]
        )

    @property
    def sample_rate(self):
        return self.porcupine.sample_rate

    @property
    def frame_length(self):
        return self.porcupine.frame_length

    def process(self, pcm):
        detected = self.porcupine.process(pcm) >= 0
        if detected:
            self.on_wake_detected()
        return detected

    def on_wake_detected(self):
        """
        Placeholder: called when the wake word is detected.
        Wire this up to trigger the STT (Speech-to-Text) pipeline
        so the system can capture and transcribe the user's command.

        TODO: Replace with actual STT pipeline trigger, e.g.:
            - Start recording the user's utterance
            - Stream audio to an STT service (Whisper, Google STT, etc.)
            - Pass the transcribed text to the agent for processing
        """
        logger.info("🎙️ Wake word detected — STT pipeline trigger point")
        print("🎙️ Wake word detected — STT pipeline trigger point")
        # Example future integration:
        # from voice.stt_pipeline import STTPipeline
        # stt = STTPipeline()
        # transcript = stt.listen_and_transcribe()
        # agent.handle_user_input(transcript)

    def close(self):
        self.porcupine.delete()
