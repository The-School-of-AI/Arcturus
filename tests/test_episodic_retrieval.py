
import unittest
import os
import sys
import json
from pathlib import Path
import pytest

# Add project root to path
sys.path.append(os.getcwd())

try:
    from memory.episodic import search_episodes, MEMORY_DIR
except ModuleNotFoundError:
    pytest.skip("memory.episodic module not available", allow_module_level=True)

class TestEpisodicRetrieval(unittest.TestCase):
    def setUp(self):
        # Create a mock episode
        self.mock_file = MEMORY_DIR / "skeleton_test_123.json"
        self.mock_data = {
            "id": "test_123",
            "original_query": "How to bake a chocolate cake with sprinkles",
            "status": "completed",
            "nodes": [
                {"id": "T001", "agent": "CoderAgent", "description": "Baking logic"}
            ]
        }
        with open(self.mock_file, "w") as f:
            json.dump(self.mock_data, f)

    def tearDown(self):
        if self.mock_file.exists():
            os.remove(self.mock_file)

    def test_search_hit(self):
        results = search_episodes("chocolate cake")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["id"], "test_123")
        print("✅ search_episodes hit passed")

    def test_search_miss(self):
        results = search_episodes("random query about space")
        # Check if test_123 is in results (it shouldn't be high enough score)
        ids = [r["id"] for r in results]
        self.assertNotIn("test_123", ids)
        print("✅ search_episodes miss passed")

if __name__ == "__main__":
    unittest.main()
