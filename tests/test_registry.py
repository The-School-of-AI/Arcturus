
import sys
import os
sys.path.append(os.getcwd())
import unittest
from core.registry import AgentRegistry

class MockAgent:
    def __init__(self):
        self.name = "Mock"

class TestAgentRegistry(unittest.TestCase):
    def setUp(self):
        AgentRegistry.clear()

    def test_register_and_get(self):
        AgentRegistry.register("MockAgent", MockAgent, "A mock agent")
        retrieved_class = AgentRegistry.get("MockAgent")
        
        self.assertEqual(retrieved_class, MockAgent)
        self.assertEqual(retrieved_class().name, "Mock")

    def test_list_agents(self):
        AgentRegistry.register("AgentA", MockAgent, "Desc A")
        AgentRegistry.register("AgentB", MockAgent, "Desc B")
        
        agents = AgentRegistry.list_agents()
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents["AgentA"], "Desc A")
        self.assertEqual(agents["AgentB"], "Desc B")

    def test_overwrite_warning(self):
        # This test just ensures no exception is raised on overwrite
        AgentRegistry.register("AgentA", MockAgent, "Desc A")
        AgentRegistry.register("AgentA", MockAgent, "New Desc")
        
        agents = AgentRegistry.list_agents()
        self.assertEqual(agents["AgentA"], "New Desc")

if __name__ == "__main__":
    unittest.main()
