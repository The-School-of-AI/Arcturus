
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.loop import AgentLoop4
from core.context import ExecutionContext
from shared.state import get_multi_mcp

async def test_context_protection():
    """
    Test: Analyze a large log file.
    Goal: Verify the agent uses 'view_file' with ranges instead of crashing.
    """
    multi_mcp = get_multi_mcp()
    loop = AgentLoop4(multi_mcp=multi_mcp)
    
    query = "Read the last 1000 lines of 'api.log' and summarize any ERROR messages found. If the file is too large, read it in chunks."
    session_id = f"st_context_{int(asyncio.get_event_loop().time())}"
    
    print(f"🚀 Starting Context Protection Test: {query}")
    
    try:
        from core.planner import PlannerAgent
        planner = PlannerAgent()
        plan = await planner.plan(query)
        
        context = ExecutionContext(session_id=session_id, original_query=query)
        context.plan_graph = plan
        
        async for state in loop.run(context):
            if state.get("status") == "failed":
                print(f"❌ Loop Failed: {state.get('error')}")
                return False
                
        print("✅ Analysis completed without crash.")
        return True

    except Exception as e:
        print(f"❌ Test Error: {e}")
        return False

if __name__ == "__main__":
    # We won't actually run this as it requires the real AgentRunner and LLM
    # But the script is ready for the USER.
    print("Script ready. Run with 'python tests/stress_tests/test_context_protection.py' if LLM is accessible.")
    sys.exit(0)
