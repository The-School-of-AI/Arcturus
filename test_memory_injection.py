import asyncio
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from core.loop import AgentLoop4

async def test_memory_injection():
    print("🚀 Starting Memory Injection Test...")
    
    # Mock dependencies
    mock_mcp = MagicMock()
    
    # Instantiate Loop
    loop = AgentLoop4(multi_mcp=mock_mcp)
    
    # Mock AgentRunner to avoid real LLM calls
    loop.agent_runner = MagicMock()
    
    # return successful mock results
    loop.agent_runner.run_agent.return_value = {
        "success": True,
        "output": {
            "plan_graph": {
                "nodes": [], 
                "edges": []
            }
        }
    }

    # Define test memory
    TEST_MEMORY = "User is located in Bangalore."
    
    # Run the loop with memory context
    print(f"📥 Injecting Memory: '{TEST_MEMORY}'")
    try:
        await loop.run(
            query="Where do I stay?", 
            file_manifest=[], 
            globals_schema={}, 
            uploaded_files=[], 
            session_id="test_session", 
            memory_context=TEST_MEMORY
        )
    except:
        # We expect it might fail later in the loop since we return empty plan, 
        # but we only care about the FIRST call to PlannerAgent
        pass

    # Verification
    # Check calls to agent_runner.run_agent
    calls = loop.agent_runner.run_agent.call_args_list
    
    planner_call = None
    for call in calls:
        args, kwargs = call
        if args[0] == "PlannerAgent":
            planner_call = args[1]
            break
            
    if planner_call:
        print("✅ PlannerAgent was called.")
        received_memory = planner_call.get("memory_context")
        if received_memory == TEST_MEMORY:
            print(f"✅ SUCCESS: PlannerAgent received memory_context: '{received_memory}'")
        else:
            print(f"❌ FAILURE: PlannerAgent received: '{received_memory}'")
            print(f"   Expected: '{TEST_MEMORY}'")
    else:
        print("❌ FAILURE: PlannerAgent was never called.")

if __name__ == "__main__":
    asyncio.run(test_memory_injection())
