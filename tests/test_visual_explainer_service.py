"""Tests for Visual Explainer service (generate_html, architecture path)."""
import pytest
from core.visual_explainer_service import generate_html


def test_architecture_legacy_single_section():
    """Legacy payload: single section, no variant or flowLabels, still works."""
    content = {
        "sections": [
            {"title": "Backend", "description": "API and services", "items": ["REST API", "WebSocket", "DB"]}
        ]
    }
    html = generate_html("architecture", "Test Diagram", content)
    assert "Test Diagram" in html
    assert "Backend" in html
    assert "API and services" in html
    assert "REST API" in html
    assert "WebSocket" in html
    assert "DB" in html
    assert "class=\"section\"" in html
    assert "class=\"diagram\"" in html
    assert "node-list" in html


def test_architecture_multi_section_with_variants():
    """Multi-section with variant classes and optional label."""
    content = {
        "sections": [
            {"title": "Input", "description": "Sources", "items": ["Slack", "GitHub"], "variant": "hero", "label": "Sources"},
            {"title": "Gateway", "description": "Router", "items": ["HTTP", "WS"], "variant": "accent"},
            {"title": "DB", "description": "Storage", "items": [], "variant": "recessed"},
        ]
    }
    html = generate_html("architecture", "System", content)
    assert "System" in html
    assert "section--hero" in html
    assert "section--accent" in html
    assert "section--recessed" in html
    assert "Sources" in html
    assert "section-label" in html
    assert "Gateway" in html
    assert "DB" in html


def test_architecture_flow_labels():
    """flowLabels between sections render as flow-arrow divs."""
    content = {
        "sections": [
            {"title": "A", "description": "", "items": []},
            {"title": "B", "description": "", "items": []},
        ],
        "flowLabels": ["incoming"],
    }
    html = generate_html("architecture", "Flow", content)
    assert "Flow" in html
    assert "flow-arrow" in html
    assert "incoming" in html


def test_architecture_subtitle():
    """Optional subtitle appears under title."""
    content = {
        "sections": [{"title": "S1", "description": "", "items": []}],
        "subtitle": "High-level overview",
    }
    html = generate_html("architecture", "Title", content)
    assert "subtitle" in html
    assert "High-level overview" in html


def test_architecture_escapes_user_content():
    """User-provided strings are escaped (no raw HTML/script)."""
    content = {
        "sections": [
            {
                "title": "<script>alert(1)</script>",
                "description": "Desc with <b>tags</b>",
                "items": ["Item with \"quotes\"", "& ampersand"],
                "label": "Label <img onerror=1>",
            }
        ],
        "flowLabels": ["Flow <script>"],
    }
    html = generate_html("architecture", "Title & <script>", content)
    assert "&lt;script&gt;" in html or "&lt;script" in html
    assert "<script>" not in html or html.count("<script>") == 0
    assert "&quot;quotes&quot;" in html or "quotes" in html
    assert "&amp;" in html
    assert "&lt;b&gt;" in html or "&lt;b" in html
    assert "onerror" not in html or "&lt;" in html


def test_architecture_sections_as_single_dict_normalized():
    """Backend accepts sections as a single dict and normalizes to list."""
    content = {"sections": {"title": "One", "description": "D", "items": ["a"]}}
    html = generate_html("architecture", "Diagram", content)
    assert "One" in html
    assert "D" in html
    assert "a" in html
