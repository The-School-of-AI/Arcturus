"""
Unit tests for P02 Oracle source provenance labels.
Tests that memory retriever, Citation, and formatter include provenance information.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


# T9: Memory retriever adds [SOURCE: MEMORY] tags
def test_memory_context_has_provenance_tags():
    """Memory retriever output should include [SOURCE: MEMORY] tags."""
    from memory.memory_retriever import retrieve

    mock_store = MagicMock()
    mock_results = [
        {"id": "m1", "text": "User prefers dark mode", "score": 0.92},
        {"id": "m2", "text": "User works at Acme Corp", "score": 0.85},
    ]

    with patch("memory.memory_retriever._get_store", return_value=mock_store):
        with patch("memory.memory_retriever._semantic_recall", return_value=mock_results):
            with patch("memory.memory_retriever._get_knowledge_graph", return_value=None):
                context, results = retrieve("test query", store=mock_store)

    assert "[SOURCE: MEMORY]" in context


# T10: Citation dataclass has source_type field
def test_citation_source_type_field():
    """Citation dataclass should support source_type field."""
    from search.synthesizer import Citation

    c = Citation(index=1, url="https://example.com", title="Test", source_type="memory")
    assert c.source_type == "memory"

    c_default = Citation(index=2, url="https://web.com", title="Web")
    assert c_default.source_type == "web"


# T11: Formatter prompt contains provenance instructions
def test_formatter_skill_has_provenance_section():
    """FormatterSkill prompt should include provenance handling instructions."""
    from core.skills.library.formatter.skill import FormatterSkill
    prompt = FormatterSkill().prompt_text
    assert "SOURCE PROVENANCE" in prompt or "provenance" in prompt.lower()
    assert "[SOURCE: MEMORY]" in prompt
