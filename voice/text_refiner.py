# voice/text_refiner.py

"""
LLM-powered transcript post-processor.

Takes raw STT output and refines it using a state-of-the-art model to produce
clean, properly formatted text before forwarding to the nexus channel.

Handles:
  - Auto-punctuation (periods, commas, question marks)
  - Number formatting (e.g., "twenty three" → "23", "two point five" → "2.5")
  - Capitalization (sentence case, proper nouns)
  - Minor grammar normalization
  - Filler word removal ("um", "uh", "like")
"""

import asyncio
from core.model_manager import ModelManager
from voice.config import VOICE_CONFIG

REFINE_PROMPT = """You are a voice-transcript post-processor for a voice assistant called Arcturus.

Your ONLY job is to clean up raw speech-to-text output. Apply these rules:

1. **Punctuation**: Add correct sentence-ending punctuation (periods, question marks, exclamation marks) and commas where natural pauses exist.
2. **Numbers**: Convert spoken numbers to digits (e.g., "twenty three" → "23", "one hundred and fifty" → "150", "two point five" → "2.5", "three percent" → "3%").
3. **Capitalization**: Capitalize the first word of each sentence and proper nouns.
4. **Fillers**: Remove filler words like "um", "uh", "like", "you know", "so" (when used as fillers).
5. **Minor grammar**: Fix obvious speech-to-text errors but NEVER change the user's meaning or intent.

CRITICAL RULES:
- Output ONLY the cleaned text. No explanations, no quotes, no labels.
- Do NOT add content the user didn't say.
- Do NOT summarize or paraphrase. Keep the original wording.
- If the input is already clean, return it as-is.

Raw transcript: "{text}"
"""


class TextRefiner:
    """
    Refines raw STT transcripts using an LLM for punctuation,
    number formatting, and grammar normalization.
    """

    def __init__(self):
        cfg = VOICE_CONFIG.get("text_refiner", {})
        self._enabled = cfg.get("enabled", True)
        model_name = cfg.get("model", "gemini-2.5-flash-lite")
        provider = cfg.get("provider", "gemini")

        if self._enabled:
            self._model = ModelManager(
                model_name=model_name,
                provider=provider,
            )
            # print(f"✅ [TextRefiner] Initialized (model: {provider}/{model_name})")
        else:
            self._model = None
            print("ℹ️ [TextRefiner] Disabled via config")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def refine(self, raw_text: str) -> str:
        """
        Synchronous entry point — safe to call from the Orchestrator thread.
        Returns the refined text, or the original if refinement fails or is disabled.
        """
        if not self._enabled or not raw_text or not raw_text.strip():
            return raw_text

        # Fast-path: very short utterances (1-3 words) don't need LLM cleanup
        words = raw_text.strip().split()
        if len(words) <= 3:
            cleaned = raw_text.strip()
            cleaned = cleaned[0].upper() + cleaned[1:] if cleaned else cleaned
            if cleaned and cleaned[-1] not in ".?!":
                cleaned += "."
            return cleaned

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._refine_async(raw_text), loop
                )
                return future.result(timeout=5.0)
            else:
                return asyncio.run(self._refine_async(raw_text))

        except Exception as e:
            print(f"⚠️ [TextRefiner] Refinement failed, using raw text: {e}")
            return raw_text

    async def _refine_async(self, raw_text: str) -> str:
        """
        Call the LLM to refine the transcript.
        """
        prompt = REFINE_PROMPT.format(text=raw_text)
        refined = await self._model.generate_text(prompt)
        refined = refined.strip().strip('"').strip("'")

        # Safety: if the model returns empty or something wildly different, keep original
        if not refined or len(refined) < len(raw_text) * 0.3:
            return raw_text

        return refined
