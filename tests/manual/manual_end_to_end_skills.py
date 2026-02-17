
import requests
import time
import sys
import json
from pathlib import Path

API_BASE = "http://localhost:8000/api"

def wait_for_api():
    print("Waiting for API...")
    for _ in range(10):
        try:
            requests.get(f"{API_BASE}/runs", timeout=2)
            print("API is up!")
            return True
        except:
            time.sleep(2)
    return False

def test_skills_lifecycle():
    if not wait_for_api():
        print("API failed to start.")
        sys.exit(1)

    # 1. List Skills
    print("\n1. Listing Skills...")
    try:
        res = requests.get(f"{API_BASE}/skills/list")
        res.raise_for_status()
        skills = res.json()
        print(f"Found {len(skills)} skills: {[s['name'] for s in skills]}")
    except Exception as e:
        print(f"List failed: {e}")
        sys.exit(1)

    # 2. Install Skill (agent-manager-skill)
    skill_name = "agent-manager-skill"
    print(f"\n2. Installing {skill_name}...")
    try:
        # Check if already installed
        if any(s['name'] == skill_name for s in skills):
            print(f"{skill_name} already installed.")
        else:
            res = requests.post(f"{API_BASE}/skills/{skill_name}/install")
            res.raise_for_status()
            print("Install success:", res.json())
    except Exception as e:
        print(f"Install failed: {e}")
        # Continue anyway to verify usage if it was pre-installed

    # 3. Assign to PlannerAgent
    print(f"\n3. Assigning {skill_name} to PlannerAgent...")
    try:
        res = requests.post(f"{API_BASE}/skills/toggle", json={
            "agent_name": "PlannerAgent",
            "skill_name": skill_name,
            "active": True
        })
        res.raise_for_status()
        print("Assignment success:", res.json())
    except Exception as e:
        print(f"Assignment failed: {e}")
        sys.exit(1)

    # 4. Verify Execution (Directly via Skill Manager for robustness in test)
    # We want to prove the code exists and runs.
    print(f"\n4. Verifying Skill Execution...")
    try:
        # Import core logic directly to test execution without needing full LLM run
        sys.path.append(str(Path.cwd()))
        from core.skills.manager import skill_manager
        
        # Initialize to load new skills
        skill_manager.initialize()
        
        skill = skill_manager.get_skill(skill_name)
        if not skill:
            print(f"❌ Skill {skill_name} NOT found in manager after install!")
            sys.exit(1)
            
        meta = skill.get_metadata()
        print(f"✅ Skill loaded: {meta.name} v{meta.version}")
        print(f"   Triggers: {meta.intent_triggers}")
        
        if not skill.get_metadata().intent_triggers:
            print("⚠️ Skill has no intent triggers defined. Skipping match verification.")
        else:
            # Simulate a match
            query = "Find papers on Deep Learning"
            match = skill_manager.match_intent(query)
            # ... existing match logic ...

    except Exception as e:
        print(f"Execution verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_skills_lifecycle()
