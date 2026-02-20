"""Tests for core/schemas/studio_schema.py — unit + contract tests."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from core.schemas.studio_schema import (
    Artifact,
    ArtifactType,
    Asset,
    AssetKind,
    DocumentContentTree,
    DocumentSection,
    Outline,
    OutlineItem,
    OutlineStatus,
    Revision,
    SheetContentTree,
    SheetTab,
    Slide,
    SlideElement,
    SlidesContentTree,
    validate_artifact,
    validate_content_tree,
)


# === Fixtures ===

@pytest.fixture
def sample_slides_tree():
    return SlidesContentTree(
        deck_title="Test Deck",
        subtitle="A subtitle",
        slides=[
            Slide(
                id="s1",
                slide_type="title",
                title="Opening",
                elements=[
                    SlideElement(id="e1", type="title", content="Hello"),
                    SlideElement(id="e2", type="subtitle", content="World"),
                ],
                speaker_notes="Introduce yourself.",
            ),
            Slide(
                id="s2",
                slide_type="content",
                title="Main Point",
                elements=[
                    SlideElement(id="e3", type="body", content="Details here."),
                ],
            ),
        ],
        metadata={"audience": "investors"},
    )


@pytest.fixture
def sample_document_tree():
    return DocumentContentTree(
        doc_title="Test Spec",
        doc_type="technical_spec",
        abstract="An abstract.",
        sections=[
            DocumentSection(
                id="sec1",
                heading="Introduction",
                level=1,
                content="Intro content.",
                subsections=[
                    DocumentSection(
                        id="sec1a",
                        heading="Background",
                        level=2,
                        content="Background content.",
                    )
                ],
                citations=["ref1"],
            )
        ],
        bibliography=[{"key": "ref1", "title": "A Book", "author": "Author"}],
        metadata={"tone": "formal"},
    )


@pytest.fixture
def sample_sheet_tree():
    return SheetContentTree(
        workbook_title="Financial Model",
        tabs=[
            SheetTab(
                id="tab1",
                name="Revenue",
                headers=["Month", "Users", "MRR"],
                rows=[["Jan", 100, 5000], ["Feb", 110, 5500]],
                formulas={"C3": "=C2*1.1"},
                column_widths=[120, 80, 100],
            )
        ],
        assumptions="10% monthly growth.",
    )


@pytest.fixture
def sample_outline():
    return Outline(
        artifact_type=ArtifactType.slides,
        title="Test Deck",
        items=[
            OutlineItem(
                id="1",
                title="Intro",
                description="Opening slide",
                children=[
                    OutlineItem(id="1.1", title="Hook", description="Attention grabber"),
                ],
            ),
            OutlineItem(id="2", title="Problem", description="Define the problem"),
        ],
        status=OutlineStatus.pending,
        parameters={"slide_count": 10},
    )


@pytest.fixture
def sample_artifact(sample_outline):
    now = datetime.now(timezone.utc)
    return Artifact(
        id="art-001",
        type=ArtifactType.slides,
        title="Test Deck",
        created_at=now,
        updated_at=now,
        outline=sample_outline,
    )


@pytest.fixture
def sample_revision():
    return Revision(
        id="rev-001",
        artifact_id="art-001",
        parent_revision_id=None,
        change_summary="Initial draft",
        content_tree_snapshot={"deck_title": "Test", "slides": []},
        created_at=datetime.now(timezone.utc),
    )


# === Unit Tests: Model Validation ===

class TestSlidesContentTree:
    def test_valid(self, sample_slides_tree):
        assert sample_slides_tree.deck_title == "Test Deck"
        assert len(sample_slides_tree.slides) == 2
        assert sample_slides_tree.slides[0].elements[0].type == "title"

    def test_empty_slides(self):
        tree = SlidesContentTree(deck_title="Empty", slides=[])
        assert tree.slides == []

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            SlidesContentTree(slides=[])  # missing deck_title


class TestDocumentContentTree:
    def test_valid(self, sample_document_tree):
        assert sample_document_tree.doc_title == "Test Spec"
        assert len(sample_document_tree.sections) == 1

    def test_recursive_sections(self):
        tree = DocumentContentTree(
            doc_title="Deep Doc",
            doc_type="report",
            sections=[
                DocumentSection(
                    id="s1",
                    heading="Top",
                    level=1,
                    subsections=[
                        DocumentSection(
                            id="s1a",
                            heading="Mid",
                            level=2,
                            subsections=[
                                DocumentSection(
                                    id="s1a1",
                                    heading="Deep",
                                    level=3,
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        assert tree.sections[0].subsections[0].subsections[0].heading == "Deep"


class TestSheetContentTree:
    def test_valid(self, sample_sheet_tree):
        assert sample_sheet_tree.workbook_title == "Financial Model"
        assert len(sample_sheet_tree.tabs) == 1
        assert sample_sheet_tree.tabs[0].formulas["C3"] == "=C2*1.1"

    def test_column_widths_mismatch(self):
        with pytest.raises(ValidationError, match="column_widths length"):
            SheetTab(
                id="t1",
                name="Bad",
                headers=["A", "B", "C"],
                column_widths=[100, 200],  # 2 widths for 3 headers
            )

    def test_column_widths_empty_ok(self):
        tab = SheetTab(id="t1", name="OK", headers=["A", "B"])
        assert tab.column_widths == []


class TestOutlineModels:
    def test_outline_creation(self, sample_outline):
        assert sample_outline.title == "Test Deck"
        assert len(sample_outline.items) == 2
        assert len(sample_outline.items[0].children) == 1
        assert sample_outline.status == OutlineStatus.pending

    def test_outline_item_defaults(self):
        item = OutlineItem(id="x", title="Test")
        assert item.description is None
        assert item.children == []


class TestArtifactModel:
    def test_creation(self, sample_artifact):
        assert sample_artifact.id == "art-001"
        assert sample_artifact.type == ArtifactType.slides
        assert sample_artifact.outline is not None
        assert sample_artifact.content_tree is None

    def test_defaults(self):
        now = datetime.now(timezone.utc)
        a = Artifact(
            id="a1",
            type=ArtifactType.document,
            title="Minimal",
            created_at=now,
            updated_at=now,
        )
        assert a.schema_version == "1.0"
        assert a.theme_id is None
        assert a.revision_head_id is None
        assert a.outline is None
        assert a.content_tree is None


class TestRevisionModel:
    def test_creation(self, sample_revision):
        assert sample_revision.id == "rev-001"
        assert sample_revision.artifact_id == "art-001"
        assert sample_revision.parent_revision_id is None
        assert sample_revision.change_summary == "Initial draft"


class TestAssetModel:
    def test_creation(self):
        asset = Asset(
            id="asset-1",
            artifact_id="art-001",
            kind=AssetKind.image,
            uri="https://example.com/img.png",
        )
        assert asset.kind == AssetKind.image
        assert asset.metadata == {}


# === Validation Helper Tests ===

class TestValidateContentTree:
    def test_slides(self):
        data = {
            "deck_title": "Test",
            "slides": [{"id": "s1", "slide_type": "title", "elements": []}],
        }
        result = validate_content_tree(ArtifactType.slides, data)
        assert isinstance(result, SlidesContentTree)

    def test_document(self):
        data = {
            "doc_title": "Test",
            "doc_type": "report",
            "sections": [{"id": "s1", "heading": "Intro"}],
        }
        result = validate_content_tree(ArtifactType.document, data)
        assert isinstance(result, DocumentContentTree)

    def test_sheet(self):
        data = {
            "workbook_title": "Test",
            "tabs": [{"id": "t1", "name": "Sheet1"}],
        }
        result = validate_content_tree(ArtifactType.sheet, data)
        assert isinstance(result, SheetContentTree)

    def test_malformed_raises_validation_error(self):
        with pytest.raises(ValidationError):
            validate_content_tree(ArtifactType.slides, {"bad": "data"})

    def test_unknown_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown artifact type"):
            validate_content_tree("nonexistent", {"data": 1})


class TestValidateArtifact:
    def test_valid(self):
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "id": "a1",
            "type": "slides",
            "title": "Test",
            "created_at": now,
            "updated_at": now,
        }
        result = validate_artifact(data)
        assert result.id == "a1"

    def test_invalid(self):
        with pytest.raises(ValidationError):
            validate_artifact({"id": "a1"})  # missing required fields


# === Contract Tests: Round-Trip Serialization ===

class TestRoundTrips:
    def test_slides_roundtrip(self, sample_slides_tree):
        dumped = sample_slides_tree.model_dump()
        reconstructed = SlidesContentTree(**dumped)
        assert reconstructed == sample_slides_tree

    def test_document_roundtrip(self, sample_document_tree):
        dumped = sample_document_tree.model_dump()
        reconstructed = DocumentContentTree(**dumped)
        assert reconstructed == sample_document_tree

    def test_sheet_roundtrip(self, sample_sheet_tree):
        dumped = sample_sheet_tree.model_dump()
        reconstructed = SheetContentTree(**dumped)
        assert reconstructed == sample_sheet_tree

    def test_artifact_roundtrip(self, sample_artifact):
        dumped = sample_artifact.model_dump()
        reconstructed = Artifact(**dumped)
        assert reconstructed == sample_artifact

    def test_revision_roundtrip(self, sample_revision):
        dumped = sample_revision.model_dump()
        reconstructed = Revision(**dumped)
        assert reconstructed == sample_revision

    def test_outline_roundtrip(self, sample_outline):
        dumped = sample_outline.model_dump()
        reconstructed = Outline(**dumped)
        assert reconstructed == sample_outline

    def test_artifact_json_roundtrip(self, sample_artifact):
        """Test round-trip through JSON mode (ISO 8601 strings for datetimes)."""
        dumped = sample_artifact.model_dump(mode="json")
        reconstructed = Artifact(**dumped)
        assert reconstructed.id == sample_artifact.id
        assert reconstructed.type == sample_artifact.type
        assert reconstructed.title == sample_artifact.title
