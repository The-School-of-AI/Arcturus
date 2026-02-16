
from core.skills.base import Skill

class ReporttoapppromptSkill(Skill):
    name = "reporttoappprompt"
    description = "Skill derived from ReportToAppPrompt.md"
    
    @property
    def prompt_text(self) -> str:
        return """# Report-to-App Generation Prompt

## 📋 USER GOAL
The user wants to convert a **structured report** (HTML/Markdown) into a **visual dashboard app** for the Agentic Platform.

**INPUT REPORT:**
{{REPORT_CONTENT}}

**GLOBALS CONTEXT (EXTRACTED DATA):**
{{GLOBALS_CONTENT}}

---

## YOUR TASK
Generate a valid `ui.json` configuration for a dashboard that visualizes this report.

You must:
1.  **Analyze the Report**: Identify key sections, metrics, data points, and tables.
2.  **Map to Components**:
    -   **Text Sections** -> `markdown` or `text` components. Use width 12 or 24.
    -   **Executive Summary** -> `summary` component (width 12 or 24).
    -   **Key Metrics** -> `metric` or `trend` components. Group them in a row.
    -   **Detailed Analysis** -> `markdown` cards (width 12).
    -   **Tables** -> `table` components. Extract rows/cols from text.
    -   **Comparisons** -> `bar_chart` or `peer_table`.
    -   **Trends** -> `line_chart` or `trend`.
3.  **Use Globals**: If `GLOBALS_CONTENT` contains raw data (e.g., JSON lists of competitors, stock prices), PREFER using that to populate charts over converting static text.
4. **Design**: You must keep the dashboard component heavy and interactive. Use charts, tables, and metrics to visualize the data. Do not use static text to visualize data. Less text, more charts.

## 🚨 LAYOUT RULES (CRITICAL)
1.  **Grid Width: 24 COLUMNS** – Every row must total exactly 24 width.
2.  **Row Height**: All components on the same Y-row MUST have the SAME height.
3.  **No Gaps**: x positions must be adjacent (0, 6, 12, 18).
4.  **Flow**: Start with a Header, then Summary/Metrics, then Charts/Tables, finally Detailed Text.

---

## COMPONENT CATALOG (SHORTLIST)

| Type | Label | W (Default) | H (Default) | Data |
|------|-------|---|---|---|
| `header` | Header | 24 | 2 | `{ text: "Title" }` |
| `summary` | Exec Summary | 12 or 24 | 5 | `{ text: "...", bullets: [] }` |
| `markdown` | Markdown Text | 12 or 24 | 6 | `{ content: "# Title\nBody..." }` |
| `metric` | Metric | 4 or 6 | 3 | `{ value: "100", change: 10, trend: "up" }` |
| `table` | Table | 12 or 24 | 6 | `{ headers: [], rows: [] }` |
| `bar_chart` | Bar Chart | 12 | 6 | `{ title: "", points: [{x,y,color}] }` |
| `line_chart` | Line Chart | 12 | 6 | `{ title: "", series: [] }` |
| `pie_chart` | Pie Chart | 12 | 6 | `{ title: "", slices: [] }` |
| `peer_table` | Comparison | 12 or 24 | 6 | `{ peers: [{ticker, metric}] }` |

---

## OUTPUT FORMAT
Return **ONLY valid JSON**.

```json
{
  "name": "App Name based on Report Title",
  "description": "Brief description...",
  "cards": [
    {
      "id": "header",
      "type": "header",
      "label": "Header",
      "config": { "centered": true },
      "data": { "text": "Report Title" },
      "style": {}
    }
  ],
  "layout": [
    { "i": "header", "x": 0, "y": 0, "w": 24, "h": 2 }
  ]
}
```

**THINK STEP BY STEP:**
1.  Extract the title.
2.  Extract the Executive Summary (create a `summary` or `markdown` card).
3.  Find all numbers/stats -> Make `metric` cards.
4.  Find tables/lists -> Make `table` or `bar_chart` cards.
5.  Find long text sections -> Make `markdown` cards.
6.  Assemble the grid, ensuring **Row Sum = 24** and **Same Height per Row**.

Generate now.
"""

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
