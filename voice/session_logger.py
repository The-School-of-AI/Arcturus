# voice/session_logger.py

"""
Voice Session Logger — persists every voice interaction to dated JSON files.

Each voice session (wake → idle) produces a JSON file under:
    memory/voice_sessions/YYYY/MM/DD/voice_session_<session_id>.json

Each file contains a header with session metadata and an ordered list of
turns.  Every turn captures:
    - timestamp (ISO 8601)
    - user_transcript (STT text from the user)
    - tts_text (what the agent spoke back)
    - run_id (Nexus run ID, if routed through Nexus)
    - persona (active voice persona at the time)
    - latency_ms (wall-clock time from query dispatch to TTS start)
    - source ("nexus" or "direct")

The logger is thread-safe and designed to be called from the Orchestrator's
background threads.
"""

import json
import time
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone


_VOICE_LOG_DIR = Path(__file__).resolve().parent.parent / "memory" / "voice_sessions"


class VoiceSessionLogger:
    """
    Accumulates voice turns for the current session and flushes to disk.

    Usage:
        logger = VoiceSessionLogger()
        logger.start_session()                       # on wake
        logger.log_turn(user_text, tts_text, ...)    # per interaction
        logger.end_session()                          # on idle
    """

    def __init__(self, log_dir: Path = None):
        self._log_dir = log_dir or _VOICE_LOG_DIR
        self._lock = threading.Lock()

        # Current session state
        self._session_id: str | None = None
        self._session_start: str | None = None
        self._turns: list[dict] = []
        self._conversation_history: list[dict] = []

    # ── Session lifecycle ───────────────────────────────────

    def start_session(self) -> str:
        """Begin a new voice session.  Returns the session_id."""
        with self._lock:
            # Flush any previous un-ended session
            if self._session_id and self._turns:
                self._flush_unlocked()

            self._session_id = f"vs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            self._session_start = datetime.now(timezone.utc).isoformat()
            self._turns = []
            self._conversation_history = []
            return self._session_id

    def save_session(self) -> str | None:
        """
        Flush the current session to disk WITHOUT clearing history.
        This preserves conversation context across multiple wake→idle cycles
        so the user can have multi-turn conversations.
        Returns the path to the saved JSON file, or None if nothing to save.
        """
        with self._lock:
            if not self._session_id:
                return None
            path = self._flush_unlocked()
            return str(path) if path else None

    def end_session(self) -> str | None:
        """
        Close the current session and flush to disk.
        Returns the path to the saved JSON file, or None if nothing to save.
        """
        with self._lock:
            if not self._session_id:
                return None
            path = self._flush_unlocked()
            self._session_id = None
            self._session_start = None
            self._turns = []
            self._conversation_history = []
            return str(path) if path else None

    # ── Turn logging ────────────────────────────────────────

    def log_turn(
        self,
        user_transcript: str,
        tts_text: str | None = None,
        run_id: str | None = None,
        persona: str | None = None,
        latency_ms: float | None = None,
        source: str = "nexus",
        extra: dict | None = None,
    ) -> None:
        """Record a single voice interaction turn."""
        turn = {
            "turn_number": len(self._turns) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_transcript": user_transcript,
            "tts_text": tts_text,
            "run_id": run_id,
            "persona": persona,
            "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
            "source": source,
        }
        if extra:
            turn["extra"] = extra

        with self._lock:
            self._turns.append(turn)

            # Also maintain conversation history for context injection
            self._conversation_history.append({"role": "user", "content": user_transcript})
            if tts_text:
                self._conversation_history.append({"role": "assistant", "content": tts_text})

    # ── Conversation history (for context injection) ────────

    def get_conversation_history(self) -> list[dict]:
        """
        Return the conversation history for the current session.
        Each entry: {"role": "user"|"assistant", "content": "..."}
        """
        with self._lock:
            return list(self._conversation_history)

    def get_history_prompt(self, max_turns: int = 10) -> str:
        """
        Format recent conversation history as a text block suitable
        for injection into an LLM prompt.
        """
        with self._lock:
            history = list(self._conversation_history)

        if not history:
            return ""

        # Keep the last N messages (max_turns * 2 for user+assistant pairs)
        recent = history[-(max_turns * 2):]

        lines = ["[Conversation so far]"]
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Arcturus"
            lines.append(f"  {role}: {msg['content']}")
        lines.append("[End of conversation history]\n")

        return "\n".join(lines)

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def turn_count(self) -> int:
        with self._lock:
            return len(self._turns)

    def get_turns(self) -> list[dict]:
        """Return all turns for the current session (for API exposure)."""
        with self._lock:
            return list(self._turns)

    # ── Private ─────────────────────────────────────────────

    def _flush_unlocked(self) -> Path | None:
        """Write the current session to disk.  Must hold self._lock."""
        if not self._turns:
            return None

        now = datetime.now()
        folder = self._log_dir / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
        folder.mkdir(parents=True, exist_ok=True)

        filepath = folder / f"{self._session_id}.json"

        session_data = {
            "session_id": self._session_id,
            "started_at": self._session_start,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "total_turns": len(self._turns),
            "turns": self._turns,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        return filepath
