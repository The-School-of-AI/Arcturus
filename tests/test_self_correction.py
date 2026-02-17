
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

class TestSelfCorrection(unittest.IsolatedAsyncioTestCase):
    async def test_ui_self_correction(self):
        if os.getenv("RUN_EXTERNAL_TESTS") != "1":
            self.skipTest("Set RUN_EXTERNAL_TESTS=1 to run external LLM-dependent test")

        # 1. Bootstrap
        bootstrap_agents()
        
        # 2. Setup malformed UI data (intentional breakage)
        malformed_ui = {
            "name": "Broken App",
            "pages": [
                {
                    "title": "Home",
                    # Missing path
                    "components": [
                        {
                            "id": "c1",
                            "type": "hero",
                            # Misspelled content key or malformed JSON string inside
                            "content": "This should be a dict but is a string"
                        }
                    ]
                }
            ]
            # Missing theme
        }
        
        # 3. Use FormatterAgent to "fix and format" this
        mcp = MultiMCP()
        runner = AgentRunner(mcp)
        
        input_data = {
            "task": "Fix this malformed UI config and ensure it follows the AppSchema (theme is required!).",
            "all_globals_schema": {"broken_config": malformed_ui},
            "markdown_report": "unused" # key for writes
        }
        
        try:
            result = await runner.run_agent("FormatterAgent", input_data)
            output = result.get("output", {})
            ui_config = output.get("ui_config", {})
            
            print(f"DEBUG: Fixed UI Config: {json.dumps(ui_config, indent=2)}")
            
            # Verify its fixed
            self.assertIn("theme", ui_config)
            self.assertIn("pages", ui_config)
            self.assertEqual(ui_config["pages"][0]["path"], "/") # It should have inferred the path
            self.assertIsInstance(ui_config["pages"][0]["components"][0]["content"], dict) # Fixed string to dict
            
            print("✅ FormatterAgent self-correction verification passed!")
        except Exception as e:
            self.fail(f"Self-correction failed: {e}")

if __name__ == "__main__":
    asyncio.run(unittest.main())
