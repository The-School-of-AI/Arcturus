"""
Visual Explainer service: produce self-contained HTML for diagrams and tables.
Does not depend on the visual_explainer skill class; callable from any pipeline or API.
"""
from pathlib import Path
from typing import Any, Optional

# Base path for optional template/ref reads (e.g. for future LLM prompts)
VISUAL_EXPLAINER_ROOT = Path(__file__).parent / "skills" / "library" / "visual_explainer"


def _escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_table(title: str, headers: list, rows: list[list]) -> str:
    """Build a minimal data-table HTML page (no external deps)."""
    thead = "".join(f"<th>{_escape(h)}</th>" for h in headers)
    tbody = ""
    for row in rows:
        tbody += "<tr>"
        for i, cell in enumerate(row):
            tbody += f"<td>{_escape(str(cell))}</td>"
        tbody += "</tr>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --font-body: 'Instrument Serif', Georgia, serif;
    --font-mono: 'JetBrains Mono', monospace;
    --bg: #fff5f5;
    --surface: #ffffff;
    --border: rgba(0,0,0,0.07);
    --text: #1c1917;
    --text-dim: #78716c;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #1a0a0a;
      --surface: #231414;
      --border: rgba(255,255,255,0.06);
      --text: #fde2e2;
      --text-dim: #c9a3a3;
    }}
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: var(--font-body); padding: 40px; min-height: 100vh; }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 28px; margin-bottom: 8px; }}
  .table-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-top: 24px; }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: var(--surface); font-family: var(--font-mono); font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 14px 16px; border-bottom: 2px solid var(--border); text-align: left; }}
  td {{ padding: 14px 16px; border-bottom: 1px solid var(--border); }}
  tr:nth-child(even) {{ background: rgba(0,0,0,0.02); }}
  @media (prefers-color-scheme: dark) {{ tr:nth-child(even) {{ background: rgba(255,255,255,0.04); }} }}
</style>
</head>
<body>
<div class="container">
  <h1>{_escape(title)}</h1>
  <div class="table-wrap">
    <div class="table-scroll">
      <table>
        <thead><tr>{thead}</tr></thead>
        <tbody>{tbody}</tbody>
      </table>
    </div>
  </div>
</div>
</body>
</html>"""


def _html_mermaid(title: str, mermaid_code: str) -> str:
    """Build a minimal HTML page that renders Mermaid from CDN."""
    # Escape for use inside a script tag: avoid </script> in user content
    code_escaped = mermaid_code.replace("</script>", "<\\/script>").replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape(title)}</title>
<script type="module" src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.mjs"></script>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{ --bg: #f0fdfa; --text: #134e4a; --font-body: 'Bricolage Grotesque', system-ui, sans-serif; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg: #042f2e; --text: #ccfbf1; }} }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: var(--font-body); padding: 24px; min-height: 100vh; }}
  h1 {{ font-size: 28px; margin-bottom: 16px; }}
  .mermaid-wrap {{ margin-top: 16px; }}
</style>
</head>
<body>
<h1>{_escape(title)}</h1>
<div class="mermaid-wrap">
  <pre class="mermaid">
{code_escaped}
  </pre>
</div>
<script type="module">
  const code = document.querySelector('.mermaid').textContent;
  await mermaid.default.run({{ nodes: document.querySelectorAll('.mermaid') }});
</script>
</body>
</html>"""


def _html_architecture(title: str, sections: list[dict]) -> str:
    """Build a minimal architecture card layout."""
    parts = []
    for s in sections:
        stitle = _escape(s.get("title", ""))
        desc = _escape(s.get("description", ""))
        items = s.get("items", [])
        items_html = "".join(f"<li>{_escape(str(i))}</li>" for i in items) if items else ""
        parts.append(
            f'<section class="card">'
            f'<h2>{stitle}</h2>'
            f'<p class="desc">{desc}</p>'
            f'<ul>{items_html}</ul>'
            f'</section>'
        )
    sections_html = "\n".join(parts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{ --bg: #faf7f5; --surface: #fff; --border: rgba(0,0,0,0.07); --text: #292017; --accent: #c2410c; --font-body: 'IBM Plex Sans', sans-serif; --font-mono: 'IBM Plex Mono', monospace; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg: #1a1412; --surface: #231d1a; --border: rgba(255,255,255,0.06); --text: #ede5dd; --accent: #fb923c; }} }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: var(--font-body); padding: 40px; min-height: 100vh; }}
  h1 {{ font-size: 28px; margin-bottom: 24px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--accent); border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
  .card h2 {{ font-size: 16px; font-family: var(--font-mono); margin-bottom: 8px; }}
  .card .desc {{ color: var(--text); opacity: 0.9; font-size: 14px; margin-bottom: 12px; }}
  .card ul {{ list-style: none; }}
  .card li {{ font-size: 13px; padding: 4px 0; border-bottom: 1px solid var(--border); }}
</style>
</head>
<body>
<h1>{_escape(title)}</h1>
{sections_html}
</body>
</html>"""


def _html_raw(html_fragment: str) -> str:
    """Wrap a raw HTML fragment in a minimal document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Visual</title>
</head>
<body>
{html_fragment}
</body>
</html>"""


def generate_html(
    diagram_type: str,
    title: str,
    content: Any,
) -> str:
    """
    Produce a self-contained HTML string for the given type and content.
    Does not depend on the visual_explainer skill class.

    diagram_type: "table" | "mermaid" | "architecture" | "raw"
    title: page title
    content:
      - table: dict with "headers" (list) and "rows" (list of lists)
      - mermaid: str (mermaid diagram code)
      - architecture: dict with "sections" (list of {"title", "description?", "items"?})
      - raw: str (HTML fragment; title ignored)
    """
    if diagram_type == "table":
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        return _html_table(title, headers, rows)
    if diagram_type == "mermaid":
        code = content if isinstance(content, str) else content.get("code", "")
        return _html_mermaid(title, code)
    if diagram_type == "architecture":
        sections = content.get("sections", []) if isinstance(content, dict) else []
        return _html_architecture(title, sections)
    if diagram_type == "raw":
        fragment = content if isinstance(content, str) else content.get("html", "")
        return _html_raw(fragment)
    raise ValueError(f"Unknown diagram_type: {diagram_type!r}; use table|mermaid|architecture|raw")

# Optional LLM path (add only if you want server-side generation from natural language)
async def generate_html_with_llm(prompt: str, diagram_type: str = "architecture", title: str = "Diagram") -> str:
    from core.model_manager import ModelManager
    skill_path = VISUAL_EXPLAINER_ROOT / "SKILL.md"
    instructions = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
    mm = ModelManager()
    full_prompt = f"{instructions}\n\nGenerate a single self-contained HTML file (no external assets except CDN fonts). User request: {prompt}. Title: {title}. Output only the HTML, no markdown fence."
    raw = await mm.generate_text(full_prompt)
    # Strip markdown code fence if present
    if raw.strip().startswith("```html"):
        raw = raw.strip().split("```html", 1)[1].strip()
    if raw.strip().endswith("```"):
        raw = raw.strip().split("```", 1)[0].strip()
    return raw