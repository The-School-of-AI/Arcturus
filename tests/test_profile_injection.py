
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

class TestProfileInjection(unittest.IsolatedAsyncioTestCase):
    async def test_profile_injection(self):
        # 1. Bootstrap
        bootstrap_agents()
        
        # 2. Run an agent
        mcp = MultiMCP()
        runner = AgentRunner(mcp)
        
        try:
            await runner.run_agent("RetrieverAgent", {"task": "test profile injection"})
        except:
            pass
            
        # 3. Check debug logs
        debug_file = Path("memory/debug_logs/latest_prompt.txt")
        content = debug_file.read_text()
        
        # Verify system profile is present
        self.assertIn("## System Profile", content)
        self.assertIn("- Tone: concise", content)
        self.assertIn("- Verbosity: low", content)
        
        print("✅ Profile injection verification passed!")

if __name__ == "__main__":
    asyncio.run(unittest.main())
