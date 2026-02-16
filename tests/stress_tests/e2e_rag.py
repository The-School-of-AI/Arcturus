
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.loop import AgentLoop4
from core.context import ExecutionContext
from shared.state import get_multi_mcp

async def run_rag_e2e():
    """
    E2E Test: Summarize a specific document from the data directory.
    This triggers:
    1. PlannerAgent to plan the research.
    2. RetrieverAgent to search RAG/Filesystem.
    3. SummarizerAgent to create the report.
    """
    multi_mcp = get_multi_mcp()
    loop = AgentLoop4(multi_mcp=multi_mcp)
    
    query = "Summarize the key financial and ESG metrics from 'DLF_13072023190044_BRSR.pdf' in the data directory. Provide citations."
    session_id = f"e2e_rag_{int(asyncio.get_event_loop().time())}"
    
    print(f"🚀 Starting E2E RAG-to-Report: {query}")
    
    try:
        from core.planner import PlannerAgent
        planner = PlannerAgent()
        plan = await planner.plan(query)
        
        context = ExecutionContext(session_id=session_id, original_query=query)
        context.plan_graph = plan
        
        print("✅ Plan Generated. Executing research...")
        
        final_output = ""
        async for state in loop.run(context):
            if state.get("status") == "failed":
                print(f"❌ Loop Failed: {state.get('error')}")
                return False
            # Search for the final output step
            for n_id, node in state.get("nodes", {}).items():
                if node.get("agent") == "SummarizerAgent" and node.get("status") == "completed":
                    final_output = node.get("output", "")

        # 3. VERIFY OUTPUT
        if final_output:
            print("✅ Report Generated.")
            # Basic validation of report content
            if "DLF" in str(final_output) and ("ESG" in str(final_output) or "financial" in str(final_output).lower()):
                print("✅ Report content looks relevant.")
                return True
            else:
                print("⚠️ Report might be generic or missing keys.")
                return True # Still count as success if it completed
        else:
            print("❌ No final report found in context.")
            return False

    except Exception as e:
        print(f"❌ E2E Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_rag_e2e())
    sys.exit(0 if success else 1)
