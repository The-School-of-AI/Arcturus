"""Tests for core/studio/editing/diff.py — diff computation."""

import copy

from core.studio.editing.diff import compute_revision_diff, summarize_diff_highlights

# === Fixture data ===

def _slides_tree():
    return {
        "deck_title": "Test Deck",
        "slides": [
            {"id": "s1", "slide_type": "title", "title": "Opening", "elements": [], "speaker_notes": "Welcome."},
            {"id": "s2", "slide_type": "content", "title": "Main Point", "elements": [
                {"id": "e1", "type": "body", "content": "Details here."},
            ], "speaker_notes": "Talk about details."},
            {"id": "s3", "slide_type": "content", "title": "Evidence", "elements": [], "speaker_notes": "Data."},
        ],
    }


def _doc_tree():
    return {
        "doc_title": "Test Report",
        "doc_type": "report",
        "abstract": "Summary.",
        "sections": [
            {"id": "sec1", "heading": "Introduction", "level": 1, "content": "Intro.", "subsections": [], "citations": []},
            {"id": "sec2", "heading": "Conclusion", "level": 1, "content": "End.", "subsections": [], "citations": []},
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


# === Tests ===

class TestDiffIdentical:
    def test_diff_identical_trees(self):
        tree = _slides_tree()
        diff = compute_revision_diff("slides", tree, copy.deepcopy(tree))
        assert diff["stats"]["paths_changed"] == 0
        assert diff["highlights"] == []
        assert diff["paths"] == []


class TestDiffSlides:
    def test_diff_slide_title_change(self):
        before = _slides_tree()
        after = copy.deepcopy(before)
        after["slides"][1]["title"] = "Updated Main Point"

        diff = compute_revision_diff("slides", before, after)
        assert diff["stats"]["paths_changed"] >= 1
        assert diff["stats"]["slides_changed"] == 1
        assert any(h["kind"] == "slide" and h["slide_index"] == 2 for h in diff["highlights"])

    def test_diff_slide_element_added(self):
        before = _slides_tree()
        after = copy.deepcopy(before)
        after["slides"][0]["elements"].append({"id": "e99", "type": "body", "content": "New"})

        diff = compute_revision_diff("slides", before, after)
        assert diff["stats"]["paths_changed"] >= 1
        assert diff["stats"]["slides_changed"] >= 1


class TestDiffDocument:
    def test_diff_doc_section_content_change(self):
        before = _doc_tree()
        after = copy.deepcopy(before)
        after["sections"][0]["content"] = "Updated introduction."

        diff = compute_revision_diff("document", before, after)
        assert diff["stats"]["paths_changed"] >= 1
        assert diff["stats"]["sections_changed"] >= 1
        assert any(h["kind"] == "section" for h in diff["highlights"])

    def test_diff_doc_subsection_added(self):
        before = _doc_tree()
        after = copy.deepcopy(before)
        after["sections"][0]["subsections"].append({
            "id": "sec1a", "heading": "New Sub", "level": 2, "content": "Added.", "subsections": [], "citations": [],
        })

        diff = compute_revision_diff("document", before, after)
        assert diff["stats"]["paths_changed"] >= 1


class TestDiffSheet:
    def test_diff_sheet_tab_row_change(self):
        before = _sheet_tree()
        after = copy.deepcopy(before)
        after["tabs"][0]["rows"][0][1] = 6000

        diff = compute_revision_diff("sheet", before, after)
        assert diff["stats"]["paths_changed"] >= 1
        assert diff["stats"]["tabs_changed"] >= 1
        assert any(h["kind"] == "tab" for h in diff["highlights"])

    def test_diff_sheet_formula_added(self):
        before = _sheet_tree()
        after = copy.deepcopy(before)
        after["tabs"][0]["formulas"]["B2"] = "=B1*1.1"

        diff = compute_revision_diff("sheet", before, after)
        assert diff["stats"]["paths_changed"] >= 1


class TestDiffBounds:
    def test_diff_max_paths_bounded(self):
        before = _slides_tree()
        after = copy.deepcopy(before)
        # Change every field to trigger many paths
        after["deck_title"] = "Changed"
        for i, s in enumerate(after["slides"]):
            s["title"] = f"Changed {i}"
            s["speaker_notes"] = f"Changed notes {i}"

        diff = compute_revision_diff("slides", before, after, max_paths=3)
        assert len(diff["paths"]) <= 3

    def test_diff_stats_correct(self):
        before = _slides_tree()
        after = copy.deepcopy(before)
        after["slides"][0]["title"] = "New Opening"
        after["slides"][2]["title"] = "New Evidence"

        diff = compute_revision_diff("slides", before, after)
        assert diff["stats"]["slides_changed"] == 2
        assert diff["stats"]["paths_changed"] == 2


class TestDiffHighlights:
    def test_diff_highlights_readable(self):
        before = _slides_tree()
        after = copy.deepcopy(before)
        after["slides"][1]["title"] = "Changed Title"

        diff = compute_revision_diff("slides", before, after)
        summary = summarize_diff_highlights(diff["highlights"])
        assert "Slide 2" in summary
        assert isinstance(summary, str)
        assert len(summary) > 0
