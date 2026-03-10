"""Entity extraction skill for Neo4j knowledge graph."""

from pathlib import Path

from core.skills.base import Skill


class EntityExtractionSkill(Skill):
    name = "entity_extraction"
    description = "Extracts entities and relationships from memory text for the knowledge graph"

    @property
    def prompt_text(self) -> str:
        skill_dir = Path(__file__).parent
        prompt_path = skill_dir / "SKILL.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8", errors="replace").strip()
        return self._fallback_prompt()

    def _fallback_prompt(self) -> str:
        return (
            "Extract entities (Person, Company, City, Concept, etc.), "
            "entity_relationships (from_type, from_name, to_type, to_name, type), "
            "and user_facts (rel_type: LIVES_IN|WORKS_AT|KNOWS|PREFERS, type, name). "
            "Return JSON: {entities: [...], entity_relationships: [...], user_facts: [...]}"
        )

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
