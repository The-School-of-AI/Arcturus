# voice/piper_tts_service.py

"""
Piper TTS — Local, offline text-to-speech with **streaming playback**.

Key feature: speak_streamed() accepts a queue/iterator of text chunks and
begins speaking the *first complete sentence* immediately — it does NOT
wait for the entire response.  This makes voice responses feel instant
even when the upstream LLM / Nexus is still generating output.

Fallback for Azure Speech:  runs 100 % locally, zero API cost, works
offline.  Quality is very good for English with the right ONNX model.

Requires:
    pip install piper-tts sounddevice numpy

Model files:
    Download .onnx + .onnx.json from  https://huggingface.co/rhasspy/piper-voices
    Place them under  voice/piper_models/<model_name>/
"""

import os
import re
import queue
import threading
import wave
import io
import struct
import time

try:
    from piper import PiperVoice          # type: ignore
    _HAS_PIPER = True
except ImportError:
    _HAS_PIPER = False
    print("⚠️ [PiperTTS] piper-tts not installed. "
          "Install with: pip install piper-tts")

try:
    import sounddevice as sd              # type: ignore
    import numpy as np                    # type: ignore
    _HAS_AUDIO = True
except ImportError:
    _HAS_AUDIO = False
    print("⚠️ [PiperTTS] sounddevice/numpy not installed. "
          "Install with: pip install sounddevice numpy")

from shared.state import (
    cancel_tts_event,
    tts_mark_start,
    tts_mark_stop,
    tts_request_cancel,
)
from voice.config import VOICE_CONFIG

# ── Sentence-boundary regex ───────────────────────────────────
# Splits on . ! ? followed by whitespace or end — keeps the punctuation.
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')


class PiperTTSService:
    """
    Local TTS via Piper (ONNX) with real-time streaming playback.

    Interface mirrors TTSService so the Orchestrator can use either
    backend interchangeably:

        .speak(text)         — synthesise full text, block until done
        .speak_streamed(q)   — consume chunks from a Queue, speak ASAP
        .cancel()            — barge-in: stop playback immediately
        .is_speaking         — True while audio is playing
    """

    def __init__(
        self,
        model_path: str | None = None,
        config_path: str | None = None,
        speaker_id: int | None = None,
        length_scale: float = 1.0,        # 1.0 = normal speed
        sentence_silence: float = 0.15,   # pause between sentences (sec)
    ):
        self._is_speaking = False
        self._cancelled = False
        self._lock = threading.Lock()
        self._voice: PiperVoice | None = None
        self._speaker_id = speaker_id
        self._length_scale = length_scale
        self._sentence_silence = sentence_silence

        # Playback control
        self._playback_stream = None

        # Resolve model path
        if model_path is None:
            # Default: look in voice/piper_models/
            _voice_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(_voice_dir, "piper_models", "en_US-lessac-medium.onnx")

        if config_path is None and model_path:
            config_path = model_path + ".json"

        self._model_path = model_path
        self._config_path = config_path

        self._build_voice()

    # ── Public properties (TTSService compat) ──────────────────

    @property
    def active_persona(self) -> str | None:
        """Piper doesn't have Azure-style personas — returns None."""
        return None

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._is_speaking

    # ── Core: speak() — full text at once ──────────────────────

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
        # Global speaking state + grace window for barge-in gating.
        grace_ms = VOICE_CONFIG.get("barge_in", {}).get("grace_ms", 700)
        tts_mark_start(grace_ms=grace_ms)

        preview = text[:120].replace('\n', ' ')
        print(f"🔊 [PiperTTS] Speaking: \"{preview}{'...' if len(text) > 120 else ''}\"")

        if not self._voice:
            print(f"   📢 [PiperTTS-Fallback] {text}")
            with self._lock:
                self._is_speaking = False
            return

        try:
            # Split into sentences for natural pauses
            sentences = _SENTENCE_RE.split(text)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                with self._lock:
                    if self._cancelled or cancel_tts_event.is_set():
                        break

                self._synthesize_and_play_streaming(sentence)

        except Exception as e:
            print(f"❌ [PiperTTS] Playback failed: {e}")
        finally:
            with self._lock:
                self._is_speaking = False
            tts_mark_stop()
            self._close_playback_stream()

    # ── Core: speak_streamed() — streaming chunks ─────────────

    def speak_streamed(self, text_queue: queue.Queue, sentinel=None):
        """
        Consume text chunks from *text_queue* and start speaking as
        soon as a complete sentence is available.

        The producer (Orchestrator) pushes partial text strings into
        the queue.  When we accumulate enough to form a sentence
        (ending in .!?) we immediately synthesise and play it.

        Args:
            text_queue:  queue.Queue that yields str chunks.
                         The producer pushes *sentinel* (default None)
                         when done.
            sentinel:    Value that signals "no more chunks".

        This method **blocks** until all chunks are spoken or
        cancel() is called.
        """
        with self._lock:
            self._is_speaking = True
            self._cancelled = False
        grace_ms = VOICE_CONFIG.get("barge_in", {}).get("grace_ms", 700)
        tts_mark_start(grace_ms=grace_ms)

        print("🔊 [PiperTTS] Streaming mode — waiting for first chunk...")

        if not self._voice:
            # Drain the queue (fallback mode)
            full_text = []
            while True:
                chunk = text_queue.get()
                if chunk is sentinel:
                    break
                full_text.append(chunk)
            joined = " ".join(full_text)
            print(f"   📢 [PiperTTS-Fallback] {joined}")
            with self._lock:
                self._is_speaking = False
            return

        try:
            buffer = ""
            spoken_count = 0

            while True:
                with self._lock:
                    if self._cancelled or cancel_tts_event.is_set():
                        break

                # Non-blocking get with short timeout so we can check cancel
                try:
                    chunk = text_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if chunk is sentinel:
                    # Flush remaining buffer
                    if buffer.strip():
                        self._speak_sentence(buffer.strip())
                        spoken_count += 1
                    break

                buffer += chunk

                # Try to extract complete sentences from buffer
                while True:
                    match = _SENTENCE_RE.search(buffer)
                    if not match:
                        break

                    # Everything up to and including the sentence-end
                    sentence = buffer[:match.start()].strip()
                    buffer = buffer[match.end():]

                    if sentence:
                        with self._lock:
                            if self._cancelled or cancel_tts_event.is_set():
                                break
                        self._speak_sentence(sentence)
                        spoken_count += 1

            if spoken_count == 0:
                print("⚠️ [PiperTTS] No sentences spoken (empty stream).")
            else:
                print(f"✅ [PiperTTS] Streamed {spoken_count} sentence(s).")

        except Exception as e:
            print(f"❌ [PiperTTS] Streaming playback failed: {e}")
        finally:
            with self._lock:
                self._is_speaking = False
            tts_mark_stop()
            self._close_playback_stream()

    # ── Cancel / barge-in ──────────────────────────────────────

    def cancel(self):
        """Immediately stop any ongoing speech playback (barge-in)."""
        # Global cancel event (checked by synthesis/playback loops).
        tts_request_cancel()
        with self._lock:
            if not self._is_speaking:
                # Nothing to cancel — avoid logging a barge-in when we weren't speaking.
                return
            self._cancelled = True
            # Do not rely on draining buffers. We abort the output path immediately.

        print("🔇 [PiperTTS] Barge-in — speech interrupted!")

        # Stop the sounddevice stream immediately (do not drain buffers).
        try:
            sd.stop()
        except Exception:
            pass
        self._abort_playback_stream()
        tts_mark_stop()

    # ── Private helpers ────────────────────────────────────────

    def _speak_sentence(self, sentence: str):
        """Synthesize one sentence and play it.  Used by both speak() and speak_streamed()."""
        sentence = self._clean_for_speech(sentence)
        if not sentence:
            return
        preview = sentence[:80]
        print(f"   🗣️ [PiperTTS] \"{preview}{'...' if len(sentence) > 80 else ''}\"")
        self._synthesize_and_play_streaming(sentence)

    def _ensure_playback_stream(self, sample_rate: int):
        """
        Create and start an OutputStream for low-latency chunked playback.
        """
        if not _HAS_AUDIO:
            return
        if self._playback_stream is not None:
            return
        try:
            self._playback_stream = sd.OutputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                # blocksize is a hint; we also slice writes to 20–40ms
            )
            self._playback_stream.start()
        except Exception as e:
            # Fall back to sd.play path if stream can't be created.
            print(f"⚠️ [PiperTTS] Failed to open OutputStream, falling back: {e}")
            self._playback_stream = None

    def _abort_playback_stream(self):
        """
        Abort playback immediately without draining buffers.
        """
        s = self._playback_stream
        if s is None:
            return
        try:
            # abort() is preferred for immediate stop; not all backends expose it.
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
        """
        Close the playback stream (normal completion path).
        """
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

    def _synthesize_and_play_streaming(self, text: str):
        """
        Run Piper synthesis and play audio in small chunks (20–40ms),
        checking cancellation on every chunk.
        """
        if not self._voice or not _HAS_AUDIO:
            return

        try:
            from piper.config import SynthesisConfig

            sample_rate = self._voice.config.sample_rate

            # Build a SynthesisConfig with the parameters Piper supports
            syn_config = SynthesisConfig(
                length_scale=self._length_scale,
                speaker_id=self._speaker_id,
            )

            # Prepare output stream for chunked playback.
            self._ensure_playback_stream(sample_rate)

            # Target chunk size: 30ms (within required 20–40ms).
            chunk_samples = max(1, int(sample_rate * 0.030))

            # voice.synthesize() yields AudioChunk objects (numpy int16 arrays).
            for audio_chunk in self._voice.synthesize(text, syn_config):
                if cancel_tts_event.is_set():
                    return
                with self._lock:
                    if self._cancelled:
                        return

                arr_i16 = audio_chunk.audio_int16_array
                if arr_i16 is None or len(arr_i16) == 0:
                    continue

                # Convert to float32 [-1, 1)
                arr_f32 = arr_i16.astype(np.float32) / 32768.0

                # Write in small slices for low latency + responsive cancel.
                idx = 0
                n = len(arr_f32)
                while idx < n:
                    if cancel_tts_event.is_set():
                        return
                    with self._lock:
                        if self._cancelled:
                            return

                    sl = arr_f32[idx: idx + chunk_samples]
                    idx += chunk_samples

                    if self._playback_stream is not None:
                        self._playback_stream.write(sl)
                    else:
                        # Fallback: sd.play on a small slice (still cancellable via sd.stop()).
                        sd.play(sl, samplerate=sample_rate, blocking=True)

            # Sentence gap: write silence (also chunked/cancellable).
            if self._sentence_silence > 0:
                silence_total = int(sample_rate * self._sentence_silence)
                remaining = silence_total
                while remaining > 0:
                    if cancel_tts_event.is_set():
                        return
                    with self._lock:
                        if self._cancelled:
                            return
                    take = min(chunk_samples, remaining)
                    remaining -= take
                    silence = np.zeros(take, dtype=np.float32)
                    if self._playback_stream is not None:
                        self._playback_stream.write(silence)
                    else:
                        sd.play(silence, samplerate=sample_rate, blocking=True)

        except Exception as e:
            print(f"⚠️ [PiperTTS] Synthesis error: {e}")

    def _clean_for_speech(self, text: str) -> str:
        """
        Strip markdown / code artifacts and symbols for clean speech output.
        Kept in sync with Orchestrator._markdown_to_speech().
        """
        # ── Guard: never speak raw Python exception strings ─────────────────
        _EXCEPTION_PATTERN = re.compile(
            r'^(NameError|TypeError|ValueError|AttributeError|KeyError|'
            r'IndexError|RuntimeError|ImportError|ModuleNotFoundError|'
            r'ZeroDivisionError|AssertionError|OSError|FileNotFoundError|'
            r'StopIteration|GeneratorExit|SystemExit|Exception|BaseException|'
            r'Traceback \(most recent call last\))',
            re.MULTILINE
        )
        if _EXCEPTION_PATTERN.search(text.strip()):
            print(f"⚠️ [PiperTTS] Suppressing error string: {text[:120]!r}")
            return "I ran into a small issue. Please try again."

        # Step 1: Remove code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)

        # Step 2: Remove markdown images
        text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)

        # Step 3: Convert links → label only
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Step 4: Strip header markers (# ## ### at line start)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Step 5: Strip bold/italic — longest-match first (*** → ** → *)
        text = re.sub(r'\*{3}([^*]+)\*{3}', r'\1', text)
        text = re.sub(r'\*{2}([^*]+)\*{2}', r'\1', text)
        text = re.sub(r'\*([^*\n]+)\*',     r'\1', text)
        text = re.sub(r'_{3}([^_]+)_{3}',   r'\1', text)
        text = re.sub(r'_{2}([^_]+)_{2}',   r'\1', text)
        text = re.sub(r'_([^_\n]+)_',       r'\1', text)

        # Step 6: Remove horizontal rules
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

        # Step 7: Remove bullet/list markers
        text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)

        # Step 8: Remove table formatting
        text = re.sub(r'\|', ' ', text)
        text = re.sub(r'^[-:]+\s*$', '', text, flags=re.MULTILINE)

        # Step 9: Remove LLM placeholder boilerplate
        text = re.sub(r'\[?[Pp]laceholder\b[^\]\n]*\]?\.?', '', text)
        text = re.sub(
            r'\[(?:Add|Insert|Include|Enter|TODO|TBD|Content goes here)[^\]]*\]',
            '', text, flags=re.IGNORECASE
        )

        # Step 10: Remove "Captain" in all forms
        text = re.sub(r'\bCaptain\b[\s:,.\!]*', '', text, flags=re.IGNORECASE)

        # Step 11: Scrub surviving bare # and * characters
        text = re.sub(r'#+',  '', text)
        text = re.sub(r'\*+', '', text)

        # Step 12: Whitespace cleanup
        text = re.sub(r'^[ \t]+', '', text, flags=re.MULTILINE)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        # Step 13: Truncate for voice (Piper limit is higher for streaming)
        if len(text) > 2000:
            cut = text[:2000].rfind('.')
            if cut > 400:
                text = text[:cut + 1]
            else:
                text = text[:2000] + "... I've summarized the rest for brevity."

        return text

    def _build_voice(self):
        """Load the Piper ONNX model."""
        self._voice = None

        if not _HAS_PIPER:
            print("⚠️ [PiperTTS] Running in console-only mode (no piper-tts)")
            return

        if not self._model_path or not os.path.exists(self._model_path):
            print(f"⚠️ [PiperTTS] Model not found: {self._model_path}")
            print("   Download from: https://huggingface.co/rhasspy/piper-voices")
            print("   Place .onnx + .onnx.json in voice/piper_models/")
            return

        try:
            self._voice = PiperVoice.load(
                self._model_path,
                config_path=self._config_path,
            )
            print(f"✅ [PiperTTS] Piper voice loaded — model: {os.path.basename(self._model_path)}, "
                  f"sample_rate: {self._voice.config.sample_rate}")
        except Exception as e:
            print(f"❌ [PiperTTS] Failed to load voice: {e}")
            self._voice = None
