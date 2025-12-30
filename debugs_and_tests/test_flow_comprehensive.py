import asyncio
import sys
import os
import json
from rich.console import Console

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import AgentLoop4
from mcp_servers.multi_mcp import MultiMCP

console = Console()

async def main():
    console.print("[bold cyan]🚀 Starting Comprehensive System Flow Test[/bold cyan]")
    
    multi_mcp = MultiMCP()
    await multi_mcp.start()
    
    # MOCK INPUTS for Clarification Agent to avoid actual blocking input
    # Logic in context.py _handle_user_interaction_rich reads stdin usually.
    # We might need to manually inject if it blocks, but let's see. 
    # Actually, for an automated test, we might want to let it prompt or mock it?
    # User said "Test whole flow *yourself*", implying I run it and interact if needed.
    # But as an AI, I can't interact with stdin. 
    # However, context.py usually uses a rich Prompt.ask. 
    # If I run this via `run_command`, I can use `send_command_input`.
    
    try:
        agent_loop = AgentLoop4(multi_mcp=multi_mcp)
        
        # PROMPT DESIGNED FOR MAX COVERAGE
        query = """
        I need a 'Python Package Manager Decision Helper'.
        Please execute the following plan:
        1. Research the key differences between 'Poetry' and 'UV' (Python tools) in 2024 (Retriever).
        2. Compare their speed, features, and popularity (Thinker).
        3. Summarize the findings into a concise briefing (Distiller).
        4. Write a Python script that recommends one based on user input (speed vs features) (Coder).
        5. Ask me which one I prefer right now (Clarification).
        6. Create a final HTML report with the summary and my preference (Formatter).
        7. Review the final report and code for quality (QAAgent).
        """
        
        console.print(f"[bold yellow]📜 Query:[/bold yellow] {query}")
        
        # Execute the loop
        context = await agent_loop.run(query, [], {}, [])
        
        # Analyze Results
        summary = context.get_execution_summary()
        console.print("\n[bold]Execution Summary:[/bold]")
        print(json.dumps(summary, indent=2))
        
        # Check Agent Coverage
        executed_steps = context.plan_graph.nodes(data=True)
        agents_used = {data['agent'] for _, data in executed_steps}
        
        console.print(f"\n[bold]Agents Used:[/bold] {agents_used}")
        
    finally:
        await multi_mcp.stop()

if __name__ == "__main__":
    asyncio.run(main())
