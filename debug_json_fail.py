import sys
from pathlib import Path
import os
import json

# Setup paths
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.append(str(PROJECT_ROOT / "mcp_servers"))
sys.path.append(str(PROJECT_ROOT))

from mcp_servers.server_rag import advanced_ripgrep_search

def test_debug():
    print("Searching for 'Dhurandhar'...")
    results = advanced_ripgrep_search("Dhurandhar", max_results=5)
    
    if not results or (isinstance(results, list) and "error" in results[0]):
        print("Search failed:", results)
        return

    print(f"Found {len(results)} matches.")
    
    # Extract unique files
    files = set()
    for r in results:
        if "file" in r:
            files.add(r["file"])
            
    print(f"Unique files: {files}")
    
    for f in files:
        print(f"\n--- Testing read for: {f} ---")
        
        # Simulate routers/rag.py logic
        root = PROJECT_ROOT / "data"
        doc_path = root / f
        
        print(f"Trying data path: {doc_path}")
        if not doc_path.exists():
            print("Not found in data/")
            alt_path = PROJECT_ROOT / f
            print(f"Trying alt path: {alt_path}")
            if alt_path.exists():
                doc_path = alt_path
                print("Found in alt path!")
        
        # Deep Search Fallback
        if not doc_path.exists() and len(Path(f).parts) == 1:
            print("Trying rglob fallback...")
            found_files = list(PROJECT_ROOT.rglob(f))
            for found in found_files:
                if "memory" in str(found) or "data" in str(found):
                    doc_path = found
                    print(f"Found via rglob: {doc_path}")
                    break
            if not doc_path.exists() and found_files:
                doc_path = found_files[0]
                print(f"Found via rglob (first): {doc_path}")
                
        if not doc_path.exists():
             print("FAILED TO FIND FILE")
             continue
        else:
            print("Found in data/")
            
        try:
            content = doc_path.read_text(errors='replace')
            print(f"Read success. Length: {len(content)}")
        except Exception as e:
            print(f"READ ERROR: {e}")

if __name__ == "__main__":
    test_debug()
