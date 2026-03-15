"""Tests for episodic memory retrieval. Phase B: Uses Qdrant backend."""

import unittest
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")

from memory.episodic import search_episodes, get_recent_episodes


class TestEpisodicRetrieval(unittest.TestCase):
    def test_search_episodes_mock(self):
        """Test search_episodes returns mocked results."""
        mock_result = [{"id": "test_123", "original_query": "chocolate cake", "nodes": []}]

        with patch("memory.episodic.get_episodic_store_provider", return_value="qdrant"):
            with patch("memory.episodic._get_episodic_store") as mock_get:
                store = MagicMock()
                store.search = MagicMock(return_value=mock_result)
                mock_get.return_value = store

                with patch("remme.utils.get_embedding", return_value=[0.1] * 768):
                    results = search_episodes("chocolate cake", limit=5)
                    self.assertEqual(len(results), 1)
                    self.assertEqual(results[0]["id"], "test_123")
                    self.assertEqual(results[0]["original_query"], "chocolate cake")

    def test_search_episodes_store_unavailable(self):
        """Test search_episodes returns [] when store init fails."""
        with patch("memory.episodic.get_episodic_store_provider", return_value="qdrant"):
            with patch("memory.episodic._get_episodic_store", return_value=None):
                results = search_episodes("any query")
                self.assertEqual(results, [])

    def test_get_recent_episodes_mock(self):
        """Test get_recent_episodes returns mocked results."""
        mock_results = [{"id": "ep1", "original_query": "task 1", "nodes": []}]

        with patch("memory.episodic.get_episodic_store_provider", return_value="qdrant"):
            with patch("memory.episodic._get_episodic_store") as mock_get:
                store = MagicMock()
                store.get_recent = MagicMock(return_value=mock_results)
                mock_get.return_value = store

                results = get_recent_episodes(limit=5)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["id"], "ep1")


if __name__ == "__main__":
    unittest.main()
