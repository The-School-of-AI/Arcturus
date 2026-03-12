import json
from typing import Any, Dict

from core.schemas.studio_schema import ArtifactType, Outline


def get_outline_prompt(artifact_type: ArtifactType, user_prompt: str, parameters: Dict[str, Any]) -> str:
    """Build a system prompt requesting structured outline JSON from the LLM."""

    type_guidance = _get_type_specific_outline_guidance(artifact_type)
    params_str = json.dumps(parameters, indent=2) if parameters else "{}"

    return f"""You are a content architect specializing in creating structured outlines.

The user wants to create a **{artifact_type.value}** artifact.

User's request: {user_prompt}

Additional parameters: {params_str}

{type_guidance}

Your task: Generate a structured outline for this {artifact_type.value}.

Return ONLY valid JSON in this exact format:
{{
  "title": "The title for this artifact",
  "items": [
    {{
      "id": "1",
      "title": "Section/slide/tab title",
      "description": "Brief description of what this section covers",
      "children": [
        {{
          "id": "1.1",
          "title": "Sub-item title",
          "description": "Sub-item description",
          "children": []
        }}
      ]
    }}
  ]
}}

Rules:
- Every item must have a unique id, title, and description
- Use hierarchical ids (1, 1.1, 1.2, 2, 2.1, etc.)
- Include children for sub-items where appropriate
- Return ONLY the JSON object, no markdown fences or explanations"""


def get_draft_prompt(artifact_type: ArtifactType, outline: Outline) -> str:
    """Build a system prompt requesting full content_tree JSON from an approved outline."""

    outline_json = json.dumps(outline.model_dump(mode="json"), indent=2)
    type_schema = _get_type_specific_draft_schema(artifact_type)

    return f"""You are a professional content creator. Generate a complete {artifact_type.value} based on the approved outline below.

Approved outline:
{outline_json}

{type_schema}

Rules:
- Follow the outline structure exactly
- Populate ALL fields with substantive, professional content
- Use unique ids for all elements
- Return ONLY valid JSON matching the schema above, no markdown fences or explanations"""


def _get_type_specific_outline_guidance(artifact_type: ArtifactType) -> str:
    """Return type-specific guidance for outline generation."""
    if artifact_type == ArtifactType.slides:
        return """Guidance for slides:
- Plan a narrative arc: problem statement, solution overview, evidence/data, call to action
- Each outline item represents one CONTENT slide
- The slide count refers to content slides only — an opening title slide, closing title slide, and section dividers are generated automatically. Do NOT include them in the outline.
- Suggest 8-12 content slides unless the user specifies a count
- Include speaker notes suggestions in descriptions — these become presenter notes in the exported PPTX
- Available content slide types (pick the best fit for each slide):
  * content — Standard slide with title + body paragraphs or bullet points
  * two_column — Side-by-side comparison or complementary content
  * comparison — Explicit pros/cons or before/after layout
  * timeline — Sequential steps, milestones, or roadmap
  * chart — Data visualization with supporting context
  * stat — Key metrics displayed as large callouts (1-3 per slide)
  * image_text — Split layout with image area and descriptive text
  * image_full — Full-bleed image covering entire slide with overlay text (dramatic visual impact)
  * quote — Featured quotation with attribution
  * code — Technical slide with monospace code block
  * team — Team members, credits, or acknowledgments
  * agenda — Table of contents / overview with numbered cards (use as first content slide for decks with 8+ slides)
  * table — Data table with styled header row, alternating bands, and optional status badges
- Do NOT use "title" or "section_divider" as slide_type — these are structural and added automatically
- When the topic involves data, metrics, or KPIs, prefer stat or chart slide types
- Use table slide type when comparing platforms, tools, or features across dimensions
- Bullet points should be SHORT phrases (6-8 words max), not full sentences
- Assign a slide_type to each item in the description field (e.g., "slide_type: two_column")"""

    elif artifact_type == ArtifactType.document:
        return """Guidance for documents:
- Plan hierarchical sections with clear heading levels
- Each outline item represents a major section
- Use children for subsections (heading level 2, 3, etc.)
- Maximum nesting depth: 3 levels (section → subsection → sub-subsection)
- Core document types for Phase 4:
  * technical_spec — Required sections: Introduction, Requirements, Architecture, Implementation
  * report — Required sections: Executive Summary, Introduction, Findings, Conclusion
  * proposal — Required sections: Executive Summary, Problem Statement, Proposed Solution, Timeline
- Always include an abstract/executive summary section
- Plan for citations and bibliography where appropriate
- Suggest 4-15 sections depending on document complexity
- For technical_spec: include diagrams, code examples, API references in descriptions
- For report: include data analysis, methodology, findings in descriptions
- For proposal: include budget, timeline, risk assessment in descriptions"""

    elif artifact_type == ArtifactType.sheet:
        return """Guidance for spreadsheets:
- Each outline item represents a tab/worksheet
- Describe what columns and data each tab will contain
- Plan for formulas and calculated fields
- Consider tab types: data entry, summary, charts, assumptions
- Include column planning in the description
- When formulas are appropriate, describe them in the tab description
- Plan tabs with consistent column naming across related tabs
- Consider including a summary/totals tab for multi-tab workbooks"""

    return ""


def _get_type_specific_draft_schema(artifact_type: ArtifactType) -> str:
    """Return the exact JSON schema the LLM should produce for the draft."""
    if artifact_type == ArtifactType.slides:
        return """Generate a SlidesContentTree JSON with this exact schema:
{
  "deck_title": "Presentation title",
  "subtitle": "Optional subtitle",
  "slides": [
    {
      "id": "s1",
      "slide_type": "title|content|two_column|comparison|timeline|chart|stat|image_text|image_full|quote|code|team|section_divider|agenda|table",
      "title": "Slide title",
      "elements": [
        {"id": "e1", "type": "title|subtitle|kicker|takeaway|body|bullet_list|image|chart|code|quote|stat_callout|table_data|tag_badge|callout_box|source_citation|progress_bar", "content": "..."}
      ],
      "speaker_notes": "Notes for the presenter"
    }
  ],
  "metadata": {"audience": "...", "tone": "..."}
}

- For bullet_list elements, content must be a JSON array of strings
- For "kicker" elements, content is a SHORT phrase (2-5 words) that categorizes the slide (e.g., "MARKET OPPORTUNITY", "KEY INSIGHT", "PHASE 2"). Include a kicker on content, two_column, comparison, timeline, chart, and stat slides.
- For "takeaway" elements, content is a single concise sentence (max 15 words) summarizing the slide's key message. Include a takeaway on content, two_column, comparison, timeline, chart, and stat slides.
- Each slide must have a unique id (s1, s2, ...) and each element a unique id (e1, e2, ...)
- Match the slide_type to the content purpose:
  * Use "title" for opening and closing slides
  * Use "content" for main narrative slides
  * Use "two_column" when comparing or contrasting
  * Use "quote" for testimonials or key insights
  * Use "chart" when referencing data or metrics
  * Use "image_full" for dramatic full-bleed visuals (provide image description in an "image" element)

For elements with type="chart", content MUST be a structured JSON object:
{
  "chart_type": "bar" | "line" | "pie" | "funnel" | "scatter",
  "title": "Chart Title",
  "categories": ["Label1", "Label2", ...],
  "series": [{"name": "Series Name", "values": [1.0, 2.0, ...]}],
  "x_label": "X Axis Label",
  "y_label": "Y Axis Label"
}
For scatter charts, use "points": [{"x": 1.0, "y": 2.0}, ...] instead of categories/series.
Do NOT use plain text strings for chart content — always use structured JSON.

For elements with type="stat_callout", content MUST be a JSON array of stat objects:
[{"value": "85%", "label": "Customer Satisfaction"}, {"value": "2.4M", "label": "Active Users"}]
Include 1-3 stat objects per slide. Values should be punchy numbers/percentages.

For "table_data" elements: content = {"headers": ["Col1", "Col2", "Status"], "rows": [["Cell1", "Cell2", "HIGH"], ...], "badge_column": 2}
For "callout_box" elements: content = {"text": "Synthesizing insight quote", "attribution": "Source"}
For "source_citation" elements: content = "Source: Company Annual Report 2025"
For "tag_badge" elements: content = "TAG LABEL"

For agenda slides: bullet_list items formatted as "Section Title: Brief description"
For timeline slides: bullet_list items formatted as "Date | Event Title | Description | CATEGORY TAG"
For comparison slides: include a callout_box element with a synthesizing insight
For title slides: set metadata.date and metadata.category for enhanced visuals

SLIDE CONTENT DENSITY RULES (mandatory):
- MAX 6 bullets per slide, MAX 8 words per bullet
- MAX 3 short sentences per body element (25 words max per sentence)
- The slide should contain MAX 30% of the information (key phrases only). The other 70% belongs in speaker_notes
- NEVER use placeholder text like "Content to be developed", "TBD", "Lorem ipsum", or "To be added"
- Every slide must have substantive, specific content — no filler
- agenda slides: MAX 6 items in bullet_list, each as "Title: Description"
- table slides: MAX 8 rows, MAX 6 columns

SPEAKER NOTES REQUIREMENTS (mandatory for every slide):
- Write 2-4 concise sentences of presenter guidance per slide
- Include at least one key talking point not visible on the slide
- Include a transition sentence or audience callout
- Do NOT repeat bullet points or body text verbatim in notes
- Title/closing slides may have 1-2 shorter sentences
- Target 15-60 words per slide's speaker notes"""

    elif artifact_type == ArtifactType.document:
        return """Generate a DocumentContentTree JSON with this exact schema:
{
  "doc_title": "Document title",
  "doc_type": "technical_spec|report|proposal",
  "abstract": "Executive summary or abstract",
  "sections": [
    {
      "id": "sec1",
      "heading": "Section heading",
      "level": 1,
      "content": "Section body text (can be multiple paragraphs)",
      "subsections": [
        {
          "id": "sec1a",
          "heading": "Subsection heading",
          "level": 2,
          "content": "Subsection body text",
          "subsections": [],
          "citations": []
        }
      ],
      "citations": ["citation_key"]
    }
  ],
  "bibliography": [{"key": "citation_key", "title": "Source Title", "author": "Author Name"}],
  "metadata": {"audience": "...", "tone": "..."}
}

- Each section must have a unique id
- Use level 1 for top sections, 2 for subsections, 3 for sub-subsections (max depth 3)
- Write substantive multi-paragraph content for each section
- NEVER use placeholder text like "TBD", "Lorem ipsum", "Content to be developed", or "To be added"
- Every section must contain real, substantive content — no filler
- Citations in section content should use bracket notation: [citation_key]
- Every citation key used in sections MUST have a matching entry in bibliography
- Bibliography entries must have: key, title, author (year and url optional)
- Include metadata.provenance_slots as an array of {"citation_key": "...", "source_type": "reference", "verified": false}
- doc_type must be one of: technical_spec, report, proposal"""

    elif artifact_type == ArtifactType.sheet:
        return """Generate a SheetContentTree JSON with this exact schema:
{
  "workbook_title": "Spreadsheet title",
  "tabs": [
    {
      "id": "tab1",
      "name": "Tab Name",
      "headers": ["Column1", "Column2", "Column3"],
      "rows": [["val1", 100, null], ["val2", 200, null]],
      "formulas": {"C2": "=B2*1.1"},
      "column_widths": [120, 80, 100]
    }
  ],
  "assumptions": "Key assumptions used in the model",
  "metadata": {
    "model_type": "...",
    "currency": "...",
    "visual_profile": "balanced|conservative|max",
    "palette_hint": "slate-executive|iron-neutral|sand-warm",
    "chart_plan": [
      {
        "tab_name": "Summary",
        "chart_type": "line|bar|pie|scatter",
        "title": "Chart title",
        "category_column": "Month",
        "value_columns": ["Revenue"],
        "x_column": "X (scatter only)",
        "y_column": "Y (scatter only)"
      }
    ]
  }
}

- column_widths must match the number of headers
- Use realistic sample data in rows
- Include formulas for calculated fields using Excel-style notation
- Each tab must have a unique id

FORMULA REQUIREMENTS:
- Include formulas for totals, growth percentages, and derived metrics where appropriate
- Formulas must start with '=' and use valid A1-notation cell references
- Cell references must point to cells within the same tab's data range
- Do not reference cells beyond the last data row or column
- NEVER create circular references: a formula must NOT reference its own cell
- NEVER create indirect circular references: if A2 references B2, then B2 must NOT reference A2 (or any chain back to A2)

FORMATTING CONVENTIONS:
- Use meaningful, descriptive headers (not generic "Column1", "Column2")
- Provide appropriate column_widths for each column (wider for text, narrower for numbers)
- Include an assumptions section when the data involves projections or estimates
- Set metadata.visual_profile to "balanced" unless the user explicitly asks otherwise
- Use metadata.palette_hint when a specific visual theme is obvious from context
- Provide metadata.chart_plan for chartable datasets (1-3 charts for balanced profile)
- chart_plan entries should prefer summary/pivot tabs when available

DATA INTEGRITY:
- All rows must have the same number of columns as headers
- Each tab must have a unique id and name
- Do not use placeholder content (TBD, Lorem ipsum, N/A for all values)
- Include at least one raw-data tab and one computed summary tab when applicable"""

    return ""


def get_draft_prompt_with_sequence(
    artifact_type: ArtifactType,
    outline: "Outline",
    slide_sequence: list[dict] | None = None,
) -> str:
    """Enhanced draft prompt that includes planned slide sequence."""
    base_prompt = get_draft_prompt(artifact_type, outline)

    if slide_sequence and artifact_type == ArtifactType.slides:
        sequence_hint = "\n\nPlanned slide sequence — You MUST use the exact slide_type specified for each position. Do NOT substitute content or image_text for the assigned type:\n"
        for i, s in enumerate(slide_sequence, 1):
            sequence_hint += f"  Slide {i}: slide_type={s['slide_type']} (MANDATORY), position={s['position']}\n"

        # Count content vs structural for mapping guidance
        content_count = sum(1 for s in slide_sequence if s["position"] == "body" and s["slide_type"] not in ("title", "section_divider"))
        outline_count = len(outline.items) if hasattr(outline, "items") else content_count
        sequence_hint += (
            f"\nThe outline contains {outline_count} content items. "
            f"These map 1:1 to the {content_count} body-position content slides above. "
            "Opening, closing, and section_divider slides are structural — generate "
            "appropriate content for them based on the deck's topic, not from specific outline items.\n"
        )
        base_prompt += sequence_hint

    return base_prompt


def get_sheet_visual_repair_prompt(outline: Outline, content_tree: Dict[str, Any]) -> str:
    """Build a focused prompt to enrich ONLY sheet visual metadata."""
    outline_json = json.dumps(outline.model_dump(mode="json"), indent=2)
    content_json = json.dumps(content_tree, indent=2)

    return f"""You are a spreadsheet visual designer. Your task is to improve ONLY visual metadata for an existing workbook.

Approved outline:
{outline_json}

Current SheetContentTree:
{content_json}

Return ONLY valid JSON in this exact schema:
{{
  "metadata": {{
    "visual_profile": "balanced|conservative|max",
    "palette_hint": "slate-executive|iron-neutral|sand-warm",
    "chart_plan": [
      {{
        "tab_name": "Existing tab name",
        "chart_type": "line|bar|pie|scatter",
        "title": "Chart title",
        "category_column": "Header name (for line/bar/pie)",
        "value_columns": ["Numeric header name"],
        "x_column": "Numeric header name (scatter only)",
        "y_column": "Numeric header name (scatter only)"
      }}
    ]
  }}
}}

Rules:
- Do NOT modify workbook_title, tabs, headers, rows, formulas, or assumptions
- Use only tab names and header names that already exist in the current content tree
- Keep chart_plan practical: 1-3 charts for balanced profile
- Prefer summary, stats, or pivot-like tabs when available
- If no chartable numeric data exists, return an empty chart_plan and visual_profile "balanced"
- Return ONLY the JSON object, no markdown fences or explanations"""


def get_edit_prompt(artifact_type: str, instruction: str, content_tree_json: str, target_map: str) -> str:
    """Build a prompt requesting a structured Patch JSON from the LLM."""
    return f"""You are a content editor. The user wants to modify an existing {artifact_type} artifact.

User instruction: {instruction}

Current content tree (JSON):
{content_tree_json}

Available targets:
{target_map}

Your task: Generate a Patch JSON that applies the user's instruction.

Return ONLY valid JSON in this exact format:
{{
  "artifact_type": "{artifact_type}",
  "target": {{
    "kind": "<target_kind>",
    ... target-specific fields ...
  }},
  "ops": [
    {{
      "op": "SET|INSERT_AFTER|DELETE",
      "path": "<dot-notation path, numeric indices only>",
      "value": "<new value for SET>",
      "item": "<item to insert for INSERT_AFTER>",
      "id_key": "<key for idempotency on INSERT_AFTER>"
    }}
  ],
  "summary": "Human-readable summary of the change"
}}

Target kinds:
- For slides: "deck" (for deck-level properties like deck_title), "slide_index" (with "index": 1-based), "slide_id" (with "id"), "slide_element" (with "element_id")
- For documents: "section_id" (with "id"), "heading_contains" (with "text")
- For sheets: "tab_name" (with "name"), "cell_range" (with "tab_name" and "a1")

Operation types:
- SET: Replace a value at the given path. Include "value".
- INSERT_AFTER: Append an item to a list at the given path. Include "item" and optionally "id_key".
- DELETE: Remove the value at the given path.

Rules:
- Path is relative to the resolved target (e.g., if target is slide 3, path "title" means slide 3's title)
- Path format: dot notation with numeric indices ONLY. Valid: "title", "content", "elements[0].content". NEVER use filter expressions like elements[?(@.id == "e7")] — instead use target kind "slide_element" with "element_id".
- To edit a specific element by id, set target kind to "slide_element" with "element_id" — then path is relative to that element (e.g. "content", "type").
- Use only existing target ids/indices from the target map
- IMPORTANT: "title", "speaker_notes", "deck_title", "subtitle", "heading" are plain strings. Never set them to objects/dicts — use a simple string value.
- Return ONLY the JSON object, no markdown fences or explanations"""


def get_edit_repair_prompt(artifact_type: str, instruction: str, failed_patch_json: str, error_message: str, target_map: str) -> str:
    """Build a retry prompt when the first patch attempt failed."""
    return f"""You are a content editor. Your previous patch attempt failed validation.

Original instruction: {instruction}

Your previous output:
{failed_patch_json}

Error message: {error_message}

Available targets:
{target_map}

Please fix the patch and return ONLY valid JSON matching the Patch schema:
{{
  "artifact_type": "{artifact_type}",
  "target": {{"kind": "...", ...}},
  "ops": [{{"op": "SET|INSERT_AFTER|DELETE", "path": "...", ...}}],
  "summary": "..."
}}

Rules:
- Fix the error identified above
- Path format: dot notation with numeric indices ONLY. Valid: "title", "content", "elements[0].content". NEVER use filter expressions like elements[?(@.id == "e7")] — instead use target kind "slide_element" with "element_id".
- To edit a specific element by id, set target kind to "slide_element" with "element_id" — then path is relative to that element (e.g. "content", "type").
- Use only valid target kinds and existing ids from the target map
- IMPORTANT: "title", "speaker_notes", "deck_title", "subtitle", "heading" are plain strings. Never set them to objects/dicts — use a simple string value.
- Return ONLY the JSON object, no markdown fences or explanations"""
