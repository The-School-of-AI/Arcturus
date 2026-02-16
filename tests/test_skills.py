
import unittest
import sys
import os
sys.path.append(os.getcwd())
from core.skills.base import Skill, SkillConfig

class MockSkill(Skill):
    name = "mock"
    def get_system_prompt_additions(self) -> str:
        return "Mock Prompt"

class TestSkillBase(unittest.TestCase):
    def test_instantiation(self):
        s = MockSkill()
        self.assertEqual(s.name, "mock")
        self.assertEqual(s.get_system_prompt_additions(), "Mock Prompt")
        self.assertIsInstance(s.config, SkillConfig)

    def test_config(self):
        c = SkillConfig(enabled=False, params={"p": 1})
        s = MockSkill(config=c)
        self.assertFalse(s.config.enabled)
        self.assertEqual(s.config.params["p"], 1)

if __name__ == "__main__":
    unittest.main()
