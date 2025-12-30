import sys
import json
import faiss
import numpy as np
from pathlib import Path
import requests

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from remme.utils import get_embedding

def rebuild_index():
    print("🔧 Starting Remme Index Repair...")
    
    # Paths
    root = Path(__file__).parent / "memory" / "remme_index"
    index_path = root / "index.bin"
    metadata_path = root / "memories.json"
    
    if not metadata_path.exists():
        print("❌ No memories.json found!")
        return
        
    # Load Memories
    print("📂 Loading memories.json...")
    try:
        memories = json.loads(metadata_path.read_text())
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}")
        return

    print(f"   Found {len(memories)} memory items.")
    
    # Initialize New Index
    dimension = 768
    new_index = faiss.IndexFlatL2(dimension)
    
    # Re-embed everything
    updated_memories = []
    
    print("🧠 Regenerating embeddings (this may take a moment)...")
    
    successful_count = 0
    
    for i, m in enumerate(memories):
        text = m.get("text")
        if not text:
            print(f"   ⚠️ Skipping item {m.get('id')} (no text)")
            continue
            
        try:
            # Generate Embedding
            emb = get_embedding(text, task_type="search_document")
            
            # Add to Index
            new_index.add(emb.reshape(1, -1))
            
            # Update Metadata
            m["faiss_id"] = new_index.ntotal - 1
            updated_memories.append(m)
            
            successful_count += 1
            if successful_count % 10 == 0:
                print(f"   Processed {successful_count}/{len(memories)}...")
                
        except Exception as e:
            print(f"   ❌ Failed to embed '{text[:30]}...': {e}")
    
    # Save Index
    print(f"💾 Saving new index to {index_path}...")
    faiss.write_index(new_index, str(index_path))
    
    # Save Metadata
    print(f"💾 Saving updated metadata to {metadata_path}...")
    metadata_path.write_text(json.dumps(updated_memories, indent=2))
    
    print("✅ Repair Complete! Sync restored.")
    print(f"   Total Memories: {successful_count}")

if __name__ == "__main__":
    rebuild_index()
