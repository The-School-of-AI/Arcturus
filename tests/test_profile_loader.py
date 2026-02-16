
import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.profile_loader import get_profile

class TestProfileLoader(unittest.TestCase):
    def test_load_biases(self):
        profile = get_profile()
        biases = profile.biases
        
        print(f"DEBUG: Biases: {biases}")
        
        # In current profiles.yaml: persona.tone is 'concise'
        self.assertEqual(biases["tone"], "concise")
        self.assertTrue(biases["conciseness"])
        
    def test_load_strategy(self):
        profile = get_profile()
        max_steps = profile.get("strategy.max_steps")
        
        print(f"DEBUG: Max Steps: {max_steps}")
        # In current profiles.yaml: strategy.max_steps is 3
        self.assertEqual(max_steps, 3)

if __name__ == "__main__":
    unittest.main()
