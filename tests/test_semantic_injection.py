
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

class TestSemanticInjection(unittest.IsolatedAsyncioTestCase):
    async def test_factual_injection_hook(self):
        # 1. Setup mock factual memory
        os.makedirs("data", exist_ok=True)
        memory_file = Path("data/user_memory.json")
        mock_facts = [
            {"id": "mem-1", "content": "The user is based in Bangalore."},
            {"id": "mem-2", "content": "The user loves spicy food."},
            {"id": "mem-3", "content": "The project name is Arcturus."}
        ]
        with open(memory_file, "w") as f:
            json.dump(mock_facts, f)
            
        # 2. Bootstrap
        bootstrap_agents()
        
        # 3. Run SummarizerAgent with a query that triggers the fact
        mcp = MultiMCP()
        runner = AgentRunner(mcp)
        
        try:
            # Query about Arcturus
            await runner.run_agent("SummarizerAgent", {"task": "What is the status of Arcturus?"})
        except:
            pass
            
        # 4. Check debug logs
        debug_file = Path("memory/debug_logs/latest_prompt.txt")
        content = debug_file.read_text()
        
        # Verify factual context is present
        self.assertIn("Memories of User Preferences & Facts", content)
        self.assertIn("The project name is Arcturus", content)
        
        # Cleanup
        if memory_file.exists():
            os.remove(memory_file)
            
        print("✅ Semantic injection hook verification passed!")

if __name__ == "__main__":
    asyncio.run(unittest.main())
