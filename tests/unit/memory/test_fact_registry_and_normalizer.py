"""Tests for fact_field_registry and fact_normalizer (field_id-based extraction)."""

import pytest

from memory.fact_field_registry import (
    get_field_def,
    get_valid_field_ids,
    resolve_field_id_to_canonical,
)
from memory.fact_normalizer import normalize_facts


class TestFactFieldRegistry:
    """Registry is source of truth for field_id → namespace, key, append."""

    def test_valid_field_id_resolves(self):
        r = resolve_field_id_to_canonical("personal_hobbies")
        assert r is not None
        ns, key, vt, _hub, append = r
        assert ns == "identity"
        assert key == "personal_hobbies"
        assert append is True

    def test_unknown_field_id_returns_none(self):
        assert resolve_field_id_to_canonical("nonexistent_field") is None
        assert resolve_field_id_to_canonical("") is None

    def test_get_valid_field_ids(self):
        ids = get_valid_field_ids()
        assert "personal_hobbies" in ids
        assert "dietary_style" in ids
        assert len(ids) > 10

    def test_get_field_def(self):
        d = get_field_def("personal_hobbies")
        assert d is not None
        assert d["namespace"] == "identity"
        assert d["key"] == "personal_hobbies"
        assert d["append"] is True


class TestFactNormalizer:
    """Normalizer resolves field_id via registry; unknown → extras."""

    def test_valid_field_id_produces_canonical_namespace_key(self):
        facts = [{"field_id": "personal_hobbies", "value": "Running", "value_type": "text"}]
        out = normalize_facts(facts)
        assert len(out) == 1
        assert out[0]["namespace"] == "identity"
        assert out[0]["key"] == "personal_hobbies"
        assert out[0]["append"] is True
        assert "Running" in out[0].get("value_json", [])

    def test_unknown_field_id_routes_to_extras(self):
        facts = [{"field_id": "invalid_field", "value": "foo", "value_type": "text"}]
        out = normalize_facts(facts)
        assert len(out) == 1
        assert out[0]["namespace"] == "extras"
        assert out[0]["key"] == "invalid_field"

    def test_empty_field_id_skipped(self):
        facts = [{"field_id": "", "value": "x"}, {"field_id": "personal_hobbies", "value": "Y"}]
        out = normalize_facts(facts)
        assert len(out) == 1
        assert out[0]["key"] == "personal_hobbies"

    def test_append_merge_same_field_id(self):
        facts = [
            {"field_id": "personal_hobbies", "value": "Running"},
            {"field_id": "personal_hobbies", "value": ["Chess", "Reading"]},
        ]
        out = normalize_facts(facts)
        assert len(out) == 1
        vals = out[0].get("value_json", [])
        assert "Running" in vals
        assert "Chess" in vals
        assert "Reading" in vals

    def test_scalar_field_replace(self):
        facts = [{"field_id": "dietary_style", "value": "vegetarian", "value_type": "text"}]
        out = normalize_facts(facts)
        assert len(out) == 1
        assert out[0]["namespace"] == "identity.food"
        assert out[0]["key"] == "dietary_style"
        assert out[0]["append"] is False
        assert out[0]["value"] == "vegetarian"

    def test_no_duplicate_facts_from_namespace_drift(self):
        """Same semantic fact with different model outputs → single canonical fact."""
        facts = [
            {"field_id": "personal_hobbies", "value": "Running"},
        ]
        out = normalize_facts(facts)
        assert len(out) == 1
        assert out[0]["namespace"] == "identity"
        assert out[0]["key"] == "personal_hobbies"
