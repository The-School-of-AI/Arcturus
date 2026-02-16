
from core.skills.base import Skill

class RagSemanticChunkingSkill(Skill):
    name = "rag_semantic_chunking"
    description = "Skill derived from rag_semantic_chunking.md"
    
    @property
    def prompt_text(self) -> str:
        return """You are a document segmentation assistant.

Below is an ordered list of sentences from a document. Your task is to find where the topic clearly changes.

INSTRUCTIONS:
1. Read the sentences carefully.
2. If there is a clear topic shift, reply with ONLY the sentence number where the NEW topic begins (e.g., "7").
3. If all sentences belong to the same topic, reply with "NONE".

SENTENCES:
{numbered_sentences}

ANSWER (number or NONE):
"""

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
