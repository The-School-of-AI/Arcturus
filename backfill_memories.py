import sys
import os
import json
import logging
from pathlib import Path
from tqdm import tqdm

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from remme.store import RemmeStore
from remme.extractor import RemmeExtractor
from remme.utils import get_embedding

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def backfill():
    print("\n🚀 Starting Remme Memory Backfill...")
    print("---------------------------------------")
    
    root = Path(__file__).parent
    sessions_dir = root / "memory" / "session_summaries_index"
    
    if not sessions_dir.exists():
        print(f"❌ No sessions found at {sessions_dir}")
        return

    # Initialize Components
    try:
        store = RemmeStore()
        # USE FASTER MODEL: Llama 3.2 (2GB) is much faster than Qwen 8B (6GB)
        extractor = RemmeExtractor(model="llama3.2:latest") 
        print("✅ Connected to Remme Store & Extractor (Model: llama3.2:latest)")
    except Exception as e:
        print(f"❌ Failed to initialize Remme components: {e}")
        print("Make sure Ollama is running!")
        return
    
    # Setup Paths
    # Pattern: YYYY/MM/DD/session_*.json
    files = list(sessions_dir.rglob("session_*.json"))
    files = sorted(files, key=lambda x: x.stat().st_mtime) # Oldest first
    
    print(f"📂 Found {len(files)} historical session logs.")
    
    new_facts_count = 0
    errors = 0
    skipped = 0
    
    # Determine which sessions are already processed?
    # Remme v1 doesn't track "processed sessions" in a separate DB, 
    # but we can check if "source" exists in memories.
    # Reading all memories to memory for quick lookup (if small)
    existing_memories = store.get_all()
    processed_sources = set()
    for m in existing_memories:
        processed_sources.add(m.get("source", ""))
        
    print(f"🧠 Existing memories: {len(existing_memories)}")
    
    for f in tqdm(files, desc="Processing Sessions", unit="session"):
        try:
            # Check if likely already processed
            # We construct source ID as: "backfill_{run_id}" or "run_{run_id}"
            # Let's peek at ID first
            run_id = f.stem.replace("session_", "")
            
            # If we already have memories from this source, skip
            # Note: A run might have produced 0 memories, so this check strictly prevents DUPLICATE processing
            # but won't help if we missed it before. Backfill is usually safe to re-run if idempotent.
            # But here we are adding new vectors. We should avoid duplicates.
            # Let's check if ANY memory exists with source containing run_id
            is_processed = any(run_id in s for s in processed_sources)
            if is_processed:
                # print(f"Skipping {run_id} (Already in Memory)")
                skipped += 1
                continue
            
            # Load Data
            text_content = f.read_text()
            if not text_content.strip(): continue
            
            data = json.loads(text_content)
            
            # Extract basic info
            if "graph" in data:
                graph = data["graph"]
                query = graph.get("original_query", "")
            else:
                # Fallback for older formats if any
                query = data.get("query", "")
            
            if not query:
                skipped += 1
                continue
                
            # Reconstruct History
            # We look for nodes with outputs
            final_output = ""
            nodes = data.get("nodes", [])
            valid_run = False
            
            for node in nodes:
                # Check for completion
                if node.get("status") == "completed":
                    valid_run = True # At least one thing finished
                    output = node.get("output", "")
                    agent = node.get("agent", "Unknown")
                    if output:
                       # TRUNCATE OUTPUT to avoid massive context
                       # Llama 3.2 can handle larger context, but we still want to be safe.
                       # Limit to 10k chars (approx 2500 tokens) to catch most "Final Answers" without overloading.
                       out_str = str(output)
                       if len(out_str) > 10000:
                           out_str = out_str[:10000] + "... [TRUNCATED]"
                       final_output += f"[{agent}]: {out_str}\n"
            
            if not valid_run or not final_output:
                skipped += 1
                continue
                
            history = [{"role": "assistant", "content": final_output}]
            
            # NEW SMARTER MERGE LOGIC
            # 1. Search for existing related memories
            emb = get_embedding(query)
            existing = store.search(emb, k=5)
            
            # 2. Extract with context
            print(f"[{run_id}] Extracting facts (Context Aware)...")
            commands = extractor.extract(query, history, existing_memories=existing)
            
            if commands:
                for cmd in commands:
                    action = cmd.get("action")
                    text = cmd.get("text")
                    target_id = cmd.get("id")
                    
                    if action == "add" and text:
                        new_emb = get_embedding(text)
                        store.add(text, new_emb, category="historical", source=f"backfill_{run_id}")
                        new_facts_count += 1
                    elif action == "update" and target_id and text:
                        new_emb = get_embedding(text)
                        store.update_text(target_id, text, new_emb)
                    elif action == "delete" and target_id:
                        store.delete(target_id)
                
                print(f"[{run_id}] Processed {len(commands)} memory operations.")
            
            processed_sources.add(run_id)
            
        except Exception as e:
            logging.error(f"Failed to process {f.name}: {e}") # Changed to logging.error
            errors += 1
            
    print("\n---------------------------------------")
    print(f"🎉 Backfill Complete!")
    print(f"   - Processed: {len(files) - skipped} sessions")
    print(f"   - Skipped: {skipped} (Empty/Already Indexed)")
    print(f"   - Errors: {errors}")
    print(f"   - New Memories Added: {new_facts_count}")
    print("---------------------------------------")

if __name__ == "__main__":
    backfill()
