
from typing import List, Any, Dict
from core.skills.base import Skill
from core.scheduler import scheduler_service
import json

class SimpleTool:
    def __init__(self, name: str, description: str, func: Any, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.func = func
        self.inputSchema = {
            "type": "object",
            "properties": parameters,
            "required": list(parameters.keys())
        }

class SchedulerSkill(Skill):
    name = "scheduler"
    description = "Skill derived from scheduler.md"

    @property
    def prompt_text(self) -> str:
        return """
You are the **Scheduler Agent**. Your job is to manage time-based tasks.

### Capabilities
1.  **Schedule New Tasks**: Add jobs to run at specific times or intervals using CRON syntax.
    -   *Example*: "Check emails every morning at 9am" -> `0 9 * * *`
    -   *Example*: "Run report every Friday at 5pm" -> `0 17 * * 5`
2.  **List Tasks**: See pending jobs.
3.  **Delete Tasks**: Cancel jobs by ID.

### Instructions
-   ALWAYS confirm the CRON expression before scheduling.
-   Use `schedule_task` for adding new jobs.
-   Use `list_tasks` to check existing schedule.
-   Use `delete_task` to remove jobs.

### CRON Reference
* * * * *
| | | | |
| | | | +----- Day of Week (0 - 6) (Sunday=0)
| | | +------- Month (1 - 12)
| | +--------- Day of Month (1 - 31)
| +----------- Hour (0 - 23)
+------------- Minute (0 - 59)
"""

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text

    def get_tools(self) -> List[Any]:
        return [
            SimpleTool(
                name="schedule_task",
                description="Schedule a new task with a CRON expression.",
                func=self._schedule_task,
                parameters={
                    "task_description": {"type": "string", "description": "Description of the task to run"},
                    "cron_expression": {"type": "string", "description": "CRON expression (e.g., '0 9 * * *')"},
                    "agent_type": {"type": "string", "description": "Agent to execute the task (default: 'PlannerAgent')"}
                }
            ),
            SimpleTool(
                name="list_tasks",
                description="List all scheduled tasks.",
                func=self._list_tasks,
                parameters={}
            ),
            SimpleTool(
                name="delete_task",
                description="Delete a scheduled task by ID.",
                func=self._delete_task,
                parameters={
                    "job_id": {"type": "string", "description": "ID of the job to delete"}
                }
            )
        ]

    async def _schedule_task(self, task_description: str, cron_expression: str, agent_type: str = "PlannerAgent") -> str:
        try:
            job = scheduler_service.add_job(
                name=task_description[:50],  # Short name
                cron_expression=cron_expression,
                agent_type=agent_type,
                query=task_description
            )
            return f"✅ Scheduled task '{task_description}' (ID: {job.id}) with cron '{cron_expression}'"
        except Exception as e:
            return f"❌ Failed to schedule task: {str(e)}"

    async def _list_tasks(self) -> str:
        try:
            jobs = scheduler_service.list_jobs()
            if not jobs:
                return "No scheduled tasks found."
            
            output = "📅 Scheduled Tasks:\n"
            for job in jobs:
                output += f"- [{job.id}] {job.name} ({job.cron_expression}) -> Next: {job.next_run}\n"
            return output
        except Exception as e:
            return f"❌ Failed to list tasks: {str(e)}"

    async def _delete_task(self, job_id: str) -> str:
        try:
            scheduler_service.delete_job(job_id)
            return f"🗑️ Deleted task {job_id}"
        except Exception as e:
            return f"❌ Failed to delete task: {str(e)}"
