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


# Section variants matching reference template (templates/architecture.html)
_ARCH_SECTION_VARIANTS = frozenset({"hero", "accent", "green", "orange", "sage", "teal", "plum", "recessed"})

# Inline CSS for architecture diagrams (theme, sections, flow arrows, animation). Matches reference template.
_ARCHITECTURE_CSS = """
  :root {
    --font-body: 'IBM Plex Sans', system-ui, sans-serif;
    --font-mono: 'IBM Plex Mono', 'SF Mono', Consolas, monospace;
    --bg: #faf7f5;
    --surface: #ffffff;
    --surface2: #f5f0ec;
    --surface-elevated: #fff9f5;
    --border: rgba(0, 0, 0, 0.07);
    --border-bright: rgba(0, 0, 0, 0.14);
    --text: #292017;
    --text-dim: #8a7e72;
    --accent: #c2410c;
    --accent-dim: rgba(194, 65, 12, 0.07);
    --green: #4d7c0f;
    --green-dim: rgba(77, 124, 15, 0.07);
    --orange: #b45309;
    --orange-dim: rgba(180, 83, 9, 0.07);
    --sage: #65a30d;
    --sage-dim: rgba(101, 163, 13, 0.07);
    --teal: #0f766e;
    --teal-dim: rgba(15, 118, 110, 0.07);
    --plum: #9f1239;
    --plum-dim: rgba(159, 18, 57, 0.07);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #1a1412;
      --surface: #231d1a;
      --surface2: #2e2622;
      --surface-elevated: #352d28;
      --border: rgba(255, 255, 255, 0.06);
      --border-bright: rgba(255, 255, 255, 0.12);
      --text: #ede5dd;
      --text-dim: #a69889;
      --accent: #fb923c;
      --accent-dim: rgba(251, 146, 60, 0.12);
      --green: #a3e635;
      --green-dim: rgba(163, 230, 53, 0.1);
      --orange: #fbbf24;
      --orange-dim: rgba(251, 191, 36, 0.1);
      --sage: #bef264;
      --sage-dim: rgba(190, 242, 100, 0.1);
      --teal: #5eead4;
      --teal-dim: rgba(94, 234, 212, 0.1);
      --plum: #fda4af;
      --plum-dim: rgba(253, 164, 175, 0.1);
    }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    background-image:
      radial-gradient(ellipse at 20% 0%, var(--accent-dim) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 100%, var(--sage-dim) 0%, transparent 40%);
    color: var(--text);
    font-family: var(--font-body);
    padding: 40px;
    min-height: 100vh;
  }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .section, .flow-arrow {
    animation: fadeUp 0.4s ease-out both;
    animation-delay: calc(var(--i, 0) * 0.06s);
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-delay: 0ms !important;
      transition-duration: 0.01ms !important;
    }
  }
  h1 {
    font-size: 38px;
    font-weight: 700;
    letter-spacing: -1px;
    margin-bottom: 6px;
    text-wrap: balance;
  }
  .subtitle {
    color: var(--text-dim);
    font-size: 14px;
    margin-bottom: 40px;
    font-family: var(--font-mono);
  }
  .diagram {
    display: grid;
    grid-template-columns: 1fr;
    gap: 24px;
    max-width: 1100px;
    margin: 0 auto;
  }
  .section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
  }
  .section--hero {
    background: var(--surface-elevated);
    border-color: color-mix(in srgb, var(--border) 50%, var(--accent) 50%);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    padding: 28px 32px;
  }
  .section--recessed {
    background: var(--surface2);
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.04);
  }
  .section-label {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .section-label .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .section--accent { border-color: var(--accent-dim); }
  .section--accent .section-label { color: var(--accent); }
  .section--accent .section-label .dot { background: var(--accent); }
  .section--green { border-color: var(--green-dim); }
  .section--green .section-label { color: var(--green); }
  .section--green .section-label .dot { background: var(--green); }
  .section--orange { border-color: var(--orange-dim); }
  .section--orange .section-label { color: var(--orange); }
  .section--orange .section-label .dot { background: var(--orange); }
  .section--sage { border-color: var(--sage-dim); }
  .section--sage .section-label { color: var(--sage); }
  .section--sage .section-label .dot { background: var(--sage); }
  .section--teal { border-color: var(--teal-dim); }
  .section--teal .section-label { color: var(--teal); }
  .section--teal .section-label .dot { background: var(--teal); }
  .section--plum { border-color: var(--plum-dim); }
  .section--plum .section-label { color: var(--plum); }
  .section--plum .section-label .dot { background: var(--plum); }
  .section h2 { font-size: 16px; font-family: var(--font-mono); margin-bottom: 8px; }
  .section .desc { color: var(--text); opacity: 0.9; font-size: 14px; margin-bottom: 12px; }
  .section .node-list { list-style: none; font-size: 12px; line-height: 1.8; }
  .section .node-list li { padding-left: 14px; position: relative; }
  .section .node-list li::before { content: '›'; color: var(--text-dim); font-weight: 600; position: absolute; left: 0; }
  .flow-arrow {
    display: flex; justify-content: center; align-items: center; gap: 8px;
    color: var(--text-dim); font-family: var(--font-mono); font-size: 12px; padding: 4px 0;
  }
  .flow-arrow svg {
    width: 20px; height: 20px; fill: none; stroke: var(--border-bright);
    stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
  }
"""

_FLOW_ARROW_SVG = '<svg viewBox="0 0 20 20"><path d="M10 4 L10 16 M6 12 L10 16 L14 12"/></svg>'


def _html_architecture(title: str, sections: list[dict], subtitle: str = "", flow_labels: Optional[list[str]] = None) -> str:
    """
    Build an architecture diagram matching the reference template.
    Sections: list of { title, description?, items?, variant?, label? }.
    variant: hero | accent | green | orange | sage | teal | plum | recessed (optional).
    label: optional monospace label above title (section-label + dot).
    flow_labels: optional list of strings; flow_labels[i] is rendered between section[i] and section[i+1].
    """
    flow_labels = flow_labels or []
    diagram_parts = []
    idx = 0
    for i, s in enumerate(sections):
        stitle = _escape(s.get("title", ""))
        desc = _escape(s.get("description", ""))
        items = s.get("items", [])
        variant = (s.get("variant") or "").strip().lower()
        if variant not in _ARCH_SECTION_VARIANTS:
            variant = ""
        label_text = _escape((s.get("label") or stitle or "").strip())
        items_html = "".join(f"<li>{_escape(str(i))}</li>" for i in items) if items else ""
        section_class = "section"
        if variant:
            section_class += f" section--{variant}"
        label_block = ""
        if label_text:
            label_block = f'<div class="section-label"><span class="dot"></span>{label_text}</div>'
        desc_block = f'<p class="desc">{desc}</p>' if desc else ""
        list_block = f'<ul class="node-list">{items_html}</ul>' if items_html else ""
        section_html = (
            f'<section class="{section_class}" style="--i:{idx}">'
            f"{label_block}"
            f"<h2>{stitle}</h2>"
            f"{desc_block}"
            f"{list_block}"
            f"</section>"
        )
        diagram_parts.append(section_html)
        idx += 1
        if i < len(flow_labels) and flow_labels[i]:
            diagram_parts.append(
                f'<div class="flow-arrow" style="--i:{idx}">'
                f"{_FLOW_ARROW_SVG}\n  {_escape(flow_labels[i])}"
                f"</div>"
            )
            idx += 1
    diagram_html = "\n".join(diagram_parts)
    subtitle_html = f'<p class="subtitle">{_escape(subtitle)}</p>' if subtitle else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_ARCHITECTURE_CSS}</style>
</head>
<body>
<h1>{_escape(title)}</h1>
{subtitle_html}
<div class="diagram">
{diagram_html}
</div>
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
      - architecture: dict with "sections" (list of {"title", "description?", "items?", "variant?", "label?"}),
        optional "subtitle", "flowLabels" (list of strings between sections)
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
        if not isinstance(content, dict):
            content = {}
        sections = content.get("sections", [])
        if isinstance(sections, dict):
            sections = [sections]
        if not isinstance(sections, list):
            sections = []
        subtitle = (content.get("subtitle") or "").strip()
        flow_labels = content.get("flowLabels") or content.get("flow_labels") or []
        if not isinstance(flow_labels, list):
            flow_labels = []
        return _html_architecture(title, sections, subtitle=subtitle, flow_labels=flow_labels)
    if diagram_type == "raw":
        fragment = content if isinstance(content, str) else content.get("html", "")
        return _html_raw(fragment)
    raise ValueError(f"Unknown diagram_type: {diagram_type!r}; use table|mermaid|architecture|raw")

# Optional LLM path (add only if you want server-side generation from natural language).
# For architecture diagrams, the agent can instead call the API with content shape:
#   sections: [{ title, description?, items?, variant?, label? }], subtitle?, flowLabels?
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