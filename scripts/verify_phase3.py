import asyncio
import json
import time
import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
sys.path.append(str(PROJECT_ROOT))

async def test_memory():
    print("\n[TEST] Verifying EpisodicMemory Integration...")
    from core.episodic_memory import EpisodicMemory
    
    session_id = f"test_verify_{int(time.time())}"
    session_data = {
        "graph": {
            "session_id": session_id,
            "original_query": "Verify memory persistence",
            "status": "completed"
        },
        "nodes": [{"id": "T1", "agent": "IDEAgent", "description": "Verification", "status": "completed", "output": "Success"}]
    }
    
    memory = EpisodicMemory()
    await memory.save_episode(session_data)
    
    memory_dir = PROJECT_ROOT / "memory" / "episodes"
    expected_file = memory_dir / f"skeleton_{session_id}.json"
    
    if expected_file.exists():
        print(f"✅ SUCCESS: Episodic skeleton saved at {expected_file}")
    else:
        print(f"❌ FAILURE: Skeleton not found at {expected_file}")

async def test_skill():
    print("\n[TEST] Verifying FileReaderSkill...")
    from shared.state import get_agent_runner
    from core.registry import AgentRegistry
    
    runner = get_agent_runner()
    AgentRegistry.register("Phase3Tester", {
        "description": "Tester for Phase 3 skills",
        "prompt_text": (
            "You are a TEST_BOT. READ CAREFULLY: You MUST return ONLY a raw JSON object. "
            "DO NOT include 'Captain:', DO NOT include any prose. "
            "Use the 'read_file' tool to read 'README.md'.\n"
            "Final output must be: {\"response\": \"summary\", \"call_tool\": {\"name\": \"read_file\", \"arguments\": {\"path\": \"README.md\"}}}"
        ),
        "skills": ["file_reader"]
    })
    
    result = await runner.run_agent("Phase3Tester", {"task": "Read README.md"})
    
    if result["success"]:
        response = result["output"].get('response', 'No response field')
        print(f"✅ SUCCESS: Agent Execution Success!")
        print(f"Agent Output: {response[:100]}...")
        if "Arcturus" in str(result["output"]):
             print("✅ SUCCESS: Content verification passed.")
    else:
        print(f"❌ FAILURE: Agent Execution Failed: {result.get('error')}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", choices=["memory", "skill"], help="Specific test to run")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    args = parser.parse_args()
    
    if args.test == "memory" or args.all:
        await test_memory()
    
    if args.test == "skill" or args.all:
        await test_skill()
    
    if not args.test and not args.all:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())
