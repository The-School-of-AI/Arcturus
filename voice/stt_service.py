# voice/stt_service.py

import threading
import time
import numpy as np
from faster_whisper import WhisperModel

try:
    import noisereduce as nr
    _HAS_NOISEREDUCE = True
except ImportError:
    _HAS_NOISEREDUCE = False
    print("⚠️ [STT] noisereduce not installed — skipping noise cancellation. "
          "Install with: pip install noisereduce")


class STTService:
    def __init__(
        self,
        sample_rate: int,
        on_text_callback,
        model_size="small",
        device="cpu",
        noise_reduce: bool = True,
    ):
        self.sample_rate = sample_rate
        self.on_text = on_text_callback
        self.noise_reduce = noise_reduce and _HAS_NOISEREDUCE
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type="int8",
        )

        self._audio_buffer = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        # if self.noise_reduce:
        #     print("✅ [STT] Noise reduction enabled (noisereduce/spectral gating)")

    def start(self):
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._running = False
        time.sleep(0.05)
        self._clear_buffer()

    def cancel(self):
        """Hard cancel: drop everything immediately"""
        self._clear_buffer()

    def push_audio(self, pcm_frame):
        """
        pcm_frame: tuple[int] or np.int16 array
        """
        with self._lock:
            self._audio_buffer.extend(pcm_frame)

    def _clear_buffer(self):
        with self._lock:
            self._audio_buffer.clear()

    def _denoise(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply stationary noise reduction via spectral gating.
        Uses noisereduce's fast algorithm suited for real-time use:
          - Suppresses steady-state background noise (fans, AC, traffic hum)
          - Preserves speech transients
        Falls back to raw audio if anything goes wrong.
        """
        try:
            cleaned = nr.reduce_noise(
                y=audio,
                sr=self.sample_rate,
                stationary=True,       # Fast: assumes noise is stationary
                prop_decrease=0.75,    # Suppress 75% of detected noise energy
                n_fft=512,             # Small FFT window for low latency
                n_std_thresh_stationary=1.5,  # Sensitivity threshold
            )
            return cleaned
        except Exception as e:
            print(f"⚠️ [STT] Noise reduction failed, using raw audio: {e}")
            return audio

    def _loop(self):
        """
        Periodically transcribe whatever we have.
        Short windows = lower latency.
        """
        while self._running:
            time.sleep(0.1)  # Lowered from 0.4s for better responsiveness

            with self._lock:
                # Transcribe if we have at least 0.2s of audio (Lowered from 0.5s)
                if len(self._audio_buffer) < self.sample_rate * 0.2:
                    continue

                pcm = np.array(
                    self._audio_buffer,
                    dtype=np.int16,
                )
                self._audio_buffer.clear()

            # normalize to float32 [-1, 1]
            audio = pcm.astype(np.float32) / 32768.0

            # Noise cancellation preprocessing
            if self.noise_reduce:
                audio = self._denoise(audio)

            segments, _ = self.model.transcribe(
                audio,
                language="en",
                vad_filter=True,
                beam_size=1,
                word_timestamps=True,
                condition_on_previous_text=True,
            )

            text = "".join(seg.text for seg in segments).strip()
            if text:
                self.on_text(text)