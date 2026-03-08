"""Integration tests for P03 Spark Oracle data pipeline.

These tests enforce contract-level integration gates across repo structure and CI wiring.
Phase 2/3: Tests Oracle → Spark → Forge integration pipeline with export capabilities.
"""
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

# Import components for integration testing
from content import oracle_client, page_generator
from content.export import export_page_to_format, get_export_formats

PROJECT_ID = "P03"
PROJECT_KEY = "p03_spark"
CI_CHECK = "p03-spark-pages"
CHARTER = Path("CAPSTONE/project_charters/P03_spark_synthesized_content_pages_sparkpages.md")
ACCEPTANCE_FILE = Path("tests/acceptance/p03_spark/test_structured_page_not_text_wall.py")
INTEGRATION_FILE = Path("tests/integration/test_spark_oracle_data_pipeline.py")
WORKFLOW_FILE = Path(".github/workflows/project-gates.yml")
BASELINE_SCRIPT = Path("scripts/test_all.sh")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_01_integration_file_is_declared_in_charter() -> None:
    assert INTEGRATION_FILE.as_posix() in _read(CHARTER)


def test_02_acceptance_and_integration_files_exist() -> None:
    assert ACCEPTANCE_FILE.exists(), "Missing acceptance file: " + str(ACCEPTANCE_FILE)
    assert INTEGRATION_FILE.exists(), "Missing integration file: " + str(INTEGRATION_FILE)


def test_03_baseline_script_exists_and_is_executable() -> None:
    assert BASELINE_SCRIPT.exists(), "Missing baseline script scripts/test_all.sh"
    assert BASELINE_SCRIPT.stat().st_mode & 0o111, "scripts/test_all.sh must be executable"


def test_04_project_ci_check_is_wired_in_workflow() -> None:
    assert WORKFLOW_FILE.exists(), "Missing workflow .github/workflows/project-gates.yml"
    assert CI_CHECK in _read(WORKFLOW_FILE), "CI check not found in workflow: " + CI_CHECK


def test_05_charter_requires_baseline_regression() -> None:
    assert "scripts/test_all.sh quick" in _read(CHARTER)


# Integration Test Scenarios (Oracle → Spark → Forge pipeline)

def test_06_oracle_to_spark_data_pipeline():
    """Test Oracle client provides structured data that Spark can consume."""
    # Test Oracle client produces expected data structure
    oracle_response = oracle_client.search_oracle("test query integration", k=3)
    
    assert "results" in oracle_response
    assert "query_id" in oracle_response
    assert "metrics" in oracle_response
    
    results = oracle_response["results"]
    assert len(results) > 0
    
    # Verify Oracle results have required structure for Spark consumption
    first_result = results[0]
    required_fields = ["citation_id", "title", "snippet", "structured_extracts"]
    for field in required_fields:
        assert field in first_result, f"Oracle result missing required field: {field}"
    
    # Verify structured extracts contain tables for chart generation
    extracts = first_result["structured_extracts"]
    assert "tables" in extracts
    if extracts["tables"]:
        table = extracts["tables"][0]
        assert "columns" in table
        assert "rows" in table


def test_07_spark_page_generation_consumes_oracle_data():
    """Test Spark page generator properly consumes Oracle outputs."""
    
    async def generate_test_page():
        page = await page_generator.generate_page(
            "blockchain technology analysis", 
            template="topic_overview", 
            created_by="integration_test"
        )
        return page
    
    # Generate page and verify structure
    page = asyncio.get_event_loop().run_until_complete(generate_test_page())
    
    # Verify page has proper structure
    assert "id" in page
    assert "sections" in page
    assert "citations" in page
    assert len(page["sections"]) >= 2  # Multiple sections generated
    
    # Verify citations map to Oracle results
    citations = page["citations"]
    assert len(citations) > 0
    
    # Check that sections reference valid citation IDs
    citation_refs_found = False
    for section in page["sections"]:
        for block in section.get("blocks", []):
            if block.get("kind") == "citation":
                for cid in block.get("ids", []):
                    assert cid in citations, f"Section references invalid citation ID: {cid}"
                    citation_refs_found = True
    
    assert citation_refs_found, "No citation references found linking sections to Oracle data"
    
    # Verify enhanced features (charts, media) are present
    charts_found = any(len(section.get("charts", [])) > 0 for section in page["sections"])
    assert charts_found, "No charts generated from Oracle structured data"


def test_08_export_pipeline_produces_valid_formats():
    """Test export engine can convert Spark pages to multiple formats."""
    
    # First generate a test page
    async def create_test_page():
        return await page_generator.generate_page(
            "export test data analysis", 
            template="topic_overview", 
            created_by="export_test"
        )
    
    page = asyncio.get_event_loop().run_until_complete(create_test_page())
    page_id = page["id"]
    
    # Test each export format
    supported_formats = get_export_formats()
    assert len(supported_formats) >= 3, "Should support multiple export formats"
    
    for format_info in supported_formats:
        format_type = format_info["format"]
        
        # Test export
        export_result = export_page_to_format(page_id, format_type)
        
        assert export_result["success"], f"Export failed for {format_type}: {export_result.get('error')}"
        assert export_result["format"] == format_type
        assert "filename" in export_result
        assert "exported_at" in export_result
        
        # Verify export file exists
        export_path = Path(export_result["path"])
        assert export_path.exists(), f"Export file not created: {export_path}"
        assert export_path.stat().st_size > 0, f"Export file is empty: {export_path}"


def test_09_failure_propagation_and_graceful_degradation():
    """Test cross-project failure handling and graceful degradation."""
    
    # Test with invalid Oracle response structure
    async def test_with_missing_oracle_data():
        # Mock empty Oracle response
        original_search = oracle_client.search_oracle
        
        def mock_empty_oracle(query, k=5, timeout=5.0):
            return {"query_id": "test", "results": [], "metrics": {"num_sources": 0}}
        
        oracle_client.search_oracle = mock_empty_oracle
        
        try:
            # Should still generate page but with degraded content
            page = await page_generator.generate_page(
                "empty data test", 
                template="topic_overview", 
                created_by="failure_test"
            )
            
            # Verify page structure is maintained even with no data
            assert "sections" in page
            assert len(page["sections"]) > 0
            assert "citations" in page
            
            # Should gracefully handle lack of charts/media
            for section in page["sections"]:
                assert "blocks" in section  # Sections should still have content blocks
            
        finally:
            # Restore original function
            oracle_client.search_oracle = original_search
    
    asyncio.get_event_loop().run_until_complete(test_with_missing_oracle_data())
    
    # Test export with invalid page ID
    export_result = export_page_to_format("invalid_page_id", "markdown")
    assert not export_result["success"]
    assert "not found" in export_result["error"].lower()


def test_10_end_to_end_oracle_spark_forge_handoff():
    """Test complete pipeline from Oracle query to Forge-ready export structures."""
    
    async def full_pipeline_test():
        # 1. Oracle: Generate query response
        oracle_query = "artificial intelligence market analysis 2026"
        oracle_response = oracle_client.search_oracle(oracle_query, k=5)
        
        assert len(oracle_response["results"]) > 0, "Oracle should return results"
        
        # 2. Spark: Generate structured page from Oracle data
        page = await page_generator.generate_page(
            oracle_query, 
            template="topic_overview", 
            created_by="pipeline_test"
        )
        
        # Verify Spark output has Forge-compatible structure
        assert "sections" in page
        assert "metadata" in page
        assert "citations" in page
        
        # Verify enhanced Phase 2/3 features are present
        enhanced_sections = [s for s in page["sections"] if s.get("metadata", {}).get("enhanced")]
        assert len(enhanced_sections) > 0, "Should have enhanced sections with Phase 2/3 features"
        
        # 3. Forge handoff: Export to multiple formats
        page_id = page["id"]
        
        # Test key export formats for Forge compatibility
        formats_to_test = ["html", "markdown"] 
        export_results = []
        
        for fmt in formats_to_test:
            result = export_page_to_format(page_id, fmt)
            assert result["success"], f"Export to {fmt} failed: {result.get('error')}"
            export_results.append(result)
        
        # Verify export structure is Forge-compatible
        for result in export_results:
            assert "path" in result, "Export should provide file path for Forge ingestion"
            assert "size" in result, "Export should provide size metadata"
            assert "exported_at" in result, "Export should provide timestamp"
            
            # Verify exported content exists and is substantial
            export_path = Path(result["path"])
            content = export_path.read_text(encoding="utf-8")
            assert len(content) > 500, "Exported content should be substantial"
            assert oracle_query in content, "Exported content should contain original query context"
        
        return {
            "oracle_results_count": len(oracle_response["results"]),
            "spark_sections_count": len(page["sections"]),
            "enhanced_sections_count": len(enhanced_sections),
            "export_formats_count": len(export_results),
            "pipeline_success": True
        }
    
    # Execute full pipeline test
    pipeline_result = asyncio.get_event_loop().run_until_complete(full_pipeline_test())
    
    # Verify pipeline metrics
    assert pipeline_result["oracle_results_count"] >= 3, "Oracle should provide multiple sources"
    assert pipeline_result["spark_sections_count"] >= 3, "Spark should generate multiple sections"
    assert pipeline_result["enhanced_sections_count"] >= 2, "Should have enhanced Phase 2/3 sections"
    assert pipeline_result["export_formats_count"] >= 2, "Should support multiple export formats"
    assert pipeline_result["pipeline_success"], "End-to-end pipeline should succeed"
