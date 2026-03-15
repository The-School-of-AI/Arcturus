"""Tests for core/studio/editing/patch_apply.py — patch engine."""

import copy

import pytest

from core.studio.editing.patch_apply import _parse_path, apply_patch_to_content_tree


# === Fixture data ===

def _slides_tree():
    return {
        "deck_title": "Test Deck",
        "subtitle": "Subtitle",
        "slides": [
            {
                "id": "s1",
                "slide_type": "title",
                "title": "Opening",
                "elements": [
                    {"id": "e1", "type": "title", "content": "Welcome"},
                    {"id": "e2", "type": "subtitle", "content": "Intro"},
                ],
                "speaker_notes": "Open with a greeting.",
            },
            {
                "id": "s2",
                "slide_type": "content",
                "title": "Main Point",
                "elements": [
                    {"id": "e3", "type": "body", "content": "Details here."},
                ],
                "speaker_notes": "Cover the main details.",
            },
            {
                "id": "s3",
                "slide_type": "content",
                "title": "Evidence",
                "elements": [
                    {"id": "e4", "type": "body", "content": "Data supports this."},
                ],
                "speaker_notes": "Present supporting evidence.",
            },
            {
                "id": "s4",
                "slide_type": "content",
                "title": "Analysis",
                "elements": [
                    {"id": "e5", "type": "body", "content": "Deeper analysis here."},
                ],
                "speaker_notes": "Analyze the data in detail.",
            },
            {
                "id": "s5",
                "slide_type": "content",
                "title": "Implications",
                "elements": [
                    {"id": "e6", "type": "body", "content": "What this means."},
                ],
                "speaker_notes": "Explain the implications.",
            },
            {
                "id": "s6",
                "slide_type": "content",
                "title": "Recommendations",
                "elements": [
                    {"id": "e7", "type": "body", "content": "Our recommendations."},
                ],
                "speaker_notes": "Present recommendations.",
            },
            {
                "id": "s7",
                "slide_type": "content",
                "title": "Timeline",
                "elements": [
                    {"id": "e8", "type": "body", "content": "Project timeline."},
                ],
                "speaker_notes": "Walk through the timeline.",
            },
            {
                "id": "s8",
                "slide_type": "title",
                "title": "Thank You",
                "elements": [
                    {"id": "e9", "type": "title", "content": "Thanks"},
                ],
                "speaker_notes": "Close the presentation.",
            },
        ],
    }


def _doc_tree():
    return {
        "doc_title": "Test Report",
        "doc_type": "report",
        "abstract": "Summary here.",
        "sections": [
            {
                "id": "sec1",
                "heading": "Introduction",
                "level": 1,
                "content": "Intro content paragraph.",
                "subsections": [
                    {
                        "id": "sec1a",
                        "heading": "Background",
                        "level": 2,
                        "content": "Background info.",
                        "subsections": [],
                        "citations": [],
                    }
                ],
                "citations": [],
            },
            {
                "id": "sec2",
                "heading": "Conclusion",
                "level": 1,
                "content": "Closing remarks.",
                "subsections": [],
                "citations": [],
            },
        ],
        "bibliography": [],
    }


def _sheet_tree():
    return {
        "workbook_title": "Financial Model",
        "tabs": [
            {
                "id": "tab1",
                "name": "Revenue",
                "headers": ["Month", "MRR"],
                "rows": [["Jan", 5000], ["Feb", 5500]],
                "formulas": {},
                "column_widths": [120, 100],
            }
        ],
    }


# === SET Tests ===

class TestSetOp:
    def test_set_updates_slide_title(self):
        tree = _slides_tree()
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [{"op": "SET", "path": "title", "value": "Updated Main Point"}],
            "summary": "Update slide 2 title",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        assert result["slides"][1]["title"] == "Updated Main Point"
        assert len(warnings) == 0

    def test_set_idempotent(self):
        tree = _slides_tree()
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [{"op": "SET", "path": "title", "value": "Main Point"}],
            "summary": "No-op: same title",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        assert result["slides"][1]["title"] == "Main Point"
        assert any("no-op" in w.lower() for w in warnings)


# === INSERT_AFTER Tests ===

class TestInsertAfterOp:
    def test_insert_after_adds_element(self):
        tree = _slides_tree()
        new_element = {"id": "e99", "type": "body", "content": "New paragraph"}
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [{"op": "INSERT_AFTER", "path": "elements", "item": new_element, "id_key": "id"}],
            "summary": "Add element to slide 2",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        slide2_elements = result["slides"][1]["elements"]
        assert any(e.get("id") == "e99" for e in slide2_elements)
        assert len(warnings) == 0

    def test_insert_after_idempotent(self):
        tree = _slides_tree()
        existing_element = {"id": "e3", "type": "body", "content": "Details here."}
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [{"op": "INSERT_AFTER", "path": "elements", "item": existing_element, "id_key": "id"}],
            "summary": "No-op: element already exists",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        assert any("no-op" in w.lower() for w in warnings)


# === DELETE Tests ===

class TestDeleteOp:
    def test_delete_removes_element(self):
        tree = _slides_tree()
        # Slide 2 has 1 element at elements[0], add another first
        tree["slides"][1]["elements"].append(
            {"id": "e-extra", "type": "body", "content": "Extra content."}
        )
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [{"op": "DELETE", "path": "elements[1]"}],
            "summary": "Delete second element from slide 2",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        assert len(result["slides"][1]["elements"]) == 1
        assert len(warnings) == 0

    def test_delete_missing_path_no_op(self):
        tree = _slides_tree()
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [{"op": "DELETE", "path": "elements[99]"}],
            "summary": "Delete non-existent element",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        assert any("no-op" in w.lower() for w in warnings)


# === Validation & Error Tests ===

class TestValidation:
    def test_invalid_path_raises_value_error(self):
        tree = _slides_tree()
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [{"op": "SET", "path": "!!!invalid", "value": "x"}],
            "summary": "Bad path",
        }
        with pytest.raises(ValueError):
            apply_patch_to_content_tree("slides", tree, patch)

    def test_schema_breaking_patch_rejected(self):
        tree = _slides_tree()
        # Delete deck_title — required field
        patch = {
            "target": {"kind": "slide_index", "index": 1},
            "ops": [{"op": "SET", "path": "slide_type", "value": None}],
            "summary": "Break schema",
        }
        # slide_type is required in Slide model, setting to None may break validation
        # The tree-level validation should still pass since it validates the whole tree
        # Let's try something that actually breaks the schema
        tree_bad = _slides_tree()
        patch_bad = {
            "target": {"kind": "slide_index", "index": 1},
            "ops": [{"op": "DELETE", "path": "id"}],
            "summary": "Remove required id field",
        }
        with pytest.raises(ValueError, match="invalid content tree"):
            apply_patch_to_content_tree("slides", tree_bad, patch_bad)


# === Normalization Tests ===

class TestNormalization:
    def test_patch_validates_after_apply(self):
        tree = _slides_tree()
        patch = {
            "target": {"kind": "slide_id", "id": "s2"},
            "ops": [{"op": "SET", "path": "title", "value": "Validated Title"}],
            "summary": "Simple valid patch",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        # Should succeed without raising
        assert result["slides"][1]["title"] == "Validated Title"

    def test_patch_runs_slide_normalization(self):
        tree = _slides_tree()
        # Set a speaker note to empty — repair_speaker_notes should fix it
        patch = {
            "target": {"kind": "slide_index", "index": 3},
            "ops": [{"op": "SET", "path": "speaker_notes", "value": ""}],
            "summary": "Clear notes to trigger repair",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        # After normalization, the empty note should be repaired
        assert result["slides"][2]["speaker_notes"] != ""

    def test_patch_runs_doc_normalization(self):
        tree = _doc_tree()
        patch = {
            "target": {"kind": "section_id", "id": "sec1"},
            "ops": [{"op": "SET", "path": "content", "value": "Updated introduction content."}],
            "summary": "Update intro",
        }
        result, warnings = apply_patch_to_content_tree("document", tree, patch)
        # After normalization, provenance_slots should be in metadata
        assert "provenance_slots" in result.get("metadata", {})

    def test_patch_runs_sheet_normalization(self):
        tree = _sheet_tree()
        patch = {
            "target": {"kind": "tab_name", "name": "Revenue"},
            "ops": [{"op": "SET", "path": "headers", "value": ["Month", "MRR", "Growth"]}],
            "summary": "Add Growth column header",
        }
        result, warnings = apply_patch_to_content_tree("sheet", tree, patch)
        # After normalization, row widths should be aligned to header count
        tab = result["tabs"][0]
        assert len(tab["column_widths"]) == len(tab["headers"])


# === Multi-op and safety tests ===

class TestMultiOpAndSafety:
    def test_multi_op_patch_applies_in_order(self):
        tree = _slides_tree()
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [
                {"op": "SET", "path": "title", "value": "Step 1"},
                {"op": "SET", "path": "title", "value": "Step 2"},
            ],
            "summary": "Two sequential SETs",
        }
        result, warnings = apply_patch_to_content_tree("slides", tree, patch)
        # Second SET should win
        assert result["slides"][1]["title"] == "Step 2"

    def test_deep_copy_preserves_original(self):
        tree = _slides_tree()
        original = copy.deepcopy(tree)
        patch = {
            "target": {"kind": "slide_index", "index": 2},
            "ops": [{"op": "SET", "path": "title", "value": "Changed"}],
            "summary": "Modify slide 2",
        }
        apply_patch_to_content_tree("slides", tree, patch)
        # Original should be unchanged
        assert tree == original


# === JSONPath filter detection ===

class TestJsonPathFilterDetection:
    def test_parse_path_rejects_filter_expression(self):
        with pytest.raises(ValueError, match="JSONPath filter expressions are not supported"):
            _parse_path("elements[?(@.id == 'e7')]")

    def test_parse_path_rejects_filter_with_suffix(self):
        with pytest.raises(ValueError, match="JSONPath filter expressions are not supported"):
            _parse_path('elements[?(@.id == "e7")].content')

    def test_parse_path_valid_paths_still_work(self):
        # Smoke check: valid paths are unaffected
        assert _parse_path("title") == [("title", None)]
        assert _parse_path("elements[0].content") == [("elements", 0), ("content", None)]
