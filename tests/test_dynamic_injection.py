
import sys
import os
sys.path.append(os.getcwd())
import asyncio
import unittest
from core.registry import AgentRegistry
from routers.agent import inject_agent, list_agents, AgentInjectionRequest

class TestDynamicInjection(unittest.TestCase):
    def setUp(self):
        AgentRegistry.clear()

    def test_injection_and_hotswap(self):
        # 1. Inject new agent
        new_agent_name = "DynamicAgent"
        initial_config = {
            "prompt_text": "You are version 1",
            "model_provider": "gemini",
            "model": "gemini-1.5-flash"
        }
        
        # Run async endpoints in a sync test.
        response = asyncio.run(inject_agent(
            AgentInjectionRequest(name=new_agent_name, config=initial_config)
        ))
        
        self.assertEqual(response["status"], "success")
        self.assertEqual(AgentRegistry.get(new_agent_name), initial_config)
        
        # 2. Verify List
        list_response = asyncio.run(list_agents())
        self.assertIn(new_agent_name, list_response["agents"])
        
        # 3. Hot-Swap (Update existing agent)
        updated_config = initial_config.copy()
        updated_config["prompt_text"] = "You are version 2"
        
        response = asyncio.run(inject_agent(
            AgentInjectionRequest(name=new_agent_name, config=updated_config, description="Updated version")
        ))
        
        # Registry should have new config
        current_config = AgentRegistry.get(new_agent_name)
        self.assertEqual(current_config["prompt_text"], "You are version 2")
        self.assertEqual(AgentRegistry.list_agents()[new_agent_name], "Updated version")

if __name__ == "__main__":
    unittest.main()
