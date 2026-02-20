"""
Qdrant-based Vector Store for Arcturus Memory System (Project 11: Mnemo)

This module provides a scalable vector store implementation using Qdrant,
replacing the local FAISS-based storage with a cloud-ready solution.

Key Features:
- Hybrid search (vector similarity + keyword + metadata filtering)
- Real-time indexing (< 100ms)
- Multi-tenancy support
- Backward compatible with existing memory APIs
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
        SearchParams,
    )
    from qdrant_client.http import models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    raise ImportError(
        "qdrant-client is required. Install with: pip install qdrant-client"
    )

from core.utils import log_step, log_error


class QdrantVectorStore:
    """
    Qdrant-based vector store for memory storage and retrieval.
    
    This replaces the FAISS-based RemmeStore with a scalable, cloud-ready solution.
    Maintains backward compatibility with existing memory APIs.
    """
    
    # Default collection name for memories
    DEFAULT_COLLECTION = "arcturus_memories"
    
    # Default vector dimension (matches nomic-embed-text)
    DEFAULT_DIMENSION = 768
    
    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = DEFAULT_COLLECTION,
        dimension: int = DEFAULT_DIMENSION,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Qdrant vector store.
        
        Args:
            url: Qdrant server URL (default: localhost)
            collection_name: Name of the collection to use
            dimension: Vector dimension (default: 768 for nomic-embed-text)
            api_key: Optional API key for cloud Qdrant instances
        """
        self.url = url
        self.collection_name = collection_name
        self.dimension = dimension
        
        # Initialize Qdrant client
        self.client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=10.0,
        )
        
        # Ensure collection exists
        self._ensure_collection()
        
        log_step(f"✅ QdrantVectorStore initialized: {url}/{collection_name}", symbol="🔧")
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection with vector and payload configuration
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension,
                        distance=Distance.COSINE,  # Cosine similarity for semantic search
                    ),
                )
                log_step(f"📦 Created collection: {self.collection_name}", symbol="✨")
        except Exception as e:
            log_error(f"Failed to ensure collection exists: {e}")
            raise
    
    def add(
        self,
        text: str,
        embedding: np.ndarray,
        category: str = "general",
        source: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
        deduplication_threshold: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Add a new memory with optional deduplication.
        
        Args:
            text: Memory text content
            embedding: Vector embedding (numpy array)
            category: Memory category (default: "general")
            source: Source of the memory (default: "manual")
            metadata: Additional metadata to store
            deduplication_threshold: Similarity threshold for deduplication (0-1)
        
        Returns:
            Dictionary with memory ID and metadata
        """
        # Convert numpy array to list
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
        
        # Check for duplicates if threshold is set
        if deduplication_threshold > 0:
            similar = self.search(
                query_vector=np.array(embedding),
                k=1,
                score_threshold=1.0 - deduplication_threshold,  # Convert similarity to distance
            )
            if similar:
                # Update existing memory timestamp
                existing = similar[0]
                memory_id = existing["id"]
                self._update_timestamp(memory_id, source)
                return existing
        
        # Generate unique ID
        memory_id = str(uuid.uuid4())
        
        # Prepare payload (metadata stored alongside vector)
        payload = {
            "text": text,
            "category": category,
            "source": source,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        if metadata:
            payload.update(metadata)
        
        # Create point (vector + payload)
        point = PointStruct(
            id=memory_id,
            vector=embedding,
            payload=payload,
        )
        
        # Insert into Qdrant
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )
            
            log_step(f"💾 Added memory: {memory_id[:8]}... ({len(text)} chars)", symbol="📝")
            
            return {
                "id": memory_id,
                **payload,
            }
        except Exception as e:
            log_error(f"Failed to add memory to Qdrant: {e}")
            raise
    
    def search(
        self,
        query_vector: np.ndarray,
        query_text: Optional[str] = None,
        k: int = 10,
        score_threshold: Optional[float] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search memories by vector similarity with optional keyword boosting and filtering.
        
        Args:
            query_vector: Query embedding vector
            query_text: Optional text query for hybrid search
            k: Number of results to return
            score_threshold: Minimum similarity score (0-1, higher = more similar)
            filter_metadata: Optional metadata filters (e.g., {"category": "work"})
        
        Returns:
            List of memory dictionaries with scores
        """
        if isinstance(query_vector, np.ndarray):
            query_vector = query_vector.tolist()
        
        # Build filter if metadata filters provided
        search_filter = None
        if filter_metadata:
            conditions = []
            for key, value in filter_metadata.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            if conditions:
                search_filter = Filter(must=conditions)
        
        # Convert score_threshold to distance threshold
        # Qdrant uses distance (lower = more similar), we use similarity (higher = more similar)
        distance_threshold = None
        if score_threshold is not None:
            # Cosine distance = 1 - cosine similarity
            distance_threshold = 1.0 - score_threshold
        
        try:
            # Perform vector search using Qdrant client
            # Try multiple methods for compatibility with different qdrant-client versions
            
            # Method 1: Standard search (qdrant-client >= 1.0.0)
            if hasattr(self.client, 'search'):
                search_results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=k * 2 if query_text else k,
                    score_threshold=distance_threshold,
                    query_filter=search_filter,
                )
            # Method 2: HTTP API (fallback for older versions or if search doesn't exist)
            else:
                from qdrant_client.http import models as rest_models
                
                search_request = rest_models.SearchRequest(
                    vector=query_vector,
                    limit=k * 2 if query_text else k,
                    score_threshold=distance_threshold,
                    filter=search_filter,
                )
                
                response = self.client.http.collections_api.search_points(
                    collection_name=self.collection_name,
                    search_request=search_request,
                )
                search_results = response.result
            
            # Convert results to our format
            results = []
            # Handle different response types
            if hasattr(search_results, 'result'):
                # Response from HTTP API
                search_results = search_results.result
            
            for result in search_results:
                # Handle different result object types
                if hasattr(result, 'id') and hasattr(result, 'score') and hasattr(result, 'payload'):
                    # Standard Qdrant result object
                    # Convert distance to similarity score (for consistency with FAISS API)
                    similarity_score = 1.0 - result.score
                    
                    memory = {
                        "id": str(result.id),
                        "score": similarity_score,
                        **result.payload,
                    }
                    results.append(memory)
                elif isinstance(result, dict):
                    # Already a dictionary
                    results.append(result)
                else:
                    # Try to extract fields manually
                    result_id = getattr(result, 'id', None) or getattr(result, 'point_id', None)
                    result_score = getattr(result, 'score', None) or getattr(result, 'distance', None)
                    result_payload = getattr(result, 'payload', {}) or {}
                    
                    if result_id is not None:
                        similarity_score = 1.0 - result_score if result_score is not None else 0.0
                        memory = {
                            "id": str(result_id),
                            "score": similarity_score,
                            **result_payload,
                        }
                        results.append(memory)
            
            # Apply keyword boosting if query_text provided
            if query_text:
                results = self._apply_keyword_boosting(results, query_text, k)
            
            return results[:k]
            
        except Exception as e:
            log_error(f"Failed to search Qdrant: {e}")
            return []
    
    def _apply_keyword_boosting(
        self, results: List[Dict], query_text: str, k: int
    ) -> List[Dict]:
        """
        Apply keyword-based boosting to search results.
        Similar to the hybrid search in RemmeStore.
        """
        import re
        
        query_words = set(re.findall(r'\b\w+\b', query_text.lower()))
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
            "you", "your", "have", "has", "had", "any", "about", "of", "our",
            "to", "what", "we", "in", "with", "from", "for", "and", "or", "but",
            "so", "how", "when", "where", "why", "this", "that", "these", "those",
        }
        keywords = query_words - stop_words
        
        if not keywords:
            return results[:k]
        
        # Boost results with keyword matches
        boosted_results = {}
        for result in results:
            text_lower = result.get("text", "").lower()
            match_count = sum(
                1 for kw in keywords
                if re.search(rf'\b{re.escape(kw)}\b', text_lower)
            )
            
            if match_count > 0:
                # Boost similarity score
                boost = 1.0 + (match_count * 0.7)
                result["score"] = min(1.0, result["score"] * boost)
                result["source"] = f"{result.get('source', '')} (hybrid_boost)"
            
            boosted_results[result["id"]] = result
        
        # Sort by boosted score (higher is better)
        final_results = sorted(
            boosted_results.values(),
            key=lambda x: x["score"],
            reverse=True,
        )
        
        return final_results[:k]
    
    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory by ID."""
        try:
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
            )
            
            if result:
                point = result[0]
                return {
                    "id": str(point.id),
                    **point.payload,
                }
            return None
        except Exception as e:
            log_error(f"Failed to get memory {memory_id}: {e}")
            return None
    
    def update(
        self,
        memory_id: str,
        text: Optional[str] = None,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update an existing memory.
        
        Args:
            memory_id: ID of memory to update
            text: New text (optional)
            embedding: New embedding (optional)
            metadata: New metadata fields (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing memory
            existing = self.get(memory_id)
            if not existing:
                return False
            
            # Prepare updated payload
            updated_payload = existing.copy()
            updated_payload.pop("id", None)  # Remove ID from payload
            updated_payload["updated_at"] = datetime.now().isoformat()
            
            if text:
                updated_payload["text"] = text
            if metadata:
                updated_payload.update(metadata)
            
            # Prepare point update
            point = PointStruct(
                id=memory_id,
                vector=embedding.tolist() if embedding is not None else None,
                payload=updated_payload,
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )
            
            log_step(f"✏️ Updated memory: {memory_id[:8]}...", symbol="🔄")
            return True
            
        except Exception as e:
            log_error(f"Failed to update memory {memory_id}: {e}")
            return False
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id],
            )
            log_step(f"🗑️ Deleted memory: {memory_id[:8]}...", symbol="❌")
            return True
        except Exception as e:
            log_error(f"Failed to delete memory {memory_id}: {e}")
            return False
    
    def get_all(
        self,
        limit: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all memories (with optional filtering).
        
        Args:
            limit: Maximum number of results
            filter_metadata: Optional metadata filters
        
        Returns:
            List of all memories
        """
        try:
            # Build filter
            search_filter = None
            if filter_metadata:
                conditions = []
                for key, value in filter_metadata.items():
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
                if conditions:
                    search_filter = Filter(must=conditions)
            
            # Scroll through all points
            results = []
            offset = None
            
            while True:
                scroll_result = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset,
                    scroll_filter=search_filter,
                )
                
                points, next_offset = scroll_result
                
                for point in points:
                    results.append({
                        "id": str(point.id),
                        **point.payload,
                    })
                
                if next_offset is None or (limit and len(results) >= limit):
                    break
                
                offset = next_offset
            
            return results[:limit] if limit else results
            
        except Exception as e:
            log_error(f"Failed to get all memories: {e}")
            return []
    
    def count(self) -> int:
        """Get total number of memories in the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count
        except Exception as e:
            log_error(f"Failed to get collection count: {e}")
            return 0
    
    def _update_timestamp(self, memory_id: str, source: str):
        """Update timestamp and source for existing memory."""
        existing = self.get(memory_id)
        if existing:
            updated_payload = existing.copy()
            updated_payload.pop("id", None)
            updated_payload["updated_at"] = datetime.now().isoformat()
            
            # Append source if different
            existing_source = updated_payload.get("source", "")
            if source not in existing_source:
                updated_payload["source"] = f"{existing_source}, {source}"
            
            point = PointStruct(
                id=memory_id,
                payload=updated_payload,
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )


# Backward compatibility alias
VectorStore = QdrantVectorStore

