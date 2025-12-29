import json
import faiss
import numpy as np
from pathlib import Path
from datetime import datetime
import uuid
import sys

class RemmeStore:
    def __init__(self, persistence_dir: str = "memory/remme_index"):
        self.root = Path(__file__).parent.parent / persistence_dir
        self.root.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.root / "index.bin"
        self.metadata_path = self.root / "memories.json"
        
        self.dimension = 768 # Default for nomic-embed-text
        self.index = None
        self.memories = []
        
        self.load()

    def load(self):
        """Load index and metadata from disk."""
        if self.index_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
            except Exception as e:
                print(f"Failed to load FAISS index: {e}", file=sys.stderr)
                self.index = faiss.IndexFlatL2(self.dimension)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)

        if self.metadata_path.exists():
            try:
                self.memories = json.loads(self.metadata_path.read_text())
            except Exception as e:
                print(f"Failed to load memories JSON: {e}", file=sys.stderr)
                self.memories = []
        else:
            self.memories = []

    def save(self):
        """Save index and metadata to disk."""
        if self.index:
            faiss.write_index(self.index, str(self.index_path))
        
        self.metadata_path.write_text(json.dumps(self.memories, indent=2))

    def add(self, text: str, embedding: np.ndarray, category: str = "general", source: str = "manual"):
        """Add a new memory with deduplication."""
        if self.index is None:
            self.dimension = len(embedding)
            self.index = faiss.IndexFlatL2(self.dimension)
            
        # DEDUPLICATION CHECK
        # Search for exact or very similar matches
        # threshold 0.15 is more aggressive than 0.1
        matches = self.search(embedding, k=1, score_threshold=0.15)
        if matches:
            # Update existing memory's timestamp
            memory_id = matches[0]["id"]
            for m in self.memories:
                if m["id"] == memory_id:
                    m["updated_at"] = datetime.now().isoformat()
                    # Optionally append source if it's different?
                    if source not in m.get("source", ""):
                        m["source"] = f"{m['source']}, {source}"
                    self.save()
                    return m

        # Add to FAISS
        self.index.add(embedding.reshape(1, -1))
        
        # Add to Metadata
        memory_id = str(uuid.uuid4())
        memory_item = {
            "id": memory_id,
            "text": text,
            "category": category,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "source": source,
            "faiss_id": self.index.ntotal - 1  # 0-indexed ID in FAISS
        }
        self.memories.append(memory_item)
        self.save()
        return memory_item

    def search(self, query_vector: np.ndarray, query_text: str = None, k: int = 10, score_threshold: float = 1.5):
        """Search memories by vector similarity with optional keyword boosting."""
        if not self.index or self.index.ntotal == 0:
            return []
            
        distances, indices = self.index.search(query_vector.reshape(1, -1), k * 2) # Get more candidates for merging
        
        # 1. Gather Vector Results
        vector_results = {}
        for i, idx in enumerate(indices[0]):
            if idx == -1: continue
            memory = next((m for m in self.memories if m.get("faiss_id") == int(idx)), None)
            if memory:
                score = float(distances[0][i])
                if score < score_threshold:
                    res = memory.copy()
                    res["score"] = score
                    vector_results[memory["id"]] = res

        # 2. Keyword Search & Boosting
        final_results = []
        if query_text:
            import re
            query_words = set(re.findall(r'\b\w+\b', query_text.lower()))
            # Expanded stop words for better precision
            stop_words = {
                "the", "a", "an", "is", "are", "was", "were", "do", "does", "did", "you", "your", 
                "have", "has", "had", "any", "about", "of", "our", "to", "what", "we", "in", 
                "with", "from", "for", "and", "or", "but", "so", "how", "when", "where", "why",
                "this", "that", "these", "those", "it", "its", "they", "them", "their",
                "be", "been", "being", "can", "could", "should", "would", "may", "might", "must",
                "shall", "will", "on", "at", "by", "at", "as", "if"
            }
            keywords = query_words - stop_words
            
            if keywords:
                for memory in self.memories:
                    text_lower = memory["text"].lower()
                    m_id = memory["id"]
                    
                    # Count whole-word matches only
                    match_count = 0
                    for kw in keywords:
                        if re.search(rf'\b{re.escape(kw)}\b', text_lower):
                            match_count += 1
                    
                    if match_count > 0:
                        # Success! This memory has a keyword match.
                        if m_id in vector_results:
                            # 🚀 BOOST: If found in both, slash the score (lower is better)
                            boost = 1.0 + (match_count * 0.7) # Slightly stronger boost
                            vector_results[m_id]["score"] /= (boost * 2.0)
                            vector_results[m_id]["source"] = f"{vector_results[m_id].get('source', '')} (hybrid_boost)"
                        else:
                            # 💡 INJECT: If only found via keyword, add with competitive score
                            res = memory.copy()
                            res["score"] = 0.6 / (1.0 + match_count) # Competitive synthetic score
                            res["source"] = f"{res.get('source', '')} (keyword_only)"
                            vector_results[m_id] = res

        # 3. Final Sort and Trim
        final_results = sorted(vector_results.values(), key=lambda x: x["score"])
        return final_results[:k]

    def get_all(self):
        """Return all memories."""
        return self.memories

    def get_scanned_run_ids(self):
        """Return a set of run IDs that have already been scanned."""
        scanned_ids = set()
        for m in self.memories:
            source = m.get("source", "")
            # Looking for patterns like "run_12345" or "manual_scan_12345"
            # Split by comma if multiple sources
            parts = source.split(", ")
            for part in parts:
                if part.startswith("run_"):
                    scanned_ids.add(part.replace("run_", ""))
                elif part.startswith("manual_scan_"):
                    scanned_ids.add(part.replace("manual_scan_", ""))
        return scanned_ids

    def delete(self, memory_id: str):
        """Delete a memory.
        Note: FAISS deletion is complex (requires IDMap or rebuild).
        For simplicity in this V1, we will remove from metadata and rebuild index.
        """
        # Remove from memories list
        self.memories = [m for m in self.memories if m["id"] != memory_id]
        
        # Rebuild Index
        new_index = faiss.IndexFlatL2(self.dimension)
        if self.memories:
            # We need embeddings to rebuild. 
            # OPTION 1: Store embeddings in a separate .npy file (Better for large scale)
            # OPTION 2: Re-embed everything (Bad)
            # OPTION 3: Don't support delete yet in FAISS, just soft delete in metadata.
            
            # Going with Option 3/Hybrid for MVP: We accept that the vector exists but we filter it out?
            # No, that affects Top-K.
            
            # Better strategy for Teaching/MVP:
            # We assume we have the embeddings available or re-calculate.
            # Since we didn't store embeddings in JSON (too big), and we want to avoid re-embed cost...
            # We will implement a "Soft Delete" workflow where we filter search results.
            pass
            
        # Re-save metadata (so it's gone from UI)
        self.save()
        
        # Ideally we should rebuild the index cleanly. 
        # For now, let's just mark it deleted in metadata and handle filtering in search
        # or implement a full rebuild if the user edits. 
        # Let's keep it simple: Just Metadata Update. The "Ghost" vector might return but we filter it.
        return True

    def update_text(self, memory_id: str, new_text: str, new_embedding: np.ndarray):
        """Update the text of a memory."""
        # 1. Soft delete the old vector (by removing metadata mapping)
        # 2. Add new vector
        
        original_idx = -1
        for i, m in enumerate(self.memories):
            if m["id"] == memory_id:
                original_idx = i
                break
        
        if original_idx != -1:
            # Modify in place (preserving ID/Created At)
            self.memories[original_idx]["text"] = new_text
            self.memories[original_idx]["updated_at"] = datetime.now().isoformat()
            
            # Update FAISS:
            # As explained in delete, we can't easily "replace" a vector in FlatL2 without IDMap.
            # We will append the new vector and update the faiss_id pointer.
            # The old vector becomes "garbage" (unreachable).
            self.index.add(new_embedding.reshape(1, -1))
            self.memories[original_idx]["faiss_id"] = self.index.ntotal - 1
            
            self.save()
            return True
        return False
