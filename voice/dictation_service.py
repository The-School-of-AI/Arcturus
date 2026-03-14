# voice/dictation_service.py

"""
Dictation Mode — long-form speech → document input.

When the Orchestrator enters DICTATING state, every STT fragment is routed
here instead of to the Nexus agent.  Fragments are:
  1. Accumulated in an in-memory buffer (self._document)
  2. Periodically auto-saved to  memory/dictation/<id>.txt
  3. Exposed via  get_document() / get_document_as_markdown()

Usage (via Orchestrator):
    orch.start_dictation()      # switches to DICTATING state
    ...user speaks...
    text = orch.stop_dictation()  # returns the finished document

The saved files live under:
    memory/dictation/YYYY/MM/dictation_<id>.txt
"""

import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DICTATION_DIR = Path(__file__).resolve().parent.parent / "memory" / "dictation"

# How often (seconds) to auto-save the document while dictation is active.
_AUTOSAVE_INTERVAL_SEC = 10.0


class DictationSession:
    """
    Manages one dictation session: accumulates fragments, auto-saves, finishes.
    Thread-safe — all public methods acquire the internal lock.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._lock = threading.Lock()
        self._fragments: list[str] = []    # raw STT fragments as received
        self._autosave_timer: Optional[threading.Timer] = None
        self._finished = False
        self._saved_path: Optional[Path] = None

        self._schedule_autosave()

    # ── Fragment accumulation ───────────────────────────────────────

    def push_fragment(self, fragment: str) -> None:
        """Append one STT transcript fragment to the document."""
        fragment = fragment.strip()
        if not fragment:
            return
        with self._lock:
            if self._finished:
                return
            self._fragments.append(fragment)
            print(f"   📝 [Dictation] Fragment #{len(self._fragments)}: \"{fragment[:80]}\"")

    # ── Document access ────────────────────────────────────────────

    def get_document(self) -> str:
        """
        Return the current accumulated document as plain text.
        Fragments are joined with spaces; double-spaces are collapsed.
        """
        with self._lock:
            raw = " ".join(self._fragments)
        return re.sub(r" {2,}", " ", raw).strip()

    def get_document_as_markdown(self, title: str = "Dictated Document") -> str:
        """
        Return the document wrapped in a simple Markdown structure,
        suitable for saving to a canvas card or sending to a text editor.
        """
        text = self.get_document()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            f"# {title}\n\n"
            f"*Dictated: {now}*\n\n"
            f"---\n\n"
            f"{text}\n"
        )

    @property
    def fragment_count(self) -> int:
        with self._lock:
            return len(self._fragments)

    @property
    def word_count(self) -> int:
        return len(self.get_document().split())

    # ── Finish / save ──────────────────────────────────────────────

    def finish(self) -> str:
        """
        Mark dictation as complete, cancel auto-save, and write the final
        document to disk.  Returns the saved file path string.
        """
        with self._lock:
            if self._finished:
                return str(self._saved_path) if self._saved_path else ""
            self._finished = True
            self._cancel_autosave_unlocked()

        path = self._save_to_disk()
        with self._lock:
            self._saved_path = path

        print(f"✅ [Dictation] Session {self.session_id} finished — "
              f"{self.fragment_count} fragment(s), {self.word_count} word(s). "
              f"Saved → {path}")
        return str(path)

    def save_snapshot(self) -> None:
        """Write a mid-session snapshot (called by autosave timer)."""
        if self._finished:
            return
        path = self._save_to_disk()
        print(f"💾 [Dictation] Auto-saved snapshot → {path}")

    def save_to_notes(self) -> str:
        """
        Save the final document as Markdown to the central Notes directory.
        Returns the saved file path string.
        """
        notes_dir = Path(__file__).resolve().parent.parent / "data" / "Notes" / "Voice"
        notes_dir.mkdir(parents=True, exist_ok=True)
        
        # Use a human-friendly timestamped name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"Dictation_{timestamp}.md"
        filepath = notes_dir / filename
        
        doc_md = self.get_document_as_markdown(title=f"Voice Dictation ({timestamp})")
        
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(doc_md)
            
        print(f"📄 [Dictation] Saved Markdown note → {filepath}")
        return str(filepath)

    # ── Private helpers ────────────────────────────────────────────

    def _save_to_disk(self) -> Path:
        text = self.get_document()
        if not text:
            # Nothing to save yet — create a placeholder
            text = "(empty dictation)"

        now = datetime.now()
        folder = _DICTATION_DIR / str(now.year) / f"{now.month:02d}"
        folder.mkdir(parents=True, exist_ok=True)

        filepath = folder / f"dictation_{self.session_id}.txt"
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(f"Session: {self.session_id}\n")
            fh.write(f"Started: {self.started_at}\n")
            fh.write(f"Saved:   {datetime.now(timezone.utc).isoformat()}\n")
            fh.write(f"Words:   {self.word_count}\n")
            fh.write("-" * 40 + "\n\n")
            fh.write(text)
            fh.write("\n")
        return filepath

    def _schedule_autosave(self) -> None:
        timer = threading.Timer(_AUTOSAVE_INTERVAL_SEC, self._autosave_tick)
        timer.daemon = True
        timer.start()
        with self._lock:
            self._autosave_timer = timer

    def _autosave_tick(self) -> None:
        if not self._finished:
            self.save_snapshot()
            self._schedule_autosave()

    def _cancel_autosave_unlocked(self) -> None:
        """Cancel the autosave timer.  Caller must hold self._lock."""
        if self._autosave_timer:
            self._autosave_timer.cancel()
            self._autosave_timer = None
