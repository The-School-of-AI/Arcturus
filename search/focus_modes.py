"""
search/focus_modes.py
Domain-filter configs per focus mode. Works by appending site: prefixes to sub-queries.
"""
from dataclasses import dataclass, field


@dataclass
class FocusConfig:
    name: str
    label: str
    description: str
    search_suffix: str
    retriever_instruction: str
    citation_format: str = "standard"
    decomposition_hint: str = ""
    freshness: str = ""  # Brave freshness value (pd/pw/pm/py), empty = no filter


FOCUS_CONFIGS: dict[str, FocusConfig] = {
    "web": FocusConfig(
        name="web",
        label="Web",
        description="Open web search across all sources",
        search_suffix="",
        retriever_instruction="Use default search behavior.",
        citation_format="standard",
        decomposition_hint="Apply general research best practices.",
    ),
    "academic": FocusConfig(
        name="academic",
        label="Academic",
        description="Prioritize arXiv, Google Scholar, PubMed, Semantic Scholar",
        search_suffix="site:scholar.google.com OR site:arxiv.org OR site:pubmed.ncbi.nlm.nih.gov OR site:semanticscholar.org",
        retriever_instruction="Prioritize peer-reviewed papers, academic journals, and research institutions. Ignore blog posts and opinion pieces.",
        citation_format="apa",
        decomposition_hint="Focus on academic and scholarly angles — peer-reviewed research, theoretical frameworks, key researchers, institutions, and landmark papers.",
    ),
    "news": FocusConfig(
        name="news",
        label="News",
        description="Prioritize recent news articles and journalism",
        search_suffix="news OR latest OR breaking OR report",
        retriever_instruction="Prioritize recent news from the last 7 days. Include publication dates. Prefer established news outlets.",
        citation_format="standard",
        decomposition_hint="Focus on recent events, breaking developments, policy changes, and current affairs angles.",
        freshness="pw",  # past week
    ),
    "code": FocusConfig(
        name="code",
        label="Code",
        description="Prioritize GitHub, StackOverflow, and technical documentation",
        search_suffix="site:github.com OR site:stackoverflow.com OR site:docs.python.org OR documentation",
        retriever_instruction="Prioritize code repositories, technical documentation, and developer forums. Extract code snippets and API examples.",
        citation_format="standard",
        decomposition_hint="Focus on technical implementation, APIs, libraries, frameworks, code architecture, and developer ecosystem.",
    ),
    "finance": FocusConfig(
        name="finance",
        label="Finance",
        description="Prioritize SEC filings, earnings, and market data",
        search_suffix="site:sec.gov OR financial report OR earnings OR market data OR investor",
        retriever_instruction="Prioritize SEC filings, financial reports, earnings calls, and market data sources. Extract numerical data, percentages, and financial metrics.",
        citation_format="standard",
        decomposition_hint="Focus on financial aspects — market data, companies, valuations, economic impact, investment angles, and regulatory landscape.",
        freshness="pm",  # past month
    ),
    "writing": FocusConfig(
        name="writing",
        label="Writing",
        description="Focus on editorial content, style guides, and writing techniques",
        search_suffix="",
        retriever_instruction="Focus on editorial content, style guides, writing techniques, and audience analysis. Look for examples of effective writing in the target genre/style.",
        citation_format="standard",
        decomposition_hint="Focus on narrative craft, communication styles, audience analysis, and editorial perspectives.",
    ),
}


def get_focus_config(mode: str) -> FocusConfig:
    """Return config for *mode*, defaults to 'web' for unknown modes."""
    return FOCUS_CONFIGS.get(mode, FOCUS_CONFIGS["web"])


def list_focus_modes() -> list[FocusConfig]:
    """Return all available focus configs."""
    return list(FOCUS_CONFIGS.values())


def apply_focus(sub_queries: list[str], mode: str) -> list[str]:
    """Append the focus mode's search suffix to each sub-query.

    If the mode has no suffix (web, writing), queries are returned unchanged.
    """
    cfg = get_focus_config(mode)
    if not cfg.search_suffix:
        return sub_queries
    return [f"{q} {cfg.search_suffix}" for q in sub_queries]
