# RAG: FAISS → Qdrant — Unified notes

This document merges findings from code review of **Arcturus** with external research notes. Paths are relative to the repo root.

**Implementation plan (Qdrant-first listing, spaces, optional S3):** [rag_qdrant_implementation_plan.md](./rag_qdrant_implementation_plan.md).

## What `RAG_VECTOR_STORE_PROVIDER=qdrant` actually changes

It switches **where vectors are stored and searched** in the RAG MCP server (`mcp_servers/server_rag.py` via `memory.rag_store.get_rag_vector_store()`): chunks go to Qdrant (default collection **`arcturus_rag_chunks`** per `config/qdrant_config.yaml` / `memory/rag_backends/qdrant_rag_store.py`), and `rag_store.search()` uses Qdrant (including hybrid sparse + dense when configured).

It does **not** by itself replace:

- The **document tree** HTTP API (`GET /api/rag/documents`)
- All uses of **`mcp_servers/faiss_index/metadata.json`** and **`ledger.json`**
- **Local `data/`** as the place source files live on disk

So “still seeing local files” for `/api/rag/documents` is **expected** with the current code.

---

## Why things still touch local files / FAISS paths

### 1. Document list API

**`routers/rag.py` → `GET /api/rag/documents`**

- Builds the tree from **`PROJECT_ROOT / "data"`** (local filesystem).
- Enriches each file with **`indexed` / `status` / `chunk_count`** from **`mcp_servers/faiss_index/ledger.json`** (or legacy **`doc_index_cache.json`**).
- **Does not** query Qdrant.

The UI “RAG documents” list is **file-first + local ledger**, not “what exists only in Qdrant.”

### 2. MCP server: metadata and hybrid search

**`search_stored_documents_rag`** (`mcp_servers/server_rag.py`)

- Vector/hybrid retrieval uses **`rag_store.search()`** → Qdrant when provider is `qdrant`.
- **Chunk text and doc paths** (entity gate, keyword fallback, final assembly) come from a **`metadata` list**:
  - If **`use_qdrant`**, the store has **`get_metadata`**, and **`user_id` is set** → metadata is loaded by **`QdrantRAGStore.get_metadata(user_id=...)`** (scrolls Qdrant payloads).
  - **Otherwise** → reads **`mcp_servers/faiss_index/metadata.json`**.

So the Qdrant path still depends on **`user_id`** being passed through; without it, behavior can fall back to **`metadata.json`**.

**`keyword_search`**

- Tries **ripgrep on `data/`** first.
- On failure / no rg → scans **`metadata.json`** for substring matches in chunk text.

**`advanced_ripgrep_search`**

- Primarily **ripgrep on `data/`** (and related paths).
- **Additionally** scans **`metadata.json`** so **PDF/binary-derived chunks** (not line-addressable like plain files) can still match — it **supplements** rg, not only “rg failed.”

### 3. Indexing and “ready” checks

- **`process_documents`** still writes **`metadata.json`**, **`ledger.json`**, and (for FAISS) **`index.bin`**. Comments in code note **`metadata.json`** supports BM25 / lexical flows.
- **`ensure_rag_ready()`**: with Qdrant, **`metadata.json` existing** still gates “RAG ready”; missing **`index.bin`** alone does not force a full reindex when Qdrant is enabled.

### 4. Migration script

**`scripts/migrate_rag_faiss_to_qdrant.py`** copies data into Qdrant but does not remove the need for **`metadata.json`** for the flows above. Set **`RAG_VECTOR_STORE_PROVIDER=qdrant`** for search to use Qdrant; local index files may still be required for listing, fallbacks, and tooling.

### 5. Collection naming

The codebase defaults to **`arcturus_rag_chunks`**. A custom collection (e.g. `arcturus_rag`) must align with **`QdrantRAGStore`** / **`get_rag_vector_store(..., collection_name=...)`** and **`qdrant_config.yaml`**.

---

## Spaces: why “Global” shows files but another space shows nothing

This is **filesystem layout**, not Qdrant. The document tree does not read spaces from the DB or Qdrant—it **filters the `data/` tree by folder names** that must match the space model.

### How the frontend passes `space_id`

| UI space | `currentSpaceId` in store | `GET /api/rag/documents` query |
|----------|---------------------------|--------------------------------|
| **Global** | `null` | **`space_id` omitted** — no server-side filter |
| **A specific space** | that space’s UUID (string) | `?space_id=<uuid>` |

RAG panel and notes refresh when `currentSpaceId` changes (`RagPanel.tsx` `useEffect` → `fetchRagFiles`; `NotesPanel` → `fetchNotesFiles`). Both use the same pattern in `platform-frontend/src/store/index.ts`: `params.space_id = spaceId` only when `spaceId` is set.

So **Global = full `data/` tree**. **Any other space = only subtrees whose folder name equals that UUID (or `__global__` when that branch of the filter runs).**

### What the backend expects on disk (`routers/rag.py`)

When **`space_id` is present** (non-null query param), after building the full tree from `data/`:

1. **First**, it tries **top-level** folders under `data/`:
   - For `space_id == "__global__"` *or* empty-ish handling inside `_filter_tree_by_space`: keep only the child named **`__global__`** if it exists; if there is no `data/__global__/`, it **falls back to the full top-level list** (backward compatibility).
   - For a **normal space UUID**: keep only the top-level folder whose **`name` equals that UUID** exactly: `data/<space_uuid>/`.

2. **If that yields nothing**, it applies the **same rule under `data/Notes/`**:
   - Looks for `data/Notes/__global__/` vs `data/Notes/<space_uuid>/`.

If **neither** `data/<uuid>/` **nor** `data/Notes/<uuid>/` exists, the API returns **`files: []`** → the UI looks **empty**. That is expected with the current code.

### Common reasons you see nothing for a non-Global space

- All your content lives under paths like **`Notes/Ideas/...`**, **`Notes/SomeName/...`**, or loose under **`data/`** without a segment that is **exactly** the space UUID or **`__global__`** under `Notes/`.
- You never created **`data/Notes/<your-space-uuid>/`** (or **`data/<your-space-uuid>/`**) and moved or added files there.
- **Global** still shows everything because **no `space_id` is sent**, so **no filter** runs—not because “Global” is wired to Qdrant or a space registry.

### How this relates to indexing / Qdrant `space_id`

When files **are** under `Notes/...`, the MCP server derives Qdrant payload **`space_id`** from the path (`mcp_servers/server_rag.py` → `_derive_space_id_for_notes`):

- `Notes/__global__/...` → global scope constant (e.g. `__global__`).
- `Notes/<valid-uuid>/...` → that UUID.
- Anything else under `Notes/` (e.g. `Notes/Ideas/...`) → falls back to **global** for vector storage unless a default is passed.

So you can have chunks in Qdrant tagged for **global** while the **UI space filter** hides them because the **on-disk tree** for that UUID folder doesn’t exist. **Listing and Qdrant scoping use different rules** until paths follow the convention.

### Semantic search vs document list (space)

- **`GET /api/rag/search`** forwards **`space_id`** to the MCP tool so Qdrant search can filter by tenant/space payloads (`routers/rag.py` → `rag_search`).
- **`GET /api/rag/documents`** only filters the **directory tree** as above; it does **not** list “everything Qdrant knows for this space.”

### What to do in practice (no code changes)

For a space to show documents in RAG / Notes sidebars:

1. Create **`data/Notes/<space-uuid>/`** (or **`data/<space-uuid>/`** for non-Notes RAG layout).
2. Put that space’s files (or symlinks) under that folder.
3. Reindex as needed so ledger + Qdrant stay aligned.

### Roadmap tie-in (spaces)

A future improvement would be: **document list** that can show “all files indexed with this `space_id` in Qdrant” or merge DB-backed spaces with disk layout—today it is **folder-name == space id** only.

---

## Roadmap: toward a more Qdrant-centric RAG

| Area | Today | If you want Qdrant as primary source of truth |
|------|--------|-----------------------------------------------|
| **Document list** | `data/` + `ledger.json` | Add Qdrant-backed **document discovery** (e.g. aggregate distinct `doc` from payloads, optionally merge with `data/`), or a **provider-agnostic ledger** (DB or service) updated on index/delete. |
| **Per-space file tree** | Folder name must be **`__global__`** or **`<space_uuid>`** under `data/` or `data/Notes/` | Same as document list: drive UI from Qdrant `space_id` + `doc` paths, or enforce path convention via tooling/UI when creating spaces. |
| **Search metadata** | `get_metadata(user_id)` **or** `metadata.json` | Always resolve chunk text from **Qdrant payloads** when provider is qdrant; ensure **`user_id`** (and **`space_id`** where needed) is passed from API/agents so you don’t silently fall back to disk. |
| **Keyword / rg** | `data/` + `metadata.json` fallbacks | Optionally add **Qdrant payload / full-text** indexing, or keep rg on `data/` for source files and Qdrant only for extracted chunks. |
| **Hybrid / BM25** | Local `metadata.json` + entity gate over that list | Either keep a derived file synced from Qdrant, or lean on **Qdrant sparse vectors + filters** (dense+sparse RRF is already used when configured). |
| **Indexing status** | `ledger.json` + scheduler | Decouple status from FAISS-specific files: external ledger, or **status derived from Qdrant** + reconciliation with `data/`. |

Using **MongoDB** (or another DB) for a document ledger is an architectural option; Arcturus may use Mongo elsewhere (e.g. ops/watchtower), but the RAG router does **not** use it for the document list today.

---

## Short summary

1. **`/api/rag/documents` uses local files** by design: it walks **`data/`** and reads **`faiss_index/ledger.json`** (or legacy cache). It never calls Qdrant.
2. **`RAG_VECTOR_STORE_PROVIDER=qdrant`** affects **vector storage and search** in the MCP RAG server, not that HTTP handler.
3. **Search** can still use **`metadata.json`** if the Qdrant metadata path isn’t taken (e.g. missing **`user_id`**). **Keyword** and **advanced ripgrep** paths also use **`metadata.json`** for fallbacks or PDF chunk search.
4. **Full switch** means updating **document listing**, **metadata sourcing** for tools, and optionally **keyword/hybrid** behavior, plus clear **ledger / readiness** rules that aren’t tied only to `faiss_index` filenames.
5. **Non-Global spaces look empty** when there is no `data/<uuid>/` or `data/Notes/<uuid>/` folder matching the selected space; **Global** sends no `space_id`, so you see the whole `data/` tree.

---

## Related files

| Component | Path |
|-----------|------|
| Document list API + space filter | `routers/rag.py` — `GET /documents`, `_filter_tree_by_space` |
| RAG semantic search + `space_id` | `routers/rag.py` — `rag_search` |
| RAG MCP tools | `mcp_servers/server_rag.py` — `_derive_space_id_for_notes`, `search_stored_documents_rag` |
| Vector store factory | `memory/rag_store.py` |
| Qdrant backend | `memory/rag_backends/qdrant_rag_store.py` |
| FAISS backend | `memory/rag_backends/faiss_rag_store.py` |
| Qdrant collection config | `config/qdrant_config.yaml` |
| FAISS → Qdrant migration | `scripts/migrate_rag_faiss_to_qdrant.py` |
| Index ledger / scheduler | `mcp_servers/index_scheduler.py` |
| Frontend: RAG + `currentSpaceId` | `platform-frontend/src/components/sidebar/RagPanel.tsx` |
| Frontend: Notes + spaces | `platform-frontend/src/components/sidebar/NotesPanel.tsx` |
| Frontend: store (`fetchRagFiles`, `fetchNotesFiles`) | `platform-frontend/src/store/index.ts` |
| Notes suggestions (no space param) | `platform-frontend/src/components/notes/NotesEditor.tsx` |
