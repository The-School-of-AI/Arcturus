import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from remme.store import RemmeStore
from remme.utils import get_embedding

def test_aqi_retrieval():
    print("🔎 Testing AQI Retrieval...")
    store = RemmeStore()
    
    queries = [
        "Do you have any memory of our discussions about AQI?",
        "AQI",
        "What do we know about Bangalore AQI?",
        "How is the user located and what is the AQI?"
    ]
    
    for query in queries:
        print(f"\n📡 Query: '{query}'")
        emb = get_embedding(query, task_type="search_query")
        
        # Test HYBRID Search
        results = store.search(emb, query_text=query, k=10)
        
        print(f"✅ Top matches (Hybrid):")
        for i, memory in enumerate(results):
            dist = memory.get("score", 0)
            print(f"   - [{dist:.4f}] {memory['text'][:100]}...")

if __name__ == "__main__":
    test_aqi_retrieval()
