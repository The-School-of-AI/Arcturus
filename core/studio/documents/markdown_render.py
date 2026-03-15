"""Shared markdown-to-HTML converter for document exporters."""

from __future__ import annotations

import html
import re

import markdown

_EXTENSIONS = [
    "fenced_code",
    "tables",
    "sane_lists",
]

# Matches <pre><code class="language-mermaid">...</code></pre> blocks
_MERMAID_BLOCK_RE = re.compile(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>',
    re.DOTALL,
)

_MERMAID_LIVE_URL = "https://mermaid.live"


def _normalize_inline_lists(text: str) -> str:
    """Insert line breaks before inline list markers so markdown can parse them.

    LLMs commonly emit list items on a single line:
        "Terms defined: * **Monolith:** desc * **MS:** desc"
    Markdown requires items to start at the beginning of a line.
    This normalizer detects common inline-list patterns and adds ``\\n\\n``.
    """
    # Bold-labeled bullets:  ...text * **Label:**  or  ...text - **Label:**
    text = re.sub(r"(?<!\n)\s+(\*\s+\*\*)", r"\n\n\1", text)
    text = re.sub(r"(?<!\n)\s+(-\s+\*\*)", r"\n\n\1", text)
    # Plain bullets after sentence-ending punctuation + capital letter
    text = re.sub(r"([.:;])\s+(\*\s+[A-Z])", r"\1\n\n\2", text)
    text = re.sub(r"([.:;])\s+(-\s+[A-Z])", r"\1\n\n\2", text)
    # Inline numbered items: "1. Capital" pattern
    text = re.sub(r"(?<!\n)\s+(\d+\.\s+[A-Z])", r"\n\n\1", text)
    return text


def _mermaid_to_diagram_box(match: re.Match) -> str:
    """Replace a mermaid code block with a styled 'Diagram (source)' container."""
    # Content is HTML-escaped by markdown; unescape for display
    source = html.unescape(match.group(1)).strip()
    # Re-escape for safe embedding in the styled container
    escaped = html.escape(source)
    return (
        '<div class="mermaid-source">'
        '<div class="mermaid-header">Diagram (source)</div>'
        f'<pre class="mermaid-code"><code>{escaped}</code></pre>'
        '<div class="mermaid-footer">'
        f'Paste into <a href="{_MERMAID_LIVE_URL}">mermaid.live</a> to render'
        '</div></div>'
    )


def markdown_to_html(text: str | None) -> str:
    """Convert a markdown string to an HTML fragment.

    Returns an empty string for None or whitespace-only input.
    Plain text is wrapped in ``<p>`` tags by the markdown library.
    Inline list markers are normalized before conversion.
    Mermaid code blocks are replaced with a styled diagram-source container.
    """
    if not text or not text.strip():
        return ""
    text = _normalize_inline_lists(text)
    result = markdown.markdown(text, extensions=_EXTENSIONS)
    result = _MERMAID_BLOCK_RE.sub(_mermaid_to_diagram_box, result)
    return result


# ── HTML sanitization (defense-in-depth for LLM output) ──────────
# Python-Markdown passes raw HTML through by default, and the template
# uses {{ section.content | safe }}.  Since content originates from LLM
# output, we strip executable constructs before rendering.

_DANGEROUS_TAG_RE = re.compile(
    r"<script[\s>].*?</script>|<script[\s>][^<]*$",
    re.DOTALL | re.IGNORECASE | re.MULTILINE,
)
_EVENT_HANDLER_RE = re.compile(
    r"""\s+on\w+\s*=\s*(?:["'][^"']*["']|[^\s>]+)""",
    re.IGNORECASE,
)
_JS_URL_RE = re.compile(r"""(href|src|action)\s*=\s*["']?\s*javascript:""", re.IGNORECASE)


def _strip_dangerous_html(html_text: str) -> str:
    """Remove executable HTML constructs from converted markdown.

    Strips: <script> tags, on*= event handlers, javascript: URLs.
    """
    result = _DANGEROUS_TAG_RE.sub("", html_text)
    result = _EVENT_HANDLER_RE.sub("", result)
    result = _JS_URL_RE.sub(r'\1="', result)
    return result


def _mermaid_to_live_div(match: re.Match) -> str:
    """Replace a mermaid code block with a live-renderable <div class='mermaid'>.

    Content stays HTML-entity-encoded (as emitted by markdown's fenced_code).
    The browser decodes entities into text nodes (not elements), so Mermaid.js
    reads correct diagram source via textContent without HTML injection risk.
    """
    source = match.group(1).strip()
    return f'<div class="mermaid">\n{source}\n</div>'


def markdown_to_html_web(text: str | None) -> str:
    """Convert markdown to HTML with live Mermaid blocks for web viewing.

    Unlike ``markdown_to_html``, this variant:
    - Sanitizes executable HTML (scripts, event handlers, javascript: URLs)
    - Replaces Mermaid code blocks with ``<div class="mermaid">`` for
      client-side rendering by Mermaid.js
    """
    if not text or not text.strip():
        return ""
    text = _normalize_inline_lists(text)
    result = markdown.markdown(text, extensions=_EXTENSIONS)
    result = _strip_dangerous_html(result)
    result = _MERMAID_BLOCK_RE.sub(_mermaid_to_live_div, result)
    return result
