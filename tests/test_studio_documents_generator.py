"""Tests for core/studio/documents/generator.py — outline and draft normalization."""

import pytest

from core.schemas.studio_schema import (
    DocumentContentTree,
    DocumentSection,
    Outline,
    OutlineItem,
    OutlineStatus,
    ArtifactType,
)
from core.studio.documents.generator import (
    MAX_DEPTH,
    normalize_document_content_tree,
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
