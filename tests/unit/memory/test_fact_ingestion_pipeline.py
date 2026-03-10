"""Integration-style tests for the fact ingestion pipeline (no Neo4j required)."""

from memory.fact_normalizer import normalize_facts
from memory.unified_extraction_schema import FactItem, UnifiedExtractionResult


class TestFactIngestionPipeline:
    """Simulates: LLM JSON -> FactItem -> normalize_facts -> canonical output."""

    def test_simulated_llm_hobby_extraction(self):
        """Simulate LLM returns field_id=personal_hobbies; pipeline produces canonical fact."""
        # What extractor would produce from _normalize_facts of LLM JSON
        facts = [FactItem(field_id="personal_hobbies", value="Running", value_type="text")]
        normalized = normalize_facts(facts)
        assert len(normalized) == 1
        assert normalized[0]["namespace"] == "identity"
        assert normalized[0]["key"] == "personal_hobbies"
        assert normalized[0]["append"] is True
        assert "Running" in normalized[0]["value_json"]

    def test_simulated_unified_result_to_normalized_facts(self):
        """UnifiedExtractionResult.facts (FactItem) -> normalize_facts -> ingest-ready."""
        result = UnifiedExtractionResult(
            source="memory",
            memories=[],
            entities=[],
            entity_relationships=[],
            facts=[
                FactItem(field_id="personal_hobbies", value="Chess"),
                FactItem(field_id="dietary_style", value="vegetarian"),
            ],
            evidence_events=[],
        )
        normalized = normalize_facts(result.facts)
        assert len(normalized) == 2
        keys = {f["key"] for f in normalized}
        assert "personal_hobbies" in keys
        assert "dietary_style" in keys
