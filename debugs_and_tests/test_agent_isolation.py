
import asyncio
import sys
import os
from rich import print

# Add path
sys.path.append(os.getcwd())

from mcp_servers.multi_mcp import MultiMCP
from agents.base_agent import AgentRunner

async def main():
    print("[bold blue]🧪 Testing CoderAgent Isolation...[/bold blue]")
    
    # 1. Start MultiMCP
    multi_mcp = MultiMCP()
    await multi_mcp.start()
    
    try:
        # 2. Initialize Runner
        runner = AgentRunner(multi_mcp)
        
        # 3. Definte Input
        task = {
            "step_id": "TEST_RETRIEVER_01",
            "agent_prompt": "Find recent news about Agentic AI frameworks released in 2024.",
            "reads": [],
            "writes": ["ai_news_results"],
            "inputs": {}
        }
        
        # 4. Run Agent
        print(f"🤖 Invoking RetrieverAgent with task: {task['agent_prompt']}")
        result = await runner.run_agent("RetrieverAgent", task)
        
        # 5. Output Result
        if result["success"]:
            print("[bold green]✅ Success![/bold green]")
            print(result["output"])
        else:
            print("[bold red]❌ Failed![/bold red]")
            print(result.get("error"))
            
    finally:
        await multi_mcp.stop()

if __name__ == "__main__":
    asyncio.run(main())
