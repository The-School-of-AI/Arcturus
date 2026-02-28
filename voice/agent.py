# voice/agent.py

import asyncio
import json
from core.model_manager import ModelManager

class Agent:
    """
    A voice agent that uses an LLM to extract intent and action from 
    transcribed text and provides a relevant response.

    Supports conversation context: when `conversation_history` is
    provided to respond(), the agent sees prior exchanges and can
    give context-aware answers (just like text chat sessions).
    """
    def __init__(self):
        self.is_processing = False
        # Initialize the model manager. 
        # It will use defaults from models.json/yaml (usually Gemini or Ollama)
        self.model = ModelManager()
        self._loop = None

    def respond(self, text: str, conversation_history: str = "") -> str:
        """
        Reads text from STT, uses LLM to extract intent/action,
        and returns a response string.

        Args:
            text: The transcribed user utterance.
            conversation_history: Formatted prior conversation context
                                  (from VoiceSessionLogger.get_history_prompt).
        """
        self.is_processing = True
        print(f"🧠 [AgentVoice] LLM Analyzing: \"{text}\"")
        
        try:
            # Handle async call from the Orchestrator thread
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # Fallback if no loop is running in this thread
                pass

            if self._loop and self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._get_llm_response(text, conversation_history), self._loop
                )
                return future.result()
            else:
                return asyncio.run(self._get_llm_response(text, conversation_history))
        except Exception as e:
            print(f"❌ [AgentVoice] LLM Error: {e}")
            return f"I'm sorry, I encountered an error processing your request: {str(e)}"
        finally:
            self.is_processing = False

    async def _get_llm_response(self, text: str, conversation_history: str = "") -> str:
        """
        Queries the LLM with a system-style prompt to extract intent and action.
        Includes conversation history when available for context continuity.
        """
        # Build the prompt with optional conversation context
        history_block = ""
        if conversation_history:
            history_block = (
                "\n--- Prior conversation in this voice session ---\n"
                f"{conversation_history}"
                "--- End of prior conversation ---\n\n"
            )

        prompt = (
            "You are Arcturus, a voice assistant. Analyze the following user transcription.\n"
            "Task: Extract the user's INTENT and requested ACTION.\n"
            f"{history_block}"
            "Transcription: \"" + text + "\"\n\n"
            "Provide a concise, helpful verbal response that confirms you understood the intent "
            "and what action you would take. Keep it short (1-2 sentences) for voice playback. "
            "Do not mention that you are listening for further commands or refer to any 30-second window."
        )

        if conversation_history:
            prompt += (
                "\n\nIMPORTANT: Use the conversation history above for context. "
                "The user may be referring to something discussed earlier in this "
                "voice session. Maintain continuity."
            )

        response = await self.model.generate_text(prompt)
        return response.strip()

    def cancel(self):
        """
        Stops any ongoing processing.
        """
        if self.is_processing:
            print("🛑 [AgentVoice] LLM processing cancelled.")
            self.is_processing = False
