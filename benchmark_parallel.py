import time
import shutil
from pathlib import Path
import sys
import os

# Add mcp_servers to path to import server_rag
sys.path.append(os.path.join(os.getcwd(), "mcp_servers"))
from server_rag import process_documents

ROOT_INDEX = Path("mcp_servers/faiss_index")
BAK_INDEX = Path("mcp_servers/faiss_index_bak")

def setup():
    """Move existing index out of the way to force fresh ingestion."""
    if ROOT_INDEX.exists():
        if BAK_INDEX.exists():
            shutil.rmtree(BAK_INDEX)
        shutil.move(str(ROOT_INDEX), str(BAK_INDEX))
    print("✅ FAISS Index backed up. Cache cleared.")

def restore():
    """Restore the original index."""
    if ROOT_INDEX.exists():
        shutil.rmtree(ROOT_INDEX)
    if BAK_INDEX.exists():
        shutil.move(str(BAK_INDEX), str(ROOT_INDEX))
    print("✅ FAISS Index restored.")

if __name__ == "__main__":
    print("🚀 Benchmarking Parallel Ingestion...")
    try:
        setup()
        
        start_time = time.time()
        # This will now use ThreadPoolExecutor(max_workers=4)
        process_documents() 
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"\n⏱️ Total Time: {duration:.2f} seconds")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        restore()
