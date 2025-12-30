import sys
import os
import json
import faiss
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from remme.store import RemmeStore
from remme.utils import get_embedding

def sync():
    print("🔄 Synchronizing Remme Vault (Metadata -> FAISS Index)...")
    store = RemmeStore()
    
    # Reload from JSON
    if store.metadata_path.exists():
        with open(store.metadata_path, 'r') as f:
            store.memories = json.load(f)
    
    if not store.memories:
        print("Vault is empty. Nothing to sync.")
        return

    print(f"Syncing {len(store.memories)} memories...")
    
    # Rebuild Index
    dimension = 768 # nomic-embed-text
    new_index = faiss.IndexFlatL2(dimension)
    
    for i, m in enumerate(store.memories):
        print(f"  [{i+1}/{len(store.memories)}] Embedding: {m['text'][:50]}...")
        emb = get_embedding(m["text"])
        new_index.add(emb.reshape(1, -1))
        m["faiss_id"] = i
    
    store.index = new_index
    store.save()
    print("✅ Sync complete.")

if __name__ == "__main__":
    sync()
