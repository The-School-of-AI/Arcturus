# P11 Graph Query via Planner — Design Doc

**Gap addressed:** No dedicated API for graph-style reasoning ("What do I know about X and how does it relate to Y?").

**Approach:** Make the planner agent smarter so runs that ask graph-reasoning questions produce a plan that uses tools (entity extraction → KG query → summarizer) instead of building a monolithic backend API.

---

## 1. Overview

When a user asks *"What do I know about John and how does he relate to Acme Corp?"*, the planner should:

1. **Extract entities** from the query (e.g. John, Acme Corp)
2. **Query the knowledge graph** to find entities, relationships, paths, and user facts
3. **Summarize** the structured result into a natural-language answer

This is implemented as tools and plan steps, not a single backend endpoint.

---

## 2. Flow

```
User: "What do I know about John and how does he relate to Acme Corp?"
    │
    ▼
Planner recognizes graph-reasoning query
    │
    ├─► Step 1: Extract entities
    │       Tool: entity_extract(query) → ["John", "Acme Corp"]
    │
    ├─► Step 2: Query knowledge graph
    │       Tool: kg_query_paths(entity_names=["John", "Acme Corp"])
    │       Returns: { entities, relationships, paths, user_facts }
    │
    └─► Step 3: Summarize
            Formatter/Summarizer agent produces natural-language answer
```

---

## 3. Components

### 3.1 KG Query Tool (MCP or native)

- **Input:** `entity_names: string[]`, optional `space_id`
- **Output:** Structured JSON:
  - `entities`: matched nodes (id, name, type)
  - `relationships`: entity–entity edges
  - `paths`: paths between requested entities (1–2 hops)
  - `user_facts`: user–entity facts (LIVES_IN, WORKS_AT, etc.)
- **Implementation:** Add `get_entities_paths_and_facts()` (or similar) to `knowledge_graph.py`; expose via MCP tool or native tool registry.

### 3.2 Entity Extraction Tool

- **Input:** query text
- **Output:** list of entity names
- **Implementation:** Wrap existing `EntityExtractor.extract_from_query()` or equivalent.

### 3.3 Planner Awareness

- Planner must recognize graph-reasoning questions (e.g. "what do I know about X", "how does X relate to Y", "what’s the connection between X and Y").
- Approach: instructions, few-shot examples, or pattern hints in the planner prompt.

### 3.4 Summarizer / Formatter Agent

- Receives structured KG output and produces a concise natural-language answer for the user.

---

## 4. Backend Additions (knowledge_graph.py)

Add a method that:

1. Resolves `entity_names` to Neo4j entity IDs (use `resolve_entity_candidates`)
2. Finds entity–entity relationships and paths (e.g. Neo4j `shortestPath` / `allShortestPaths`)
3. Fetches user–entity facts (LIVES_IN, WORKS_AT, KNOWS, PREFERS)
4. Returns a structured dict for the summarizer

---

## 5. Benefits

- **Reuses existing code** — Entity extractor and KG logic already exist
- **Tool-first** — KG call is a tool; planner decides when to use it
- **Composable** — Plan can mix KG query with retrieval, preferences, etc.
- **Clear separation** — Backend exposes tools; orchestration handles flow

---

## 6. Dependencies

- Planner reliability for recognizing graph-reasoning intents
- MCP tool wiring or native tool registration for the KG tool

---

## 7. Future / Optional

- LLM-based intent detection instead of pattern-based
- "Explain this relationship" in the graph explorer UI using the same tools
