# voice/voice_wake_service.py

import threading
import time
import numpy as np
from datetime import datetime

from voice.audio_input import AudioInput
from voice.wake_engine import create_wake_engine
from voice.config import VOICE_CONFIG

# ── VAD (Voice Activity Detection) parameters ───────────────────
# RMS energy threshold for detecting user speech during TTS playback.
# If the mic RMS exceeds this for BARGE_IN_FRAMES consecutive frames,
# we treat it as the user interrupting.
BARGE_IN_RMS_THRESHOLD = 1500     # int16 scale (0–32768)
BARGE_IN_FRAMES        = 3        # consecutive loud frames needed
# ────────────────────────────────────────────────────────────────


class VoiceWakeService:
    def __init__(self, on_wake_callback):
        self.on_wake = on_wake_callback
        self.engine = create_wake_engine(on_wake_detected=self._on_internal_wake)

        self.audio = AudioInput(
            self.engine.sample_rate,
            self.engine.frame_length
        )

        self.orchestrator = None  # Will be set after initialization
        self._running = False
        self._thread = None
        self._loud_frame_streak = 0  # consecutive frames above VAD threshold

    def _on_internal_wake(self):
        """Called directly by the engine thread when detection occurs"""
        self.on_wake({
            "type": "VOICE_WAKE",
            "timestamp": datetime.now().isoformat(),
            "wake_word": VOICE_CONFIG["wake_word"]
        })

    def start(self):
        self._running = True
        self.audio.start()

        self._thread = threading.Thread(
            target=self._loop,
            daemon=True
        )
        self._thread.start()

    def _loop(self):
        print("🎙️ [Voice] Priming microphone and engine...")
        # 2.5s warmup — Windows audio drivers often need extra time to stabilize
        warmup_frames = int(2.5 * self.engine.sample_rate / self.engine.frame_length)
        rms_sum = 0.0
        rms_count = 0

        for i in range(warmup_frames):
            if not self._running:
                return
            pcm = self.audio.read()  # Drain priming frames
            if pcm is None:
                continue  # read timed out — skip this iteration
            # Accumulate RMS over last half of warmup to check mic is live
            if i > warmup_frames // 2:
                samples = np.array(pcm, dtype=np.float64)
                rms_sum += np.sqrt(np.mean(samples ** 2))
                rms_count += 1

        if rms_count > 0:
            avg_rms = rms_sum / rms_count
            if avg_rms < 10:
                print("⚠️ [Voice] Microphone appears silent (RMS ≈ 0). "
                      "Check mic permissions or hardware.")
        print("🎙️ [Voice] Hardware WARM. Listening for wake word now.")

        while self._running:
            try:
                pcm = self.audio.read()

                # None means the read timed out (no audio frame yet) —
                # just loop so we can re-check _running and stay interruptible
                if pcm is None:
                    continue

                # 1. Always process wake word (calls _on_internal_wake on match)
                self.engine.process(pcm)

                if not self.orchestrator:
                    continue

                state = self.orchestrator.state

                # 2. Push audio to STT while LISTENING
                if state == "LISTENING":
                    if self.orchestrator.stt:
                        self.orchestrator.stt.push_audio(pcm)
                    self._loud_frame_streak = 0  # reset VAD counter

                # 3. VAD barge-in: detect user speech during SPEAKING
                elif state == "SPEAKING":
                    # Suppress barge-in while TTS is actively outputting audio —
                    # the mic picks up our own speaker output and the VAD
                    # mistakes it for user speech (echo/feedback loop).
                    tts = getattr(self.orchestrator, 'tts', None)
                    if tts and tts.is_speaking:
                        # TTS is still playing — any loud audio is just echo
                        self._loud_frame_streak = 0
                    elif self._is_speech(pcm):
                        self._loud_frame_streak += 1
                        if self._loud_frame_streak >= BARGE_IN_FRAMES:
                            print("⚡ [VAD] User speech detected — barge-in!")
                            self._loud_frame_streak = 0
                            self.orchestrator.interrupt()
                    else:
                        self._loud_frame_streak = 0
                else:
                    self._loud_frame_streak = 0

            except KeyboardInterrupt:
                # Ctrl+C pressed while inside the audio loop — stop cleanly
                print("\n🛑 [Voice] KeyboardInterrupt received. Stopping wake service.")
                self._running = False
                break
            except Exception as e:
                if self._running:
                    print(f"⚠️ [Voice] Audio loop error: {e}")


    @staticmethod
    def _is_speech(pcm) -> bool:
        """Simple energy-based VAD: True if frame RMS exceeds threshold."""
        samples = np.array(pcm, dtype=np.int16)
        rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
        return rms > BARGE_IN_RMS_THRESHOLD

    def _flush_audio(self):
        q = self.audio.q
        with q.mutex:
            q.queue.clear()

    def stop(self):
        self._running = False
        time.sleep(0.05)
        self.audio.stop()
        self.engine.close()