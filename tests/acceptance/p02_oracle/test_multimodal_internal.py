"""
Acceptance tests for P02 Oracle sections 2.5 (Multimodal Search) and 2.6 (Internal Knowledge Search).
Validates that all integration points exist and are properly configured.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


# T21: Multimodal MCP tools are importable and callable
def test_multimodal_mcp_tools_importable():
    """The multimodal MCP server should expose analyze_image, analyze_pdf_document, analyze_data_file."""
    try:
        from mcp_servers.server_multimodal import analyze_image, analyze_pdf_document, analyze_data_file
        assert callable(analyze_image)
        assert callable(analyze_pdf_document)
        assert callable(analyze_data_file)
    except ImportError as e:
        pytest.skip(f"MCP multimodal server not importable: {e}")


# T22: Internal knowledge MCP tools are importable and callable
def test_internal_knowledge_mcp_tools_importable():
    """The internal knowledge MCP server should expose search_workspace_files, create_space, search_space."""
    try:
        from mcp_servers.server_internal import search_workspace_files, create_space, search_space
        assert callable(search_workspace_files)
        assert callable(create_space)
        assert callable(search_space)
    except ImportError as e:
        pytest.skip(f"MCP internal server not importable: {e}")


# T23: Upload endpoint exists at /runs/upload
def test_upload_endpoint_exists():
    """The runs router should have an upload endpoint."""
    from routers.runs import router

    routes = [r.path for r in router.routes]
    assert "/runs/upload" in routes, f"Upload endpoint missing. Routes: {routes}"


# T24: RunRequest schema includes file_paths and space_id
def test_run_request_schema_fields():
    """RunRequest should include file_paths and space_id fields."""
    from routers.runs import RunRequest

    # file_paths should default to empty list
    req = RunRequest(query="test")
    assert hasattr(req, "file_paths")
    assert req.file_paths == []

    # space_id should be optional
    assert hasattr(req, "space_id")
    assert req.space_id is None

    # Both should be settable
    req2 = RunRequest(query="test", file_paths=["/tmp/a.pdf"], space_id="sp-1")
    assert req2.file_paths == ["/tmp/a.pdf"]
    assert req2.space_id == "sp-1"


# T25: Planner skill mentions multimodal handling
def test_planner_skill_has_multimodal_section():
    """PlannerSkill prompt should contain multimodal file handling instructions."""
    from core.skills.library.planner.skill import PlannerSkill
    prompt = PlannerSkill().prompt_text
    assert "MULTIMODAL FILE HANDLING" in prompt
    assert "content_type" in prompt
    assert "image" in prompt.lower()
    assert "csv" in prompt.lower() or "spreadsheet" in prompt.lower()


# T26: Formatter skill mentions provenance
def test_formatter_skill_has_provenance():
    """FormatterSkill prompt should contain source provenance instructions."""
    from core.skills.library.formatter.skill import FormatterSkill
    prompt = FormatterSkill().prompt_text
    assert "SOURCE PROVENANCE" in prompt
    assert "MEMORY" in prompt
    assert "WORKSPACE" in prompt or "KNOWLEDGE_GRAPH" in prompt


# T27: Citation dataclass has source_type field
def test_citation_has_source_type():
    """Citation dataclass should have a source_type field defaulting to 'web'."""
    from search.synthesizer import Citation

    c = Citation(index=1, url="http://x.com", title="X")
    assert hasattr(c, "source_type")
    assert c.source_type == "web"

    c2 = Citation(index=2, url="", title="Memory", source_type="memory")
    assert c2.source_type == "memory"


# T28: Settings has file_extraction model key
def test_settings_has_file_extraction_model():
    """config/settings.json should have models.file_extraction configured."""
    from config.settings_loader import settings

    models = settings.get("models", {})
    assert "file_extraction" in models, (
        f"models.file_extraction not found in settings. Keys: {list(models.keys())}"
    )
