# voice/voice_wake_service.py

import threading
import time
import numpy as np
from collections import deque
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

        # Pre-barge-in audio buffer: keeps the last ~500ms of audio frames
        # captured during SPEAKING state (post-grace). When barge-in fires,
        # these frames are pushed to STT so the user's speech isn't lost.
        # At 16kHz / 512 samples per frame = 32ms/frame → 16 frames ≈ 512ms
        self._barge_in_buffer: deque = deque(maxlen=16)

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

                # ── HARD GATE: no wake detection during SPEAKING or DICTATING ─
                # During SPEAKING: speaker echo can false-trigger wake detection.
                # During DICTATING: user is actively speaking; we never want a
                #   mid-dictation "Arcturus" to abort the session.
                if state not in ("SPEAKING", "DICTATING"):
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

                elif state == "DICTATING":
                    # Feed STT continuously — all speech is raw dictation content.
                    # Barge-in and wake detection are suppressed (on_wake already
                    # guards against DICTATING, but skipping detect is cheaper).
                    if self.orchestrator.stt:
                        self.orchestrator.stt.push_audio(pcm)
                    # Keep updating ambient floor so barge-in thresholds stay calibrated
                    # for when dictation ends and we return to LISTENING.
                    self._barge.observe_ambient(pcm)
                    self._barge.reset_speech_streak()

                elif state in ("IDLE", "THINKING"):

                    # Keep learning ambient noise while idle/thinking.
                    self._barge.observe_ambient(pcm)
                    self._barge.reset_speech_streak()

                elif state == "SPEAKING":
                    # --- PRODUCTION BARGE-IN (Interruption) ---
                    # While speaking, we check for continuous user speech.
                    # 1. Skip if still in grace window (prevents start-of-speech echo false-triggers).
                    if tts_in_barge_in_grace_window():
                        # Actively suppress: clear buffer and reset streak so no
                        # energy from the TTS attack phase carries over into the
                        # post-grace detection window.
                        self._barge_in_buffer.clear()
                        self._barge.reset_speech_streak()

                    else:
                        # 2. If TTS already finished but orchestrator state is lagging,
                        #    don't falsely barge-in — just reset and wait for state update.
                        if not tts_is_speaking():
                            self._barge_in_buffer.clear()
                            self._barge.observe_ambient(pcm)
                            self._barge.reset_speech_streak()

                        else:
                            # Buffer this frame for potential STT pre-fill on barge-in.
                            self._barge_in_buffer.append(pcm)

                            # 3. Check if user is speaking over us
                            interrupted, rms, ratio = self._barge.should_interrupt(pcm)
                            if interrupted:
                                print(f"⚡ [Voice] VAD Barge-in detected! (RMS: {rms:.1f}, Ratio: {ratio:.2f}x)")

                                # Pre-fill STT with buffered speech BEFORE calling on_wake()
                                # so the frames are already queued when state → LISTENING.
                                # on_wake(BARGE_IN) deliberately skips stt.cancel() to keep them.
                                if self.orchestrator and self.orchestrator.stt:
                                    n_frames = len(self._barge_in_buffer)
                                    for buffered_pcm in self._barge_in_buffer:
                                        self.orchestrator.stt.push_audio(buffered_pcm)
                                    print(f"🔊 [Voice] Pre-filled STT with {n_frames} buffered frames (~{n_frames * 32}ms)")
                                self._barge_in_buffer.clear()

                                # NOW trigger wake flow — state → LISTENING, TTS cancel, nexus abort
                                self.on_wake({"type": "BARGE_IN"})

                                self._barge.reset_speech_streak()
                                continue
                else:
                    self._barge_in_buffer.clear()
                    self._barge.reset_speech_streak()

            except KeyboardInterrupt:
                # Ctrl+C pressed while inside the audio loop — stop EVERYTHING cleanly
                print("\n🛑 [Voice] KeyboardInterrupt received. Stopping pipeline.")
                self._running = False
                if self.orchestrator:
                    # Request immediate TTS cancellation before process exits
                    self.orchestrator.tts.cancel()
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