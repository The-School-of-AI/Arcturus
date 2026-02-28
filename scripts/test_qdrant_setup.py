#!/usr/bin/env python3
"""
Test script to verify Qdrant setup and basic operations.

Tests two vector stores:
1. Remme memories — uses "test_memories" collection (indexed_payload_fields: category, source)
2. RAG chunks — uses "arcturus_rag_chunks" collection

Run this after starting Qdrant with: docker-compose up -d
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env so QDRANT_URL and QDRANT_API_KEY are available (for Cloud)
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

import numpy as np
from memory.vector_store import get_vector_store, VectorStoreProtocol
from memory.rag_store import get_rag_vector_store


def test_connection():
    """Test basic connection to Qdrant via provider-agnostic factory."""
    print("\n🔍 Testing Qdrant Connection (via get_vector_store)...")
    try:
        store: VectorStoreProtocol = get_vector_store(provider="qdrant", collection_name="test_memories")
        print("✅ Successfully connected to Qdrant!")
        return store
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        print("\n💡 Make sure Qdrant is running:")
        print("   docker-compose up -d")
        return None


def test_add_and_search(store: VectorStoreProtocol):
    """Test adding memories and searching."""
    print("\n📝 Testing Add and Search Operations...")
    
    # Create some test embeddings (random for testing)
    # In production, these would come from an embedding model
    dimension = 768
    test_memories = [
        {
            "text": "I love working with Python and machine learning",
            "category": "tech",
            "source": "test",
        },
        {
            "text": "My favorite programming language is Python",
            "category": "tech",
            "source": "test",
        },
        {
            "text": "I enjoy cooking Italian food on weekends",
            "category": "personal",
            "source": "test",
        },
    ]
    
    # Add test memories
    added_ids = []
    for i, memory in enumerate(test_memories):
        # Generate random embedding (in production, use actual embedding model)
        embedding = np.random.rand(dimension).astype(np.float32)
        
        result = store.add(
            text=memory["text"],
            embedding=embedding,
            category=memory["category"],
            source=memory["source"],
        )
        added_ids.append(result["id"])
        print(f"  ✅ Added memory {i+1}: {result['id'][:8]}...")
    
    # Test search
    print("\n🔍 Testing Search...")
    query_embedding = np.random.rand(dimension).astype(np.float32)
    
    results = store.search(
        query_vector=query_embedding,
        query_text="Python programming",
        k=3,
    )
    
    print(f"  ✅ Found {len(results)} results")
    for i, result in enumerate(results, 1):
        print(f"    {i}. Score: {result['score']:.4f} - {result['text'][:50]}...")
    
    return added_ids


def test_get_and_update(store: VectorStoreProtocol, memory_id: str):
    """Test getting and updating a memory."""
    print("\n✏️ Testing Get and Update Operations...")
    
    # Get memory
    memory = store.get(memory_id)
    if memory:
        print(f"  ✅ Retrieved memory: {memory['text'][:50]}...")
    else:
        print(f"  ❌ Failed to retrieve memory {memory_id}")
        return
    
    # Update memory
    new_embedding = np.random.rand(768).astype(np.float32)
    success = store.update(
        memory_id=memory_id,
        text=memory["text"] + " (updated)",
        embedding=new_embedding,
    )
    
    if success:
        print(f"  ✅ Updated memory successfully")
    else:
        print(f"  ❌ Failed to update memory")


def test_filtering(store: VectorStoreProtocol):
    """Test metadata filtering (relies on category/source payload indexes)."""
    print("\n🔍 Testing Metadata Filtering (category & source indexes)...")
    
    # Search with category filter (requires category index in Qdrant Cloud)
    query_embedding = np.random.rand(768).astype(np.float32)
    results = store.search(
        query_vector=query_embedding,
        filter_metadata={"category": "tech"},
        k=10,
    )
    
    print(f"  ✅ Found {len(results)} tech memories (category filter)")
    for result in results:
        assert result["category"] == "tech", "Category filter failed!"

    # Search with source filter (requires source index in Qdrant Cloud)
    results_src = store.search(
        query_vector=query_embedding,
        filter_metadata={"source": "test"},
        k=10,
    )
    print(f"  ✅ Found {len(results_src)} memories with source=test")
    for result in results_src:
        assert result["source"] == "test", "Source filter failed!"
    
    print("  ✅ Filtering works correctly (indexes OK)!")


def test_count_and_get_all(store: VectorStoreProtocol):
    """Test counting and getting all memories."""
    print("\n📊 Testing Count and Get All Operations...")
    
    count = store.count()
    print(f"  ✅ Total memories: {count}")
    
    all_memories = store.get_all(limit=10)
    print(f"  ✅ Retrieved {len(all_memories)} memories (limited to 10)")


def test_delete(store: VectorStoreProtocol, memory_id: str):
    """Test deleting a memory."""
    print("\n🗑️ Testing Delete Operation...")
    
    success = store.delete(memory_id)
    if success:
        print(f"  ✅ Deleted memory {memory_id[:8]}...")
        
        # Verify deletion
        memory = store.get(memory_id)
        if memory is None:
            print("  ✅ Deletion verified (memory no longer exists)")
        else:
            print("  ⚠️ Warning: Memory still exists after deletion")
    else:
        print(f"  ❌ Failed to delete memory")


# =============================================================================
# RAG Vector Store Tests (test_rag_chunks collection)
# =============================================================================


def test_rag_connection():
    """Test RAG store connection to Qdrant (uses test_rag_chunks collection)."""
    print("\n🔍 Testing RAG Qdrant Connection (via get_rag_vector_store)...")
    try:
        store = get_rag_vector_store(provider="qdrant", collection_name="test_rag_chunks")
        print("  ✅ Successfully connected to RAG Qdrant store!")
        return store
    except Exception as e:
        print(f"  ❌ Failed to connect: {e}")
        return None


def test_rag_add_and_search(rag_store):
    """Test adding RAG chunks and searching."""
    print("\n📝 Testing RAG Add and Search Operations...")
    dimension = 768
    entries = [
        {"chunk_id": "test_doc_0", "doc": "Notes/test.md", "chunk": "Python is great for ML.", "page": 1},
        {"chunk_id": "test_doc_1", "doc": "Notes/test.md", "chunk": "Machine learning uses Python.", "page": 1},
        {"chunk_id": "test_doc_2", "doc": "Docs/other.md", "chunk": "Cooking recipes here.", "page": 1},
    ]
    embeddings = [np.random.rand(dimension).astype(np.float32) for _ in entries]
    rag_store.add_chunks(entries=entries, embeddings=embeddings)
    print(f"  ✅ Added {len(entries)} chunks")
    query_vec = np.random.rand(dimension).astype(np.float32)
    results = rag_store.search(query_vec, k=3)
    print(f"  ✅ Search returned {len(results)} results: {[r[0] for r in results]}")
    assert len(results) >= 1, "RAG search should return at least one result"
    for chunk_id, score in results:
        assert isinstance(chunk_id, str), "chunk_id should be string"
        assert isinstance(score, (int, float)), "score should be numeric"
    return entries


def test_rag_delete_by_doc(rag_store):
    """Test deleting RAG chunks by document path."""
    print("\n🗑️ Testing RAG Delete by Doc...")
    deleted = rag_store.delete_by_doc("Docs/other.md")
    print(f"  ✅ delete_by_doc returned {deleted}")
    # Add a chunk for test_doc, then delete to verify
    entries = [{"chunk_id": "del_test_0", "doc": "to_delete.md", "chunk": "Temp chunk.", "page": 1}]
    embeddings = [np.random.rand(768).astype(np.float32)]
    rag_store.add_chunks(entries=entries, embeddings=embeddings)
    rag_store.delete_by_doc("to_delete.md")
    print("  ✅ delete_by_doc completed")


def test_rag_get_metadata(rag_store):
    """Test get_metadata for BM25/corpus retrieval."""
    print("\n📊 Testing RAG get_metadata...")
    meta = rag_store.get_metadata()
    print(f"  ✅ get_metadata returned {len(meta)} entries")


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Qdrant Vector Store Test Suite")
    print("=" * 60)

    # --- Remme memories (test_memories collection) ---
    print("\n" + "-" * 40)
    print("Part 1: Remme Memories (test_memories)")
    print("-" * 40)

    store = test_connection()
    if not store:
        sys.exit(1)

    added_ids = test_add_and_search(store)
    if not added_ids:
        print("❌ Failed to add test memories")
        sys.exit(1)

    test_get_and_update(store, added_ids[0])
    test_filtering(store)
    test_count_and_get_all(store)
    test_delete(store, added_ids[-1])

    # --- RAG chunks (test_rag_chunks collection) ---
    print("\n" + "-" * 40)
    print("Part 2: RAG Chunks (test_rag_chunks)")
    print("-" * 40)

    rag_store = test_rag_connection()
    if not rag_store:
        print("❌ Failed to connect to RAG store (is Qdrant running?)")
        sys.exit(1)

    test_rag_add_and_search(rag_store)
    test_rag_delete_by_doc(rag_store)
    test_rag_get_metadata(rag_store)

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print("\n💡 Note: Test data uses random embeddings.")
    print("   In production, use actual embedding models for meaningful results.")


if __name__ == "__main__":
    main()

