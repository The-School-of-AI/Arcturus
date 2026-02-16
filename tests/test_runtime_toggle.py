
import asyncio
import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from agents.base_agent import AgentRunner
from core.skills.base import Skill
from core.registry import registry
from mcp_servers.multi_mcp import MultiMCP

class ResearchSkill(Skill):
    name = "research"
    def get_system_prompt_additions(self) -> str:
        return "RESEARCH_PROMPT"
    
    def get_tools(self):
        class Tool:
            name = "web_search"
            description = "Search the web"
        return [Tool()]

class TestRuntimeToggle(unittest.IsolatedAsyncioTestCase):
    async def test_toggle(self):
        mcp = MultiMCP()
        runner = AgentRunner(mcp)
        
        # 1. Register agent WITHOUT skill
        registry.register("Worker", {
            "prompt_text": "WORKER_BASE",
            "skills": []
        })
        
        from shared.state import get_skill_manager
        sm = get_skill_manager()
        sm.skill_classes["research"] = ResearchSkill
        
        # 2. Run once - tools should be missing
        try: await runner.run_agent("Worker", {"task": "t1"})
        except: pass
        content = Path("memory/debug_logs/latest_prompt.txt").read_text()
        self.assertNotIn("web_search", content)
        
        # 3. Simulate Toggle (simulating the /toggle_skill logic)
        config = registry.get_config("Worker")
        config["skills"] = ["research"]
        registry.register("Worker", config)
        
        # 4. Run again - tools should be present
        try: await runner.run_agent("Worker", {"task": "t2"})
        except: pass
        content = Path("memory/debug_logs/latest_prompt.txt").read_text()
        self.assertIn("web_search", content)
        self.assertIn("RESEARCH_PROMPT", content)
        
        print("✅ Runtime skill toggle verification passed!")

if __name__ == "__main__":
    asyncio.run(unittest.main())
