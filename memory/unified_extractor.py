"""
Unified Extractor — Single LLM extraction for memories, entities, relationships, facts, evidence.

Merges responsibilities of memory/entity_extractor.py and remme/extractor.py.
Produces UnifiedExtractionResult (schema in unified_extraction_schema.py).
Used when MNEMO_ENABLED=true; step 3 will ingest to Neo4j (Fact/Evidence).

Entry points:
- extract_from_session(query, conversation_history, existing_memories) for session/smart-scan
- extract_from_memory_text(text) for direct memory add / Qdrant ingestion
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings_loader import get_ollama_url, get_model, get_timeout, settings

import requests

from memory.unified_extraction_schema import (
    EvidenceEventItem,
    EntityItem,
    EntityRelationshipItem,
    FactItem,
    MemoryCommand,
    UnifiedExtractionResult,
)


UNIFIED_EXTRACTION_SYSTEM = """You extract structured information from conversation or memory text in a single JSON object.

Output JSON with these keys only (use empty arrays when nothing applies):
- memories: list of { "action": "add"|"update"|"delete", "text": "...", "id": "T001" or null }
- entities: list of { "type": "Person"|"Company"|"City"|"Concept"|..., "name": "..." }
- entity_relationships: list of { "from_type", "from_name", "to_type", "to_name", "type": "works_at"|"lives_in"|..., "value"?: "...", "confidence"?: 1.0 }
- facts: list of user facts. Each: { "field_id": "<one of {{VALID_FIELD_IDS}}>", "value_type": "text"|"number"|"bool"|"json", "value": "concise" or value_text/value_number/value_bool/value_json, "entity_ref"?: "Concept::vegetarian" }
  You MUST use only valid field_ids from the list above. Do NOT invent namespace or key.
- evidence_events: list of { "source_type": "extraction", "source_ref": "session_123" or "memory_id", "timestamp"?: "..." }

Return ONLY valid JSON, no markdown."""


class UnifiedExtractor:
    """
    Single-call extractor producing UnifiedExtractionResult.
    Uses the unified_extraction skill for prompts (same pattern as entity_extractor).
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or get_model("unified_extraction")
        self.api_url = get_ollama_url("chat")
        self._prompt: Optional[str] = None

    def _load_prompt(self) -> str:
        """Load prompt: Skill > file in skill folder > settings > inline fallback."""
        if self._prompt is not None:
            return self._prompt
        try:
            from shared.state import get_skill_manager
            skill = get_skill_manager().get_skill("unified_extraction")
            if skill and skill.prompt_text:
                self._prompt = skill.prompt_text.strip()
        except Exception:
            pass
        if self._prompt is None:
            skill_prompt_path = Path(__file__).parent.parent / "core" / "skills" / "library" / "unified_extraction" / "SKILL.md"
            if skill_prompt_path.exists():
                self._prompt = skill_prompt_path.read_text(encoding="utf-8", errors="replace").strip()
            elif settings.get("unified_extraction", {}).get("extraction_prompt"):
                self._prompt = settings["unified_extraction"]["extraction_prompt"]
            else:
                self._prompt = UNIFIED_EXTRACTION_SYSTEM
        # Inject valid field_ids from registry
        from memory.fact_field_registry import get_valid_field_ids
        valid_ids = ", ".join(get_valid_field_ids())
        self._prompt = self._prompt.replace("{{VALID_FIELD_IDS}}", valid_ids)
        return self._prompt

    def extract_from_session(
        self,
        query: str,
        conversation_history: List[Dict[str, Any]],
        existing_memories: Optional[List[Dict[str, Any]]] = None,
    ) -> UnifiedExtractionResult:
        """
        Extract from a session: transcript + existing memories → memories, entities, relationships, facts, evidence.
        """
        transcript = ""
        for msg in (conversation_history or [])[-10:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            transcript += f"{role.upper()}: {content}\n"
        transcript += f"USER: {query}\n"
        memories_str = "NONE"
        if existing_memories:
            memories_str = "\n".join(
                [f"ID: T{i+1:03d} | {m.get('text', '')}" for i, m in enumerate(existing_memories)]
            )
        user_content = f"Conversation:\n{transcript}\n\nExisting relevant memories:\n{memories_str}\n\nExtract and return the single JSON object."
        return self._call_llm(user_content, source="session")

    def extract_from_memory_text(self, text: str) -> UnifiedExtractionResult:
        """
        Extract from a single memory text (e.g. direct add or Qdrant ingest).
        """
        user_content = f"Memory text:\n{text}\n\nExtract and return the single JSON object (memories can be one add with this text or empty)."
        return self._call_llm(user_content, source="memory")

    def _call_llm(self, user_content: str, source: str) -> UnifiedExtractionResult:
        prompt = self._load_prompt()
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=get_timeout(),
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "{}")
            return self._parse(content, source=source)
        except Exception as e:
            print(f"[UnifiedExtractor] LLM failed: {e}")
            return UnifiedExtractionResult(source=source)

    def _parse(self, content: str, source: str) -> UnifiedExtractionResult:
        raw = (content or "").strip()
        if raw.startswith("```"):
            for start in ("```json\n", "```\n"):
                if raw.startswith(start):
                    raw = raw[len(start):]
                    break
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                import json_repair
                data = json_repair.loads(raw)
            except Exception:
                return UnifiedExtractionResult(source=source)
        if not isinstance(data, dict):
            return UnifiedExtractionResult(source=source)
        memories = self._normalize_memories(data.get("memories") or data.get("commands") or [])
        entities = self._normalize_entities(data.get("entities") or [])
        rels = self._normalize_relationships(data.get("entity_relationships") or data.get("entity_relations") or [])
        facts = self._normalize_facts(data.get("facts") or [])
        evidence = self._normalize_evidence(data.get("evidence_events") or [])
        return UnifiedExtractionResult(
            source=source,
            memories=memories,
            entities=entities,
            entity_relationships=rels,
            facts=facts,
            evidence_events=evidence,
        )

    def _normalize_memories(self, raw: List[Any]) -> List[MemoryCommand]:
        out = []
        for m in raw:
            if isinstance(m, dict) and m.get("action"):
                action = (m.get("action") or "add").lower()
                if action not in ("add", "update", "delete"):
                    action = "add"
                out.append(MemoryCommand(
                    action=action,
                    text=str(m.get("text", "") or ""),
                    id=m.get("id"),
                ))
            elif isinstance(m, str) and m.strip():
                out.append(MemoryCommand(action="add", text=m.strip()))
        return out

    def _normalize_entities(self, raw: List[Any]) -> List[EntityItem]:
        out = []
        for e in raw:
            if isinstance(e, dict) and (e.get("name") or e.get("name") == "" and e.get("type")):
                out.append(EntityItem(
                    type=str(e.get("type", "Concept")).strip(),
                    name=str(e.get("name", "")).strip(),
                ))
        return out

    def _normalize_relationships(self, raw: List[Any]) -> List[EntityRelationshipItem]:
        out = []
        for r in raw:
            if isinstance(r, dict) and r.get("from_name") is not None and r.get("to_name") is not None:
                out.append(EntityRelationshipItem(
                    from_type=str(r.get("from_type", "Entity")).strip(),
                    from_name=str(r.get("from_name", "")).strip(),
                    to_type=str(r.get("to_type", "Entity")).strip(),
                    to_name=str(r.get("to_name", "")).strip(),
                    type=str(r.get("type", "related_to")).strip(),
                    value=r.get("value"),
                    confidence=float(r.get("confidence", 1.0)),
                ))
        return out

    def _normalize_facts(self, raw: List[Any]) -> List[FactItem]:
        out = []
        for f in raw:
            if not isinstance(f, dict):
                continue
            field_id = str(f.get("field_id", "")).strip()
            if not field_id:
                continue
            vt = str(f.get("value_type", "text")).strip().lower()
            if vt not in ("text", "number", "bool", "json"):
                vt = "text"
            val = f.get("value")
            out.append(FactItem(
                field_id=field_id,
                value_type=vt,
                value=val,
                value_text=str(val) if vt == "text" and val is not None else f.get("value_text"),
                value_number=float(val) if vt == "number" and val is not None else f.get("value_number"),
                value_bool=bool(val) if vt == "bool" and val is not None else f.get("value_bool"),
                value_json=f.get("value_json") if vt == "json" else None,
                entity_ref=f.get("entity_ref"),
            ))
        return out

    def _normalize_evidence(self, raw: List[Any]) -> List[EvidenceEventItem]:
        out = []
        for e in raw:
            if isinstance(e, dict) and e.get("source_type") is not None:
                out.append(EvidenceEventItem(
                    source_type=str(e.get("source_type", "extraction")).strip(),
                    source_ref=str(e.get("source_ref", "")).strip(),
                    timestamp=e.get("timestamp"),
                    signal_category=e.get("signal_category"),
                    raw_excerpt=e.get("raw_excerpt"),
                    confidence_delta=e.get("confidence_delta"),
                ))
        return out


