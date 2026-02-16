
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.loop import AgentLoop4
from core.context import ExecutionContext
from shared.state import get_multi_mcp
from core.utils import log_step

async def run_snake_e2e():
    """
    E2E Test: Build a simple Python Snake Game.
    This triggers:
    1. PlannerAgent to create the implementation graph.
    2. CoderAgent to write the code.
    3. Sandbox to execute/verify it.
    """
    multi_mcp = get_multi_mcp()
    loop = AgentLoop4(multi_mcp=multi_mcp)
    
    query = "Create a simple command-line Snake game in Python. Save it to 'snake_game.py' and verify it runs (just check for syntax/startup)."
    session_id = f"e2e_snake_{int(asyncio.get_event_loop().time())}"
    
    print(f"🚀 Starting E2E Plan-to-Code: {query}")
    
    # 1. PLAN
    # Standard loop.run_query handles planning then execution
    # We'll use the loop directly
    try:
        # In a real scenario, we'd call the API, but here we run the loop core
        # We need to simulate the entry point
        from core.planner import PlannerAgent
        planner = PlannerAgent()
        plan = await planner.plan(query)
        
        context = ExecutionContext(session_id=session_id, original_query=query)
        context.plan_graph = plan # Assuming plan is a NetworkX graph or similar
        
        print("✅ Plan Generated. Executing...")
        
        # 2. RUN LOOP
        async for state in loop.run(context):
            # Check for failures
            if state.get("status") == "failed":
                print(f"❌ Loop Failed: {state.get('error')}")
                return False
                
        # 3. VERIFY OUTPUT
        output_file = Path("snake_game.py")
        if output_file.exists():
            content = output_file.read_text()
            print(f"✅ snake_game.py created ({len(content)} bytes)")
            if "import" in content and "snake" in content.lower():
                 print("✅ Code content looks valid.")
                 return True
        else:
            print("❌ snake_game.py was NOT created.")
            return False

    except Exception as e:
        print(f"❌ E2E Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_snake_e2e())
    sys.exit(0 if success else 1)
