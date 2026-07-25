from core.skills.base import Skill
from pathlib import Path

SKILL_MD = (Path(__file__).parent / "SKILL.md").read_text()

class VisualExplainerSkill(Skill):
    name = "visual_explainer"
    description = "Core skill for prioritizing rich, visual, browser-renderable HTML artifacts."
    
    @property
    def prompt_text(self) -> str:
        return SKILL_MD

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
