
import sys
import os
sys.path.append(os.getcwd())
import asyncio
import unittest
from unittest.mock import MagicMock, patch
from core.registry import AgentRegistry
from agents.base_agent import AgentRunner

class TestPlannerInjection(unittest.TestCase):
    def setUp(self):
        AgentRegistry.clear()
        # Register a mock agent to verify injection
        AgentRegistry.register("MockAgent", {"description": "A mock agent for testing"}, "A mock agent for testing")
        AgentRegistry.register("PlannerAgent", {
            "prompt_text": "Available Agents: {available_agents_enum}\nDescriptions:\n{available_agents_description}",
            "model": "mock",
            "description": "The Planner"
        })

    @patch("agents.base_agent.ModelManager")
    def test_prompt_injection(self, MockModelManager):
        # Setup mock model
        mock_instance = MockModelManager.return_value
        
        # Create a future for the async result
        f = asyncio.Future()
        f.set_result('{"plan_graph": {}}')
        mock_instance.generate_text.return_value = f
        
        runner = AgentRunner(None)
        
        # Run agent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(runner.run_agent("PlannerAgent", {"task": "test"}))
        
        # Verify result success
        self.assertTrue(result["success"])
        
        # Verify prompt content in the passed argument to generate_text
        call_args = mock_instance.generate_text.call_args
        full_prompt = call_args[0][0]
        
        # Check Enum
        self.assertIn('"MockAgent"', full_prompt)
        self.assertIn('"PlannerAgent"', full_prompt)
        
        # Check Description
        self.assertIn("* **MockAgent**: A mock agent for testing", full_prompt)

if __name__ == "__main__":
    unittest.main()
