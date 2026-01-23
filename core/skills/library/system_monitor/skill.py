from typing import List, Any, Dict
from core.skills.base import BaseSkill, SkillMetadata
import psutil
import platform
from pathlib import Path



class SystemMonitorSkill(BaseSkill):
    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="system_monitor",
            version="1.0.0",
            description="Checks system resources (CPU, RAM, Disk)",
            author="Arcturus",
            intent_triggers=["check system", "cpu usage", "disk space", "system health", "cpu", "ram", "memory", "disk"]
        )

    def get_tools(self) -> List[Any]:
        return []

    async def on_run_start(self, initial_prompt: str) -> str:
        return initial_prompt # No prompt modification needed, we do the work in python

    async def on_run_success(self, artifact: Dict[str, Any]):
        # Perform check
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        
        report = f"""# 🖥️ System Health Report
- **Timestamp**: {self.context.run_id}
- **OS**: {platform.system()} {platform.release()}
- **CPU Usage**: {cpu}%
- **RAM Usage**: {ram}%
- **Disk Usage**: {disk}%
"""
        # Save
        target = Path(f"data/Notes/System/Health_{self.context.run_id}.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report)
        print(f"✅ System Monitor saved report to {target}")
        
        return {
            "file_path": str(target),
            "type": "system_health",
            "summary": f"CPU: {cpu}%, RAM: {ram}%, Disk: {disk}%"
        }

    async def on_run_failure(self, error: str):
        pass
