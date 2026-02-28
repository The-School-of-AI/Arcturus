# voice/voice_wake_service.py

import threading
import time
import numpy as np
from datetime import datetime

from voice.audio_input import AudioInput
from voice.wake_engine import create_wake_engine
from voice.config import VOICE_CONFIG
from voice.barge_in import BargeInDetector, BargeInConfig
from shared.state import tts_is_speaking, tts_in_barge_in_grace_window


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

        # Robust barge-in detector (separate from wake/VAD/STT path).
        bi = VOICE_CONFIG.get("barge_in", {}) or {}
        self._barge = BargeInDetector(
            sample_rate=self.engine.sample_rate,
            frame_length=self.engine.frame_length,
            config=BargeInConfig(
                # Requirements: 120–200ms continuous speech; choose mid.
                min_continuous_speech_ms=float(bi.get("min_speech_ms", 160.0)),
                # Requirements: ~2.0–2.5× noise floor; choose mid.
                energy_ratio_threshold=float(bi.get("energy_ratio", 2.5)),
                # Near-field gates (reduce distant-speaker false barge-in).
                min_absolute_rms=float(bi.get("min_absolute_rms", 900.0)),
                min_rms_above_noise=float(bi.get("min_rms_above_noise", 250.0)),
            ),
        )

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
            # Establish an initial ambient noise floor during warmup.
            self._barge.observe_ambient(pcm)
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

                state = self.orchestrator.state if self.orchestrator else "IDLE"

                # ── HARD GATE mic → VAD/STT during TTS SPEAKING ─────────────
                # Non-negotiable: while TTS is speaking, mic frames must NOT reach
                # wake/VAD/STT. We still allow *barge-in detection* after grace,
                # via a separate detector that does not feed STT.
                if state != "SPEAKING":
                    # Wake engine is allowed in IDLE/LISTENING/THINKING.
                    self.engine.process(pcm)

                if not self.orchestrator:
                    # No downstream pipeline yet; keep learning ambient floor.
                    self._barge.observe_ambient(pcm)
                    continue

                if state == "LISTENING":
                    # Feed STT only while listening (never during TTS).
                    if self.orchestrator.stt:
                        self.orchestrator.stt.push_audio(pcm)
                    # Update ambient noise floor continuously when not speaking.
                    self._barge.observe_ambient(pcm)
                    self._barge.reset_speech_streak()

                elif state in ("IDLE", "THINKING"):
                    # Keep learning ambient noise while idle/thinking.
                    self._barge.observe_ambient(pcm)
                    self._barge.reset_speech_streak()

                elif state == "SPEAKING":
                    # Hard gate: do not process wake engine, do not feed STT, do not
                    # call any existing VAD modules here.
                    if not tts_is_speaking():
                        # If orchestrator says SPEAKING but TTS isn't active, treat as ambient.
                        self._barge.observe_ambient(pcm)
                        self._barge.reset_speech_streak()
                        continue

                    # Grace window: suppress barge-in completely for ~300ms on TTS start.
                    if tts_in_barge_in_grace_window():
                        self._barge.reset_speech_streak()
                        continue

                    interrupt, rms, ratio = self._barge.should_interrupt(pcm)
                    if interrupt:
                        # Minimal logging: orchestrator will log state transition.
                        self._barge.reset_speech_streak()
                        self.orchestrator.interrupt()
                    # else: keep accumulating until continuous speech threshold is hit.
                else:
                    self._barge.reset_speech_streak()

            except KeyboardInterrupt:
                # Ctrl+C pressed while inside the audio loop — stop cleanly
                print("\n🛑 [Voice] KeyboardInterrupt received. Stopping wake service.")
                self._running = False
                break
            except Exception as e:
                if self._running:
                    print(f"⚠️ [Voice] Audio loop error: {e}")

    def _flush_audio(self):
        q = self.audio.q
        with q.mutex:
            q.queue.clear()

    def stop(self):
        self._running = False
        time.sleep(0.05)
        self.audio.stop()
        self.engine.close()