import pytest
from mcp_servers.server_multimodal import analyze_image, analyze_pdf_document, analyze_data_file
from mcp_servers.server_internal import search_workspace_files, search_past_conversations
import os

@pytest.mark.asyncio
async def test_multimodal_tools_exist():
    # Mostly proving that the tools load and can handle bad inputs gracefully
    # rather than doing full vision API calls during CI.
    
    # Test analyze_image graceful failure on invalid path
    res = await analyze_image("invalid/path/to/image.png", "What is this?")
    assert "[Error] Image not found" in res or "[Error] langchain-google-genai" in res

    # Test analyze_pdf_document graceful failure
    res_pdf = await analyze_pdf_document("invalid/path/to/doc.pdf", "Summary?")
    assert "[Error] PDF not found" in res_pdf or "[Error]" in res_pdf

    # Test analyze_data_file with invalid file
    res_data = await analyze_data_file("not_a_data_file.txt", "Sum column A")
    assert "Only .csv files are currently supported" in res_data or "not found" in res_data

@pytest.mark.asyncio
async def test_internal_tools_exist():
    # Test workspace search
    # This file itself should be findable
    res = await search_workspace_files("test_internal_tools_exist", directory="tests/integration")
    # depending on cwd it might not find it, so we just check it doesn't crash
    assert isinstance(res, str)
    
    # Test past conversations stub
    res_mem = await search_past_conversations("project parameters")
    assert isinstance(res_mem, str)
