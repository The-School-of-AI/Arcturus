import sys
import os
import time
import requests
import json
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8000"
NOTES_DIR = Path("data/Notes")

def check_health():
    try:
        r = requests.get(f"{API_BASE}/health")
        return r.status_code == 200
    except:
        return False

def run_suite():

    print("🚀 Starting REAL 10-Job Verification Suite (Integration Test)")
    
    print("Prombing health...")
    if not check_health():
        print("❌ Error: Arcturus Backend (localhost:8000) is NOT running.")
        print("Please ensure the app is open.")
        return
    print("✅ Health check passed.")

    # Cleanup Old Test Files (DISABLED per user request)
    # print("🧹 Cleaning up old artifacts...")
    # test_files = list(NOTES_DIR.glob("**/*test_*.md")) + list(NOTES_DIR.glob("**/System/Health_*.md")) + list(NOTES_DIR.glob("**/scheduler/Silver_price.md"))
    # for f in test_files:
    #     try:
    #         f.unlink()
    #     except:
    #         pass
    print("ℹ️ Cleanup skipped (persisting results for frontend).")


    # Define Detailed Jobs
    jobs = [
         # 1. Market Analyst
        {
            "name": "Market Check",
            "query": "Check current stock price of Apple. Save brief to Notes/test_apple.md",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": "data/Notes/test_apple.md"
        },
        # 2. Market Analyst (Silver - User Request)
        {
            "name": "Silver Price",
            "query": "Find silver price and save to Notes/Scheduler/Silver_price.md",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": "data/Notes/Scheduler/Silver_price.md"
        },
        # 3. System Monitor
        {
            "name": "System Health",
            "query": "Check system cpu usage",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": None # Name is dynamic timestamp-based, handle differently
        },
        # 4. Web Clipper
        {
            "name": "Clip Google",
            "query": "Clip url https://www.google.com",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": None # Dynamic
        },
        # 5. Web Clipper 2
        {
            "name": "Clip Example",
            "query": "Archive page https://example.com",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": None
        },
        # 6. General Agent (Poem)
        # Note: General Agent doesn't auto-save to file unless asked! 
        # But process_run saves to memory. How to verify?
        # The prompt should ask to SAVE to a file for verification.
        {
            "name": "Poem Writer",
            "query": "Write a poem about rust and save it to Notes/test_poem.md",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent", 
            "expected_file": "data/Notes/test_poem.md"
        },
        # 7. Joke Teller
        {
            "name": "Joke Writer",
            "query": "Write a joke and save to Notes/test_joke.md",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": "data/Notes/test_joke.md"
        },
        # 8. Disk Check
        {
            "name": "Disk Check",
            "query": "Check disk space",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": None # Dynamic
        },
        # 9. Tesla News
        {
            "name": "Tesla News",
            "query": "Get news for Tesla and save to Notes/test_tesla.md",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": "data/Notes/test_tesla.md"
        },
         # 10. History Fact (General)
        {
            "name": "Pyramids",
            "query": "Who built the pyramids? Save answer to Notes/test_pyramids.md",
            "cron": "* * * * *",
            "agent_type": "PlannerAgent",
            "expected_file": "data/Notes/test_pyramids.md"
        }
    ]

    results = []

    for i, job_def in enumerate(jobs, 1):
        print(f"\n---------------------------------------------------------------")
        print(f"🔄 Running Job {i}/{len(jobs)}: {job_def['name']}")
        print(f"   Query: {job_def['query']}")
        
        job_id = None
        try:
            # 1. Create
            r = requests.post(f"{API_BASE}/cron/jobs", json={
                "name": f"Test {job_def['name']}",
                "cron": job_def['cron'],
                "agent_type": job_def['agent_type'],
                "query": job_def['query']
            })
            r.raise_for_status()
            job_data = r.json()
            job_id = job_data['id']
            print(f"   ✅ Created Job {job_id}")
            
            if "skill_id" in job_data and job_data["skill_id"]:
                 print(f"   🧠 Detected Skill: {job_data['skill_id']}")
            
            # 2. Trigger
            print(f"   👉 Triggering execution...")
            r = requests.post(f"{API_BASE}/cron/jobs/{job_id}/trigger")
            r.raise_for_status()
            
            # 3. Poll for Completion (Max 300s)
            start_time = time.time()
            max_wait = 300 # 5 minutes
            found = False
            
            print(f"   ⏳ Waiting for output (timeout: {max_wait}s)...")
            
            while time.time() - start_time < max_wait:
                # Check for file
                if job_def['expected_file']:
                    p = Path(job_def['expected_file'])
                    if p.exists():
                        print(f"   ✅ File Created: {p}")
                        found = True
                        break
                else:
                    # Dynamic check
                    # We need to be careful not to match OLD files.
                    # Ideally we check creation time > start_time
                    if "System Health" in job_def['name'] or "Disk" in job_def['name']:
                         matches = list(Path("data/Notes/System").glob("Health_*.md"))
                         # Check if any match is new
                         new_matches = [m for m in matches if m.stat().st_mtime > start_time]
                         if new_matches:
                             print(f"   ✅ Health Report Created: {new_matches[0]}")
                             found = True
                             break
                             
                    elif "Clip" in job_def['name']:
                         matches = list(Path("data/Notes/Clips").glob("*.md"))
                         new_matches = [m for m in matches if m.stat().st_mtime > start_time]
                         if new_matches:
                             print(f"   ✅ Web Clip Created: {new_matches[0]}")
                             found = True
                             break
                
                time.sleep(5)
                # Optional: Print simple progress dot
                print(".", end="", flush=True)
            
            print() # Newline
            
            if found:
                results.append("PASS")
                print(f"   🎉 Job {i} PASSED")
            else:
                results.append("FAIL")
                print(f"   ❌ Job {i} FAILED (Timeout)")
                
        except Exception as e:
            print(f"   ❌ Job {i} Error: {e}")
            results.append("ERROR")
            
        finally:
            # 4. Cleanup immediately (DISABLED per user request to see on frontend)
            if job_id:
                try:
                     # requests.delete(f"{API_BASE}/cron/jobs/{job_id}")
                     print(f"   ℹ️ Job {job_id} persisted for frontend review.")
                except:
                    pass
                    
        # Small buffer between jobs to let backend cool down
        time.sleep(5)

    # Summary
    print("\n\n📊 Test Summary")
    print("=================")
    pass_count = results.count("PASS")
    print(f"Passed: {pass_count}/{len(jobs)}")
    
    if pass_count == len(jobs):
        print("\n✅ SUCCESS: All integration tests passed.")
    else:
        print("\n❌ FAILURE: Some tests failed.")

if __name__ == "__main__":
    run_suite()
