"""Tests for UnifiedExtractor._normalize_facts (field_id-based parsing)."""

from memory.unified_extractor import UnifiedExtractor
from memory.unified_extraction_schema import FactItem


class TestNormalizeFacts:
    """Extractor _normalize_facts expects field_id, skips facts without it."""

    def test_normalize_accepts_field_id(self):
        ext = UnifiedExtractor()
        raw = [{"field_id": "personal_hobbies", "value": "Running", "value_type": "text"}]
        out = ext._normalize_facts(raw)
        assert len(out) == 1
        assert isinstance(out[0], FactItem)
        assert out[0].field_id == "personal_hobbies"

    def test_normalize_skips_missing_field_id(self):
        ext = UnifiedExtractor()
        raw = [
            {"key": "hobby", "namespace": "identity", "value": "x"},
            {"field_id": "personal_hobbies", "value": "Running"},
        ]
        out = ext._normalize_facts(raw)
        assert len(out) == 1
        assert out[0].field_id == "personal_hobbies"

    def test_normalize_coerces_value_type(self):
        ext = UnifiedExtractor()
        raw = [{"field_id": "dietary_style", "value": "vegan", "value_type": "text"}]
        out = ext._normalize_facts(raw)
        assert out[0].value_type == "text"
