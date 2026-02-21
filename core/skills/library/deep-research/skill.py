
from core.skills.base import Skill


class DeepResearchSkill(Skill):
    name = "deep_research"
    description = "Teaches PlannerAgent to generate iterative deep research plans with focus modes"

    @property
    def prompt_text(self) -> str:
        return """

################################################################################################
# DEEP RESEARCH MODE — Iterative Multi-Phase Research Planning
# Activated when input contains: "research_mode": "deep_research"
################################################################################################

## WHEN TO USE THIS

If the input payload contains `"research_mode": "deep_research"`, you MUST generate an
**iterative deep research plan** instead of a standard plan. This plan uses the same agents
(RetrieverAgent, ThinkerAgent, SummarizerAgent, FormatterAgent) but structures them into
a multi-phase iterative research pipeline with gap analysis and targeted follow-up searches.

If `research_mode` is NOT "deep_research" (or is absent), IGNORE this section entirely
and plan normally.

---

## DEEP RESEARCH PLAN STRUCTURE (6 Phases)

### Phase 1: Query Decomposition (ThinkerAgent)
- Break the original query into 3-8 sub-queries that cover distinct dimensions
- Identify the key entities, concepts, and angles to research
- Consider temporal scope (historical vs current), geographic scope, and domain scope
- Output variables: `decomposed_queries_T001`, `research_dimensions_T001`

Example node:
```json
{
  "id": "T001",
  "description": "Decompose query into research sub-queries",
  "agent": "ThinkerAgent",
  "agent_prompt": "Break the following research query into 3-8 distinct sub-queries that cover different dimensions of the topic. For each sub-query, specify what aspect it investigates and why it matters. Query: '<original_query>'. Output a JSON object with keys: decomposed_queries (list of {query, dimension, rationale}), research_dimensions (list of dimension names).",
  "reads": ["original_query"],
  "writes": ["decomposed_queries_T001", "research_dimensions_T001"]
}
```

### Phase 2: Initial Broad Search (RetrieverAgent × N, parallel where possible)
- Create one RetrieverAgent task per sub-query (or batch 2-3 related sub-queries)
- Each RetrieverAgent uses `search_web_with_text_content` with `integer=10` to fetch 10 sources per sub-query
- IMPORTANT: Always pass `integer=10` (or up to 15) in the tool call to override the default of 5
- Example tool call in agent_prompt: "Use search_web_with_text_content with string='<sub_query>' and integer=10 to get 10 results with full text content"
- Collect: URL, title, snippet, full extracted text, publication date
- Apply focus_mode constraints to search queries (see FOCUS MODE section below)
- Output variables: `initial_sources_T00N` (one per retriever task)

### Phase 3: Gap Analysis (ThinkerAgent)
- Reads ALL initial source outputs from Phase 2
- Analyzes collected sources for:
  * Coverage gaps — dimensions with insufficient information
  * Conflicting claims — sources that disagree on facts
  * Weak evidence — claims supported by only 1 source
  * Missing perspectives — viewpoints not yet represented
- Generates targeted follow-up queries to fill gaps
- Output variables: `gap_analysis_T00N`, `followup_queries_T00N`, `contradictions_T00N`

Example node:
```json
{
  "id": "T005",
  "description": "Analyze research gaps and contradictions",
  "agent": "ThinkerAgent",
  "agent_prompt": "Analyze the following research sources for coverage gaps, contradictions, and weak evidence. For each gap, generate a targeted follow-up search query. Sources: <reads from Phase 2 outputs>. Output: gap_analysis (list of {dimension, gap_description, severity}), followup_queries (list of targeted queries), contradictions (list of {claim, source_a, source_b, details}).",
  "reads": ["initial_sources_T002", "initial_sources_T003", "initial_sources_T004"],
  "writes": ["gap_analysis_T005", "followup_queries_T005", "contradictions_T005"]
}
```

### Phase 4: Targeted Deep Search (RetrieverAgent × N)
- Execute follow-up queries from gap analysis
- These searches are more specific and targeted than Phase 2
- Use `search_web_with_text_content` with `integer=10` to get 10 results per follow-up query
- Apply focus_mode constraints
- Output variables: `deep_sources_T00N`

### Phase 5: Synthesis with Citations (SummarizerAgent)
- Reads ALL sources (initial + deep) plus gap analysis and contradictions
- Merges information into a coherent narrative
- MUST include:
  * Inline citations: every factual claim tagged with [source_index]
  * Per-paragraph confidence level: HIGH (3+ sources agree), MEDIUM (2 sources), LOW (1 source)
  * Contradiction surfacing: "Source A claims X, while Source B states Y"
  * Source agreement map: which sources support which claims
- Output variables: `research_synthesis_T00N`

### Phase 6: Report Generation (FormatterAgent)
- Generates structured comprehensive report with these sections:
  * **Executive Summary** — 3-5 sentence overview of findings
  * **Key Findings** — Numbered findings with confidence levels and citation refs
  * **Detailed Analysis** — Full narrative organized by research dimension
  * **Contradictions & Debates** — Where sources disagree
  * **Methodology** — Search queries used, number of sources analyzed, date range
  * **Complete Citations** — Numbered list with URL, title, publication date, snippet
- Output variables: `formatted_report_T00N`

---

## FOCUS MODE CONSTRAINTS

The input may contain a `focus_mode` field. When set, ALL RetrieverAgent tasks (Phase 2 and Phase 4)
MUST include focus-specific constraints in their `agent_prompt`:

### focus_mode: "academic"
- Append to search queries: `site:scholar.google.com OR site:arxiv.org OR site:pubmed.ncbi.nlm.nih.gov OR site:semanticscholar.org`
- Instruct RetrieverAgent: "Prioritize peer-reviewed papers, academic journals, and research institutions. Ignore blog posts and opinion pieces."
- Citations must use APA format: Author (Year). Title. Journal, Volume(Issue), Pages. DOI/URL
- Include: publication year, journal name, citation count if available

### focus_mode: "news"
- Append to search queries: `news OR latest OR breaking OR report`
- Instruct RetrieverAgent: "Prioritize recent news articles from the last 7 days. Include publication date prominently. Prefer established news outlets."
- Include publication date, outlet name, and reporter name in citations
- Sort findings by recency

### focus_mode: "code"
- Append to search queries: `site:github.com OR site:stackoverflow.com OR site:docs.python.org OR documentation`
- Instruct RetrieverAgent: "Prioritize code repositories, technical documentation, and developer forums. Extract code snippets and API examples."
- Include executable code blocks in report
- Citation format: Repository/Documentation name, URL, last updated date

### focus_mode: "finance"
- Append to search queries: `site:sec.gov OR financial report OR earnings OR market data OR investor`
- Instruct RetrieverAgent: "Prioritize SEC filings, financial reports, earnings calls, and market data sources. Extract numerical data, percentages, and financial metrics."
- Include data tables and numerical summaries in report
- Citation format: Company/Source, Filing type, Date, URL

### focus_mode: "writing"
- Instruct RetrieverAgent: "Focus on editorial content, style guides, writing techniques, and audience analysis. Look for examples of effective writing in the target genre/style."
- Report should include tone analysis, audience targeting suggestions, and style recommendations
- Less emphasis on citations, more on synthesis and creative guidance

### focus_mode: "general" (or absent)
- No special constraints. Use default search behavior.

---

## EDGE STRUCTURE FOR DEEP RESEARCH

**CRITICAL: Each edge MUST be an object with "source" and "target" keys.**

Example edges for a deep research plan:
```json
"edges": [
  {"source": "ROOT", "target": "T001"},
  {"source": "T001", "target": "T002"},
  {"source": "T001", "target": "T003"},
  {"source": "T002", "target": "T005"},
  {"source": "T003", "target": "T005"},
  {"source": "T005", "target": "T006"},
  {"source": "T006", "target": "T007"},
  {"source": "T007", "target": "T008"}
]
```

Edges must enforce this execution order:
1. ROOT → T001 (Query Decomposition)
2. T001 → T002, T003, T004 ... (Initial Search tasks — can be parallel)
3. T002, T003, T004 → T005 (Gap Analysis — waits for all initial searches)
4. T005 → T006, T007 ... (Targeted Search tasks — can be parallel)
5. T006, T007 → T008 (Synthesis — waits for all targeted searches)
6. T008 → T009 (Report Generation)

---

## IMPORTANT RULES FOR DEEP RESEARCH PLANS

1. Minimum 6 nodes, typically 8-12 nodes for thorough research
2. At least 2 RetrieverAgent tasks in Phase 2 (parallel sub-query searches)
3. ALWAYS include a Gap Analysis step (Phase 3) — this is what makes deep research iterative
4. ALWAYS include at least 1 targeted follow-up search (Phase 4) after gap analysis
5. The SummarizerAgent MUST receive ALL source outputs in its reads (both initial and deep)
6. Every variable in agent_prompt MUST appear in reads (standard planner rule applies)
7. Use the focus_mode constraints in EVERY RetrieverAgent agent_prompt when focus_mode is set

"""

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
