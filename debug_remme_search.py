import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from remme.store import RemmeStore
from remme.utils import get_embedding

def debug_search():
    print("🔎 Debugging Remme Search...")
    store = RemmeStore()
    
    query = "where is the user located?"
    print(f"\n📡 Query: '{query}'")
    
    emb = get_embedding(query)
    print(f"📐 Query Embedding Shape: {emb.shape}")

    # Test RAW Search
    print("\n🔬 Raw FAISS Search (k=10):")
    if store.index:
        distances, indices = store.index.search(emb.reshape(1, -1), 10)
        print(f"   Distances: {distances}")
        print(f"   Indices:   {indices}")
        print(f"   Index Total: {store.index.ntotal}")
    else:
        print("❌ Index is NONE")

    # Test with default threshold
    results = store.search(emb, k=10, score_threshold=1.5)
    
    print(f"✅ Found {len(results)} results (Threshold 1.5):")
    for r in results:
        print(f"   - [{r.get('score', 0):.4f}] {r['text']}")

    # Test with VERY SOFT threshold
    results_soft = store.search(emb, k=10, score_threshold=5.0)
    print(f"\n✅ Found {len(results_soft)} results (Threshold 5.0):")
    for r in results_soft:
        print(f"   - [{r.get('score', 0):.4f}] {r['text']}")
        
    # Check all memories to see if 'Bangalore' exists
    print("\n📂 Scanning all memories for 'Bangalore'...")
    all_mems = store.get_all()
    found = False
    for m in all_mems:
        if "bangalore" in m['text'].lower() or "bengaluru" in m['text'].lower():
            print(f"   ✨ Match found: ID={m['id']}, Text='{m['text']}'")
            found = True
            
    if not found:
        print("   ❌ No Bangalore reference found in the entire vault!")

if __name__ == "__main__":
    debug_search()
