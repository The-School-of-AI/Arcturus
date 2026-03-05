"""
Unified Extractor — One session pass: memories + preferences + graph (entities, relationships, user_facts).

Uses the unified_extraction skill prompt and returns a single JSON object conforming to
P11 unified extraction schema (schema_version, source, memories, preferences, graph, quality).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Project root
sys_path = Path(__file__).resolve().parent.parent
if str(sys_path) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(sys_path))

from config.settings_loader import get_ollama_url, get_model, get_timeout


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_json_block(raw: str) -> str:
    """Remove markdown code fences and trim."""
    s = raw.strip()
    if not s:
        return s
    # ```json ... ``` or ``` ... ```
    m = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", s, re.DOTALL)
    if m:
        return m.group(1).strip()
    if s.startswith("```"):
        for prefix in ("```json\n", "```\n"):
            if s.startswith(prefix):
                s = s[len(prefix) :]
                break
        if s.endswith("```"):
            s = s[:-3].strip()
    return s


class UnifiedExtractor:
    """
    Extracts memories, preferences, and graph (entities, entity_relationships, user_facts)
    in one LLM call from a session or message context.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or get_model("unified_extraction") or get_model("memory_extraction")
        self.api_url = get_ollama_url("chat")
        self._prompt: Optional[str] = None

    def _load_prompt(self) -> str:
        if self._prompt is not None:
            return self._prompt
        try:
            from shared.state import get_skill_manager
            skill = get_skill_manager().get_skill("unified_extraction")
            if skill and skill.prompt_text:
                self._prompt = skill.prompt_text.strip()
                return self._prompt
        except Exception:
            pass
        path = Path(__file__).resolve().parent.parent / "core" / "skills" / "library" / "unified_extraction" / "SKILL.md"
        if path.exists():
            self._prompt = path.read_text(encoding="utf-8", errors="replace").strip()
        else:
            self._prompt = (
                "Extract a single JSON object with keys: schema_version (1.0), source, memories (commands), "
                "preferences (raw, normalized), graph (entities, entity_relationships, user_facts), quality. "
                "Output valid JSON only, no markdown."
            )
        return self._prompt

    def _build_user_message(
        self,
        *,
        source_type: str,
        timestamp: str,
        conversation_turns: Optional[List[Dict[str, Any]]] = None,
        existing_memories: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        space_id: Optional[str] = None,
        run_id: Optional[str] = None,
        window: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the user prompt (INPUT section) for the LLM."""
        lines = [
            "INPUT:",
            "source:",
            f"  type: {source_type}",
            f"  timestamp: {timestamp}",
        ]
        if user_id is not None:
            lines.append(f"  user_id: {user_id}")
        if session_id is not None:
            lines.append(f"  session_id: {session_id}")
        if space_id is not None:
            lines.append(f"  space_id: {space_id}")
        if run_id is not None:
            lines.append(f"  run_id: {run_id}")

        if source_type in ("session", "message") and conversation_turns:
            lines.append("conversation:")
            lines.append("  turns:")
            for t in conversation_turns:
                role = t.get("role", "user")
                content = (t.get("content") or "").strip().replace("\n", " ")[:800]
                if not content:
                    continue
                lines.append(f"    - role: {role}  content: {content}")
            if window:
                lines.append("  window:")
                for k, v in window.items():
                    if v is not None:
                        lines.append(f"    {k}: {v}")
        elif source_type in ("import", "manual") and conversation_turns:
            lines.append("conversation:")
            lines.append("  turns: []")

        lines.append("existing_relevant_memories (aliases; ONLY use these for update/delete):")
        if existing_memories:
            for i, m in enumerate(existing_memories):
                text = (m.get("text") or m.get("content") or "").strip()
                alias = f"T{i + 1:03d}"
                lines.append(f"  - {alias}: {text[:300]}")
        else:
            lines.append("  NONE")

        lines.append("")
        lines.append("OUTPUT: Return ONLY the unified extraction JSON object.")
        return "\n".join(lines)

    def extract(
        self,
        *,
        source_type: str,
        timestamp: Optional[str] = None,
        conversation_turns: Optional[List[Dict[str, Any]]] = None,
        existing_memories: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        space_id: Optional[str] = None,
        run_id: Optional[str] = None,
        window: Optional[Dict[str, Any]] = None,
        use_format_json: bool = False,
    ) -> Dict[str, Any]:
        """
        Run unified extraction.

        Returns a single dict with keys: schema_version, source, memories, preferences, graph, quality.
        """
        ts = timestamp or _now_iso()
        user_msg = self._build_user_message(
            source_type=source_type,
            timestamp=ts,
            conversation_turns=conversation_turns,
            existing_memories=existing_memories,
            user_id=user_id,
            session_id=session_id,
            space_id=space_id,
            run_id=run_id,
            window=window,
        )
        system_prompt = self._load_prompt()

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if use_format_json:
            payload["format"] = "json"

        try:
            response = requests.post(self.api_url, json=payload, timeout=get_timeout())
            response.raise_for_status()
            result = response.json()
            content = (result.get("message") or {}).get("content") or "{}"
            return self._parse(content, source_type=source_type, timestamp=ts)
        except requests.exceptions.RequestException as e:
            print(f"[UnifiedExtractor] Ollama request failed: {e}")
            return self._empty_output(source_type=source_type, timestamp=ts)
        except Exception as e:
            print(f"[UnifiedExtractor] Extraction error: {e}")
            return self._empty_output(source_type=source_type, timestamp=ts)

    def extract_from_session(
        self,
        query: str,
        conversation_history: List[Dict[str, Any]],
        existing_memories: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Convenience: build turns from query + conversation_history and run extract with source.type=session.

        Compatible with RemmeExtractor.extract(query, conversation_history, existing_memories) call pattern.
        Returns full unified dict (not a tuple).
        """
        turns = list(conversation_history) if conversation_history else []
        turns.append({"role": "user", "content": query})
        return self.extract(
            source_type="session",
            conversation_turns=turns,
            existing_memories=existing_memories or [],
            user_id=user_id,
            session_id=session_id,
            **kwargs,
        )

    def _empty_output(self, source_type: str, timestamp: str) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "source": {"type": source_type, "timestamp": timestamp},
            "memories": {"commands": []},
            "preferences": {"raw": {}, "normalized": [], "evidence": []},
            "graph": {"entities": [], "entity_relationships": [], "user_facts": []},
            "quality": {
                "confidence": 0.0,
                "warnings": ["extraction_failed"],
                "extractor_version": "unified_extraction/v1",
            },
        }

    def _parse(self, content: str, source_type: str, timestamp: str) -> Dict[str, Any]:
        """Parse LLM output into normalized unified schema."""
        raw = _strip_json_block(content)
        if not raw:
            return self._empty_output(source_type=source_type, timestamp=timestamp)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                import json_repair
                data = json_repair.loads(raw)
            except Exception:
                return self._empty_output(source_type=source_type, timestamp=timestamp)

        if not isinstance(data, dict):
            return self._empty_output(source_type=source_type, timestamp=timestamp)

        # Normalize to schema shape
        source = data.get("source") or {}
        if not isinstance(source, dict):
            source = {}
        source.setdefault("type", source_type)
        source.setdefault("timestamp", timestamp)

        memories = data.get("memories") or {}
        if not isinstance(memories, dict):
            memories = {}
        commands = memories.get("commands")
        if not isinstance(commands, list):
            commands = []
        memories = {"commands": commands, "notes": memories.get("notes")}

        preferences = data.get("preferences") or {}
        if not isinstance(preferences, dict):
            preferences = {}
        preferences.setdefault("raw", {})
        preferences.setdefault("normalized", [])
        preferences.setdefault("evidence", [])
        if not isinstance(preferences["raw"], dict):
            preferences["raw"] = {}
        if not isinstance(preferences["normalized"], list):
            preferences["normalized"] = []
        if not isinstance(preferences["evidence"], list):
            preferences["evidence"] = []

        graph = data.get("graph") or {}
        if not isinstance(graph, dict):
            graph = {}
        graph.setdefault("entities", [])
        graph.setdefault("entity_relationships", [])
        graph.setdefault("user_facts", [])
        for key in ("entities", "entity_relationships", "user_facts"):
            if not isinstance(graph[key], list):
                graph[key] = []

        quality = data.get("quality")
        if quality is not None and not isinstance(quality, dict):
            quality = {}
        if quality is None:
            quality = {}

        return {
            "schema_version": str(data.get("schema_version", "1.0")),
            "source": source,
            "memories": memories,
            "preferences": preferences,
            "graph": graph,
            "quality": quality,
        }
