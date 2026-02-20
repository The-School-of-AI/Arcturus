
import asyncio
import unittest
import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from agents.base_agent import AgentRunner
from core.registry import registry
from core.bootstrap import bootstrap_agents
from mcp_servers.multi_mcp import MultiMCP
from memory.episodic import MEMORY_DIR

class TestPrePlanRetrieval(unittest.IsolatedAsyncioTestCase):
    async def test_planner_retrieval_hook(self):
        # 1. Setup mock episode
        mock_file = MEMORY_DIR / "skeleton_bake_cake.json"
        mock_data = {
            "id": "bake_cake",
            "original_query": "How to bake a cake",
            "status": "completed",
            "nodes": [
                {"agent": "PlannerAgent"},
                {"agent": "CoderAgent"},
                {"agent": "FormatterAgent"}
            ]
        }
        with open(mock_file, "w") as f:
            json.dump(mock_data, f)
            
        # 2. Bootstrap
        bootstrap_agents()
        
        # 3. Run PlannerAgent with a similar query
        mcp = MultiMCP()
        runner = AgentRunner(mcp)
        
        try:
            # This will trigger search_episodes
            await runner.run_agent("PlannerAgent", {"task": "bake a cake"})
        except:
            pass
            
        # 4. Check debug logs
        debug_file = Path("memory/debug_logs/latest_prompt.txt")
        content = debug_file.read_text()
        
        # Verify episodic context is present
        self.assertIn("Relevant Past Experiences (Recipes)", content)
        self.assertIn("bake a cake", content)
        self.assertIn("PlannerAgent -> CoderAgent -> FormatterAgent", content)
        
        # Cleanup
        if mock_file.exists():
            os.remove(mock_file)
            
        print("✅ Pre-plan retrieval hook verification passed!")

if __name__ == "__main__":
    asyncio.run(unittest.main())
