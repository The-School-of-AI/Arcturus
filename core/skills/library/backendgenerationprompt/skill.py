
from core.skills.base import Skill

class BackendgenerationpromptSkill(Skill):
    name = "backendgenerationprompt"
    description = "Skill derived from BackendGenerationPrompt.md"
    
    @property
    def prompt_text(self) -> str:
        return """
You are an expert Python developer specialized in FastAPI and Arcturus Apps.
Your task is to generate a backend service for an Arcturus App based on the user's requirements and the frontend specification.

User Prompt: {{USER_PROMPT}}

Frontend Specification (JSON):
```json
{{FRONTEND_SPEC}}
```

Requirements:
1. Create a FastAPI router in a single file options.
2. The file should be named `backend.py`.
3. It must define a `router = APIRouter()` variable.
4. Implement endpoints required by the frontend (based on cards/data fetching needs).
5. Use standard Python/FastAPI practices.
6. Provide helpful comments.

Output Format:
Return ONLY the Python code. Wrap it in ```python``` blocks.
Do not include conversational text.
"""

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
