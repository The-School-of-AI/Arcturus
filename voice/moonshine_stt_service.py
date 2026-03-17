# voice/moonshine_stt_service.py

"""
Moonshine STT — Local, streaming speech-to-text (5x faster than Whisper).

Drop-in replacement for DeepgramSTTService / STTService with the same
public interface: start(), stop(), cancel(), push_audio().

Requires:
    pip install moonshine-voice sounddevice numpy
    (optional) pip install noisereduce   — for background noise suppression
"""

import threading
import time
import numpy as np

try:
    from moonshine_voice import Transcriber, Stream
    _HAS_MOONSHINE = True
except ImportError:
    _HAS_MOONSHINE = False
    print("⚠️ [MoonshineSTT] moonshine-voice not installed. "
          "Install with: pip install moonshine-voice")

try:
    import noisereduce as nr
    _HAS_NOISEREDUCE = True
except ImportError:
    _HAS_NOISEREDUCE = False
    print("⚠️ [MoonshineSTT] noisereduce not installed — skipping noise cancellation. "
          "Install with: pip install noisereduce")


class MoonshineSTTService:
    """
    Local STT using Moonshine (5x faster than Whisper, native streaming).

    Interface mirrors STTService / DeepgramSTTService so the Orchestrator
    can use any backend interchangeably.
    """

    def __init__(
        self,
        sample_rate: int,
        on_text_callback,
        model: str = "base",          # 'tiny' (fastest) or 'base' (best accuracy)
        noise_reduce: bool = True,
    ):
        self.sample_rate = sample_rate
        self.on_text = on_text_callback
        self.noise_reduce = noise_reduce and _HAS_NOISEREDUCE

        self._audio_buffer = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        # Moonshine state
        self._transcriber = None
        self._stream = None
        self._model_name = model
        self._prev_partial = ""

        if _HAS_MOONSHINE:
            try:
                self._transcriber = Transcriber(model=model)
                print(f"✅ [MoonshineSTT] Model loaded: moonshine/{model}")
            except Exception as e:
                print(f"❌ [MoonshineSTT] Failed to load model: {e}")

    def start(self):
        """Start background transcription thread."""
        self._running = True
        self._prev_partial = ""
        # Create a fresh Stream for each start
        if self._transcriber:
            try:
                self._stream = Stream(self._transcriber, sample_rate=self.sample_rate)
            except Exception as e:
                print(f"⚠️ [MoonshineSTT] Failed to create stream: {e}")
                self._stream = None

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Graceful stop: flush remaining audio, then shut down."""
        self._running = False
        time.sleep(0.05)
        self._flush_final()
        self._clear_buffer()

    def cancel(self):
        """Hard cancel: drop everything immediately."""
        self._clear_buffer()
        self._prev_partial = ""

    def push_audio(self, pcm_frame):
        """
        pcm_frame: tuple[int] or np.int16 array — raw 16kHz mono samples.
        """
        with self._lock:
            self._audio_buffer.extend(pcm_frame)

    # ── Private ─────────────────────────────────────────────────

    def _clear_buffer(self):
        with self._lock:
            self._audio_buffer.clear()

    def _denoise(self, audio: np.ndarray) -> np.ndarray:
        """Apply stationary noise reduction (same algorithm as STTService)."""
        try:
            return nr.reduce_noise(
                y=audio,
                sr=self.sample_rate,
                stationary=True,
                prop_decrease=0.75,
                n_fft=512,
                n_std_thresh_stationary=1.5,
            )
        except Exception as e:
            print(f"⚠️ [MoonshineSTT] Noise reduction failed, using raw audio: {e}")
            return audio

    def _loop(self):
        """Process audio chunks through Moonshine streaming."""
        while self._running:
            time.sleep(0.1)  # ~100ms polling, matches STTService

            with self._lock:
                # Need at least 0.2s of audio before processing
                if len(self._audio_buffer) < self.sample_rate * 0.2:
                    continue
                pcm = np.array(self._audio_buffer, dtype=np.int16)
                self._audio_buffer.clear()

            # Normalize to float32 [-1, 1]
            audio = pcm.astype(np.float32) / 32768.0

            if self.noise_reduce:
                audio = self._denoise(audio)

            if not self._stream:
                # Fallback: use batch transcription if streaming not available
                self._transcribe_batch(audio)
                continue

            try:
                partial = self._stream.process_chunk(audio)

                if partial and partial.strip():
                    text = partial.strip()
                    # Moonshine streaming may return cumulative text.
                    # Emit only the new delta to match the callback contract.
                    if text != self._prev_partial:
                        if text.startswith(self._prev_partial):
                            delta = text[len(self._prev_partial):].strip()
                        else:
                            delta = text
                        if delta:
                            self.on_text(delta)
                        self._prev_partial = text
            except Exception as e:
                print(f"⚠️ [MoonshineSTT] Stream processing error: {e}")

    def _transcribe_batch(self, audio: np.ndarray):
        """Fallback: batch transcription when streaming is not available."""
        if not self._transcriber:
            return
        try:
            result = self._transcriber.transcribe(audio)
            if isinstance(result, dict):
                text = result.get("text", "").strip()
            else:
                text = str(result).strip()
            if text:
                self.on_text(text)
        except Exception as e:
            print(f"⚠️ [MoonshineSTT] Batch transcription error: {e}")

    def _flush_final(self):
        """Flush remaining audio and get final transcript from stream."""
        if not self._stream:
            return
        try:
            final = self._stream.finish()
            if final:
                if isinstance(final, dict):
                    text = final.get("text", "").strip()
                else:
                    text = str(final).strip()
                # Only emit if it's new content beyond what we already sent
                if text and text != self._prev_partial:
                    if text.startswith(self._prev_partial):
                        delta = text[len(self._prev_partial):].strip()
                    else:
                        delta = text
                    if delta:
                        self.on_text(delta)
        except Exception as e:
            print(f"⚠️ [MoonshineSTT] Flush error: {e}")
        self._prev_partial = ""
