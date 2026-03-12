"""Tests for core/studio/editing/planner.py — target map and patch planning."""

import asyncio
import json

import pytest

from core.studio.editing.planner import build_target_map, plan_patch


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# === Fixture data ===

def _slides_tree():
    return {
        "deck_title": "Test Deck",
        "slides": [
            {"id": "s1", "slide_type": "title", "title": "Opening", "elements": [
                {"id": "e1", "type": "title", "content": "Welcome"},
            ]},
            {"id": "s2", "slide_type": "content", "title": "Main", "elements": [
                {"id": "e2", "type": "body", "content": "Details"},
            ]},
        ],
    }


def _doc_tree():
    return {
        "doc_title": "Report",
        "doc_type": "report",
        "abstract": "Summary.",
        "sections": [
            {"id": "sec1", "heading": "Intro", "level": 1, "content": "...", "subsections": [
                {"id": "sec1a", "heading": "Background", "level": 2, "content": "...", "subsections": [], "citations": []},
            ], "citations": []},
        ],
        "bibliography": [],
    }


def _sheet_tree():
    return {
        "workbook_title": "Financial Model",
        "tabs": [
            {"id": "tab1", "name": "Revenue", "headers": ["Month", "MRR"], "rows": [["Jan", 5000]], "formulas": {}, "column_widths": [120, 100]},
        ],
    }


# === Target map tests ===

class TestBuildTargetMap:
    def test_build_target_map_slides(self):
        target_map = build_target_map("slides", _slides_tree())
        assert "Deck: Test Deck" in target_map
        assert "Slide 1" in target_map
        assert "Slide 2" in target_map
        assert "s1" in target_map
        assert "e1" in target_map

    def test_build_target_map_document(self):
        target_map = build_target_map("document", _doc_tree())
        assert "Document: Report" in target_map
        assert "sec1" in target_map
        assert "Intro" in target_map
        assert "Background" in target_map

    def test_build_target_map_sheet(self):
        target_map = build_target_map("sheet", _sheet_tree())
        assert "Workbook: Financial Model" in target_map
        assert "Revenue" in target_map
        assert "Month" in target_map


# === Plan patch tests (require mocking) ===

@pytest.fixture(autouse=True)
def _patch_model_manager(monkeypatch):
    """Prevent ModelManager.__init__ from calling real API clients."""
    def noop_init(self, model_name=None, provider=None, role=None):
        self.model_type = "gemini"
        self.client = None
    monkeypatch.setattr("core.model_manager.ModelManager.__init__", noop_init)


class TestPlanPatch:
    def test_plan_patch_returns_valid_patch(self, monkeypatch):
        valid_patch = json.dumps({
            "artifact_type": "slides",
            "target": {"kind": "slide_index", "index": 1},
            "ops": [{"op": "SET", "path": "title", "value": "New Title"}],
            "summary": "Update title",
        })

        async def fake_generate(self, prompt):
            return valid_patch
        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(plan_patch("slides", "Change the title", _slides_tree()))
        assert result["artifact_type"] == "slides"
        assert result["ops"][0]["op"] == "SET"

    def test_plan_patch_invalid_json_raises(self, monkeypatch):
        async def fake_generate(self, prompt):
            return "not json at all, no braces anywhere"
        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        with pytest.raises(ValueError, match="Failed to plan patch"):
            _run(plan_patch("slides", "Do something", _slides_tree()))

    def test_plan_patch_invalid_schema_raises(self, monkeypatch):
        async def fake_generate(self, prompt):
            # Valid JSON but missing required 'ops' field
            return json.dumps({"artifact_type": "slides", "target": {}, "summary": "x"})
        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        with pytest.raises(ValueError, match="Failed to plan patch"):
            _run(plan_patch("slides", "Do something", _slides_tree()))

    def test_plan_patch_canonicalizes_filter_path(self, monkeypatch):
        """LLM returns a filter-path like elements[?(@.id == "e1")].content —
        plan_patch should auto-canonicalize to slide_element target with path "content"."""
        filter_patch = json.dumps({
            "artifact_type": "slides",
            "target": {"kind": "slide_index", "index": 1},
            "ops": [{"op": "SET", "path": 'elements[?(@.id == "e1")].content', "value": "Updated"}],
            "summary": "Update element e1 content",
        })

        async def fake_generate(self, prompt):
            return filter_patch
        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(plan_patch("slides", "Update e1", _slides_tree()))
        assert result["target"]["kind"] == "slide_element"
        assert result["target"]["element_id"] == "e1"
        assert result["ops"][0]["path"] == "content"

    def test_plan_patch_canonicalizes_hyphenated_element_id(self, monkeypatch):
        """Element IDs like filler-e-1 (with hyphens) should also be canonicalized."""
        tree = {
            "deck_title": "Test Deck",
            "slides": [
                {"id": "s1", "slide_type": "title", "title": "Opening", "elements": [
                    {"id": "filler-e-1", "type": "body", "content": "Filler"},
                ]},
                {"id": "s2", "slide_type": "content", "title": "Main", "elements": [
                    {"id": "e2", "type": "body", "content": "Details"},
                ]},
            ],
        }
        filter_patch = json.dumps({
            "artifact_type": "slides",
            "target": {"kind": "slide_index", "index": 1},
            "ops": [{"op": "SET", "path": 'elements[?(@.id == "filler-e-1")].content', "value": "Updated"}],
            "summary": "Update filler element",
        })

        async def fake_generate(self, prompt):
            return filter_patch
        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(plan_patch("slides", "Update filler", tree))
        assert result["target"]["kind"] == "slide_element"
        assert result["target"]["element_id"] == "filler-e-1"
        assert result["ops"][0]["path"] == "content"

    def test_plan_patch_mixed_filter_triggers_repair(self, monkeypatch):
        """LLM first returns mixed filter + non-filter paths (invalid) —
        retry should produce a valid patch."""
        bad_patch = json.dumps({
            "artifact_type": "slides",
            "target": {"kind": "slide_index", "index": 1},
            "ops": [
                {"op": "SET", "path": 'elements[?(@.id == "e1")].content', "value": "X"},
                {"op": "SET", "path": "title", "value": "New Title"},
            ],
            "summary": "Mixed paths",
        })
        good_patch = json.dumps({
            "artifact_type": "slides",
            "target": {"kind": "slide_index", "index": 1},
            "ops": [{"op": "SET", "path": "title", "value": "Repaired Title"}],
            "summary": "Fixed patch",
        })
        call_count = 0

        async def fake_generate(self, prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return bad_patch
            return good_patch
        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(plan_patch("slides", "Fix title", _slides_tree()))
        assert result["ops"][0]["value"] == "Repaired Title"
        assert call_count == 2  # repair prompt was invoked

    def test_plan_patch_unparseable_path_triggers_repair(self, monkeypatch):
        """LLM returns a completely invalid path — repair fires."""
        bad_patch = json.dumps({
            "artifact_type": "slides",
            "target": {"kind": "slide_index", "index": 1},
            "ops": [{"op": "SET", "path": "!!!garbage", "value": "X"}],
            "summary": "Bad path",
        })
        good_patch = json.dumps({
            "artifact_type": "slides",
            "target": {"kind": "slide_index", "index": 1},
            "ops": [{"op": "SET", "path": "title", "value": "Fixed"}],
            "summary": "Repaired",
        })
        call_count = 0

        async def fake_generate(self, prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return bad_patch
            return good_patch
        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(plan_patch("slides", "Fix it", _slides_tree()))
        assert result["ops"][0]["value"] == "Fixed"
        assert call_count == 2
