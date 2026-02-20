#!/usr/bin/env python3
"""
Test script to verify Qdrant setup and basic operations.

Run this after starting Qdrant with: docker-compose up -d
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from memory.vector_store import QdrantVectorStore
from core.utils import log_step, log_error


def test_connection():
    """Test basic connection to Qdrant."""
    print("\n🔍 Testing Qdrant Connection...")
    try:
        store = QdrantVectorStore()
        print("✅ Successfully connected to Qdrant!")
        return store
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        print("\n💡 Make sure Qdrant is running:")
        print("   docker-compose up -d")
        return None


def test_add_and_search(store: QdrantVectorStore):
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


def test_get_and_update(store: QdrantVectorStore, memory_id: str):
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


def test_filtering(store: QdrantVectorStore):
    """Test metadata filtering."""
    print("\n🔍 Testing Metadata Filtering...")
    
    # Search with category filter
    query_embedding = np.random.rand(768).astype(np.float32)
    results = store.search(
        query_vector=query_embedding,
        filter_metadata={"category": "tech"},
        k=10,
    )
    
    print(f"  ✅ Found {len(results)} tech memories")
    for result in results:
        assert result["category"] == "tech", "Filter failed!"
    
    print("  ✅ Filtering works correctly!")


def test_count_and_get_all(store: QdrantVectorStore):
    """Test counting and getting all memories."""
    print("\n📊 Testing Count and Get All Operations...")
    
    count = store.count()
    print(f"  ✅ Total memories: {count}")
    
    all_memories = store.get_all(limit=10)
    print(f"  ✅ Retrieved {len(all_memories)} memories (limited to 10)")


def test_delete(store: QdrantVectorStore, memory_id: str):
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


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Qdrant Vector Store Test Suite")
    print("=" * 60)
    
    # Test 1: Connection
    store = test_connection()
    if not store:
        sys.exit(1)
    
    # Test 2: Add and Search
    added_ids = test_add_and_search(store)
    if not added_ids:
        print("❌ Failed to add test memories")
        sys.exit(1)
    
    # Test 3: Get and Update
    test_get_and_update(store, added_ids[0])
    
    # Test 4: Filtering
    test_filtering(store)
    
    # Test 5: Count and Get All
    test_count_and_get_all(store)
    
    # Test 6: Delete
    test_delete(store, added_ids[-1])  # Delete last one
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print("\n💡 Note: Test memories were added with random embeddings.")
    print("   In production, use actual embedding models for meaningful results.")


if __name__ == "__main__":
    main()

