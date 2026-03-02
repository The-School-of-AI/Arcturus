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
- Plan a narrative arc: opening hook, problem statement, solution overview, evidence/data, call to action
- Each outline item represents one slide
- Suggest 8-12 slides unless the user specifies a count
- Include speaker notes suggestions in descriptions — these become presenter notes in the exported PPTX
- Consider slide types and pick the best fit for each slide's content:
  * title — Opening/closing slides with large centered text
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
  * section_divider — Section break slide with large section number and title (use between major topic shifts)
  * agenda — Table of contents / overview with numbered cards (use as slide 2 after title)
  * table — Data table with styled header row, alternating bands, and optional status badges
- When the topic involves data, metrics, or KPIs, prefer stat or chart slide types
- For decks with 10+ slides, insert 1-2 section_divider slides to break the deck into logical sections
- Include an agenda slide as slide 2 (after title) for decks with 8+ slides
- Use table slide type when comparing platforms, tools, or features across dimensions
- Number content titles with section prefix (e.g., "1.1 Title - Subtitle") to group under section dividers
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
  "metadata": {"model_type": "...", "currency": "..."}
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
        base_prompt += sequence_hint

    return base_prompt
