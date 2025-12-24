from remme.extractor import RemmeExtractor
from remme.store import RemmeStore
from remme.utils import get_embedding
import sys

def test_remme():
    print(" Testing Remme Memory System...")
    
    # 1. Test Store
    store = RemmeStore()
    print(f"✅ Store initialized using {store.root}")
    
    # 2. Test Extraction
    extractor = RemmeExtractor()
    query = "I prefer using neon colors for my graph visualization"
    history = [{"role": "assistant", "content": "How can I help you today?"}]
    
    print(f"\n⛏️ Extracting facts from: '{query}'")
    facts = extractor.extract(query, history)
    print(f"   => Found: {facts}")
    
    if not facts:
        print("❌ Extraction failed or returned empty. Is Ollama running?")
        return

    # 3. Test Add & Persistence
    print("\n💾 Saving to Memory...")
    for fact in facts:
        emb = get_embedding(fact)
        store.add(fact, emb, category="preference")
        print(f"   + Saved: {fact}")
        
    # 4. Test Search
    print("\n🔍 Searching for 'colors'...")
    search_q = get_embedding("what colors do I like?")
    results = store.search(search_q)
    for res in results:
        print(f"   => MATCH: {res['text']} (Score: {res['score']:.4f})")
        
    print("\n✅ Test Complete!")

if __name__ == "__main__":
    test_remme()
