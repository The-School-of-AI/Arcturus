"""
Qdrant vector store for Spark Page sections (P03).

Stores section embeddings for semantic search, enabling AI-powered queries like:
- "Expand the deployment section with more examples"
- "What does this page say about pricing?"
- "Show me market analysis sections"

Uses arcturus_page_sections collection with 768-dimensional embeddings.
"""

import hashlib
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as http_models
    from qdrant_client.models import (Distance, FieldCondition, Filter,
                                      MatchValue, PointStruct, VectorParams)
except ImportError:
    raise ImportError("qdrant-client is required. Install with: pip install qdrant-client")

from memory.qdrant_config import get_qdrant_api_key, get_qdrant_url


def _section_id_to_point_id(section_id: str) -> int:
    """Convert section_id to Qdrant point ID (64-bit unsigned int)."""
    h = hashlib.md5(section_id.encode()).hexdigest()[:16]
    return int(h, 16)


class PageSectionsVectorStore:
    """
    Qdrant-backed vector store for page sections.
    
    Enables semantic search over page sections for AI copilot features:
    - Section-level refinement (expand, simplify, add examples)
    - Semantic queries across all pages
    - Similar section discovery
    """

    COLLECTION = "arcturus_page_sections"
    DIMENSION = 768  # Standard embedding dimension (e.g., OpenAI ada-002, sentence-transformers)

    def __init__(self, collection_name: Optional[str] = None):
        self.collection_name = collection_name or self.COLLECTION
        self.url = get_qdrant_url()
        api_key = get_qdrant_api_key()
        self.client = QdrantClient(url=self.url, api_key=api_key, timeout=10.0)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections()
        names = [c.name for c in collections.collections]
        
        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.DIMENSION,
                    distance=Distance.COSINE
                )
            )
        
        # Create payload indexes for efficient filtering
        try:
            # Index by page_id for fetching all sections of a page
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="page_id",
                field_schema=http_models.KeywordIndexParams(
                    type=http_models.KeywordIndexType.KEYWORD
                ),
            )
            
            # Index by section_type for filtering by section kind
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="section_type",
                field_schema=http_models.KeywordIndexParams(
                    type=http_models.KeywordIndexType.KEYWORD
                ),
            )
            
            # Index by created_by for user-scoped search
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="created_by",
                field_schema=http_models.KeywordIndexParams(
                    type=http_models.KeywordIndexType.KEYWORD
                ),
            )
        except Exception as e:
            # Indexes might already exist
            if "already exists" not in str(e).lower():
                print(f"[PageSectionsVectorStore] Warning: Failed to create indexes: {e}")

    def add_page_sections(
        self,
        page_id: str,
        sections: List[Dict[str, Any]],
        embeddings: List[np.ndarray],
        created_by: str = "system",
        page_query: str = "",
        page_template: str = ""
    ) -> int:
        """
        Add or update all sections for a page.
        
        Args:
            page_id: Page identifier
            sections: List of section dicts with id, type, title, content
            embeddings: Corresponding embeddings for each section
            created_by: Page creator
            page_query: Original query that generated the page
            page_template: Template type used
            
        Returns:
            Number of sections added
        """
        if len(sections) != len(embeddings):
            raise ValueError(f"Sections count ({len(sections)}) must match embeddings count ({len(embeddings)})")
        
        # Remove existing sections for this page first
        self.delete_page_sections(page_id)
        
        # Prepare points
        points = []
        for section, embedding in zip(sections, embeddings):
            section_id = section.get("id", f"{page_id}_{section.get('type', 'unknown')}")
            
            # Ensure embedding is numpy array with correct shape
            if not isinstance(embedding, np.ndarray):
                embedding = np.array(embedding)
            if embedding.shape != (self.DIMENSION,):
                print(f"[PageSectionsVectorStore] Warning: Embedding has shape {embedding.shape}, expected ({self.DIMENSION},)")
                continue
            
            payload = {
                "section_id": section_id,
                "page_id": page_id,
                "section_type": section.get("type", "unknown"),
                "section_title": section.get("title", ""),
                "section_content": section.get("content", "")[:1000],  # First 1000 chars for preview
                "created_by": created_by,
                "page_query": page_query,
                "page_template": page_template,
                "order": section.get("order", 0),
            }
            
            point = PointStruct(
                id=_section_id_to_point_id(section_id),
                vector=embedding.tolist(),
                payload=payload
            )
            points.append(point)
        
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        
        return len(points)

    def search_sections(
        self,
        query_embedding: np.ndarray,
        page_id: Optional[str] = None,
        section_type: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over page sections.
        
        Args:
            query_embedding: Query vector (768-dim)
            page_id: Optional filter by page
            section_type: Optional filter by section type (overview, detail, etc.)
            created_by: Optional filter by creator
            limit: Maximum results
            
        Returns:
            List of matching sections with scores
        """
        # Ensure embedding is numpy array with correct shape
        if not isinstance(query_embedding, np.ndarray):
            query_embedding = np.array(query_embedding)
        if query_embedding.shape != (self.DIMENSION,):
            raise ValueError(f"Query embedding must be {self.DIMENSION}-dimensional, got {query_embedding.shape}")
        
        # Build filter
        filter_conditions = []
        if page_id:
            filter_conditions.append(
                FieldCondition(key="page_id", match=MatchValue(value=page_id))
            )
        if section_type:
            filter_conditions.append(
                FieldCondition(key="section_type", match=MatchValue(value=section_type))
            )
        if created_by:
            filter_conditions.append(
                FieldCondition(key="created_by", match=MatchValue(value=created_by))
            )
        
        search_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding.tolist(),
            query_filter=search_filter,
            limit=limit,
            with_payload=True
        )
        
        # Format results
        sections = []
        for result in results:
            sections.append({
                "section_id": result.payload.get("section_id"),
                "page_id": result.payload.get("page_id"),
                "section_type": result.payload.get("section_type"),
                "section_title": result.payload.get("section_title"),
                "section_content": result.payload.get("section_content"),
                "page_query": result.payload.get("page_query"),
                "page_template": result.payload.get("page_template"),
                "similarity_score": result.score,
            })
        
        return sections

    def get_page_sections(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Get all sections for a specific page.
        
        Args:
            page_id: Page identifier
            
        Returns:
            List of sections ordered by their position
        """
        # Scroll through all points with matching page_id
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="page_id", match=MatchValue(value=page_id))]
            ),
            limit=100,  # Max sections per page
            with_payload=True,
            with_vectors=False
        )
        
        sections = []
        for point in results[0]:  # results is tuple (points, next_offset)
            sections.append({
                "section_id": point.payload.get("section_id"),
                "section_type": point.payload.get("section_type"),
                "section_title": point.payload.get("section_title"),
                "section_content": point.payload.get("section_content"),
                "order": point.payload.get("order", 0),
            })
        
        # Sort by order
        sections.sort(key=lambda s: s.get("order", 0))
        return sections

    def delete_page_sections(self, page_id: str) -> bool:
        """
        Delete all sections for a page.
        
        Args:
            page_id: Page identifier
            
        Returns:
            True if sections were deleted
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="page_id", match=MatchValue(value=page_id))]
                )
            )
            return True
        except Exception as e:
            print(f"[PageSectionsVectorStore] Error deleting sections for page {page_id}: {e}")
            return False

    def find_similar_sections(
        self,
        section_id: str,
        limit: int = 5,
        exclude_same_page: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find sections similar to a given section.
        
        Args:
            section_id: Section to find similar sections for
            limit: Maximum results
            exclude_same_page: Don't return sections from the same page
            
        Returns:
            List of similar sections
        """
        # Get the section's vector
        point_id = _section_id_to_point_id(section_id)
        
        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_vectors=True,
                with_payload=True
            )
            
            if not points:
                return []
            
            section_vector = points[0].vector
            page_id = points[0].payload.get("page_id")
            
            # Search for similar sections
            filter_conditions = []
            if exclude_same_page and page_id:
                # Note: Qdrant doesn't have "not equal" match, so we'll filter in post-processing
                pass
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=section_vector,
                limit=limit + 10 if exclude_same_page else limit,  # Get extra in case we filter
                with_payload=True
            )
            
            # Format and filter results
            similar = []
            for result in results:
                result_section_id = result.payload.get("section_id")
                result_page_id = result.payload.get("page_id")
                
                # Skip the section itself
                if result_section_id == section_id:
                    continue
                
                # Skip same page if requested
                if exclude_same_page and result_page_id == page_id:
                    continue
                
                similar.append({
                    "section_id": result_section_id,
                    "page_id": result_page_id,
                    "section_type": result.payload.get("section_type"),
                    "section_title": result.payload.get("section_title"),
                    "section_content": result.payload.get("section_content"),
                    "page_query": result.payload.get("page_query"),
                    "similarity_score": result.score,
                })
                
                if len(similar) >= limit:
                    break
            
            return similar
        
        except Exception as e:
            print(f"[PageSectionsVectorStore] Error finding similar sections: {e}")
            return []


def get_page_sections_vector_store() -> Optional[PageSectionsVectorStore]:
    """
    Get PageSectionsVectorStore instance.
    
    Returns:
        PageSectionsVectorStore instance, or None if Qdrant is unavailable
    """
    try:
        return PageSectionsVectorStore()
    except Exception as e:
        print(f"[PageSectionsVectorStore] Failed to connect to Qdrant: {e}")
        return None
