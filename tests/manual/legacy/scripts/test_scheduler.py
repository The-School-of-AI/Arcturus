import sys
from datetime import datetime
import asyncio
import logging

# Configure logging to see scheduler output
logging.basicConfig(level=logging.INFO)

sys.path.append(".")
from core.scheduler import scheduler_service

async def test_scheduler():
    print("🧪 Testing Scheduler Service...")
    
    # 1. Initialize
    scheduler_service.initialize()
    
    # 2. Add Job (Runs every minute)
    print("📝 Adding job 'Test Job'...")
    job = scheduler_service.add_job(
        name="Test Job",
        cron_expression="* * * * *", 
        agent_type="PlannerAgent",
        query="Say hello"
    )
    print(f"   Job ID: {job.id}")
    
    # 3. List Jobs
    jobs = scheduler_service.list_jobs()
    print(f"📊 Active Jobs: {len(jobs)}")
    for j in jobs:
        print(f"   - {j.name} | Next Run: {j.next_run}")
        if j.id == job.id and j.next_run:
            print("   ✅ Valid next_run time")
        else:
            print("   ❌ Missing next_run time")
            # apscheduler might take a split second to calculate next run
            
    # 4. Verify Persistence File
    import json
    from pathlib import Path
    if Path("data/system/jobs.json").exists():
        print("✅ Persistence file created.")
    else:
        print("❌ Persistence file missing!")
        
    # 5. Delete Job
    print("🗑️ Deleting job...")
    scheduler_service.delete_job(job.id)
    
    jobs_after = scheduler_service.list_jobs()
    if len(jobs_after) < len(jobs):
        print("✅ Job deleted.")
    else:
        print("❌ Job deletion failed.")
        
    print("🎉 Scheduler Test Complete.")

if __name__ == "__main__":
    # AsyncIOScheduler requires a running loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_scheduler())
