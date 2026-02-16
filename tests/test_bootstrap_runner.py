
import sys
import os
sys.path.append(os.getcwd())
import asyncio
import unittest
from unittest.mock import MagicMock
from core.registry import AgentRegistry
from agents.base_agent import AgentRunner

class TestAgentBootstrap(unittest.TestCase):
    def setUp(self):
        # Clear registry to test lazy loading
        AgentRegistry.clear()
        
    def test_lazy_bootstrap(self):
        # Mock multi_mcp as we don't need it for config loading
        mock_mcp = MagicMock()
        runner = AgentRunner(mock_mcp)
        
        # Verify empty initially (implied by clear)
        self.assertEqual(len(AgentRegistry.list_agents()), 0)
        
        # Trigger lazy load via get_available_agents
        agents = runner.get_available_agents()
        
        # Verify registry populated
        self.assertGreater(len(agents), 0)
        self.assertIn("PlannerAgent", agents)
        self.assertIn("CoderAgent", agents)
        
        # Verify Registry state matches
        registry_agents = AgentRegistry.list_agents()
        self.assertEqual(len(agents), len(registry_agents))

if __name__ == "__main__":
    unittest.main()
