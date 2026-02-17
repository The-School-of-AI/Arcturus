# PROJECT 2: "Oracle" — AI-Powered Search & Research Engine


> **Inspired by:** Perplexity (answer engine, citations, deep research, real-time web crawling)
> **Team:** AI/Search Engineering · **Priority:** P0 · **Duration:** 4 weeks

### Objective
Build an **answer engine** that, given any query, crawls the web in real-time, synthesizes information from multiple sources, and returns a comprehensive answer **with inline citations** — matching and exceeding Perplexity's capabilities.

### Detailed Features

#### 2.1 Real-Time Web Crawling Pipeline
- **Query decomposition agent:** Break complex queries into 3-8 sub-queries for parallel search
- **Search backends:** Integration with Brave Search API (primary), Bing Web Search API (fallback), Google Custom Search API (fallback)
- **Parallel crawler:** Fetch top 10-20 URLs per sub-query concurrently with 5s timeout
- **Content extraction:** Readability-based article extraction, PDF parsing, table extraction
- **Freshness scoring:** Prefer recent content, time-decay weighting for results
- **Rate limiting & caching:** Semantic cache (Redis) — identical/similar queries reuse cached results within TTL

#### 2.2 Answer Synthesis Engine
- **Multi-source fusion:** Merge extracted content from 20-50 sources into coherent narrative
- **Citation system:** Every claim tagged with `[source_index]` inline, clickable footnotes with URL, title, timestamp, credibility score
- **Confidence scoring:** Per-paragraph confidence level (HIGH/MEDIUM/LOW) based on source agreement
- **Contradiction detection:** Surface conflicting information explicitly: "Source A claims X, while Source B states Y"
- **Anti-hallucination guardrails:** Cross-reference generated claims against source text, flag unsupported statements

#### 2.3 Deep Research Mode
- **Multi-step research:** Agent performs iterative search → read → synthesize → identify gaps → search again (up to 5 iterations)
- **Research plan transparency:** Show the user the search plan before executing, allow modification
- **Progress streaming:** Real-time updates as each source is processed: "Reading article 7/23..."
- **Comprehensive reports:** Output structured reports with executive summary, key findings, methodology, sources

#### 2.4 Focus Modes
- **Academic:** Prioritize Google Scholar, arXiv, PubMed, Semantic Scholar — format citations in APA/MLA/Chicago
- **News:** Prioritize news APIs, recent articles, trending topics — include publication date prominence
- **Video:** Search YouTube, Vimeo — extract transcripts, timestamp-linked summaries
- **Code:** Search GitHub, Stack Overflow, documentation sites — include executable code blocks
- **Finance:** Pull from financial APIs, SEC filings, market data — include charts and data tables
- **Writing:** Focus on creative/editorial assistance — tone adjustments, audience targeting

#### 2.5 Multimodal Search
- **Image search & analysis:** Reverse image search, visual question answering on uploaded images
- **PDF/document analysis:** Upload PDFs, extract content, answer questions about the document
- **Data analysis:** Upload CSV/Excel, auto-generate statistical summaries and visualizations

#### 2.6 Internal Knowledge Search
- **Workspace search:** Search across user's local files, episodic memory, previous conversations
- **Unified results:** Blend web results with internal knowledge, clearly delineating provenance
- **Spaces & Collections:** Let users organize research into persistent spaces for ongoing projects

#### 2.7 Deliverables
- `search/crawl_pipeline.py` — parallel web crawler with content extraction
- `search/query_decomposer.py` — multi-query strategy generator
- `search/synthesizer.py` — multi-source answer fusion with citations
- `search/deep_research.py` — iterative deep research orchestrator
- `search/focus_modes.py` — per-domain search specialization
- `routers/search.py` — API endpoints for search features
- Frontend: `features/search/` — rich search UI with citation sidebar, streaming results, focus mode selector

### Strategy
- Day 1-5: Web crawling pipeline + basic search integration
- Day 6-10: Answer synthesis with citations
- Day 11-15: Deep Research mode
- Day 16-20: Focus modes (Academic, News, Code first)
- Day 21-30: Multimodal search + Internal knowledge search

---

## 20-Day Execution Addendum

### Team Split
- Student A: Retrieval, ranking, and citation grounding pipeline.
- Student B: Synthesis engine, confidence model, research UI/API contract.

### Day Plan
- Days 1-5: Query decomposition + multi-source fetch.
- Days 6-10: Source ranking, evidence graph, citation format.
- Days 11-15: Deep research mode, plan transparency, contradiction alerts.
- Days 16-20: Performance tuning and benchmark suite.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p02_oracle/test_citations_back_all_claims.py`
- Integration: `tests/integration/test_oracle_source_diversity.py`
- CI required check: `p02-oracle-research`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Every factual claim in final answer must map to at least one citation, and contradiction labeling must be present when sources disagree.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Oracle can consume Mnemo memory context and Phantom browser captures while preserving citation traceability.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p02-oracle-research must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P02_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 3.0s standard search response latency.
