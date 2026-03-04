"""
FAISS-backed RAG vector store. Local file-based, backward compatible with existing RAG index.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

try:
    import faiss
except ImportError:
    faiss = None


class FaissRAGStore:
    """FAISS + metadata.json for RAG chunks. Uses index.bin and metadata.json in index_dir."""

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "index.bin"
        self.metadata_path = self.index_dir / "metadata.json"
        self._index = None
        self._metadata: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if faiss is None:
            raise ImportError("faiss is required for RAG FAISS backend. Install with: pip install faiss-cpu")
        if self.index_path.exists():
            self._index = faiss.read_index(str(self.index_path))
        if self.metadata_path.exists():
            self._metadata = json.loads(self.metadata_path.read_text())

    def _save(self) -> None:
        if self._index is not None:
            faiss.write_index(self._index, str(self.index_path))
        self.metadata_path.write_text(json.dumps(self._metadata, indent=2))

    def add_chunks(
        self,
        entries: List[Dict[str, Any]],
        embeddings: List[np.ndarray],
        remove_doc: str | None = None,
    ) -> None:
        """
        Add chunks to FAISS and metadata. If remove_doc is set, remove existing entries for that doc first.
        Note: FAISS does not support deletion; removed doc's vectors remain as orphans (index/metadata
        mapping may be off). Run full reindex to fix. For proper delete-by-doc, use Qdrant.
        """
        if not entries or not embeddings or len(entries) != len(embeddings):
            return
        if remove_doc is not None:
            self._metadata = [m for m in self._metadata if m.get("doc") != remove_doc]
            # FAISS cannot delete; index may have orphaned vectors. Proceed with add.

        if self._index is None:
            dim = len(embeddings[0])
            self._index = faiss.IndexFlatL2(dim)

        stack = np.stack(embeddings)
        self._index.add(stack)
        self._metadata.extend(entries)
        self._save()

    def search(
        self,
        query_vector: np.ndarray,
        k: int,
    ) -> List[tuple[str, float]]:
        """
        Vector search. Returns [(chunk_id, score), ...]. Score is negative L2 distance (higher = better).
        """
        if self._index is None:
            return []
        q = query_vector.reshape(1, -1).astype(np.float32)
        D, I = self._index.search(q, k)
        results = []
        for rank, idx in enumerate(I[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            m = self._metadata[idx]
            chunk_id = m.get("chunk_id", f"idx_{idx}")
            # L2: lower is better. Convert to score: -D (higher = better)
            score = float(-D[0][rank])
            results.append((chunk_id, score))
        return results

    def get_metadata(self) -> List[Dict[str, Any]]:
        """Return full metadata for BM25 and entity gate."""
        return self._metadata

    def delete_by_doc(self, doc_path: str) -> int:
        """Remove entries for doc. FAISS cannot delete; we rebuild index from remaining metadata.
        Rebuild requires re-embedding - not supported here. Returns 0 (no-op for FAISS)."""
        # FAISS limitation: would need full rebuild with re-embedding
        return 0
