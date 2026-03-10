"""Tests for fact_field_registry and fact_normalizer (field_id-based extraction)."""

import pytest

from memory.fact_field_registry import (
    get_fact_to_hub_mappings,
    get_field_def,
    get_valid_field_ids,
    resolve_field_id_to_canonical,
    resolve_to_canonical,
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

    def test_resolve_to_canonical_for_adapter_read_path(self):
        """Adapter reads Facts with (ns, key); resolve_to_canonical maps to hub path."""
        r = resolve_to_canonical("identity", "personal_hobbies")
        assert r is not None
        ns, key, _vt, hub_path, append = r
        assert ns == "identity"
        assert key == "personal_hobbies"
        assert hub_path == ("soft_identity", "interests_and_hobbies", "personal_hobbies")
        assert append is True

    def test_get_fact_to_hub_mappings_includes_canonical_paths(self):
        mappings = get_fact_to_hub_mappings()
        assert len(mappings) >= 30
        paths = {(m[0], m[1]): m[2] for m in mappings}
        assert ("identity", "personal_hobbies") in paths
        assert paths[("identity", "personal_hobbies")] == (
            "soft_identity", "interests_and_hobbies", "personal_hobbies"
        )

    def test_append_fields_have_append_true(self):
        ids = get_valid_field_ids()
        append_fields = {"personal_hobbies", "cuisine_likes", "tone", "frameworks_frontend"}
        for fid in append_fields:
            if fid in ids:
                d = get_field_def(fid)
                assert d["append"] is True, f"{fid} should be append"


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

    def test_normalizer_accepts_pydantic_fact_item(self):
        """Normalizer works with FactItem (Pydantic) as well as dict."""
        from memory.unified_extraction_schema import FactItem

        facts = [FactItem(field_id="dietary_style", value="vegan", value_type="text")]
        out = normalize_facts(facts)
        assert len(out) == 1
        assert out[0]["namespace"] == "identity.food"
        assert out[0]["key"] == "dietary_style"
        assert out[0]["value"] == "vegan"

    def test_entity_ref_preserved_for_scalar_facts(self):
        facts = [
            {"field_id": "dietary_style", "value": "vegetarian", "entity_ref": "Concept::vegetarian"}
        ]
        out = normalize_facts(facts)
        assert len(out) == 1
        assert out[0]["entity_ref"] == "Concept::vegetarian"

    def test_multiple_distinct_field_ids_produce_separate_facts(self):
        facts = [
            {"field_id": "personal_hobbies", "value": "Running"},
            {"field_id": "dietary_style", "value": "vegetarian"},
        ]
        out = normalize_facts(facts)
        assert len(out) == 2
        keys = {f["key"] for f in out}
        assert "personal_hobbies" in keys
        assert "dietary_style" in keys

    def test_json_list_string_parsed(self):
        """LLM may return value as string '[\"x\"]'; normalizer parses to list."""
        facts = [{"field_id": "personal_hobbies", "value": '["Gaming", "Reading"]', "value_type": "json"}]
        out = normalize_facts(facts)
        assert len(out) == 1
        vals = out[0].get("value_json", [])
        assert "Gaming" in vals
        assert "Reading" in vals

    def test_empty_or_none_input_returns_empty_list(self):
        assert normalize_facts(None) == []
        assert normalize_facts([]) == []
