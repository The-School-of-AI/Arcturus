# voice/moonshine_stt_service.py

"""
Moonshine STT — Local, streaming speech-to-text (5x faster than Whisper).

Drop-in replacement for DeepgramSTTService / STTService with the same
public interface: start(), stop(), cancel(), push_audio().

Uses Moonshine's listener-based streaming API:
  - `on_line_completed` fires the callback with final text
  - Audio is fed via `add_audio()` in a background thread

Requires:
    pip install moonshine-voice sounddevice numpy
    (optional) pip install noisereduce   — for background noise suppression
"""

import os
import threading
import time
import numpy as np

try:
    from moonshine_voice import Transcriber, ModelArch
    from moonshine_voice.transcriber import TranscriptEventListener
    _HAS_MOONSHINE = True
except ImportError:
    _HAS_MOONSHINE = False
    Transcriber = None
    ModelArch = None
    TranscriptEventListener = object  # fallback base for class definition
    print("⚠️ [MoonshineSTT] moonshine-voice not installed. "
          "Install with: pip install moonshine-voice")

try:
    import noisereduce as nr
    _HAS_NOISEREDUCE = True
except ImportError:
    _HAS_NOISEREDUCE = False
    print("⚠️ [MoonshineSTT] noisereduce not installed — skipping noise cancellation. "
          "Install with: pip install noisereduce")

# Map user-friendly names to ModelArch enums
_MODEL_ARCH_MAP = {
    "tiny": ModelArch.TINY if ModelArch else None,
    "base": ModelArch.BASE if ModelArch else None,
}


def _resolve_model_path(model: str) -> tuple:
    """
    Resolve a model name ('tiny' or 'base') to (model_path, ModelArch).
    Looks for bundled assets in the moonshine_voice package.
    """
    arch = _MODEL_ARCH_MAP.get(model)
    if arch is None:
        raise ValueError(f"Unknown Moonshine model: '{model}'. Use 'tiny' or 'base'.")

    # Bundled models are in moonshine_voice/assets/<model>-en/
    import moonshine_voice
    pkg_dir = os.path.dirname(moonshine_voice.__file__)
    model_dir = os.path.join(pkg_dir, "assets", f"{model}-en")

    if not os.path.isdir(model_dir):
        raise FileNotFoundError(
            f"Moonshine {model} model not found at {model_dir}. "
            f"Only 'tiny' is bundled. For 'base', download it manually."
        )
    return model_dir, arch


class _MoonshineListener(TranscriptEventListener):
    """
    Bridges Moonshine's event-driven transcript updates to the STT callback.
    Fires on_text only on completed lines (final transcripts).
    """

    def __init__(self, on_text_callback):
        self._on_text = on_text_callback

    def on_line_completed(self, event):
        """A line is finalized — fire the callback."""
        text = getattr(event, "line", None)
        if text is not None:
            text_str = getattr(text, "text", "")
        else:
            text_str = ""
        text_str = text_str.strip()
        if text_str:
            self._on_text(text_str)

    def on_line_text_changed(self, event):
        """Partial text update — ignore (we only emit finals)."""
        pass

    def on_line_started(self, event):
        pass

    def on_line_updated(self, event):
        pass

    def on_error(self, event):
        line = getattr(event, "line", "")
        print(f"⚠️ [MoonshineSTT] Transcription error: {line}")


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
        model: str = "tiny",          # 'tiny' (bundled) or 'base' (needs download)
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
        self._model_name = model

        if _HAS_MOONSHINE:
            try:
                model_path, arch = _resolve_model_path(model)
                self._transcriber = Transcriber(
                    model_path=model_path,
                    model_arch=arch,
                )
                # Wire up the listener
                self._listener = _MoonshineListener(on_text_callback)
                self._transcriber.add_listener(self._listener)
                print(f"✅ [MoonshineSTT] Model loaded: moonshine/{model}")
            except Exception as e:
                print(f"❌ [MoonshineSTT] Failed to load model: {e}")

    def start(self):
        """Start the Moonshine streaming engine + audio feeder thread."""
        if not self._transcriber:
            print("⚠️ [MoonshineSTT] No model loaded, cannot start.")
            return

        self._running = True
        # Start Moonshine's internal streaming pipeline
        self._transcriber.start()

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Graceful stop: flush remaining audio, then shut down."""
        self._running = False
        time.sleep(0.05)
        # Feed any remaining buffered audio
        self._flush_remaining()
        if self._transcriber:
            try:
                self._transcriber.stop()
            except Exception:
                pass

    def cancel(self):
        """Hard cancel: drop everything immediately."""
        self._clear_buffer()

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
        """Drain audio buffer and feed to Moonshine's add_audio()."""
        while self._running:
            time.sleep(0.1)  # ~100ms polling, matches STTService

            with self._lock:
                # Need at least 0.2s of audio before feeding
                if len(self._audio_buffer) < self.sample_rate * 0.2:
                    continue
                pcm = np.array(self._audio_buffer, dtype=np.int16)
                self._audio_buffer.clear()

            # Normalize to float32 [-1, 1]
            audio = pcm.astype(np.float32) / 32768.0

            if self.noise_reduce:
                audio = self._denoise(audio)

            if not self._transcriber:
                continue

            try:
                # Feed audio to Moonshine — it fires listener callbacks internally
                self._transcriber.add_audio(
                    audio.tolist(), sample_rate=self.sample_rate
                )
            except Exception as e:
                print(f"⚠️ [MoonshineSTT] add_audio error: {e}")

    def _flush_remaining(self):
        """Feed any remaining buffered audio before shutdown."""
        with self._lock:
            if not self._audio_buffer:
                return
            pcm = np.array(self._audio_buffer, dtype=np.int16)
            self._audio_buffer.clear()

        audio = pcm.astype(np.float32) / 32768.0
        if self._transcriber:
            try:
                self._transcriber.add_audio(
                    audio.tolist(), sample_rate=self.sample_rate
                )
                time.sleep(0.5)  # Give Moonshine time to process final audio
            except Exception:
                pass
