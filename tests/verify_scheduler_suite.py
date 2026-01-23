import sys
import os
import asyncio
import logging
from datetime import datetime

# Setup paths
sys.path.append(os.getcwd())

from core.scheduler import scheduler_service, JobDefinition
from core.skills.manager import skill_manager
from core.event_bus import event_bus

# Mock process_run to avoid full LLM cost/latency for this test, 
# BUT return valid structure to prove Skill Handoff works.
import routers.runs
async def mock_process_run(run_id, query):
    print(f"   [MockAgent] Processing: {query}")
    await asyncio.sleep(0.5)
    return {"summary": f"Processed: {query}", "status": "completed"}

routers.runs.process_run = mock_process_run

async def run_tests():
    print("🚀 Starting 10-Job Verification Suite")
    
    # 1. Initialize
    event_bus._subscribers = [] # Clear implementation details
    skill_manager.initialize()
    
    # 2. Define Jobs
    test_cases = [
        # Skill: Market Analyst
        ("Market Check", "Check current stock price of Apple", "market_analyst"),
        # Skill: Market Analyst with Custom Path
        ("Silver Price", "Find silver price and save to Notes/Scheduler/Silver_price.md", "market_analyst"),
        # Skill: System Monitor
        ("System Health", "Check system cpu usage", "system_monitor"),
        # Skill: Web Clipper
        ("Clip Google", "Clip url https://www.google.com", "web_clipper"),
        # Skill: Web Clipper 2
        ("Clip Example", "Archive page https://example.com", "web_clipper"),
        # General Agent (No Skill)
        ("Poem Writer", "Write a poem about rust", None),
        # General Agent 2
        ("Joke Teller", "Tell me a joke", None),
        # Skill: System Monitor 2
        ("Disk Check", "Check disk space", "system_monitor"),
        # Skill: Market Analyst 3
        ("Tesla News", "Get news for Tesla", "market_analyst"),
        # General Agent 3
        ("History Fact", "Who built the pyramids?", None)
    ]
    
    results = []
    
    for i, (name, query, expected_skill) in enumerate(test_cases, 1):
        print(f"\n--- Job {i}: {name} ---")
        print(f"Query: {query}")
        
        # Test Intent Matching
        detected_skill = skill_manager.match_intent(query)
        print(f"Detected Skill: {detected_skill}")
        
        if expected_skill and detected_skill != expected_skill:
            print(f"❌ FAIL: Expected {expected_skill}, got {detected_skill}")
            results.append("FAIL")
            continue
            
        # Create Job Object
        job = JobDefinition(
            id=f"test_{i}",
            name=name,
            cron_expression="* * * * *",
            agent_type="Planner",
            query=query,
            skill_id=detected_skill
        )
        
        # Manually invoke the wrapper logic (simplified)
        try:
            skill = None
            if job.skill_id:
                skill = skill_manager.get_skill(job.skill_id)
                if skill:
                    # Setup Context
                    skill.context.config = {"query": job.query}
                    skill.context.run_id = job.id
                    
                    # Run Start Hook
                    await skill.on_run_start(job.query)
            
            # Run Agent (Mocked)
            result = await routers.runs.process_run(job.id, job.query)
            
            # Run Success Hook
            if skill:
                await skill.on_run_success(result)
                print("✅ Skill Success Hook Executed")
            else:
                print("✅ General Agent Executed")
                
            results.append("PASS")
            
        except Exception as e:
            print(f"❌ Execution Failed: {e}")
            import traceback
            traceback.print_exc()
            results.append("ERROR")

    print("\n\n📊 Test Summary")
    print("=================")
    for i, res in enumerate(results, 1):
        print(f"Job {i}: {res}")
        
    if all(r == "PASS" for r in results):
        print("\n✅ ALL TESTS PASSED")
    else:
        print("\n❌ SOME TESTS FAILED")

if __name__ == "__main__":
    asyncio.run(run_tests())
