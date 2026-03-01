# voice/tts_service.py

"""
Text-to-Speech service using Azure Cognitive Services Speech SDK.

Synthesizes agent responses into natural speech and plays them through
the system's default audio output device.  Supports barge-in: calling
cancel() mid-stream immediately stops audio playback.

Voice Personas
--------------
Multiple voice styles (professional, casual, energetic) are user-
configurable.  Each persona bundles an Azure Neural voice name with
SSML prosody parameters (rate, pitch, volume) so the agent's delivery
adapts to the user's preferred tone.  Switch at any time with
``set_persona("casual")`` or via the ``/api/voice/persona`` endpoint.

Requires:
  pip install azure-cognitiveservices-speech
  Environment variables: AZURE_SPEECH_KEY, AZURE_SPEECH_REGION
"""

import os
import html
import threading

try:
    import azure.cognitiveservices.speech as speechsdk
    _HAS_AZURE_SPEECH = True
except ImportError:
    _HAS_AZURE_SPEECH = False
    print("⚠️ [TTS] azure-cognitiveservices-speech not installed. "
          "Install with: pip install azure-cognitiveservices-speech")


# ── Default persona definitions (used when config is not provided) ──
_DEFAULT_PERSONAS = {
    "professional": {
        "voice_name": "en-US-JennyNeural",
        "rate": "1.0",
        "pitch": "+0Hz",
        "volume": "default",
        "description": "Clear, confident, and measured — great for work & productivity.",
    },
    "casual": {
        "voice_name": "en-US-AriaNeural",
        "rate": "1.05",
        "pitch": "+2Hz",
        "volume": "default",
        "description": "Warm, friendly, and conversational — ideal for everyday chat.",
    },
    "energetic": {
        "voice_name": "en-US-DavisNeural",
        "rate": "1.15",
        "pitch": "+4Hz",
        "volume": "loud",
        "description": "Upbeat, enthusiastic, and lively — perfect for motivation & hype.",
    },
}


class TTSService:
    """
    Azure Neural TTS with real-time audio playback, barge-in support,
    and **user-configurable voice personas**.

    Features:
      - Multiple voice personas (professional, casual, energetic)
      - Runtime persona switching via set_persona()
      - Automatic SSML prosody wrapping per persona
      - High-quality Azure Neural voices
      - Synchronous speak() blocks until audio finishes (or is cancelled)
      - cancel() calls stop_speaking_async() for instant mid-sentence cutoff
      - Thread-safe state management
      - Graceful fallback to console logging if SDK is missing
    """

    def __init__(
        self,
        voice_name: str = "en-US-JennyNeural",
        speech_key: str = None,
        speech_region: str = None,
        personas: dict = None,
        active_persona: str = "professional",   
    ):
        self._is_speaking = False
        self._cancelled = False
        self._lock = threading.Lock()
        self._synthesizer = None

        # Resolve credentials
        self._speech_key = (
            speech_key or os.environ.get("AZURE_SPEECH_KEY", "")
        ).strip().strip("'\"")
        self._speech_region = (
            speech_region or os.environ.get("AZURE_SPEECH_REGION", "")
        ).strip().strip("'\"")

        # ── Persona configuration ──────────────────────────────
        self._personas: dict = personas or dict(_DEFAULT_PERSONAS)
        self._active_persona_name: str | None = None

        # Set voice_name FIRST so _apply_persona can use it as fallback
        self._voice_name = voice_name or "en-US-JennyNeural"

        # Prosody defaults (overridden by persona)
        self._rate = "1.0"
        self._pitch = "+0Hz"
        self._volume = "default"

        # Determine the initial voice
        if active_persona and active_persona in self._personas:
            self._apply_persona(active_persona)
        else:
            # Try to auto-detect which persona matches
            for pname, pconf in self._personas.items():
                if pconf.get("voice_name") == self._voice_name:
                    self._active_persona_name = pname
                    self._rate = pconf.get("rate", self._rate)
                    self._pitch = pconf.get("pitch", self._pitch)
                    self._volume = pconf.get("volume", self._volume)
                    break

        # Build the initial synthesizer
        self._build_synthesizer()

    # ── Persona Management ─────────────────────────────────────

    @property
    def active_persona(self) -> str | None:
        """Name of the currently active persona, or None."""
        return self._active_persona_name

    def list_personas(self) -> dict:
        """
        Return all available personas with their configuration.

        Returns a dict like:
            { "professional": { "voice_name": ..., "rate": ..., ... }, ... }
        """
        return dict(self._personas)

    def set_persona(self, persona_name: str) -> bool:
        """
        Switch the active voice persona at runtime.

        Args:
            persona_name: One of the keys in the personas dictionary
                          (e.g. "professional", "casual", "energetic").

        Returns:
            True if the persona was applied successfully, False if the
            persona name was not recognised.
        """
        if persona_name not in self._personas:
            print(f"⚠️ [TTS] Unknown persona '{persona_name}'. "
                  f"Available: {', '.join(self._personas.keys())}")
            return False

        old_voice = self._voice_name
        self._apply_persona(persona_name)

        # Rebuild the Azure synthesizer if the voice changed
        if self._voice_name != old_voice:
            self._build_synthesizer()

        print(f"🎭 [TTS] Persona switched → {persona_name} "
              f"(voice: {self._voice_name}, rate: {self._rate}, "
              f"pitch: {self._pitch}, volume: {self._volume})")
        return True

    def add_persona(self, name: str, config: dict) -> None:
        """
        Register a new custom persona at runtime.

        Args:
            name: Unique identifier for the persona.
            config: Dict with keys: voice_name, rate, pitch, volume,
                    description (all optional; sensible defaults used).
        """
        self._personas[name] = {
            "voice_name": config.get("voice_name", "en-US-JennyNeural"),
            "rate": config.get("rate", "1.0"),
            "pitch": config.get("pitch", "+0Hz"),
            "volume": config.get("volume", "default"),
            "description": config.get("description", ""),
        }
        print(f"➕ [TTS] Custom persona '{name}' registered.")

    # ── Core TTS ───────────────────────────────────────────────

    def speak(self, text: str):
        """
        Synthesize and play the given text through speakers.
        Blocks until playback finishes or cancel() is called.

        Plain text is automatically wrapped in SSML with the active
        persona's prosody settings.  If the input already starts with
        '<speak', it is sent as raw SSML.
        """
        if not text or not text.strip():
            return

        # Truncate extremely long responses for voice (keep it conversational)
        if len(text) > 2000:
            text = text[:2000] + "... I've summarized the rest for brevity."

        is_ssml = text.strip().startswith("<speak")

        # Auto-wrap plain text with persona prosody
        if not is_ssml:
            text = self._wrap_with_prosody(text)
            is_ssml = True

        with self._lock:
            self._is_speaking = True
            self._cancelled = False

        preview = text[:120].replace('\n', ' ')
        persona_tag = f" [{self._active_persona_name}]" if self._active_persona_name else ""
        print(f"🔊 [TTS]{persona_tag} Speaking (SSML): "
              f"\"{preview}{'...' if len(text) > 120 else ''}\"")

        if not self._synthesizer:
            # Fallback: just log (no audio)
            print(f"   📢 [TTS-Fallback] {text}")
            with self._lock:
                self._is_speaking = False
            return

        try:
            result = self._synthesizer.speak_ssml_async(text).get()

            with self._lock:
                if self._cancelled:
                    return

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                pass  # Success — audio played through speakers
            elif result.reason == speechsdk.ResultReason.Canceled:
                details = result.cancellation_details
                if details.reason == speechsdk.CancellationReason.Error:
                    print(f"⚠️ [TTS] Synthesis error: {details.error_details}")
            else:
                print(f"⚠️ [TTS] Unexpected result: {result.reason}")

        except Exception as e:
            print(f"❌ [TTS] Playback failed: {e}")
        finally:
            with self._lock:
                self._is_speaking = False

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._is_speaking

    def cancel(self):
        """
        Immediately stop any ongoing speech playback (barge-in).
        Uses Azure SDK's stop_speaking_async() to cut audio mid-sentence.
        """
        with self._lock:
            if not self._is_speaking:
                return
            self._cancelled = True
            self._is_speaking = False

        print("🔇 [TTS] Barge-in — speech interrupted!")

        if self._synthesizer and _HAS_AZURE_SPEECH:
            try:
                self._synthesizer.stop_speaking_async().get()
            except Exception as e:
                print(f"⚠️ [TTS] Error during stop: {e}")

    def speak_ssml(self, ssml: str):
        """Convenience: send raw SSML directly to speak()."""
        self.speak(ssml)

    def text_to_ssml(self, text: str, rate: str = None, pitch: str = None,
                     volume: str = None) -> str:
        """
        Wrap plain text in SSML with prosody controls.

        If rate/pitch/volume are not provided, the active persona's
        values are used as defaults.

        Args:
            text:   The plain text to speak.
            rate:   Speech rate — e.g. "0.8", "1.2", "slow", "fast".
            pitch:  Pitch shift — e.g. "+2Hz", "-1st", "high", "low".
            volume: Volume — e.g. "soft", "loud", "default", "+6dB".

        Returns:
            A fully-formed SSML string ready to pass to speak().

        Example:
            ssml = tts.text_to_ssml("Hello!", rate="1.1", pitch="+2Hz")
            tts.speak(ssml)
        """
        return self._wrap_with_prosody(
            text,
            rate=rate or self._rate,
            pitch=pitch or self._pitch,
            volume=volume or self._volume,
        )

    # ── Private Helpers ────────────────────────────────────────

    def _apply_persona(self, persona_name: str):
        """Apply the persona's settings to internal state."""
        cfg = self._personas[persona_name]
        self._active_persona_name = persona_name
        self._voice_name = cfg.get("voice_name", self._voice_name)
        self._rate = cfg.get("rate", "1.0")
        self._pitch = cfg.get("pitch", "+0Hz")
        self._volume = cfg.get("volume", "default")

    def _wrap_with_prosody(self, text: str, rate: str = None,
                           pitch: str = None, volume: str = None) -> str:
        """Wrap plain text in SSML using persona prosody defaults."""
        safe_text = html.escape(text)
        r = rate or self._rate
        p = pitch or self._pitch
        v = volume or self._volume

        return (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xml:lang="en-US">'
            f'<voice name="{self._voice_name}">'
            f'<prosody rate="{r}" pitch="{p}" volume="{v}">'
            f'{safe_text}'
            f'</prosody>'
            f'</voice>'
            f'</speak>'
        )

    def _build_synthesizer(self):
        """(Re)build the Azure SpeechSynthesizer for the current voice."""
        self._synthesizer = None

        if not _HAS_AZURE_SPEECH:
            print("⚠️ [TTS] Running in console-only mode (no Azure SDK)")
            return

        if not self._speech_key or not self._speech_region:
            print("⚠️ [TTS] AZURE_SPEECH_KEY or AZURE_SPEECH_REGION not set. "
                  "TTS will log to console only.")
            return

        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=self._speech_key,
                region=self._speech_region,
            )
            speech_config.speech_synthesis_voice_name = self._voice_name

            audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

            self._synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )
            persona_tag = f" (persona: {self._active_persona_name})" if self._active_persona_name else ""
            print(f"✅ [TTS] Azure Speech ready — voice: {self._voice_name}{persona_tag}, "
                  f"region: {self._speech_region}")
        except Exception as e:
            print(f"❌ [TTS] Failed to initialize Azure Speech: {e}")
            self._synthesizer = None
