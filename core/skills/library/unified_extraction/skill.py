"""Unified extraction skill for Mnemo: memories, entities, facts, evidence."""

from pathlib import Path

from core.skills.base import Skill


class UnifiedExtractionSkill(Skill):
    name = "unified_extraction"
    description = "Extracts memories, entities, relationships, facts, and evidence from conversation or memory text (Mnemo unified path)"

    @property
    def prompt_text(self) -> str:
        skill_dir = Path(__file__).parent
        prompt_path = skill_dir / "SKILL.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8", errors="replace").strip()
        return self._fallback_prompt()

    def _fallback_prompt(self) -> str:
        return (
            "You extract structured information from conversation or memory text in a single JSON object. "
            "Output JSON with keys: memories, entities, entity_relationships, facts, evidence_events. "
            "Return ONLY valid JSON, no markdown."
        )

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
