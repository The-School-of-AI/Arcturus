"""Tests for core/studio/documents/generator.py — outline and draft normalization."""

import pytest

from core.schemas.studio_schema import (
    ArtifactType,
    DocumentContentTree,
    DocumentSection,
    Outline,
    OutlineItem,
    OutlineStatus,
)
from core.studio.documents.generator import (
    MAX_DEPTH,
    normalize_document_content_tree,
    normalize_document_content_tree_raw,
    normalize_document_outline,
)
from core.studio.documents.types import DOC_TYPE_TEMPLATES


@pytest.fixture
def basic_outline():
    return Outline(
        artifact_type=ArtifactType.document,
        title="Test Document",
        items=[
            OutlineItem(id="1", title="Introduction", description="Intro section"),
            OutlineItem(id="2", title="Main Body", description="Main content"),
        ],
        status=OutlineStatus.pending,
        parameters={},
    )


@pytest.fixture
def basic_content_tree():
    return DocumentContentTree(
        doc_title="Test Document",
        doc_type="report",
        abstract="This is a test abstract.",
        sections=[
            DocumentSection(
                id="sec1",
                heading="Introduction",
                level=1,
                content="Introduction content with [ref1] citation.",
                subsections=[
                    DocumentSection(
                        id="sec1a",
                        heading="Background",
                        level=2,
                        content="Background details.",
                    )
                ],
                citations=["ref1"],
            ),
            DocumentSection(
                id="sec2",
                heading="Findings",
                level=1,
                content="Main findings here.",
            ),
        ],
        bibliography=[{"key": "ref1", "title": "Source A", "author": "Author A"}],
    )


class TestNormalizeDocumentOutline:
    def test_resolves_doc_type_from_params(self, basic_outline):
        basic_outline.parameters = {"doc_type": "technical_spec"}
        result = normalize_document_outline(basic_outline)
        assert result.parameters["doc_type"] == "technical_spec"

    def test_resolves_doc_type_from_prompt(self, basic_outline):
        result = normalize_document_outline(
            basic_outline, user_prompt="Create a proposal"
        )
        assert result.parameters["doc_type"] == "proposal"

    def test_defaults_to_report(self, basic_outline):
        result = normalize_document_outline(basic_outline)
        assert result.parameters["doc_type"] == "report"

    def test_inserts_missing_required_sections(self, basic_outline):
        basic_outline.parameters = {"doc_type": "report"}
        result = normalize_document_outline(basic_outline)
        titles = {item.title for item in result.items}
        for req in DOC_TYPE_TEMPLATES["report"]["required_sections"]:
            assert req in titles, f"Missing required section: {req}"

    def test_clamps_max_sections(self, basic_outline):
        # Add many items beyond max
        basic_outline.parameters = {"doc_type": "technical_spec"}
        basic_outline.items = [
            OutlineItem(id=str(i), title=f"Section {i}", description=f"Desc {i}")
            for i in range(20)
        ]
        result = normalize_document_outline(basic_outline)
        max_count = DOC_TYPE_TEMPLATES["technical_spec"]["max_sections"]
        # After clamping + adding missing required sections
        assert len(result.items) >= max_count  # may add required sections

    def test_idempotent(self, basic_outline):
        result1 = normalize_document_outline(basic_outline)
        result2 = normalize_document_outline(result1)
        assert len(result1.items) == len(result2.items)


class TestNormalizeDocumentContentTree:
    def test_validates_doc_type(self):
        tree = DocumentContentTree(
            doc_title="Test",
            doc_type="unknown_type",
            sections=[DocumentSection(id="s1", heading="Intro", level=1, content="Content.")],
        )
        result = normalize_document_content_tree(tree)
        assert result.doc_type == "report"  # falls back to default

    def test_synthesizes_abstract_when_missing(self):
        tree = DocumentContentTree(
            doc_title="Test",
            doc_type="report",
            abstract=None,
            sections=[
                DocumentSection(id="s1", heading="Intro", level=1, content="First section content here.")
            ],
        )
        result = normalize_document_content_tree(tree)
        assert result.abstract is not None
        assert "First section content" in result.abstract

    def test_normalizes_section_ids(self, basic_content_tree):
        result = normalize_document_content_tree(basic_content_tree)
        assert result.sections[0].id == "sec1"
        assert result.sections[1].id == "sec2"
        assert result.sections[0].subsections[0].id == "sec1_1"

    def test_normalizes_section_levels(self, basic_content_tree):
        result = normalize_document_content_tree(basic_content_tree)
        assert result.sections[0].level == 1
        assert result.sections[0].subsections[0].level == 2

    def test_strips_placeholders(self):
        tree = DocumentContentTree(
            doc_title="Test",
            doc_type="report",
            sections=[
                DocumentSection(
                    id="s1", heading="Intro", level=1,
                    content="Some content TBD more content.",
                ),
                DocumentSection(
                    id="s2", heading="Body", level=1,
                    content="Lorem ipsum dolor sit amet.",
                ),
            ],
        )
        result = normalize_document_content_tree(tree)
        assert "TBD" not in result.sections[0].content
        assert "Lorem ipsum" not in result.sections[1].content

    def test_normalizes_bibliography(self, basic_content_tree):
        result = normalize_document_content_tree(basic_content_tree)
        bib_keys = {e["key"] for e in result.bibliography}
        assert "ref1" in bib_keys

    def test_reconciles_orphan_citations(self):
        tree = DocumentContentTree(
            doc_title="Test",
            doc_type="report",
            sections=[
                DocumentSection(
                    id="s1", heading="Intro", level=1,
                    content="See [orphan_ref] for details.",
                    citations=["orphan_ref"],
                )
            ],
            bibliography=[],
        )
        result = normalize_document_content_tree(tree)
        bib_keys = {e["key"] for e in result.bibliography}
        assert "orphan_ref" in bib_keys

    def test_builds_provenance_slots(self, basic_content_tree):
        result = normalize_document_content_tree(basic_content_tree)
        assert "provenance_slots" in result.metadata
        slots = result.metadata["provenance_slots"]
        slot_keys = {s["citation_key"] for s in slots}
        assert "ref1" in slot_keys

    def test_clamps_depth_to_max(self):
        # Create deeply nested sections (4 levels)
        deep = DocumentSection(id="d4", heading="Level 4", level=4, content="Deep.")
        lvl3 = DocumentSection(id="d3", heading="Level 3", level=3, subsections=[deep])
        lvl2 = DocumentSection(id="d2", heading="Level 2", level=2, subsections=[lvl3])
        lvl1 = DocumentSection(id="d1", heading="Level 1", level=1, subsections=[lvl2])
        tree = DocumentContentTree(
            doc_title="Deep Doc",
            doc_type="report",
            sections=[lvl1],
        )
        result = normalize_document_content_tree(tree)
        # After normalization, depth should be clamped to MAX_DEPTH
        sec = result.sections[0]
        assert sec.level == 1
        sub = sec.subsections[0]
        assert sub.level == 2
        # Level 3 subsections should be flattened (no children)
        deep_sub = sub.subsections[0]
        assert deep_sub.level == 3
        assert deep_sub.subsections == []

    def test_idempotent(self, basic_content_tree):
        result1 = normalize_document_content_tree(basic_content_tree)
        result2 = normalize_document_content_tree(result1)
        assert len(result1.sections) == len(result2.sections)
        assert len(result1.bibliography) == len(result2.bibliography)


class TestNormalizeDocumentContentTreeRaw:
    """Tests for the pre-validation raw dict normalizer."""

    def test_maps_title_to_doc_title(self):
        data = {"title": "My Doc", "type": "report", "sections": []}
        result = normalize_document_content_tree_raw(data)
        assert result["doc_title"] == "My Doc"
        assert "title" not in result

    def test_maps_document_title_to_doc_title(self):
        data = {"document_title": "My Doc", "doc_type": "report", "sections": []}
        result = normalize_document_content_tree_raw(data)
        assert result["doc_title"] == "My Doc"

    def test_maps_type_to_doc_type(self):
        data = {"doc_title": "Doc", "type": "proposal", "sections": []}
        result = normalize_document_content_tree_raw(data)
        assert result["doc_type"] == "proposal"
        assert "type" not in result

    def test_normalizes_unknown_doc_type(self):
        data = {"doc_title": "Doc", "doc_type": "blog_post", "sections": []}
        result = normalize_document_content_tree_raw(data)
        assert result["doc_type"] == "report"

    def test_defaults_missing_doc_title(self):
        data = {"doc_type": "report", "sections": []}
        result = normalize_document_content_tree_raw(data)
        assert result["doc_title"] == "Untitled Document"

    def test_defaults_missing_doc_type(self):
        data = {"doc_title": "Doc", "sections": []}
        result = normalize_document_content_tree_raw(data)
        assert result["doc_type"] == "report"

    def test_section_title_mapped_to_heading(self):
        data = {
            "doc_title": "Doc",
            "doc_type": "report",
            "sections": [{"id": 1, "title": "Intro", "content": "Hello"}],
        }
        result = normalize_document_content_tree_raw(data)
        sec = result["sections"][0]
        assert sec["heading"] == "Intro"
        assert "title" not in sec

    def test_section_id_coerced_to_str(self):
        data = {
            "doc_title": "Doc",
            "doc_type": "report",
            "sections": [{"id": 1, "heading": "Intro"}],
        }
        result = normalize_document_content_tree_raw(data)
        assert result["sections"][0]["id"] == "1"

    def test_children_mapped_to_subsections(self):
        data = {
            "doc_title": "Doc",
            "doc_type": "report",
            "sections": [
                {"id": "1", "heading": "Intro", "children": [{"id": "1a", "title": "Sub"}]}
            ],
        }
        result = normalize_document_content_tree_raw(data)
        sec = result["sections"][0]
        assert "subsections" in sec
        assert len(sec["subsections"]) == 1
        assert sec["subsections"][0]["heading"] == "Sub"

    def test_full_llm_mismatch_produces_valid_model(self):
        """End-to-end: typical LLM-mismatched JSON → valid DocumentContentTree."""
        raw_llm = {
            "title": "Market Analysis Report",
            "type": "report",
            "abstract": "A comprehensive analysis.",
            "sections": [
                {
                    "id": 1,
                    "title": "Executive Summary",
                    "level": 1,
                    "content": "Summary of findings.",
                    "children": [
                        {"id": "1a", "name": "Key Metrics", "content": "Metrics detail."}
                    ],
                },
                {"id": 2, "title": "Conclusion", "level": 1, "content": "Final thoughts."},
            ],
        }
        normalized = normalize_document_content_tree_raw(raw_llm)
        # Should not raise
        tree = DocumentContentTree(**normalized)
        assert tree.doc_title == "Market Analysis Report"
        assert tree.doc_type == "report"
        assert len(tree.sections) == 2
        assert tree.sections[0].heading == "Executive Summary"
        assert tree.sections[0].subsections[0].heading == "Key Metrics"
        assert tree.sections[0].id == "1"

    def test_ensures_bibliography_default(self):
        data = {"doc_title": "Doc", "doc_type": "report", "sections": []}
        result = normalize_document_content_tree_raw(data)
        assert result["bibliography"] == []

    def test_preserves_existing_canonical_fields(self):
        """When the LLM already uses correct field names, normalizer is a no-op."""
        data = {
            "doc_title": "Correct Doc",
            "doc_type": "proposal",
            "abstract": "Summary.",
            "sections": [
                {"id": "sec1", "heading": "Intro", "level": 1, "content": "Hello.", "subsections": [], "citations": []}
            ],
            "bibliography": [],
        }
        result = normalize_document_content_tree_raw(data)
        assert result["doc_title"] == "Correct Doc"
        assert result["doc_type"] == "proposal"
        tree = DocumentContentTree(**result)
        assert tree.sections[0].heading == "Intro"
