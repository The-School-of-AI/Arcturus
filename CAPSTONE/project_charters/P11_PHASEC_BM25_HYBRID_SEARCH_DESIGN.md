# Phase C: BM25 → Qdrant & Hybrid Search for Memories — Design

**Status:** Draft. Use this document as the implementation spec once locked.

---

## Overview

Phase C improves search quality and consistency by:
1. **3.1** Moving RAG keyword search from local BM25 (`rank_bm25` + `bm25_index.pkl`) into Qdrant
2. **3.2** Adding hybrid search (vector + keyword) for memories in `arcturus_memories`

Both items use Qdrant’s native capabilities instead of local indices, and both use RRF fusion for combining vector and keyword results.

---

## 3.1 Move BM25 to Qdrant (RAG)

### Current State

| Component | Location | Role |
|-----------|----------|------|
| BM25 corpus | `metadata` from Qdrant `get_metadata()` or `faiss_index/metadata.json` | Chunk text for keyword search |
| BM25 index | `mcp_servers/faiss_index/bm25_index.pkl` | Local rank_bm25 index |
| Search flow | `server_rag.search_stored_documents_rag()` | Vector search → BM25 search → RRF fuse → entity gate |

**Limitations:** Local BM25 is user-specific only when Qdrant is tenant-scoped (`get_metadata(user_id)`); `bm25_index.pkl` is rebuilt/loaded per user or at reindex time; no single source of truth; sync/multi-device concerns.

### Target Architecture

Use Qdrant for both vector and keyword search on `arcturus_rag_chunks`:

- **Option A (recommended): Sparse vectors + BM25 model**  
  Add a sparse vector to `arcturus_rag_chunks`, generated from chunk text via BM25 (e.g. `qdrant/bm25` or FastEmbed). Use Qdrant Query API with prefetch (dense + sparse) and RRF fusion.

- **Option B (simpler): Full-text payload index**  
  Create a full-text payload index on the chunk text field. Use it for lexical matching/filtering. Combine with vector search and fuse (e.g. RRF) on the application side. Less ranking flexibility than Option A.

This design assumes **Option A** for best ranking. Option B can be used if sparse vectors are not available (e.g. older Qdrant, no inference endpoint).

### Option A: Sparse Vectors (BM25) + Hybrid Search

#### Collection Changes

- `arcturus_rag_chunks` remains the single collection.
- Add a sparse vector `chunk-bm25` with `modifier: idf` (IDF for BM25-style scoring).
- Dense vector stays as the default/named vector; sparse is a second named vector.

#### Config (qdrant_config.yaml)

```yaml
arcturus_rag_chunks:
  dimension: 768
  distance: cosine
  is_tenant: true
  tenant_keyword_field: user_id
  indexed_payload_fields: [doc, doc_type, session_id, space_id]
  # Phase C: sparse vector for BM25 hybrid search
  sparse_vectors:
    chunk-bm25:
      modifier: idf   # for BM25 / IDF-based sparse scoring
```

#### Ingest Path

- When adding chunks, generate sparse vectors from chunk text using:
  - **Qdrant inference:** `models.Document(text=chunk_text, model="qdrant/bm25")` (requires Qdrant Cloud or configured inference)
  - **Client-side:** FastEmbed BM25 or equivalent to produce sparse (indices, values)
- Each point has: `vector` (dense) + `chunk-bm25` (sparse).
- No change to `user_id` / `space_id` payload fields.

#### Search Path

- Use Query API `prefetch`:
  - Prefetch 1: dense vector search (existing embedding) with `user_id` / `space_id` filter
  - Prefetch 2: sparse search on `chunk-bm25` with query text (same filters)
- Fuse with `query: FusionQuery(fusion=Fusion.RRF)`.
- Apply entity gate on fused results as today.

#### Fallback if Sparse Vectors Unavailable

- If Qdrant version or deployment does not support sparse vectors / BM25 inference:
  - Use Option B (full-text index) for lexical retrieval
  - Or keep local BM25 temporarily, but scope by `user_id` and avoid `bm25_index.pkl` sharing across users

### Option B: Full-Text Payload Index (Simpler)

- Create a full-text payload index on the field holding chunk text (e.g. `chunk`).
- Use `query_filter` with a `text` condition for keyword matching.
- Run vector search and full-text search separately, then RRF-fuse in application code.
- No sparse vectors; works with standard Qdrant deployments.

### Removals (After Migration)

- `BM25Index` class, `_bm25_index`, and `bm25_index.pkl` build/load in `server_rag.py`
- `rank_bm25` dependency (optional: keep only if used elsewhere)
- Any logic that reads `faiss_index/metadata.json` solely for BM25

### Migration

- Reindex all RAG chunks so new points include sparse vectors (or full-text index is populated).
- Migration script should pass chunk text to the BM25/sparse vector pipeline.
- No backfill of `bm25_index.pkl`; it is deprecated.

---

## 3.2 Hybrid Search for Memories

### Current State

| Component | Role |
|-----------|------|
| `memory_retriever.retrieve()` | Orchestrates semantic + entity + graph recall |
| `QdrantVectorStore.search()` | Vector search; optional `_apply_keyword_boosting` on results |
| Entity recall | NER → Neo4j → memory IDs |
| Graph expansion | From semantic results’ `entity_ids` |

**Gap:** Memory retrieval is vector + entity + graph. There is no true keyword/BM25 path; `_apply_keyword_boosting` only re-ranks vector results by keyword overlap.

### Target Architecture

Add a keyword/lexical search path for memories and fuse it with vector search via RRF, mirroring the RAG pattern.

- **Option A (recommended):** Sparse vector `text-bm25` on memory text in `arcturus_memories`; prefetch hybrid + RRF.
- **Option B:** Full-text payload index on memory `text`; run full-text search + vector search; RRF fuse in app.

### Option A: Sparse Vectors for Memories

#### Collection Changes

- Add sparse vector `text-bm25` to `arcturus_memories` with `modifier: idf`.
- Dense vector remains the default vector.

#### Config (qdrant_config.yaml)

```yaml
arcturus_memories:
  dimension: 768
  distance: cosine
  is_tenant: true
  tenant_keyword_field: user_id
  indexed_payload_fields: [category, source, session_id, entity_labels, space_id, archived, visibility]
  sparse_vectors:
    text-bm25:
      modifier: idf
```

#### Ingest Path

- On `add()` (and during migration): generate sparse vector from memory `text` via `qdrant/bm25` or client-side BM25; store as named vector `text-bm25`.

#### Search Path

- In `_semantic_recall` (or equivalent), use prefetch:
  - Dense vector search (current flow)
  - Sparse search on `text-bm25` with `query_text`
- Fuse with RRF.
- Then run entity recall and graph expansion as today.
- Space/session filters apply to both prefetches.

### Integration with Existing Flow

- `memory_retriever.retrieve()` already passes `query_text` into `store.search()`.
- Extend `QdrantVectorStore.search()` to:
  - If `query_text` and sparse vector available: run hybrid prefetch, RRF, return fused list.
  - Else: current vector-only search (and optional `_apply_keyword_boosting` as fallback).
- Entity recall and graph expansion stay unchanged; they consume the fused semantic results.

### Fallback

- If sparse vectors are not configured: skip keyword prefetch; use vector-only search + `_apply_keyword_boosting` (current behavior).

---

## Dependencies and Order

| Step | Item | Depends On |
|------|------|------------|
| 1 | 3.1 BM25 → Qdrant (RAG) | None |
| 2 | 3.2 Hybrid search for memories | 3.1 (reuse pattern, config, and tooling) |

Implement 3.1 first; then apply the same pattern for memories in 3.2.

---

## Qdrant Version and Inference

- **Sparse vectors:** Qdrant 1.7+ (confirm exact version in use).
- **BM25 inference:** `qdrant/bm25` requires Qdrant Cloud or a configured inference endpoint. For self-hosted, use client-side BM25 (e.g. FastEmbed, `rank_bm25` for sparse index generation) and upsert sparse vectors.
- **Full-text index (Option B):** Supported in recent Qdrant; no inference required.

---

## Config Summary

### qdrant_config.yaml Additions

```yaml
# arcturus_rag_chunks - add:
  sparse_vectors:
    chunk-bm25:
      modifier: idf

# arcturus_memories - add:
  sparse_vectors:
    text-bm25:
      modifier: idf
```

---

## Implementation Checklist

### 3.1 BM25 to Qdrant (RAG)

- [ ] Add `chunk-bm25` sparse vector config to `arcturus_rag_chunks` in qdrant_config
- [ ] Update `QdrantRAGStore.add_chunks()` to generate and store sparse vectors from chunk text
- [ ] Add `search_hybrid()` (or extend `search()`) in `QdrantRAGStore` using prefetch + RRF
- [ ] Update `server_rag.search_stored_documents_rag()` to use Qdrant hybrid search when provider is Qdrant; remove BM25Index / bm25_index.pkl
- [ ] Update migration script to populate sparse vectors for existing RAG chunks
- [ ] Optional: remove `rank-bm25` from pyproject.toml if unused

### 3.2 Hybrid Search for Memories

- [ ] Add `text-bm25` sparse vector config to `arcturus_memories` in qdrant_config
- [ ] Update `QdrantVectorStore.add()` to generate and store sparse vector from memory text
- [ ] Extend `QdrantVectorStore.search()` to use hybrid prefetch + RRF when `query_text` is provided
- [ ] Add migration/backfill for existing memories (sparse vectors)
- [ ] Deprecate or simplify `_apply_keyword_boosting` when hybrid is active

---

## Open Decisions

1. **Inference source:** Use Qdrant server-side `qdrant/bm25` vs client-side BM25 (FastEmbed / rank_bm25) for sparse vector generation. Client-side is more portable.
2. **Option B vs Option A:** If sparse vectors are not feasible, adopt full-text index + app-side RRF for both RAG and memories.
3. **Entity gate:** Keep entity gate in RAG search after fusion; no change to current behavior.
4. **Backward compatibility:** FAISS RAG backend remains vector-only; BM25 is only for Qdrant backend. Document that hybrid requires `RAG_VECTOR_STORE_PROVIDER=qdrant`.
