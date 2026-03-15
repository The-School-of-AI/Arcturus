from typing import List, Any, Dict
from core.skills.base import BaseSkill, SkillMetadata
from pathlib import Path

class EmailSkill(BaseSkill):
    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="email",
            version="1.0.0",
            description="Checks and manages your emails",
            author="Arcturus",
            intent_triggers=["check my email", "read my emails", "any new emails", "check email", "read email"]
        )

    def get_tools(self) -> List[Any]:
        return []

    async def on_run_start(self, initial_prompt: str) -> str:
        return initial_prompt

    async def on_run_success(self, artifact: Dict[str, Any]):
        emails = [
            {"from": "Alice", "subject": "Project Update", "body": "Hey, the project is on track!"},
            {"from": "Bob", "subject": "Lunch?", "body": "Are we still on for lunch today?"},
            {"from": "Deepmind", "subject": "Antigravity Update", "body": "New version of Antigravity is out!"}
        ]
        
        summary = f"You have {len(emails)} new emails.\n\n"
        for i, email in enumerate(emails, 1):
            summary += f"{i}. **{email['subject']}** from {email['from']}\n"
        
        report = f"""# 📧 Email Briefing
Your recent emails:

"""
        for email in emails:
            report += f"### {email['subject']}\n- **From**: {email['from']}\n- **Body**: {email['body']}\n\n"

        target = Path(f"data/Notes/Email/Briefing_{self.context.run_id or 'latest'}.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report)
        
        return {
            "file_path": str(target),
            "type": "email_briefing",
            "summary": summary
        }

    async def on_run_failure(self, error: str):
        pass
