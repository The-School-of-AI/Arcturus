"""
GAIA Benchmark Runner

Executes test cases from test_cases.json against the Arcturus agent system.
Results are saved to results/ directory with timestamp.

Usage:
    python runner.py                    # Run all tests
    python runner.py --id gaia_001      # Run specific test
    python runner.py --category coding  # Run tests by category
    python runner.py --delay 500        # Wait 500s between tests
"""

import asyncio
import json
import sys
import os
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.loop import AgentLoop4
from mcp_servers.multi_mcp import MultiMCP
from rich.console import Console
from rich.table import Table

console = Console()

BENCHMARK_DIR = Path(__file__).parent
TEST_CASES_FILE = BENCHMARK_DIR / "test_cases.json"
RESULTS_DIR = BENCHMARK_DIR / "results"


def load_test_cases() -> List[Dict]:
    """Load test cases from JSON file."""
    with open(TEST_CASES_FILE) as f:
        return json.load(f)


async def run_single_test(test_case: Dict, multi_mcp: MultiMCP) -> Dict[str, Any]:
    """
    Run a single GAIA test case.
    
    Returns:
        Dict with test_id, query, result, timing, and execution summary
    """
    test_id = test_case["id"]
    query = test_case["query"]
    
    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold]Running Test: {test_id}[/bold]")
    console.print(f"[dim]Category: {test_case['category']} | Difficulty: {test_case['difficulty']}[/dim]")
    console.print(f"[yellow]Query:[/yellow] {query}")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")
    
    start_time = datetime.now()
    summary = {}
    
    try:
        agent_loop = AgentLoop4(multi_mcp=multi_mcp)
        context = await agent_loop.run(
            query=query,
            file_manifest=[],
            globals_schema={},
            uploaded_files=[]
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Extract execution summary
        summary = context.get_execution_summary()
        
        # Get final output from the last completed node
        final_output = None
        # FIX: Access plan_graph instead of G
        for node_id in context.plan_graph.nodes():
            node_data = context.plan_graph.nodes[node_id]
            if node_data.get("status") == "completed":
                if node_data.get("output"):
                    final_output = node_data["output"]
        
        result = {
            "test_id": test_id,
            "category": test_case["category"],
            "difficulty": test_case["difficulty"],
            "query": query,
            "success": summary["failed_steps"] == 0,
            "duration_seconds": duration,
            "total_cost": summary.get("total_cost", 0),
            "total_tokens": summary.get("total_tokens", 0),
            "completed_steps": summary["completed_steps"],
            "failed_steps": summary["failed_steps"],
            "final_output": final_output,
            "expected_components": test_case["expected_components"],
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
        
        console.print(f"\n[green]✓ Test {test_id} completed in {duration:.1f}s[/green]")
        console.print(f"  Cost: ${summary.get('total_cost', 0):.4f} | Tokens: {summary.get('total_tokens', 0)}")
        
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result = {
            "test_id": test_id,
            "category": test_case["category"],
            "difficulty": test_case["difficulty"],
            "query": query,
            "success": False,
            "duration_seconds": duration,
            "total_cost": summary.get("total_cost", 0) if summary else 0,
            "total_tokens": summary.get("total_tokens", 0) if summary else 0,
            "completed_steps": summary.get("completed_steps", 0) if summary else 0,
            "failed_steps": 1,
            "final_output": None,
            "expected_components": test_case["expected_components"],
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
        
        console.print(f"\n[red]✗ Test {test_id} failed: {e}[/red]")
        import traceback
        traceback.print_exc()
    
    return result


async def run_benchmark(
    test_ids: Optional[List[str]] = None,
    category: Optional[str] = None,
    delay_seconds: int = 0
) -> List[Dict]:
    """
    Run GAIA benchmark tests.
    
    Args:
        test_ids: Specific test IDs to run (optional)
        category: Filter by category (optional)
        delay_seconds: Wait time between tests in seconds
    
    Returns:
        List of result dictionaries
    """
    test_cases = load_test_cases()
    
    # Filter test cases
    if test_ids:
        test_cases = [t for t in test_cases if t["id"] in test_ids]
    if category:
        test_cases = [t for t in test_cases if t["category"] == category]
    
    if not test_cases:
        console.print("[red]No matching test cases found![/red]")
        return []
    
    console.print(f"\n[bold]GAIA Benchmark Runner[/bold]")
    console.print(f"Running {len(test_cases)} test(s)...\n")
    if delay_seconds > 0:
        console.print(f"[yellow]Delay between tests: {delay_seconds} seconds[/yellow]")
    
    # Initialize MCP servers
    multi_mcp = MultiMCP()
    await multi_mcp.start()
    
    results = []
    
    try:
        total_tests = len(test_cases)
        for i, test_case in enumerate(test_cases):
            result = await run_single_test(test_case, multi_mcp)
            results.append(result)
            
            # Wait unless it's the last test
            if i < total_tests - 1 and delay_seconds > 0:
                console.print(f"\n[yellow]⏳ Waiting {delay_seconds}s before next test...[/yellow]")
                # We use time.sleep for simplicity since this is a synchronous wait between tests
                # But since we are in async function, strictly we should use asyncio.sleep
                # However, since nothing else is running concurrently here that matters,
                # time.sleep is blocking but acceptable, or asyncio.sleep is better.
                # using asyncio.sleep to be safe.
                await asyncio.sleep(delay_seconds)
                
    finally:
        await multi_mcp.stop()
    
    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"results_{timestamp}.json"
    
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    console.print(f"\n[green]Results saved to: {results_file}[/green]")
    
    # Print summary table
    print_summary(results)
    
    return results


def print_summary(results: List[Dict]):
    """Print a summary table of benchmark results."""
    table = Table(title="\n📊 GAIA Benchmark Results")
    
    table.add_column("Test ID", style="cyan")
    table.add_column("Category", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Tokens", justify="right")
    
    total_cost = 0
    total_tokens = 0
    passed = 0
    
    for r in results:
        status = "[green]✓ PASS[/green]" if r["success"] else "[red]✗ FAIL[/red]"
        table.add_row(
            r["test_id"],
            r["category"],
            status,
            f"{r['duration_seconds']:.1f}s",
            f"${r['total_cost']:.4f}",
            str(r["total_tokens"])
        )
        total_cost += r["total_cost"]
        total_tokens += r["total_tokens"]
        if r["success"]:
            passed += 1
    
    console.print(table)
    console.print(f"\n[bold]Summary:[/bold] {passed}/{len(results)} passed")
    console.print(f"Total Cost: ${total_cost:.4f} | Total Tokens: {total_tokens}")


def main():
    parser = argparse.ArgumentParser(description="GAIA Benchmark Runner")
    parser.add_argument("--id", type=str, help="Run specific test by ID")
    parser.add_argument("--category", type=str, choices=["travel", "research", "coding", "data", "reasoning"],
                        help="Run tests by category")
    parser.add_argument("--delay", type=int, default=0, help="Wait time between tests in seconds")
    parser.add_argument("--list", action="store_true", help="List all test cases")
    
    args = parser.parse_args()
    
    if args.list:
        test_cases = load_test_cases()
        table = Table(title="GAIA Test Cases")
        table.add_column("ID")
        table.add_column("Category")
        table.add_column("Difficulty")
        table.add_column("Query")
        
        for tc in test_cases:
            table.add_row(tc["id"], tc["category"], tc["difficulty"], tc["query"][:50] + "...")
        
        console.print(table)
        return
    
    test_ids = [args.id] if args.id else None
    
    # Run the benchmark
    asyncio.run(run_benchmark(
        test_ids=test_ids, 
        category=args.category,
        delay_seconds=args.delay
    ))


if __name__ == "__main__":
    main()
