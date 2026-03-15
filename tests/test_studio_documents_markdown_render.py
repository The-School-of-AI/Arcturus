"""Tests for core/studio/documents/markdown_render.py — markdown-to-HTML conversion."""

from core.studio.documents.markdown_render import markdown_to_html


class TestMarkdownToHtml:
    def test_empty_string(self):
        assert markdown_to_html("") == ""

    def test_none_input(self):
        assert markdown_to_html(None) == ""

    def test_whitespace_only(self):
        assert markdown_to_html("   \n\n  ") == ""

    def test_plain_text_wrapped_in_p(self):
        result = markdown_to_html("Hello world")
        assert "<p>" in result
        assert "Hello world" in result

    def test_bold(self):
        result = markdown_to_html("This is **bold** text")
        assert "<strong>" in result
        assert "bold" in result
        assert "**" not in result

    def test_italic(self):
        result = markdown_to_html("This is *italic* text")
        assert "<em>" in result
        assert "italic" in result

    def test_inline_code(self):
        result = markdown_to_html("Use `print()` here")
        assert "<code>" in result
        assert "print()" in result
        assert "`print()`" not in result

    def test_fenced_code_block(self):
        md = "```python\nprint('hello')\n```"
        result = markdown_to_html(md)
        assert "<pre>" in result
        assert "<code" in result
        assert "print" in result
        assert "```" not in result

    def test_mermaid_code_block_becomes_diagram_box(self):
        md = "```mermaid\ngraph TD\n  A-->B\n```"
        result = markdown_to_html(md)
        assert "mermaid-source" in result
        assert "Diagram (source)" in result
        assert "graph TD" in result
        assert "```" not in result

    def test_unordered_list(self):
        md = "- Item one\n- Item two\n- Item three"
        result = markdown_to_html(md)
        assert "<ul>" in result
        assert "<li>" in result
        assert "Item one" in result

    def test_ordered_list(self):
        md = "1. First\n2. Second\n3. Third"
        result = markdown_to_html(md)
        assert "<ol>" in result
        assert "<li>" in result
        assert "First" in result

    def test_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = markdown_to_html(md)
        assert "<table>" in result
        assert "<th>" in result
        assert "<td>" in result

    def test_multiple_paragraphs(self):
        md = "First paragraph.\n\nSecond paragraph."
        result = markdown_to_html(md)
        assert result.count("<p>") == 2

    def test_mixed_formatting(self):
        md = "**Bold** and *italic* and `code`"
        result = markdown_to_html(md)
        assert "<strong>" in result
        assert "<em>" in result
        assert "<code>" in result


class TestInlineListNormalization:
    """Tests for _normalize_inline_lists (invoked inside markdown_to_html)."""

    def test_inline_bold_bullets_become_list(self):
        md = "Defined: * **Monolith:** App. * **MS:** Svc."
        result = markdown_to_html(md)
        assert "<ul>" in result
        assert "<li>" in result
        assert "<strong>Monolith:</strong>" in result
        assert "**" not in result

    def test_inline_dash_bold_bullets(self):
        md = "Items: - **Alpha:** one - **Beta:** two"
        result = markdown_to_html(md)
        assert "<ul>" in result
        assert "<li>" in result
        assert "<strong>Alpha:</strong>" in result

    def test_inline_numbered_list(self):
        md = "Steps: 1. First step 2. Second step 3. Third step"
        result = markdown_to_html(md)
        assert "<ol>" in result
        assert "<li>" in result
        assert "First step" in result

    def test_plain_bullets_after_colon(self):
        md = "Features include: * Fast processing. * Low latency."
        result = markdown_to_html(md)
        assert "<ul>" in result
        assert "<li>" in result
        assert "Fast processing" in result

    def test_italic_not_affected(self):
        md = "This is *italic* text and *another* word."
        result = markdown_to_html(md)
        assert "<em>" in result
        assert "<ul>" not in result

    def test_already_formatted_list_unchanged(self):
        md = "Defined:\n\n* **M:** text.\n* **N:** text."
        result = markdown_to_html(md)
        assert "<ul>" in result
        assert "<strong>M:</strong>" in result

    def test_full_glossary_pattern(self):
        """Reproduces the exact pattern seen in LLM-generated document PDFs."""
        md = (
            "The following key terms are defined: "
            "* **Monolith:** The existing app. "
            "* **Microservice (MS):** A small service. "
            "* **API Gateway:** A single entry point."
        )
        result = markdown_to_html(md)
        assert "<ul>" in result
        assert result.count("<li>") == 3
        assert "<strong>Monolith:</strong>" in result
        assert "<strong>Microservice (MS):</strong>" in result
        assert "<strong>API Gateway:</strong>" in result
        assert "**" not in result


class TestMermaidDiagramSource:
    """Tests for Mermaid → styled diagram-source container."""

    def test_mermaid_block_has_header_label(self):
        md = "```mermaid\ngraph TD\n  A-->B\n```"
        result = markdown_to_html(md)
        assert 'class="mermaid-header"' in result
        assert "Diagram (source)" in result

    def test_mermaid_block_has_footer_with_link(self):
        md = "```mermaid\nsequenceDiagram\n  A->>B: hello\n```"
        result = markdown_to_html(md)
        assert 'class="mermaid-footer"' in result
        assert "mermaid.live" in result

    def test_mermaid_source_code_preserved(self):
        md = "```mermaid\ngraph LR\n  X-->Y\n  Y-->Z\n```"
        result = markdown_to_html(md)
        assert "graph LR" in result
        assert "X--&gt;Y" in result  # HTML-escaped arrows

    def test_mermaid_not_rendered_as_plain_code_block(self):
        """Mermaid blocks should NOT use the generic code block styling."""
        md = "```mermaid\ngraph TD\n  A-->B\n```"
        result = markdown_to_html(md)
        assert 'class="language-mermaid"' not in result
        assert 'class="mermaid-source"' in result

    def test_regular_code_block_unaffected(self):
        """Non-mermaid code blocks should still use the standard pre/code pattern."""
        md = "```python\nprint('hello')\n```"
        result = markdown_to_html(md)
        assert 'class="language-python"' in result
        assert "mermaid-source" not in result

    def test_mermaid_mixed_with_text(self):
        md = "Intro text.\n\n```mermaid\ngraph TD\n  A-->B\n```\n\nConclusion."
        result = markdown_to_html(md)
        assert "Intro text" in result
        assert "Conclusion" in result
        assert "mermaid-source" in result
        assert "Diagram (source)" in result
