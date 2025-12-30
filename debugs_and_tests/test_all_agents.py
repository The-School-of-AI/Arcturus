import asyncio
import sys
import os
import json
from rich.console import Console

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_servers.multi_mcp import MultiMCP
from agents.base_agent import AgentRunner

console = Console()

async def run_test(runner, agent_name, task_input, expected_key=None):
    console.print(f"\n[bold yellow]🧪 Testing {agent_name}...[/bold yellow]")
    console.print(f"[dim]Input: {task_input.get('agent_prompt', 'N/A')}[/dim]")
    
    try:
        result = await runner.run_agent(agent_name, task_input)
        
        if result["success"]:
            output = result["output"]
            console.print(f"[bold green]✅ {agent_name} PASS[/bold green]")
            
            # Basic validation
            if expected_key:
                if expected_key in output or (isinstance(output, dict) and any(k.startswith(expected_key) for k in output)):
                     console.print(f"   [green]Found expected key: {expected_key}[/green]")
                else:
                     console.print(f"   [red]⚠️ Warning: Expected key '{expected_key}' not found in output keys: {list(output.keys())}[/red]")
            
            # Print snippet
            snippet = str(output)[:200] + "..." if len(str(output)) > 200 else str(output)
            console.print(f"   [dim]Output: {snippet}[/dim]")
            return True
        else:
            console.print(f"[bold red]❌ {agent_name} FAIL[/bold red]")
            console.print(f"   Error: {result.get('error')}")
            return False
            
    except Exception as e:
        console.print(f"[bold red]❌ {agent_name} EXCEPTION[/bold red]")
        console.print(f"   {str(e)}")
        return False

async def main():
    console.print("[bold cyan]🚀 Starting Comprehensive Agent Verification Suite[/bold cyan]")
    
    # Start MultiMCP for tools
    multi_mcp = MultiMCP()
    await multi_mcp.start()
    
    # Initialize Runner
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "agent_config.yaml")
    with open(config_path, "r") as f:
        config = import_yaml(f) # Wait, need yaml import
    
    # Actually AgentRunner loads config internally if we pass dict, or we can just instantiate it
    # AgentRunner expects a config dict for a single agent? No, run_agent loads it.
    # Wait, AgentRunner init takes (multi_mcp). It acts as a dispatcher.
    runner = AgentRunner(multi_mcp=multi_mcp) # Helper refactoring might be needed
    
    # Wait, in base_agent.py AgentRunner is initialized with config?
    # No, AgentRunner IS the class.
    # checking base_agent.py... 
    # It takes `multi_mcp` in `run_agent`? No, `__init__`?
    # Let's look at `base_agent.py` usage in `test_agent_isolation.py`.
    # runner = AgentRunner(multi_mcp) -- correct.
    
    try:
        # 1. PLANNER
        await run_test(runner, "PlannerAgent", {
            "original_query": "Research the impact of AI on healthcare.",
            "planning_strategy": "exploratory",
            "globals_schema": {},
            "file_manifest": []
        }, expected_key="plan_graph")

        # 2. CODER (Sandbox)
        await run_test(runner, "CoderAgent", {
            "step_id": "T001",
            "agent_prompt": "Calculate the factorial of 5 using Python and print it.",
            "reads": [], "writes": ["factorial_result"],
            "inputs": {}
        }, expected_key="code_variants")

        # 3. RETRIEVER (Browser)
        await run_test(runner, "RetrieverAgent", {
            "step_id": "T002",
            "agent_prompt": "Find the current price of gold.",
            "reads": [], "writes": ["gold_price"],
            "inputs": {}
        }, expected_key="code_variants")

        # 4. DISTILLER
        await run_test(runner, "DistillerAgent", {
            "step_id": "T003",
            "agent_prompt": "Summarize the text in 'raw_text' variable.",
            "reads": ["raw_text"], 
            "writes": ["summary_bullets"],
            "inputs": {"raw_text": "Artificial Intelligence is transforming industries by automating repetitive tasks. However, it also raises ethical concerns regarding privacy and bias. The future of AI lies in agentic systems that can plan and execute complex workflows autonomously."}
        }, expected_key="summary_bullets")

        # 5. THINKER
        await run_test(runner, "ThinkerAgent", {
            "step_id": "T004",
            "agent_prompt": "Compare Python vs JavaScript based on these inputs.",
            "reads": ["some_input"], 
            "writes": ["comparison_table"],
            "inputs": {"some_input": "Python is slow but easy. JS is fast but quirky."}
        }, expected_key="comparison_table")

        # 6. FORMATTER
        await run_test(runner, "FormatterAgent", {
            "step_id": "T005",
            "agent_prompt": "Format the final report.",
            "reads": [], "writes": ["formatted_report"],
            "inputs": {},
            "all_globals_schema": {"some_data": "value"}
        }, expected_key="final_format")

        # 7. CLARIFICATION
        await run_test(runner, "ClarificationAgent", {
            "step_id": "T006",
            "agent_prompt": "Ask user if they prefer PDF or HTML.",
            "reads": [], "writes": ["user_pref"],
            "inputs": {}
        }, expected_key="clarificationMessage")
        
        # 8. QA
        await run_test(runner, "QAAgent", {
            "step_id": "T007",
            "agent_prompt": "Review the plan.",
            "reads": [], "writes": ["qa_verdict"],
            "plan_graph": {
                "nodes": [
                    {"id": "T001", "agent": "PlannerAgent", "description": "Plan task", "status": "completed"},
                    {"id": "T002", "agent": "CoderAgent", "description": "Calc factorial", "status": "pending"}
                ]
            },
            "globals_schema": {}
        }, expected_key="verdict")

    finally:
        await multi_mcp.stop()

def import_yaml(f):
    import yaml
    return yaml.safe_load(f)

if __name__ == "__main__":
    asyncio.run(main())
