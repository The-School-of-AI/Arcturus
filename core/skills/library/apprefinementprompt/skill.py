
from core.skills.base import Skill

class ApprefinementpromptSkill(Skill):
    name = "apprefinementprompt"
    description = "Skill for refining existing app UI based on user input"
    
    @property
    def prompt_text(self) -> str:
        return """# App Refinement Prompt for Agentic Platform

## 📋 USER REQUEST

{{USER_PROMPT}}

---

## 🏗️ YOUR TASK

You are an expert UI developer. Current Data:
{{JSON_CONTENT}}

Based on the user's request above, REFINE the existing app configuration (`cards` and `layout`) to better meet their needs.

**You CAN:**
*   Add new components (`cards` + `layout`)
*   Remove existing components
*   Change layout positions (`x`, `y`, `w`, `h`)
*   Update component configuration (`config`) and data (`data`)
*   Change styles (`style`)

**You MUST:**
*   **Maintain the 24-Column Grid System** (See Rules Below)
*   **Keep existing IDs (`i`)** for components you want to preserve (do not assign new IDs to existing components unless necessary)
*   **Ensure 100% Fill Rate** (No gaps in rows)
*   **Generate Valid JSON** matching the schema

---

## 🚨 CRITICAL GRID RULES (24-COLUMN SYSTEM)

1.  **Grid Width: 24 COLUMNS** – Every row must total exactly 24 width.
2.  **Row Height: 1 unit ≈ 40px** – Use recommended heights.
3.  **NO GAPS** – Components on the same row must be adjacent (0 → 6 → 12 → 18).
4.  **100% FILL RATE** – Every row must be completely filled.
5.  **SAME HEIGHT PER ROW** – All components on the same `y` MUST have the same `h`.

---

## Component Catalog (Reference)

You can use any of these component types:

*   **Basics:** `header`, `text`, `markdown`, `image`, `spacer`, `divider`
*   **Charts:** `metric`, `trend`, `line_chart`, `bar_chart`, `area_chart`, `pie_chart`, `sankey`, `scatter`, `heatmap`, `table`
*   **Finance:** `profile`, `valuation`, `score_card`, `grade_card`, `peer_table`, `ratios`, `cash_flow`, `balance_sheet`, `income_stmt`
*   **Controls:** `button`, `input`, `textarea`, `select`, `checkbox`, `switch`, `slider`, `date_picker`, `tags_input`
*   **Complex Blocks:** `stats_01`, `stats_grid`, `usage_stats`, `accordion_table`

---

## Output Format

Return ONLY the complete, valid JSON object for the app. Output must be parseable by `json.loads()`.

```json
{
  "id": "...",
  "name": "...",
  "description": "...",
  "cards": [...],
  "layout": [...]
}
```
"""

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
