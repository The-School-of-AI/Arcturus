
import asyncio
import sys
import os
from rich.console import Console

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import AgentLoop4
from mcp_servers.multi_mcp import MultiMCP

async def main():
    print("TEST: Starting Verification Run")
    multi_mcp = MultiMCP()
    await multi_mcp.start()

    try:
        agent_loop = AgentLoop4(multi_mcp=multi_mcp)
        query = "Plan a 3 day trip to Tokyo"
        
        print(f"TEST: Running query: {query}")
        context = await agent_loop.run(query, [], {}, [])
        
        summary = context.get_execution_summary()
        print("\nTEST COMPLETE. Summary:")
        print(summary)
        
        if summary["failed_steps"] > 0:
            print("TEST FAILED: Some steps failed.")
            sys.exit(1)
            
        print("TEST SUCCESS")

    finally:
        await multi_mcp.stop()

if __name__ == "__main__":
    asyncio.run(main())
