# voice/kokoro_tts_service.py

"""
Kokoro TTS — Local, high-quality text-to-speech (82M params, 36x real-time).

Drop-in replacement for Azure TTSService with the same public interface
including full persona support.

Requires:
    pip install kokoro-onnx sounddevice numpy
    brew install espeak-ng   (macOS — required for phonemization)

Model files:
    Download kokoro-v1.0.onnx + voices-v1.0.bin from kokoro-onnx releases
    Place them under  voice/kokoro_models/
"""

import os
import re
import queue
import shutil
import threading

try:
    from kokoro_onnx import Kokoro
    _HAS_KOKORO = True
except ImportError:
    _HAS_KOKORO = False
    print("⚠️ [KokoroTTS] kokoro-onnx not installed. "
          "Install with: pip install kokoro-onnx")

try:
    import sounddevice as sd
    import numpy as np
    _HAS_AUDIO = True
except ImportError:
    _HAS_AUDIO = False
    print("⚠️ [KokoroTTS] sounddevice/numpy not installed. "
          "Install with: pip install sounddevice numpy")

from shared.state import (
    cancel_tts_event,
    tts_mark_start,
    tts_mark_stop,
    tts_request_cancel,
)
from voice.config import VOICE_CONFIG

# ── Sentence-boundary regex (same as PiperTTSService) ────────
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

# ── Default persona → Kokoro voice mapping ───────────────────
_KOKORO_PERSONA_DEFAULTS = {
    "professional": {
        "kokoro_voice": "af_bella",
        "speed": 1.0,
        "description": "Clear, confident, and measured — great for work & productivity.",
    },
    "casual": {
        "kokoro_voice": "af_sarah",
        "speed": 1.05,
        "description": "Warm, friendly, and conversational — ideal for everyday chat.",
    },
    "energetic": {
        "kokoro_voice": "am_michael",
        "speed": 1.15,
        "description": "Upbeat, enthusiastic, and lively — perfect for motivation & hype.",
    },
}


class KokoroTTSService:
    """
    Local TTS via Kokoro ONNX (82M params, 36x real-time).
    Full persona support with 60+ voice options.

    Interface mirrors TTSService / PiperTTSService so the Orchestrator
    can use any backend interchangeably:

        .speak(text)         — synthesise full text, block until done
        .speak_streamed(q)   — consume chunks from a Queue, speak ASAP
        .cancel()            — barge-in: stop playback immediately
        .is_speaking         — True while audio is playing
        .set_persona(name)   — switch voice persona at runtime
        .list_personas()     — all available personas
        .active_persona      — current persona name
    """

    KOKORO_SAMPLE_RATE = 24000  # Kokoro always outputs 24kHz

    def __init__(
        self,
        voice_name: str = "af_bella",
        model_path: str | None = None,
        voices_path: str | None = None,
        personas: dict | None = None,
        active_persona: str = "professional",
    ):
        self._is_speaking = False
        self._cancelled = False
        self._lock = threading.Lock()
        self._kokoro = None
        self._playback_stream = None

        # Resolve model paths
        _voice_dir = os.path.dirname(os.path.abspath(__file__))
        self._model_path = model_path or os.path.join(
            _voice_dir, "kokoro_models", "kokoro-v1.0.onnx"
        )
        self._voices_path = voices_path or os.path.join(
            _voice_dir, "kokoro_models", "voices-v1.0.bin"
        )

        # Voice state
        self._voice_name = voice_name
        self._speed = 1.0

        # ── Persona setup ──
        self._personas = {}
        self._active_persona_name = None

        if personas:
            for name, cfg in personas.items():
                self._personas[name] = {
                    "kokoro_voice": cfg.get("kokoro_voice",
                                   cfg.get("voice_name", "af_bella")),
                    "speed": float(cfg.get("speed", cfg.get("rate", "1.0"))),
                    "description": cfg.get("description", ""),
                }
        else:
            self._personas = dict(_KOKORO_PERSONA_DEFAULTS)

        if active_persona and active_persona in self._personas:
            self._apply_persona(active_persona)

        self._build_kokoro()

    # ── Public properties (TTSService compat) ────────────────────

    @property
    def active_persona(self) -> str | None:
        return self._active_persona_name

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._is_speaking

    # ── Persona management ───────────────────────────────────────

    def list_personas(self) -> dict:
        return dict(self._personas)

    def set_persona(self, persona_name: str) -> bool:
        if persona_name not in self._personas:
            return False
        self._apply_persona(persona_name)
        return True

    def add_persona(self, name: str, config: dict) -> None:
        self._personas[name] = {
            "kokoro_voice": config.get("kokoro_voice",
                           config.get("voice_name", "af_bella")),
            "speed": float(config.get("speed", config.get("rate", "1.0"))),
            "description": config.get("description", ""),
        }

    def _apply_persona(self, name: str):
        cfg = self._personas[name]
        self._active_persona_name = name
        self._voice_name = cfg["kokoro_voice"]
        self._speed = cfg.get("speed", 1.0)

    # ── Core: speak() — full text at once ────────────────────────

    def speak(self, text: str):
        """
        Synthesise and play the full text.  Blocks until done or
        cancel() is called.  Markdown is stripped for clean speech.
        """
        if not text or not text.strip():
            return

        text = self._clean_for_speech(text)

        with self._lock:
            self._is_speaking = True
            self._cancelled = False
        grace_ms = VOICE_CONFIG.get("barge_in", {}).get("grace_ms", 700)
        tts_mark_start(grace_ms=grace_ms)

        preview = text[:120].replace('\n', ' ')
        print(f"🔊 [KokoroTTS] Speaking: \"{preview}{'...' if len(text) > 120 else ''}\"")

        if not self._kokoro:
            print(f"   📢 [KokoroTTS-Fallback] {text}")
            with self._lock:
                self._is_speaking = False
            tts_mark_stop()
            return

        try:
            sentences = _SENTENCE_RE.split(text)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                with self._lock:
                    if self._cancelled or cancel_tts_event.is_set():
                        break
                self._synthesize_and_play(sentence)
        except Exception as e:
            print(f"❌ [KokoroTTS] Playback failed: {e}")
        finally:
            with self._lock:
                self._is_speaking = False
            tts_mark_stop()
            self._close_playback_stream()

    # ── Core: speak_streamed() — streaming chunks ────────────────

    def speak_streamed(self, text_queue: queue.Queue, sentinel=None,
                       on_sentence_callback=None):
        """
        Consume text chunks from *text_queue* and start speaking as
        soon as a complete sentence is available.

        Args:
            text_queue:  queue.Queue yielding str chunks.
                         Producer pushes *sentinel* when done.
            sentinel:    Value that signals "no more chunks".
            on_sentence_callback: Optional callable(str) fired for each sentence.

        Blocks until all chunks are spoken or cancel() is called.
        """
        with self._lock:
            self._is_speaking = True
            self._cancelled = False
        grace_ms = VOICE_CONFIG.get("barge_in", {}).get("grace_ms", 700)
        tts_mark_start(grace_ms=grace_ms)

        print("🔊 [KokoroTTS] Streaming mode — waiting for first chunk...")

        if not self._kokoro:
            # Drain the queue (fallback mode)
            full_text = []
            while True:
                chunk = text_queue.get()
                if chunk is sentinel:
                    break
                full_text.append(chunk)
            joined = " ".join(full_text)
            print(f"   📢 [KokoroTTS-Fallback] {joined}")
            if on_sentence_callback:
                on_sentence_callback(joined)
            with self._lock:
                self._is_speaking = False
            tts_mark_stop()
            return

        try:
            buffer = ""
            spoken_count = 0

            while True:
                with self._lock:
                    if self._cancelled or cancel_tts_event.is_set():
                        break

                try:
                    chunk = text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if chunk is sentinel:
                    if buffer.strip():
                        self._speak_sentence(buffer.strip(), on_sentence_callback)
                        spoken_count += 1
                    break

                buffer += chunk

                # Extract complete sentences from buffer
                while True:
                    match = _SENTENCE_RE.search(buffer)
                    if not match:
                        break
                    sentence = buffer[:match.start()].strip()
                    buffer = buffer[match.end():]
                    if sentence:
                        with self._lock:
                            if self._cancelled or cancel_tts_event.is_set():
                                break
                        self._speak_sentence(sentence, on_sentence_callback)
                        spoken_count += 1

            if spoken_count == 0:
                print("⚠️ [KokoroTTS] No sentences spoken (empty stream).")
            else:
                print(f"✅ [KokoroTTS] Streamed {spoken_count} sentence(s).")

        except Exception as e:
            print(f"❌ [KokoroTTS] Streaming playback failed: {e}")
        finally:
            with self._lock:
                self._is_speaking = False
            tts_mark_stop()
            self._close_playback_stream()

    # ── Cancel / barge-in ────────────────────────────────────────

    def cancel(self):
        """Immediately stop any ongoing speech playback (barge-in)."""
        tts_request_cancel()
        with self._lock:
            if not self._is_speaking:
                return
            self._cancelled = True

        print("🔇 [KokoroTTS] Barge-in — speech interrupted!")

        try:
            sd.stop()
        except Exception:
            pass
        self._abort_playback_stream()
        tts_mark_stop()

    # ── Private helpers ──────────────────────────────────────────

    def _speak_sentence(self, sentence: str, on_sentence_callback=None):
        """Synthesize one sentence and play it."""
        sentence = self._clean_for_speech(sentence)
        if not sentence:
            return
        preview = sentence[:80]
        print(f"   🗣️ [KokoroTTS] \"{preview}{'...' if len(sentence) > 80 else ''}\"")

        if on_sentence_callback:
            on_sentence_callback(sentence)

        self._synthesize_and_play(sentence)

    def _synthesize_and_play(self, text: str):
        """Run Kokoro synthesis and play in 30ms chunks (cancellable)."""
        if not self._kokoro or not _HAS_AUDIO:
            return

        try:
            audio, sr = self._kokoro.synthesize(
                text=text,
                voice=self._voice_name,
                speed=self._speed,
            )
            # audio is float32 ndarray in [-1, 1], sr is 24000

            self._ensure_playback_stream(sr)
            chunk_samples = max(1, int(sr * 0.030))  # 30ms chunks

            idx = 0
            n = len(audio)
            while idx < n:
                if cancel_tts_event.is_set():
                    return
                with self._lock:
                    if self._cancelled:
                        return

                sl = audio[idx:idx + chunk_samples]
                idx += chunk_samples

                if self._playback_stream is not None:
                    self._playback_stream.write(sl)
                else:
                    sd.play(sl, samplerate=sr, blocking=True)

        except Exception as e:
            print(f"⚠️ [KokoroTTS] Synthesis error: {e}")

    def _ensure_playback_stream(self, sample_rate: int):
        """Create and start an OutputStream for low-latency chunked playback."""
        if not _HAS_AUDIO:
            return
        if self._playback_stream is not None:
            return
        try:
            self._playback_stream = sd.OutputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
            )
            self._playback_stream.start()
        except Exception as e:
            print(f"⚠️ [KokoroTTS] Failed to open OutputStream, falling back: {e}")
            self._playback_stream = None

    def _abort_playback_stream(self):
        """Abort playback immediately without draining buffers."""
        s = self._playback_stream
        if s is None:
            return
        try:
            if hasattr(s, "abort"):
                s.abort()
            else:
                s.stop()
        except Exception:
            pass
        try:
            s.close()
        except Exception:
            pass
        self._playback_stream = None

    def _close_playback_stream(self):
        """Close the playback stream (normal completion path)."""
        s = self._playback_stream
        if s is None:
            return
        try:
            s.stop()
        except Exception:
            pass
        try:
            s.close()
        except Exception:
            pass
        self._playback_stream = None

    def _build_kokoro(self):
        """Load the Kokoro ONNX model."""
        if not _HAS_KOKORO:
            print("⚠️ [KokoroTTS] Running in console-only mode (no kokoro-onnx)")
            return

        if not os.path.exists(self._model_path):
            print(f"⚠️ [KokoroTTS] Model not found: {self._model_path}")
            print("   Download from kokoro-onnx releases and place in voice/kokoro_models/")
            return

        # Check for espeak-ng (required by Kokoro for phonemization)
        if not shutil.which("espeak-ng"):
            print("⚠️ [KokoroTTS] espeak-ng not found. "
                  "Install with: brew install espeak-ng (macOS) "
                  "or apt install espeak-ng (Linux)")

        try:
            self._kokoro = Kokoro(
                model_path=self._model_path,
                voices_path=self._voices_path,
            )
            print(f"✅ [KokoroTTS] Kokoro voice loaded — "
                  f"voice: {self._voice_name}, persona: {self._active_persona_name}")
        except Exception as e:
            print(f"❌ [KokoroTTS] Failed to load Kokoro: {e}")
            self._kokoro = None

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """
        Strip markdown / code artifacts and symbols for clean speech output.
        (Same logic as PiperTTSService._clean_for_speech)
        """
        # Guard: never speak raw Python exception strings
        _EXCEPTION_PATTERN = re.compile(
            r'^(NameError|TypeError|ValueError|AttributeError|KeyError|'
            r'IndexError|RuntimeError|ImportError|ModuleNotFoundError|'
            r'ZeroDivisionError|AssertionError|OSError|FileNotFoundError|'
            r'StopIteration|GeneratorExit|SystemExit|Exception|BaseException|'
            r'Traceback \(most recent call last\))',
            re.MULTILINE
        )
        if _EXCEPTION_PATTERN.search(text.strip()):
            return "I ran into a small issue. Please try again."

        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)
        text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\*{3}([^*]+)\*{3}', r'\1', text)
        text = re.sub(r'\*{2}([^*]+)\*{2}', r'\1', text)
        text = re.sub(r'\*([^*\n]+)\*', r'\1', text)
        text = re.sub(r'_{3}([^_]+)_{3}', r'\1', text)
        text = re.sub(r'_{2}([^_]+)_{2}', r'\1', text)
        text = re.sub(r'_([^_\n]+)_', r'\1', text)
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\|', ' ', text)
        text = re.sub(r'^[-:]+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[?[Pp]laceholder\b[^\]\n]*\]?\.?', '', text)
        text = re.sub(
            r'\[(?:Add|Insert|Include|Enter|TODO|TBD|Content goes here)[^\]]*\]',
            '', text, flags=re.IGNORECASE
        )
        text = re.sub(r'\bCaptain\b[\s:,.\!]*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'#+', '', text)
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'^[ \t]+', '', text, flags=re.MULTILINE)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        if len(text) > 2000:
            cut = text[:2000].rfind('.')
            if cut > 400:
                text = text[:cut + 1]
            else:
                text = text[:2000] + "... I've summarized the rest for brevity."

        return text
