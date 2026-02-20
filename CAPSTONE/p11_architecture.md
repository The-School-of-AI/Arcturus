## 🎓 Technical Breakdown

### **1. Vector Store (`memory/vector_store.py`)**

**Purpose:** Store and search memories using vector similarity

**Current:** FAISS (local file, single device)

**New:** Qdrant or Weaviate (cloud-hosted, multi-device)

**Why?**
- FAISS is like a local hard drive - fast but only on one computer
- Qdrant/Weaviate is like Google Drive - accessible from anywhere, scales better

**Original Requirements (from Rohan)**
- **Migration from FAISS to Qdrant/Weaviate:** Cloud-hosted vector DB with multi-tenancy
- **Hybrid search:** Combined vector similarity + keyword search + metadata filtering
- **Real-time indexing:** New memories indexed within 100ms of creation
- **Sharding strategy:** Per-user shards with cross-user federated search (for shared spaces)

**Key Functions/Features:**
- `memory/vector_store.py` - New adapter that talks to Qdrant/Weaviate
    ```python
    class VectorStore:
        def add(memory_text, embedding, metadata)
        def search(query, k=10)  # Returns top-k similar memories
        def update(memory_id, new_text, new_embedding)
        def delete(memory_id)
    ```

**Migration Path:**
1. Read all existing FAISS memories
2. Convert to Qdrant/Weaviate format
3. Keep backward compatibility layer (Keep the same API so existing code doesn't break)

**Tech Selection**
1. Planning to go with Qdrant initially, but we may built Weaviate as well to compare performance (if time permits)


---

### **2. Knowledge Graph (`memory/knowledge_graph.py`)**

**Purpose:** Extract and connect entities from conversations

**Current:** Memories are isolated - like index cards in a box

**New:** Memories are connected - like Wikipedia with hyperlinks

**Original Requirements (from Rohan)**
- **Entity extraction:** Auto-extract entities (people, companies, concepts, dates) from conversations
- **Relationship mapping:** Build and maintain entity-relationship graph as agent learns
- **Temporal awareness:** Track when facts were learned and whether they've been superseded
- **Graph queries:** Agent can reason over the knowledge graph: "What do I know about X and how does it relate to Y?"
- **Visualization:** Interactive knowledge graph explorer in the frontend

**Key Functions/Features:**
- `memory/knowledge_graph.py` - Extracts entities (people, places, concepts) and relationships
    ```python
    class KnowledgeGraph:
        def extract_entities(text)  # Returns: [Person, Company, Date, ...]
        def add_relationship(entity1, relation, entity2)
        def query(pattern)  # GraphQL or Cypher queries
        def visualize()  # For frontend display
    ```

**Example:**
```python
# From conversation: "I met John at Google last week"
entities = extract_entities(text)
# Returns: [Person("John"), Company("Google"), Date("last week")]

add_relationship("user", "met", "John")
add_relationship("John", "works_at", "Google")
```

**Tech Selection**
- Planning to use Neo4j as a graph database
- Planning to use NetworkX for in memory manipulation

---

### **3. Spaces Manager (`memory/spaces.py`)**

**Purpose:** Organize memories into collections

**Current:** All memories in one big pile

**New:** Organized into "Spaces" (like folders, but smarter)

**Original Requirements (from Rohan)**
- **Personal spaces:** Dedicated knowledge areas per project/topic (e.g., "Startup Research", "Home Renovation")
- **Shared spaces:** Team members can contribute to and query shared knowledge spaces
- **Auto-organization:** Agent suggests which space new information belongs to
- **Space templates:** Pre-configured spaces for common use cases (Research Project, Code Repository, Client Management)

**Key Functions/features:**
- `memory/spaces.py` - Manages spaces and collections
    ```python
    class SpacesManager:
        def create_space(name, type="personal")
        def add_to_space(memory_id, space_id)
        def suggest_space(memory_text)  # AI suggests which space
        def search_in_space(query, space_id)
    ```
- Frontend UI to create/manage spaces
- Auto-categorization logic

**Tech Selection**
- TODO: Will do some reading and research when close to start on it

---

### **4. Sync Engine (`memory/sync.py`)**

**Purpose:** Sync memories across devices

**Current:** Memories only on one device

**New:** Memories sync across all devices (phone, laptop, tablet)

**Original Requirements (from Rohan)**
- **CRDT-based sync:** Conflict-free replication across devices using CRDTs
- **Offline-first:** Full functionality offline, sync when connected
- **Selective sync:** Per-space sync policies (some spaces local-only for privacy)

**Key Functions/Features:**
- `memory/sync.py` - CRDT-based synchronization
    ```python
    class SyncEngine:
        def sync_to_cloud(space_id)
        def sync_from_cloud(device_id)
        def resolve_conflict(local, remote)  # CRDT merge
        def get_sync_status()
    ```
- Handles conflicts gracefully
- Selective sync (some spaces can be local-only for privacy)
- Works offline, syncs when connected

---

### **5. Lifecycle Manager (`memory/lifecycle.py`)**

**Purpose:** Manage memory importance and archival

**Current:** All memories treated equally

**New:** Memories have "importance scores" and lifecycle

**Original Requirements (from Rohan)**
- **Importance scoring:** Auto-score memory importance, promote frequently accessed memories
- **Decay & archival:** Gradually archive low-importance memories (retrievable but not in active search)
- **Contradiction resolution:** When new info conflicts with existing memory, present both and let user/agent resolve
- **Privacy controls:** Per-memory privacy levels, user can mark memories as private/shareable/public

**Key Functions:**
- `memory/lifecycle.py` - Importance scoring, decay, archival logic
    ```python
    class LifecycleManager:
        def score_importance(memory_id)  # Based on access frequency
        def archive_low_importance()
        def detect_contradiction(new_memory, existing_memories)
        def set_privacy(memory_id, level="private")
    ```
    - **Importance Scoring:** Frequently accessed memories get promoted
    - **Decay & Archival:** Old, unused memories get archived (still searchable, but not in active results)
    - **Contradiction Resolution:** If you say "I like pizza" then "I hate pizza", system flags both and asks you to clarify
    - **Privacy Controls:** Mark memories as private/shareable/public
- UI to manage memory privacy

---

## 📋 Implementation Checklist

### **Week 1: Foundation**
- [ ] Set up Qdrant instance (local or cloud)
- [ ] Create `memory/vector_store.py` with basic CRUD
- [ ] Migrate existing FAISS data
- [ ] Write tests for vector operations
- [ ] Ensure backward compatibility with `episodic_memory.py`

### **Week 2: Knowledge Graph**
- [ ] Set up Neo4j or NetworkX
- [ ] Implement entity extraction (using LLM or NER)
- [ ] Build relationship extraction
- [ ] Create graph query interface
- [ ] Add visualization endpoint for frontend

### **Week 3: Spaces**
- [ ] Design space schema
- [ ] Implement space CRUD operations
- [ ] Build auto-categorization logic
- [ ] Create frontend UI for spaces
- [ ] Add space templates

### **Week 3-4: Sync**
- [ ] Research and implement CRDT library
- [ ] Build sync protocol
- [ ] Handle offline scenarios
- [ ] Add conflict resolution
- [ ] Test multi-device scenarios

### **Week 3-4: Lifecycle**
- [ ] Implement importance scoring algorithm
- [ ] Build archival system
- [ ] Add contradiction detection
- [ ] Create privacy controls
- [ ] Add UI for memory management

## 🧪 Testing Requirements

The project charter specifies **mandatory test gates**:

### **Acceptance Tests** (`tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py`)
Must have at least 8 test cases covering:
- ✅ Happy-path: Memory retrieval works end-to-end
- ✅ Invalid input handling
- ✅ Memory ingestion
- ✅ Retrieval ranking
- ✅ Contradiction handling
- ✅ Lifecycle archival

### **Integration Tests** (`tests/integration/test_mnemo_oracle_cross_project_retrieval.py`)
Must have at least 5 scenarios covering:
- ✅ Memory affects Planner behavior BEFORE plan generation
- ✅ Cross-project retrieval (finding memories from other projects)
- ✅ Failure propagation (graceful degradation)

### **CI Requirements**
- All acceptance tests pass
- All integration tests pass
- Baseline regression suite passes
- Lint/typecheck passes
- **Performance:** < 250ms for top-k retrieval

---

## 🎯 Key Success Metrics

1. **Performance:** < 250ms retrieval latency (P95)
2. **Backward Compatibility:** Existing `episodic_memory.py` code still works
3. **Test Coverage:** All mandatory tests pass
4. **User Experience:** Can create spaces, see knowledge graph, sync across devices

---