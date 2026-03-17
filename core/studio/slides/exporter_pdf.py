"""
Slide PDF Exporter — Pixel-perfect PDF generation using Playwright.

For artistic (HTML) slides: renders the slide.html directly in a headless browser.
For business (structured) slides: converts elements to HTML first, then renders.

Each slide becomes one 16:9 page in the output PDF.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from core.schemas.studio_schema import Slide, SlideTheme, SlidesContentTree

logger = logging.getLogger(__name__)

# 16:9 slide dimensions in pixels (at 96 DPI → matches typical screen rendering)
SLIDE_W = 1280
SLIDE_H = 720


def _build_structured_html(slide: Slide, theme: Optional[SlideTheme] = None) -> str:
    """Convert a business-mode slide (structured elements) into presentation HTML."""
    colors = theme.colors if theme else None
    bg = colors.background if colors else "#FFFFFF"
    fg = colors.text if colors else "#1a1a2e"
    primary = colors.primary if colors else "#1E3A5F"
    accent = colors.accent if colors else "#E8491D"
    font_heading = theme.font_heading if theme else "system-ui"
    font_body = theme.font_body if theme else "system-ui"

    parts = []
    for el in slide.elements:
        t = el.type
        c = el.content
        if t == "title":
            parts.append(
                f'<h1 style="font-family:\'{font_heading}\',system-ui;font-size:44px;'
                f'font-weight:700;color:{primary};margin:0 0 12px 0;">{_esc(c)}</h1>'
            )
        elif t == "subtitle":
            parts.append(
                f'<h2 style="font-family:\'{font_body}\',system-ui;font-size:24px;'
                f'font-weight:400;color:{fg}88;margin:0 0 24px 0;">{_esc(c)}</h2>'
            )
        elif t == "body":
            parts.append(
                f'<p style="font-family:\'{font_body}\',system-ui;font-size:18px;'
                f'line-height:1.6;color:{fg};margin:0 0 16px 0;">{_esc(c)}</p>'
            )
        elif t == "bullet_list":
            items = c if isinstance(c, list) else [c]
            li_html = "".join(
                f'<li style="margin-bottom:8px;">{_esc(str(item))}</li>'
                for item in items
            )
            parts.append(
                f'<ul style="font-family:\'{font_body}\',system-ui;font-size:18px;'
                f'line-height:1.5;color:{fg};padding-left:28px;margin:0 0 16px 0;">{li_html}</ul>'
            )
        elif t == "quote":
            parts.append(
                f'<blockquote style="font-family:\'{font_body}\',system-ui;font-size:22px;'
                f'font-style:italic;color:{fg};border-left:4px solid {accent};'
                f'padding:12px 0 12px 24px;margin:16px 0;">{_esc(c)}</blockquote>'
            )
        elif t == "code":
            parts.append(
                f'<pre style="font-family:\'Consolas\',\'Monaco\',monospace;font-size:14px;'
                f'background:#1e1e2e;color:#cdd6f4;padding:20px;border-radius:8px;'
                f'overflow:auto;margin:0 0 16px 0;">{_esc(c)}</pre>'
            )
        elif t == "image":
            url = c if isinstance(c, str) else ""
            if url:
                parts.append(
                    f'<div style="text-align:center;margin:16px 0;">'
                    f'<img src="{_esc(url)}" style="max-width:80%;max-height:300px;'
                    f'border-radius:8px;object-fit:contain;" /></div>'
                )
        elif t == "table":
            parts.append(_render_table(c, fg, primary, font_body))
        elif t == "chart":
            # Charts don't render in HTML easily — show as data table
            parts.append(
                f'<div style="font-family:\'{font_body}\',system-ui;font-size:14px;'
                f'color:{fg}88;padding:20px;background:{fg}08;border-radius:8px;'
                f'text-align:center;margin:16px 0;">[Chart: {_esc(str(c.get("title", "")))}]</div>'
                if isinstance(c, dict) else ""
            )
        else:
            # Fallback for any other element type
            parts.append(
                f'<p style="font-family:\'{font_body}\',system-ui;font-size:18px;'
                f'color:{fg};margin:0 0 12px 0;">{_esc(str(c))}</p>'
            )

    title_html = ""
    if slide.title:
        title_html = (
            f'<h1 style="font-family:\'{font_heading}\',system-ui;font-size:44px;'
            f'font-weight:700;color:{primary};margin:0 0 20px 0;">{_esc(slide.title)}</h1>'
        )

    body = "\n".join(parts)
    # Don't duplicate title if it's already in elements
    has_title_element = any(el.type == "title" for el in slide.elements)
    if has_title_element:
        title_html = ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {SLIDE_W}px; height: {SLIDE_H}px;
    background: {bg}; overflow: hidden;
    display: flex; flex-direction: column;
    justify-content: center; padding: 60px 80px;
  }}
</style></head>
<body>{title_html}{body}</body></html>"""


def _render_table(data: any, fg: str, primary: str, font: str) -> str:
    """Render a table element to HTML."""
    if not isinstance(data, dict):
        return ""
    headers = data.get("headers", [])
    rows = data.get("rows", [])
    if not headers and not rows:
        return ""

    th = "".join(
        f'<th style="padding:10px 16px;text-align:left;background:{primary};'
        f'color:white;font-weight:600;">{_esc(str(h))}</th>'
        for h in headers
    )
    tr_list = []
    for i, row in enumerate(rows):
        bg = f"{fg}04" if i % 2 == 0 else "transparent"
        tds = "".join(
            f'<td style="padding:8px 16px;border-bottom:1px solid {fg}15;">{_esc(str(cell))}</td>'
            for cell in row
        )
        tr_list.append(f'<tr style="background:{bg};">{tds}</tr>')

    return (
        f'<table style="font-family:\'{font}\',system-ui;font-size:15px;'
        f'color:{fg};border-collapse:collapse;width:100%;margin:16px 0;">'
        f'<thead><tr>{th}</tr></thead>'
        f'<tbody>{"".join(tr_list)}</tbody></table>'
    )


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _wrap_slide_html(html: str) -> str:
    """Wrap artistic slide.html in a full document with fixed viewport."""
    # If it already has <html> or <!DOCTYPE>, use as-is but inject viewport sizing
    if "<html" in html.lower() or "<!doctype" in html.lower():
        # Inject overflow:hidden to prevent scrollbars
        inject = (
            f"<style>html,body{{width:{SLIDE_W}px;height:{SLIDE_H}px;"
            f"overflow:hidden;margin:0;padding:0;}}</style>"
        )
        if "</head>" in html.lower():
            idx = html.lower().index("</head>")
            return html[:idx] + inject + html[idx:]
        return inject + html

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: {SLIDE_W}px; height: {SLIDE_H}px;
    overflow: hidden; margin: 0; padding: 0;
  }}
</style></head>
<body>{html}</body></html>"""


async def export_to_pdf(
    content_tree: SlidesContentTree,
    theme: Optional[SlideTheme],
    output_path: Path,
) -> Path:
    """
    Export slides to a multi-page PDF using Playwright.

    Each slide is rendered at 1280x720 (16:9) in a headless Chromium browser,
    producing pixel-perfect output that matches the frontend preview.
    """
    from playwright.async_api import async_playwright

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    slides = content_tree.slides
    if not slides:
        raise ValueError("No slides to export")

    logger.info(f"Exporting {len(slides)} slides to PDF: {output_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": SLIDE_W, "height": SLIDE_H},
            device_scale_factor=2,  # 2x for crisp text
        )

        page_pdfs: list[bytes] = []

        for i, slide in enumerate(slides):
            page = await context.new_page()

            # Build the HTML for this slide
            if slide.html:
                html = _wrap_slide_html(slide.html)
            else:
                html = _build_structured_html(slide, theme)

            await page.set_content(html, wait_until="networkidle")

            # Small delay for fonts/images to load
            await page.wait_for_timeout(300)

            # Render to PDF — single page, exact slide dimensions
            pdf_bytes = await page.pdf(
                width=f"{SLIDE_W}px",
                height=f"{SLIDE_H}px",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            page_pdfs.append(pdf_bytes)
            await page.close()

            if (i + 1) % 5 == 0:
                logger.info(f"  Rendered {i + 1}/{len(slides)} slides...")

        await browser.close()

    # Merge all single-page PDFs into one document
    merged = _merge_pdfs(page_pdfs)
    output_path.write_bytes(merged)

    logger.info(
        f"PDF export complete: {output_path} "
        f"({len(slides)} slides, {output_path.stat().st_size / 1024:.1f} KB)"
    )
    return output_path


def _merge_pdfs(pdf_list: list[bytes]) -> bytes:
    """Merge multiple single-page PDFs into one document."""
    if len(pdf_list) == 1:
        return pdf_list[0]

    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        # Fallback: try PyPDF2
        try:
            from PyPDF2 import PdfReader, PdfWriter  # type: ignore[no-redef]
        except ImportError:
            # Last resort: just return the first page
            logger.warning("No PDF merge library available (pypdf/PyPDF2). Returning single-page PDF.")
            return pdf_list[0]

    import io

    writer = PdfWriter()
    for pdf_bytes in pdf_list:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for pg in reader.pages:
            writer.add_page(pg)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def export_to_pdf_sync(
    content_tree: SlidesContentTree,
    theme: Optional[SlideTheme],
    output_path: Path,
) -> Path:
    """Synchronous wrapper for export_to_pdf."""
    return asyncio.run(export_to_pdf(content_tree, theme, output_path))
