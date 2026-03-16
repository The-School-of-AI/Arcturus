"""
Pydantic schema for the Unified Extraction Result (P11 Mnemo Step 2).

Single output structure from the unified extractor: memories, entities,
entity_relationships, facts, evidence_events. Used by ingestion (step 3)
and tests. See p11_unified_extraction_design.md.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# --- Memory command (same shape as RemMe extractor) ---
class MemoryCommand(BaseModel):
    action: Literal["add", "update", "delete"] = "add"
    text: str = ""
    id: Optional[str] = None  # for update/delete; T001-style or real id


# --- Entity (same as entity_extractor) ---
class EntityItem(BaseModel):
    type: str = "Concept"
    name: str = ""


# --- Entity relationship ---
class EntityRelationshipItem(BaseModel):
    from_type: str = "Entity"
    from_name: str = ""
    to_type: str = "Entity"
    to_name: str = ""
    type: str = "related_to"
    value: Optional[str] = None
    confidence: float = 1.0


# --- Fact: canonical user fact (field_id only; registry owns namespace/key) ---
class FactItem(BaseModel):
    """LLM emits field_id only. Namespace and key are resolved from the registry."""
    field_id: str = ""  # Required; must be a valid field_id from fact_field_registry
    value_type: Literal["text", "number", "bool", "json"] = "text"
    value: Optional[Union[str, float, bool, Any]] = None  # LLM may return single value
    value_text: Optional[str] = None
    value_number: Optional[float] = None
    value_bool: Optional[bool] = None
    value_json: Optional[Any] = None
    entity_ref: Optional[str] = None  # entity id or composite key (e.g. "Concept::vegetarian") for REFERS_TO

    def get_value(self) -> Optional[Union[str, float, bool, Any]]:
        if self.value_type == "text":
            return self.value_text
        if self.value_type == "number":
            return self.value_number
        if self.value_type == "bool":
            return self.value_bool
        if self.value_type == "json":
            return self.value_json
        if self.value_text is not None:
            return self.value_text
        if self.value is not None:
            return self.value
        return self.value_text


# --- Evidence event (provenance for facts) ---
class EvidenceEventItem(BaseModel):
    source_type: str = "extraction"  # extraction | session_summary | system_observation | migration | ui_edit
    source_ref: str = ""  # memory_id or session_id
    timestamp: Optional[str] = None
    signal_category: Optional[str] = None
    raw_excerpt: Optional[str] = None
    confidence_delta: Optional[float] = None


# --- Unified Extraction Result ---
class UnifiedExtractionResult(BaseModel):
    source: Literal["session", "memory", "query"] = "memory"
    memories: List[MemoryCommand] = Field(default_factory=list)
    entities: List[EntityItem] = Field(default_factory=list)
    entity_relationships: List[EntityRelationshipItem] = Field(default_factory=list)
    facts: List[FactItem] = Field(default_factory=list)
    evidence_events: List[EvidenceEventItem] = Field(default_factory=list)

    def to_legacy_entity_result(self) -> Dict[str, Any]:
        """Convert to the shape expected by KnowledgeGraph.ingest_memory (entities, entity_relationships, user_facts)."""
        entities = [{"type": e.type, "name": e.name} for e in self.entities]
        entity_relationships = [
            {
                "from_type": r.from_type,
                "from_name": r.from_name,
                "to_type": r.to_type,
                "to_name": r.to_name,
                "type": r.type,
                "value": r.value,
                "confidence": r.confidence,
            }
            for r in self.entity_relationships
        ]
        user_facts = _derive_user_facts_from_facts(self.facts)
        return {
            "entities": entities,
            "entity_relationships": entity_relationships,
            "user_facts": user_facts,
        }


def _derive_user_facts_from_facts(facts: List[FactItem]) -> List[Dict[str, str]]:
    """
    Derive legacy user_facts (rel_type, type, name) from facts that have entity_ref.
    Uses registry to resolve field_id → namespace for rel_type derivation.
    """
    from memory.fact_field_registry import get_field_def

    out: List[Dict[str, str]] = []
    for f in facts:
        if not f.entity_ref or not f.field_id:
            continue
        defn = get_field_def(f.field_id)
        if not defn:
            continue
        ref = (f.entity_ref or "").strip()
        if "::" in ref:
            part = ref.split("::", 1)
            etype = (part[0] or "Concept").strip()
            name = (part[1] or "").strip()
        else:
            etype = "Concept"
            name = ref
        if not name:
            continue
        ns = defn.get("namespace", "")
        key = defn.get("key", "")
        rel_type = "PREFERS"
        if "identity.work" in ns or "company" in key.lower():
            rel_type = "WORKS_AT"
        elif "identity.location" in ns or "location" in key.lower():
            rel_type = "LIVES_IN"
        out.append({"rel_type": rel_type, "type": etype, "name": name})
    return out
