"""Tests for core/studio/documents/exporter_pdf.py — PDF rendering."""

import pytest
from pathlib import Path
from unittest.mock import patch

from core.schemas.studio_schema import DocumentContentTree, DocumentSection

# Check if WeasyPrint native dependencies are available
_weasyprint_available = True
try:
    from weasyprint import HTML
except (ImportError, OSError):
    _weasyprint_available = False

_skip_no_weasyprint = pytest.mark.skipif(
    not _weasyprint_available,
    reason="WeasyPrint native libraries not available (gobject/pango/etc.)",
)

from core.studio.documents.exporter_pdf import export_to_pdf


@pytest.fixture
def sample_content_tree():
    return DocumentContentTree(
        doc_title="Test Report",
        doc_type="report",
        abstract="This is a test abstract.",
        sections=[
            DocumentSection(
                id="sec1",
                heading="Introduction",
                level=1,
                content="Introduction paragraph.",
                subsections=[
                    DocumentSection(
                        id="sec1a",
                        heading="Background",
                        level=2,
                        content="Background details.",
                    )
                ],
            ),
            DocumentSection(
                id="sec2",
                heading="Conclusion",
                level=1,
                content="Final conclusions.",
            ),
        ],
        bibliography=[
            {"key": "ref1", "title": "Source A", "author": "Author A"},
        ],
    )


@pytest.fixture
def output_path(tmp_path):
    return tmp_path / "test_output.pdf"


@_skip_no_weasyprint
class TestExportToPdf:
    def test_creates_file(self, sample_content_tree, output_path):
        result = export_to_pdf(sample_content_tree, output_path)
        assert result == output_path
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_creates_parent_directories(self, sample_content_tree, tmp_path):
        nested_path = tmp_path / "sub" / "dir" / "test.pdf"
        export_to_pdf(sample_content_tree, nested_path)
        assert nested_path.exists()

    def test_pdf_is_valid(self, sample_content_tree, output_path):
        export_to_pdf(sample_content_tree, output_path)
        import fitz
        pdf = fitz.open(str(output_path))
        assert len(pdf) >= 1
        pdf.close()

    def test_pdf_contains_title_text(self, sample_content_tree, output_path):
        export_to_pdf(sample_content_tree, output_path)
        import fitz
        pdf = fitz.open(str(output_path))
        text = ""
        for page in pdf:
            text += page.get_text()
        pdf.close()
        assert "Test Report" in text

    def test_pdf_contains_section_text(self, sample_content_tree, output_path):
        export_to_pdf(sample_content_tree, output_path)
        import fitz
        pdf = fitz.open(str(output_path))
        text = ""
        for page in pdf:
            text += page.get_text()
        pdf.close()
        assert "Introduction" in text
        assert "Conclusion" in text

    def test_pdf_contains_bibliography(self, sample_content_tree, output_path):
        export_to_pdf(sample_content_tree, output_path)
        import fitz
        pdf = fitz.open(str(output_path))
        text = ""
        for page in pdf:
            text += page.get_text()
        pdf.close()
        assert "Bibliography" in text
        assert "ref1" in text

    def test_no_bibliography(self, tmp_path):
        tree = DocumentContentTree(
            doc_title="No Bib",
            doc_type="report",
            sections=[
                DocumentSection(id="s1", heading="Intro", level=1, content="Content."),
            ],
            bibliography=[],
        )
        path = tmp_path / "no_bib.pdf"
        export_to_pdf(tree, path)
        assert path.exists()

    def test_no_abstract(self, tmp_path):
        tree = DocumentContentTree(
            doc_title="No Abstract",
            doc_type="report",
            abstract=None,
            sections=[
                DocumentSection(id="s1", heading="Intro", level=1, content="Content."),
            ],
        )
        path = tmp_path / "no_abstract.pdf"
        export_to_pdf(tree, path)
        assert path.exists()

    def test_weasyprint_import_failure(self, sample_content_tree, output_path):
        """Test graceful error when WeasyPrint is not available."""
        with patch.dict("sys.modules", {"weasyprint": None}):
            with pytest.raises(RuntimeError, match="WeasyPrint is required"):
                # Need to reimport to trigger the import failure
                import importlib
                import core.studio.documents.exporter_pdf as mod
                importlib.reload(mod)
                mod.export_to_pdf(sample_content_tree, output_path)

    def test_empty_content(self, tmp_path):
        tree = DocumentContentTree(
            doc_title="Empty Sections",
            doc_type="report",
            sections=[
                DocumentSection(id="s1", heading="Empty", level=1, content=""),
            ],
        )
        path = tmp_path / "empty.pdf"
        export_to_pdf(tree, path)
        assert path.exists()
