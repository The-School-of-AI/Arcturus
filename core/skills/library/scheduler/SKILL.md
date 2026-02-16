
---
name: scheduler
description: Schedule tasks using natural language or cron syntax
---

# Scheduler Skill

This skill allows an agent to schedule tasks for later execution, either one-time or recurring.

## Capabilities

1.  **Schedule Task**: Create a new scheduled job.
2.  **List Tasks**: See pending jobs.
3.  **Delete Task**: Cancel a job.

## Instructions

-   Use `schedule_task` to set up a job.
-   Cron format: `* * * * *` (minute hour day month day_of_week)
-   If user says "every day at 9am", convert to cron: `0 9 * * *`
-   If user says "in 1 hour", calculate the time or use a relative cron (if supported) or just set a one-time cron.

## Tools
- `schedule_task(description: str, cron_expression: str, agent_type: str = "PlannerAgent")`
- `list_scheduled_tasks()`
- `delete_scheduled_task(job_id: str)`
