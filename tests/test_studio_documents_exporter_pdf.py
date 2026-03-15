"""Tests for core/studio/documents/exporter_pdf.py — PDF rendering."""

from pathlib import Path
from unittest.mock import patch

import pytest

from core.schemas.studio_schema import DocumentContentTree, DocumentSection

# Check if xhtml2pdf is available
_xhtml2pdf_available = True
try:
    from xhtml2pdf import pisa
except (ImportError, OSError):
    _xhtml2pdf_available = False

_skip_no_xhtml2pdf = pytest.mark.skipif(
    not _xhtml2pdf_available,
    reason="xhtml2pdf not available",
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


@_skip_no_xhtml2pdf
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

    def test_xhtml2pdf_import_failure(self, sample_content_tree, output_path):
        """Test graceful error when xhtml2pdf is not available."""
        with patch.dict("sys.modules", {"xhtml2pdf": None}):
            with pytest.raises(RuntimeError, match="xhtml2pdf is required"):
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

    def test_pdf_renders_bold_text(self, tmp_path):
        """Bold markdown should render without raw ** markers."""
        tree = DocumentContentTree(
            doc_title="Bold Test",
            doc_type="report",
            sections=[
                DocumentSection(
                    id="s1", heading="Section", level=1,
                    content="This has **bold text** in it.",
                ),
            ],
        )
        path = tmp_path / "bold.pdf"
        export_to_pdf(tree, path)
        import fitz
        pdf = fitz.open(str(path))
        text = "".join(page.get_text() for page in pdf)
        pdf.close()
        assert "bold text" in text
        assert "**bold text**" not in text

    def test_pdf_renders_code_block(self, tmp_path):
        """Fenced code blocks should render without ``` markers."""
        tree = DocumentContentTree(
            doc_title="Code Test",
            doc_type="report",
            sections=[
                DocumentSection(
                    id="s1", heading="Section", level=1,
                    content="Example:\n\n```python\nprint('hello')\n```",
                ),
            ],
        )
        path = tmp_path / "code.pdf"
        export_to_pdf(tree, path)
        import fitz
        pdf = fitz.open(str(path))
        text = "".join(page.get_text() for page in pdf)
        pdf.close()
        assert "print" in text
        assert "```" not in text

    def test_pdf_renders_inline_glossary_list(self, tmp_path):
        """LLM-generated inline definition lists should not show raw * or ** markers."""
        tree = DocumentContentTree(
            doc_title="Glossary Test",
            doc_type="report",
            sections=[
                DocumentSection(
                    id="s1", heading="Definitions and Acronyms", level=1,
                    content=(
                        "The following key terms are defined: "
                        "* **Monolith:** The existing application. "
                        "* **Microservice (MS):** A small service. "
                        "* **API Gateway:** A single entry point."
                    ),
                ),
            ],
        )
        path = tmp_path / "glossary.pdf"
        export_to_pdf(tree, path)
        import fitz
        pdf = fitz.open(str(path))
        text = "".join(page.get_text() for page in pdf)
        pdf.close()
        assert "Monolith:" in text
        assert "**Monolith:**" not in text
        assert "Microservice (MS):" in text
        assert "* **" not in text

    def test_pdf_mermaid_shows_diagram_label(self, tmp_path):
        """Mermaid blocks should show 'Diagram (source)' label, not raw fences."""
        tree = DocumentContentTree(
            doc_title="Mermaid Test",
            doc_type="report",
            sections=[
                DocumentSection(
                    id="s1", heading="Architecture", level=1,
                    content="Overview:\n\n```mermaid\ngraph TD\n  A-->B\n```",
                ),
            ],
        )
        path = tmp_path / "mermaid.pdf"
        export_to_pdf(tree, path)
        import fitz
        pdf = fitz.open(str(path))
        text = "".join(page.get_text() for page in pdf)
        pdf.close()
        assert "Diagram (source)" in text
        assert "mermaid.live" in text
        assert "graph TD" in text
        assert "```" not in text
