"""Tests for Neo4j preferences adapter registry integration (no Neo4j required)."""

from memory.fact_field_registry import get_fact_to_hub_mappings
from memory.neo4j_preferences_adapter import FACT_TO_HUB_PATH, _set_nested, _default_hub_shape


class TestFactToHubPathFromRegistry:
    """FACT_TO_HUB_PATH is derived from registry."""

    def test_fact_to_hub_path_populated(self):
        assert len(FACT_TO_HUB_PATH) >= 30

    def test_registry_and_adapter_in_sync(self):
        mappings = get_fact_to_hub_mappings()
        assert len(FACT_TO_HUB_PATH) == len(mappings)

    def test_personal_hobbies_in_mapping(self):
        by_ns_key = {(m[0], m[1]): m for m in FACT_TO_HUB_PATH}
        assert ("identity", "personal_hobbies") in by_ns_key
        entry = by_ns_key[("identity", "personal_hobbies")]
        path, append = entry[2], entry[3]
        assert path == ("soft_identity", "interests_and_hobbies", "personal_hobbies")
        assert append is True


class TestSetNested:
    """_set_nested correctly applies scalar and append behavior."""

    def test_scalar_set(self):
        d = {}
        _set_nested(d, ("a", "b", "c"), "val", append=False)
        assert d["a"]["b"]["c"] == "val"

    def test_append_extends_list(self):
        d = {"a": {"b": {"c": []}}}
        _set_nested(d, ("a", "b", "c"), "x", append=True)
        _set_nested(d, ("a", "b", "c"), "y", append=True)
        assert d["a"]["b"]["c"] == ["x", "y"]
