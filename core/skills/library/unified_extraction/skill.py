"""Unified extraction skill: memories + preferences + graph from one session pass."""

from pathlib import Path

from core.skills.base import Skill


class UnifiedExtractionSkill(Skill):
    name = "unified_extraction"
    description = "Unified extraction contract v1.0: memories, preferences, and graph (entities, relationships, user_facts) in one JSON output"

    @property
    def prompt_text(self) -> str:
        skill_dir = Path(__file__).parent
        prompt_path = skill_dir / "SKILL.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8", errors="replace").strip()
        return self._fallback_prompt()

    def _fallback_prompt(self) -> str:
        return (
            "Extract a single JSON object with keys: schema_version (1.0), source, memories (commands), "
            "preferences (raw, normalized), graph (entities, entity_relationships, user_facts), quality. "
            "Output valid JSON only, no markdown."
        )

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
