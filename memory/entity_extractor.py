"""
Entity Extractor — Extracts entities and relationships from memory text for the knowledge graph.

Uses LLM (Ollama) to produce structured entities, entity-entity relationships,
and user-centric facts (LIVES_IN, WORKS_AT, KNOWS, PREFERS).
Model and prompt follow the same config/skill pattern as remme/extractor.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings_loader import get_ollama_url, get_model, get_timeout, settings

import requests


class EntityExtractor:
    """
    Extracts entities, relationships, and user facts from memory text.
    Output format matches KnowledgeGraph.ingest_memory() expectations.
    """

    def __init__(self, model: Optional[str] = None):
        # Use provided model or config (entity_extraction; get_model falls back to default if missing)
        self.model = model or get_model("entity_extraction")
        self.api_url = get_ollama_url("chat")
        self._prompt: Optional[str] = None

    def _load_prompt(self) -> str:
        if self._prompt is not None:
            return self._prompt
        # Priority: Skill > file in skill folder > settings > inline fallback
        try:
            from shared.state import get_skill_manager
            skill = get_skill_manager().get_skill("entity_extraction")
            if skill and skill.prompt_text:
                self._prompt = skill.prompt_text.strip()
                return self._prompt
        except Exception:
            pass
        skill_prompt_path = Path(__file__).parent.parent / "core" / "skills" / "library" / "entity_extraction" / "SKILL.md"
        if skill_prompt_path.exists():
            self._prompt = skill_prompt_path.read_text(encoding="utf-8", errors="replace").strip()
        elif settings.get("entity_extraction", {}).get("extraction_prompt"):
            self._prompt = settings["entity_extraction"]["extraction_prompt"]
        else:
            self._prompt = (
                "Extract entities (Person, Company, City, Concept, etc.), "
                "entity_relationships (from_type, from_name, to_type, to_name, type), "
                "and user_facts (rel_type: LIVES_IN|WORKS_AT|KNOWS|PREFERS, type, name). "
                "Return JSON: {entities: [...], entity_relationships: [...], user_facts: [...]}"
            )
        return self._prompt

    def extract_from_query(self, query: str) -> List[Dict[str, str]]:
        """
        Extract entities from a short query (NER-style) for entity-first retrieval.
        Uses a lighter prompt optimized for queries. Returns entities only.
        Example: {"entities": [{"name": "John", "type": "Person"}]}
        """
        prompt = "Extract only entity names and types mentioned. Return JSON: {entities: [{name, type}]}. Types: Person, Company, City, Place, Concept, Date, etc."
        try:
            user_msg = f"Query: {query}\nReturn ONLY valid JSON, no markdown."
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=get_timeout(),
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "{}")
            parsed = self._parse(content)
            print(f"[EntityExtractor] Parsed entities {parsed} from the query {query}") # TODO 
            return parsed.get("entities", [])
        except Exception:
            return []

    def extract(self, text: str, verbose: bool = False) -> Dict[str, Any]:
        """
        Extract entities and relationships from memory text.

        Returns:
            {
                "entities": [{"type": "Person", "name": "John"}, ...],
                "entity_relationships": [{"from_type", "from_name", "to_type", "to_name", "type", "value?"}, ...],
                "user_facts": [{"rel_type": "LIVES_IN", "type": "City", "name": "X"}, ...]
            }
        """
        prompt = self._load_prompt()
        try:
            # Use format=json only if model supports it well; gemma3:4b returns {} with it
            user_msg = f"Extract entities and relationships from this memory. Return ONLY valid JSON, no markdown.\n\nMemory: {text}"
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=get_timeout(),
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "{}")
            if verbose:
                print(f"[EntityExtractor] Raw LLM response ({len(content)} chars):\n{content[:1200]}")
            return self._parse(content)
        except requests.exceptions.RequestException as e:
            print(f"[EntityExtractor] Ollama request failed: {e}")
            return {"entities": [], "entity_relationships": [], "user_facts": []}
        except Exception as e:
            print(f"[EntityExtractor] Extraction error: {e}")
            return {"entities": [], "entity_relationships": [], "user_facts": []}

    def _parse(self, content: str) -> Dict[str, Any]:
        """Parse LLM JSON output into expected structure."""
        if not content or not content.strip():
            return {"entities": [], "entity_relationships": [], "user_facts": []}
        # Strip markdown code blocks (common when format=json still wraps)
        raw = content.strip()
        if raw.startswith("```"):
            for start in ("```json\n", "```\n"):
                if raw.startswith(start):
                    raw = raw[len(start):]
                    break
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return {"entities": [], "entity_relationships": [], "user_facts": []}
            # Accept common key variants (Entities, entity_relationships, etc.)
            entities = parsed.get("entities") or parsed.get("Entities") or []
            rels = parsed.get("entity_relationships") or parsed.get("entity_relations") or []
            facts = parsed.get("user_facts") or parsed.get("user_fact") or []
            return {
                "entities": self._normalize_entities(entities),
                "entity_relationships": self._normalize_relationships(rels),
                "user_facts": self._normalize_user_facts(facts),
            }
        except json.JSONDecodeError as e:
            # Try json_repair for malformed JSON
            try:
                import json_repair
                parsed = json_repair.loads(raw)
                if isinstance(parsed, dict):
                    entities = parsed.get("entities") or parsed.get("Entities") or []
                    rels = parsed.get("entity_relationships") or parsed.get("entity_relations") or []
                    facts = parsed.get("user_facts") or parsed.get("user_fact") or []
                    return {
                        "entities": self._normalize_entities(entities),
                        "entity_relationships": self._normalize_relationships(rels),
                        "user_facts": self._normalize_user_facts(facts),
                    }
            except Exception:
                pass
            return {"entities": [], "entity_relationships": [], "user_facts": []}

    def _normalize_entities(self, raw: List[Any]) -> List[Dict[str, str]]:
        out = []
        for e in raw:
            if isinstance(e, dict) and e.get("name"):
                out.append({
                    "type": str(e.get("type", "Concept")).strip(),
                    "name": str(e.get("name", "")).strip(),
                })
        return out

    def _normalize_relationships(self, raw: List[Any]) -> List[Dict[str, Any]]:
        out = []
        for r in raw:
            if isinstance(r, dict) and r.get("from_name") and r.get("to_name"):
                out.append({
                    "from_type": str(r.get("from_type", "Entity")),
                    "from_name": str(r.get("from_name", "")).strip(),
                    "to_type": str(r.get("to_type", "Entity")),
                    "to_name": str(r.get("to_name", "")).strip(),
                    "type": str(r.get("type", "related_to")).strip(),
                    "value": r.get("value"),
                    "confidence": float(r.get("confidence", 1.0)),
                })
        return out

    def _normalize_user_facts(self, raw: List[Any]) -> List[Dict[str, str]]:
        valid_rel = {"LIVES_IN", "WORKS_AT", "KNOWS", "PREFERS"}
        out = []
        for f in raw:
            if isinstance(f, dict) and f.get("name"):
                rel = str(f.get("rel_type", "KNOWS")).upper()
                if rel not in valid_rel:
                    rel = "KNOWS"
                out.append({
                    "rel_type": rel,
                    "type": str(f.get("type", "Concept")),
                    "name": str(f.get("name", "")).strip(),
                })
        return out
