from typing import List, Any, Dict
from core.skills.base import BaseSkill, SkillMetadata
from core.event_bus import event_bus

class NavigationSkill(BaseSkill):
    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="navigation",
            version="1.0.0",
            description="Navigates the UI via voice commands",
            author="Arcturus",
            intent_triggers=[
                "show me the dashboard", "go to dashboard", "show dashboard", "open dashboard", "navigate to dashboard",
                "show me the runs", "go to runs", "open runs", "navigate to runs",
                "show me the notes", "go to notes", "open notes", "navigate to notes",
                "show me the rag", "go to rag", "show me the knowledge base", "open rag", "open knowledge base", "navigate to rag",
                "go to settings", "show settings", "open settings", "navigate to settings",
                "show me the apps", "go to apps", "open apps", "navigate to apps",
                "show me the explorer", "go to explorer", "open explorer", "navigate to explorer",
                "show me the scheduler", "go to scheduler", "open scheduler", "navigate to scheduler",
                "show me the ide", "go to ide", "open ide", "navigate to ide",
                "show me the console", "go to console", "open console", "navigate to console"
            ]
        )

    def get_tools(self) -> List[Any]:
        return []

    async def on_run_start(self, initial_prompt: str) -> str:
        # Map query to tab
        query = initial_prompt.lower()
        tab = "runs" # default
        
        if "dashboard" in query or "runs" in query:
            tab = "runs"
        elif "notes" in query:
            tab = "notes"
        elif "rag" in query or "knowledge" in query:
            tab = "rag"
        elif "settings" in query:
            tab = "settings"
        elif "apps" in query:
            tab = "apps"
        elif "explorer" in query:
            tab = "explorer"
        elif "scheduler" in query:
            tab = "scheduler"
        elif "ide" in query:
            tab = "ide"
        elif "console" in query:
            tab = "console"
        elif "studio" in query:
            tab = "studio"
        elif "skills" in query:
            tab = "skills"
        elif "canvas" in query:
            tab = "canvas"
        elif "mcp" in query:
            tab = "mcp"
        elif "remme" in query:
            tab = "remme"

        # Publish navigation event
        await event_bus.publish("navigation", "navigation_skill", {"tab": tab})
        
        return f"Navigating to {tab}..."

    async def on_run_success(self, artifact: Dict[str, Any]):
        return {
            "summary": "Navigation successful."
        }

    async def on_run_failure(self, error: str):
        pass
