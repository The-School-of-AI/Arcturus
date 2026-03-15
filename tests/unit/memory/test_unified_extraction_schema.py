"""Tests for unified extraction schema (FactItem, _derive_user_facts_from_facts, to_legacy_entity_result)."""

from memory.unified_extraction_schema import (
    FactItem,
    UnifiedExtractionResult,
    _derive_user_facts_from_facts,
)


class TestFactItem:
    """FactItem uses field_id; get_value resolves by value_type."""

    def test_fact_item_with_field_id(self):
        f = FactItem(field_id="personal_hobbies", value_json=["Running"], value_type="json")
        assert f.field_id == "personal_hobbies"
        assert f.get_value() == ["Running"]

    def test_fact_item_value_type_text(self):
        f = FactItem(field_id="dietary_style", value_text="vegan", value_type="text")
        assert f.get_value() == "vegan"

    def test_fact_item_value_text_preferred(self):
        f = FactItem(field_id="x", value_type="text", value_text="explicit")
        assert f.get_value() == "explicit"


class TestDeriveUserFactsFromFacts:
    """_derive_user_facts_from_facts uses field_id → registry for rel_type."""

    def test_derive_requires_field_id_and_entity_ref(self):
        facts = [
            FactItem(field_id="dietary_style", value="veg", entity_ref="Concept::vegetarian"),
        ]
        out = _derive_user_facts_from_facts(facts)
        assert len(out) == 1
        assert out[0]["rel_type"] == "PREFERS"
        assert out[0]["type"] == "Concept"
        assert out[0]["name"] == "vegetarian"

    def test_derive_skips_missing_entity_ref(self):
        facts = [FactItem(field_id="dietary_style", value="veg")]
        assert _derive_user_facts_from_facts(facts) == []

    def test_derive_skips_unknown_field_id(self):
        facts = [FactItem(field_id="unknown_field", value="x", entity_ref="Concept::foo")]
        assert _derive_user_facts_from_facts(facts) == []


class TestUnifiedExtractionResult:
    """to_legacy_entity_result works with field_id-based facts."""

    def test_to_legacy_entity_result_entities(self):
        r = UnifiedExtractionResult(
            entities=[{"type": "Person", "name": "Alice"}],
            facts=[],
        )
        legacy = r.to_legacy_entity_result()
        assert legacy["entities"] == [{"type": "Person", "name": "Alice"}]

    def test_to_legacy_entity_result_user_facts_from_entity_ref(self):
        r = UnifiedExtractionResult(
            entities=[],
            facts=[FactItem(field_id="dietary_style", value="veg", entity_ref="Concept::vegetarian")],
        )
        legacy = r.to_legacy_entity_result()
        assert len(legacy["user_facts"]) == 1
        assert legacy["user_facts"][0]["name"] == "vegetarian"
