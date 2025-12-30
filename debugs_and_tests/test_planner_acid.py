import asyncio
import sys
import os
import json
from rich.console import Console

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_servers.multi_mcp import MultiMCP
from agents.base_agent import AgentRunner

console = Console()

async def main():
    console.print("[bold cyan]🚀 Starting Planner Acid Test (All Agents)[/bold cyan]")
    
    multi_mcp = MultiMCP()
    # No need to start servers for Planner test, as it's just LLM generation.
    # But AgentRunner might need it instantiated.
    
    runner = AgentRunner(multi_mcp=multi_mcp)
    
    # The ACID TEST Prompt
    # Explicitly asking for a complex project that would require every single agent.
    acid_prompt = """
    Plan a comprehensive software project to build a 'Stock Market Sentiment Analyzer'.
    The plan MUST include the following specific steps:
    1.  Researching available sentiment analysis APIs (Retriever).
    2.  Comparing the API features and pricing (Thinker).
    3.  Summarizing the extensive documentation found (Distiller).
    4.  Writing the Python code to fetch and analyze data (Coder).
    5.  Asking the user for their preferred output format (Clarification).
    6.  Formatting the final report into an HTML dashboard (Formatter).
    7.  Reviewing the entire code and plan for quality issues (QAAgent).
    
    Ensure clear dependencies between these steps.
    """
    
    task_input = {
        "original_query": acid_prompt,
        "planning_strategy": "exploratory",
        "globals_schema": {},
        "file_manifest": []
    }
    
    try:
        console.print(f"\n[bold yellow]🧪 Invoking PlannerAgent...[/bold yellow]")
        result = await runner.run_agent("PlannerAgent", task_input)
        
        if result["success"]:
            output = result["output"]
            plan_graph = output.get("plan_graph", {})
            nodes = plan_graph.get("nodes", [])
            
            console.print(f"[bold green]✅ Planner Output Received[/bold green]")
            console.print(f"Generated {len(nodes)} nodes.")
            
            # Verify Agent Presence
            required_agents = {
                "RetrieverAgent", "ThinkerAgent", "DistillerAgent", 
                "CoderAgent", "ClarificationAgent", "FormatterAgent", "QAAgent"
            }
            
            found_agents = {node["agent"] for node in nodes}
            
            missing = required_agents - found_agents
            
            console.print("\n[bold]Agent Coverage Analysis:[/bold]")
            for agent in required_agents:
                if agent in found_agents:
                    console.print(f"  ✅ {agent}: Found")
                else:
                    console.print(f"  ❌ {agent}: MISSING")
            
            if not missing:
                console.print("\n[bold green]🎉 ACID TEST PASSED: All agents scheduled![/bold green]")
            else:
                console.print(f"\n[bold red]⚠️ ACID TEST WARNING: Missing agents: {missing}[/bold red]")
                
            # Print Graph Structure Snippet
            console.print("\n[dim]Graph Structure:[/dim]")
            print(json.dumps(nodes, indent=2))
            
        else:
            console.print(f"[bold red]❌ Planner Failed[/bold red]")
            console.print(f"Error: {result.get('error')}")
            
    except Exception as e:
        console.print(f"[bold red]❌ Exception[/bold red]")
        console.print(str(e))

if __name__ == "__main__":
    asyncio.run(main())
