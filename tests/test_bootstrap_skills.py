
import asyncio
import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from agents.base_agent import AgentRunner
from core.registry import registry
from core.bootstrap import bootstrap_agents
from mcp_servers.multi_mcp import MultiMCP

class TestBootstrapSkills(unittest.IsolatedAsyncioTestCase):
    async def test_bootstrapped_prompt(self):
        # 1. Bootstrap
        bootstrap_agents()
        
        # 2. Check PlannerAgent
        mcp = MultiMCP()
        runner = AgentRunner(mcp)
        
        # 3. Running PlannerAgent should now use the 'planner' skill
        try:
            await runner.run_agent("PlannerAgent", {"task": "test bootstrap"})
        except:
            pass
            
        debug_file = Path("memory/debug_logs/latest_prompt.txt")
        content = debug_file.read_text()
        
        self.assertIn("AGENT: PlannerAgent", content)
        # Search for unique strings from the new planner skill
        self.assertIn("PlannerAgent v3 Prompt", content)
        self.assertIn("plan_graph", content)
        print("✅ Bootstrapped skills verification passed!")


if __name__ == "__main__":
    asyncio.run(unittest.main())
