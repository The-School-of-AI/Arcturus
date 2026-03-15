"""
Unit tests for P02 Oracle multimodal file extraction.
Tests PDF, image, CSV, Excel, and binary file handling in runs.py.
"""
import os
import sys
import asyncio
import tempfile
import pytest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# T1: PDF extraction returns content via configured provider
@pytest.mark.asyncio
async def test_pdf_extraction_returns_markdown(temp_dir):
    """PDF files should be extracted via configured multimodal provider."""
    from routers.runs import _extract_file_content

    pdf_path = os.path.join(temp_dir, "test.pdf")

    # Create a minimal valid PDF
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n206\n%%EOF"
    )
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    # Mock the multimodal extraction (covers both OpenRouter and Gemini)
    with patch("routers.runs._extract_multimodal_file", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = "# Test Document\n\nHello World"
        manifest, uploaded = await _extract_file_content([pdf_path])

    assert len(uploaded) == 1
    assert uploaded[0]["content_type"] == "pdf"
    assert "Test Document" in uploaded[0]["content"]
    mock_extract.assert_called_once_with(pdf_path)


# T2: Image extraction via _extract_file_content uses configured provider
@pytest.mark.asyncio
async def test_image_extraction_calls_provider(temp_dir):
    """Image files should be routed to configured multimodal provider."""
    from routers.runs import _extract_file_content

    img_path = os.path.join(temp_dir, "test.png")
    # Create a minimal 1x1 PNG
    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    with open(img_path, "wb") as f:
        f.write(png_bytes)

    # Mock the multimodal extraction
    with patch("routers.runs._extract_multimodal_file", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = "A small test image showing a single pixel"
        manifest, uploaded = await _extract_file_content([img_path])

    assert len(uploaded) == 1
    assert uploaded[0]["content_type"] == "image"
    assert "pixel" in uploaded[0]["content"].lower()
    mock_extract.assert_called_once_with(img_path)


# T3: CSV extraction reads content directly
@pytest.mark.asyncio
async def test_csv_extraction_reads_content(temp_dir):
    """CSV files should be read directly without LLM processing."""
    from routers.runs import _extract_file_content

    csv_path = os.path.join(temp_dir, "data.csv")
    with open(csv_path, "w") as f:
        f.write("name,value\nalpha,100\nbeta,200\n")

    manifest, uploaded = await _extract_file_content([csv_path])

    assert len(uploaded) == 1
    assert uploaded[0]["content_type"] == "csv"
    assert "alpha" in uploaded[0]["content"]
    assert "beta" in uploaded[0]["content"]


# T4: Excel conversion produces CSV-like content
@pytest.mark.asyncio
async def test_xlsx_extraction(temp_dir):
    """Excel files should be converted to CSV-like text content."""
    from routers.runs import _extract_file_content

    xlsx_path = os.path.join(temp_dir, "data.xlsx")
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Name", "Score"])
        ws.append(["Alice", 95])
        ws.append(["Bob", 87])
        wb.save(xlsx_path)

        manifest, uploaded = await _extract_file_content([xlsx_path])

        assert len(uploaded) == 1
        assert uploaded[0]["content_type"] == "spreadsheet"
        assert "Alice" in uploaded[0]["content"]
        assert "95" in uploaded[0]["content"]
    except ImportError:
        pytest.skip("openpyxl not installed")


# T5: Binary file graceful fallback
@pytest.mark.asyncio
async def test_binary_file_fallback(temp_dir):
    """Binary files should not crash; should return binary content type."""
    from routers.runs import _extract_file_content

    bin_path = os.path.join(temp_dir, "archive.zip")
    with open(bin_path, "wb") as f:
        f.write(b'\x50\x4b\x03\x04' + os.urandom(100))

    manifest, uploaded = await _extract_file_content([bin_path])

    assert len(uploaded) == 1
    assert uploaded[0]["content_type"] in ("binary", "error", "text")


# T6: File not found returns empty manifest
@pytest.mark.asyncio
async def test_nonexistent_file_skipped():
    """Non-existent paths should be skipped without error."""
    from routers.runs import _extract_file_content

    manifest, uploaded = await _extract_file_content(["/nonexistent/path/file.pdf"])

    assert len(manifest) == 0
    assert len(uploaded) == 0


# T7: _detect_file_paths_in_query backward compat
def test_detect_file_paths_in_query(temp_dir):
    """Query text containing file paths should be detected."""
    from routers.runs import _detect_file_paths_in_query

    # Create a real file so os.path.exists passes
    test_file = os.path.join(temp_dir, "test.pdf")
    with open(test_file, "w") as f:
        f.write("test")

    query = f"Please analyze the file at this location: {test_file}"
    paths = _detect_file_paths_in_query(query)
    assert test_file in paths


# T8: Settings model override works for file extraction
def test_file_extraction_model_configurable():
    """The file_extraction model should be configurable via settings."""
    from config.settings_loader import settings

    models = settings.get("models", {})
    # Should have file_extraction key
    assert "file_extraction" in models, "settings.models.file_extraction should be configured"


# T9: Post-plan enforcement rewrites RetrieverAgent for uploaded files
def test_post_plan_enforcement_rewrites_retriever():
    """When file_manifest is non-empty, RetrieverAgent tasks referencing uploaded
    files should be rewritten to ThinkerAgent or CoderAgent."""
    # Simulate the enforcement logic from loop.py
    file_manifest = [{"name": "chart.png", "type": "image"}]
    uploaded_files = [{"name": "chart.png", "content_type": "image", "content": "A bar chart showing sales"}]

    plan_nodes = [
        {"id": "T001", "agent": "RetrieverAgent", "agent_prompt": "Search for information about the uploaded image chart.png", "description": "Analyze the uploaded image"},
        {"id": "T002", "agent": "RetrieverAgent", "agent_prompt": "Search the web for recent sales trends", "description": "Web search for sales data"},
        {"id": "T003", "agent": "FormatterAgent", "agent_prompt": "Format the results", "description": "Format output"},
    ]

    # Run the same logic as loop.py enforcement
    uploaded_names = {f.get("name", "").lower() for f in file_manifest}
    content_type_map = {}
    for uf in uploaded_files:
        content_type_map[uf.get("name", "").lower()] = uf.get("content_type", "unknown")
    data_types = {"csv", "spreadsheet", "excel"}
    upload_markers = [
        "uploaded file", "uploaded image", "uploaded document",
        "file content", "image description", "extracted content",
        "the image", "the chart", "the pdf", "the document",
        "the spreadsheet", "the csv", "analyze the file",
        "uploaded", "file_manifest"
    ]

    for node in plan_nodes:
        if node.get("agent") != "RetrieverAgent":
            continue
        combined = (node.get("agent_prompt", "") + " " + node.get("description", "")).lower()
        references_upload = False
        matched_ct = None
        for fname in uploaded_names:
            if fname and fname in combined:
                references_upload = True
                matched_ct = content_type_map.get(fname)
                break
        if not references_upload:
            for marker in upload_markers:
                if marker in combined:
                    references_upload = True
                    break
        if references_upload:
            node["agent"] = "CoderAgent" if (matched_ct and matched_ct in data_types) else "ThinkerAgent"

    # T001 should be rewritten (references chart.png and "uploaded image")
    assert plan_nodes[0]["agent"] == "ThinkerAgent", f"T001 should be ThinkerAgent, got {plan_nodes[0]['agent']}"
    # T002 should remain RetrieverAgent (legitimate web search)
    assert plan_nodes[1]["agent"] == "RetrieverAgent", f"T002 should stay RetrieverAgent, got {plan_nodes[1]['agent']}"
    # T003 should remain FormatterAgent (not a RetrieverAgent)
    assert plan_nodes[2]["agent"] == "FormatterAgent"


# T10: Post-plan enforcement uses CoderAgent for CSV/spreadsheet
def test_post_plan_enforcement_csv_uses_coder():
    """RetrieverAgent tasks for CSV/spreadsheet files should be rewritten to CoderAgent."""
    file_manifest = [{"name": "sales.csv", "type": "csv"}]
    uploaded_files = [{"name": "sales.csv", "content_type": "csv", "content": "product,revenue\nA,100"}]

    plan_nodes = [
        {"id": "T001", "agent": "RetrieverAgent", "agent_prompt": "Analyze the uploaded file sales.csv", "description": "Analyze CSV data"},
    ]

    uploaded_names = {f.get("name", "").lower() for f in file_manifest}
    content_type_map = {uf.get("name", "").lower(): uf.get("content_type", "unknown") for uf in uploaded_files}
    data_types = {"csv", "spreadsheet", "excel"}

    for node in plan_nodes:
        if node.get("agent") != "RetrieverAgent":
            continue
        combined = (node.get("agent_prompt", "") + " " + node.get("description", "")).lower()
        for fname in uploaded_names:
            if fname and fname in combined:
                matched_ct = content_type_map.get(fname)
                if matched_ct and matched_ct in data_types:
                    node["agent"] = "CoderAgent"
                else:
                    node["agent"] = "ThinkerAgent"
                break

    assert plan_nodes[0]["agent"] == "CoderAgent", f"CSV task should use CoderAgent, got {plan_nodes[0]['agent']}"
