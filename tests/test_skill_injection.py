
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

class SkillA(Skill):
    name = "skill_a"
    def get_system_prompt_additions(self) -> str:
        return "PROMPT_A"

class SkillB(Skill):
    name = "skill_b"
    def get_system_prompt_additions(self) -> str:
        return "PROMPT_B"

from core.skills.library.rag.skill import RAGSkill

class TestSkillInjection(unittest.IsolatedAsyncioTestCase):
    async def test_combined_prompt(self):
        # ... (existing test) ...
        mcp = MultiMCP()
        runner = AgentRunner(mcp)
        registry.register("TestAgent", {
            "prompt_text": "BASE_PROMPT",
            "skills": ["skill_a", "skill_b"]
        })
        from shared.state import get_skill_manager
        sm = get_skill_manager()
        sm.skill_classes["skill_a"] = SkillA
        sm.skill_classes["skill_b"] = SkillB
        try:
            await runner.run_agent("TestAgent", {"data": 123})
        except:
            pass
        debug_file = Path("memory/debug_logs/latest_prompt.txt")
        content = debug_file.read_text()
        self.assertIn("BASE_PROMPT", content)
        self.assertIn("PROMPT_A", content)
        self.assertIn("PROMPT_B", content)

    async def test_tool_injection(self):
        mcp = MultiMCP()
        runner = AgentRunner(mcp)
        registry.register("RagAgent", {
            "prompt_text": "RAG_BASE",
            "skills": ["rag"]
        })
        from shared.state import get_skill_manager
        sm = get_skill_manager()
        sm.skill_classes["rag"] = RAGSkill
        
        try:
            await runner.run_agent("RagAgent", {"task": "test rag"})
        except:
            pass
            
        debug_file = Path("memory/debug_logs/latest_prompt.txt")
        content = debug_file.read_text()
        
        self.assertIn("search_knowledge_base", content)
        self.assertIn("Search through uploaded and internal documents", content)
        print("✅ Tool injection verification passed!")


if __name__ == "__main__":
    asyncio.run(unittest.main())
