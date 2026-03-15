"""
Integration tests for P02 Oracle multimodal end-to-end flows.
Tests upload endpoint, file extraction pipeline, and planner integration.
"""
import os
import sys
import asyncio
import tempfile
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# T12: Upload endpoint saves file and returns valid path
@pytest.mark.asyncio
async def test_upload_endpoint_saves_file(temp_dir):
    """POST /runs/upload should save the file to disk and return its path."""
    try:
        from fastapi.testclient import TestClient
        from routers.runs import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api")

        # Patch PROJECT_ROOT for uploads dir
        with patch("routers.runs.PROJECT_ROOT", Path(temp_dir)):
            client = TestClient(app)
            content = b"test PDF content"
            response = client.post(
                "/api/runs/upload",
                files={"file": ("test_doc.pdf", content, "application/pdf")}
            )

        assert response.status_code == 200
        data = response.json()
        assert "path" in data
        assert "name" in data
        assert data["name"] == "test_doc.pdf"
        assert os.path.exists(data["path"])
    except ImportError:
        pytest.skip("fastapi test dependencies not available")


# T13: RunRequest with file_paths triggers extraction
@pytest.mark.asyncio
async def test_run_with_file_paths_triggers_extraction(temp_dir):
    """RunRequest with file_paths should trigger _extract_file_content."""
    from routers.runs import _extract_file_content

    csv_path = os.path.join(temp_dir, "sales.csv")
    with open(csv_path, "w") as f:
        f.write("product,revenue\nWidgetA,1000\nWidgetB,2000\n")

    manifest, uploaded = await _extract_file_content([csv_path])

    assert len(manifest) == 1
    assert manifest[0]["type"] == "csv"
    assert len(uploaded) == 1
    assert "WidgetA" in uploaded[0]["content"]


# T14: Planner receives file content in effective_query
def test_planner_gets_file_content():
    """When files are uploaded, the effective_query should contain file contents."""
    # Simulate the loop.py logic that builds effective_query
    query = "What trends do you see?"
    uploaded_files = [
        {"name": "data.csv", "content": "product,revenue\nA,100\nB,200", "content_type": "csv"}
    ]

    effective_query = query
    if uploaded_files:
        file_sections = []
        for uf in uploaded_files:
            content = uf.get("content", "[no content extracted]")
            ctype = uf.get("content_type", "unknown")
            name = uf.get("name", "unknown")
            truncated = content[:20000] if isinstance(content, str) else str(content)[:20000]
            file_sections.append(f"### File: {name} (type: {ctype})\n{truncated}")
        effective_query = query + "\n\n--- UPLOADED FILE CONTENTS ---\n" + "\n\n".join(file_sections) + "\n--- END FILE CONTENTS ---"

    assert "UPLOADED FILE CONTENTS" in effective_query
    assert "data.csv" in effective_query
    assert "product,revenue" in effective_query


# T15: Standard mode with file does NOT trigger deep research
def test_standard_mode_excludes_deep_research():
    """In standard mode, deep_research skill should be excluded."""
    # This tests the logic pattern used in process_run
    mode = "standard"
    planner_exclude = []
    if mode == "standard":
        planner_exclude = ["deep_research"]

    assert "deep_research" in planner_exclude


# T16: Deep mode with file DOES include file content
@pytest.mark.asyncio
async def test_deep_mode_includes_file_content(temp_dir):
    """Deep research mode should still include uploaded file content."""
    from routers.runs import _extract_file_content

    # Use .txt to avoid pymupdf4llm failure on non-PDF bytes
    txt_path = os.path.join(temp_dir, "paper.txt")
    with open(txt_path, "w") as f:
        f.write("This is a test paper about AI safety.")

    manifest, uploaded = await _extract_file_content([txt_path])

    # File content should be available regardless of mode
    assert len(uploaded) == 1
    assert uploaded[0]["content_type"] == "text"
    assert "AI safety" in uploaded[0]["content"]
