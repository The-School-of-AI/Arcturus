
import asyncio
import sys
import os
from pathlib import Path
from rich import print
from rich.console import Console
from rich.panel import Panel

# Add 16_NetworkX to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import AgentLoop4
from mcp_servers.multi_mcp import MultiMCP

import argparse

# ... existing code ...

async def run_query(agent_loop, query):
    """Helper to run a query and get text output"""
    context = await agent_loop.run(
        query=query,
        file_manifest=[],
        globals_schema={},
        uploaded_files=[]
    )
    if context:
        summary = context.get_execution_summary()
        if "final_outputs" in summary and summary["final_outputs"]:
            return str(summary["final_outputs"])
        else:
            summarizer_node = next((n for n in context.plan_graph.nodes if context.plan_graph.nodes[n].get("agent") == "SummarizerAgent"), None)
            if summarizer_node:
                return str(context.plan_graph.nodes[summarizer_node].get("output"))
    return "No output produced."

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="Launch Web UI")
    args = parser.parse_args()

    console = Console()
    console.print(Panel.fit("[bold cyan]S16 NetworkX Agent System[/bold cyan]", border_style="blue"))

    # 1. Start MCP Servers
    multi_mcp = MultiMCP()
    await multi_mcp.start()

    try:
        # 2. Initialize Agent Loop
        agent_loop = AgentLoop4(multi_mcp=multi_mcp)

        if args.ui:
            import gradio as gr
            import core.loop
            
            # Global buffer for logs
            log_buffer = []
            
            # Monkeypatch logging
            original_log_step = core.loop.log_step
            def ui_log_step(title, payload=None, symbol="🟢", **kwargs):
                log_buffer.append(f"{symbol} {title}")
                # Pass everything to original logger
                original_log_step(title, payload, symbol, **kwargs)
            
            core.loop.log_step = ui_log_step
            
            async def chat_fn(message, history):
                log_buffer.clear()
                log_buffer.append("🚀 Starting analysis...")
                
                # Run as task effectively
                task = asyncio.create_task(run_query(agent_loop, message))
                
                # Stream logs
                while not task.done():
                    logs = "\n> ".join(log_buffer[-10:]) # Show last 10 logs
                    yield f"**Thinking...**\n\n> {logs}"
                    await asyncio.sleep(0.2)
                
                # Verify result
                try:
                    result = await task
                except Exception as e:
                    result = f"Error: {e}"
                
                full_logs = "\n".join([f"> {l}" for l in log_buffer])
                yield f"<details><summary>Execution Logs</summary>\n\n{full_logs}\n</details>\n\n{result}"

            demo = gr.ChatInterface(
                fn=chat_fn,
                title="S16 NetworkX Agent",
                description="Ask complex questions. The agent will plan, browse, code, and summarize.",
            )
            print("[bold green]Starting UI on http://localhost:7860[/bold green]")
            # Launch without blocking async loop, so MultiMCP pipes continue to work
            demo.launch(prevent_thread_lock=True) 
            
            # Keep the main thread alive and let asyncio loop process background tasks
            while True:
                await asyncio.sleep(1) 
        else:
            # 3. Interactive Loop (CLI)
            while True:
                try:
                    query = console.input("\n[bold green]User Input (or 'exit'):[/bold green] ")
                    if query.lower() in ["exit", "quit", "q"]:
                        break
                    
                    if not query.strip():
                        continue

                    console.print(f"\n[dim]Processing: {query}[/dim]")

                    # Run Workflow
                    result_text = await run_query(agent_loop, query)
                    console.print(Panel(result_text, title="Result", border_style="green"))

                except KeyboardInterrupt:
                    print("\n[yellow]Interrupted by user[/yellow]")
                    break
                except Exception as e:
                    print(f"[red]Error during execution: {e}[/red]")
                    import traceback
                    traceback.print_exc()

    finally:
        await multi_mcp.stop()
        print("[blue]System Shutdown.[/blue]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
