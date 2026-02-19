from core.skills.base import Skill, SkillMetadata


class ForgeOutlineSkill(Skill):
    name = "forge_outline"
    description = "Generates structured outlines for slides, documents, and sheets."

    @property
    def prompt_text(self) -> str:
        return """You are the Forge Outline Agent. Your job is to create structured
outlines for presentations, documents, and spreadsheets based on user prompts.

When the user asks to create slides, a document, or a spreadsheet, generate
a structured outline with sections/slides/tabs appropriate for the content type.

Supported artifact types: slides, document, sheet.
"""

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.name,
            description=self.description,
            intent_triggers=[
                "create slides", "make a presentation", "pitch deck",
                "create document", "write a report", "technical spec",
                "create spreadsheet", "financial model", "create sheet",
            ],
        )
