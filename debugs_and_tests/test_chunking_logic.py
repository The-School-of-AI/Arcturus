import sys
from pathlib import Path
import re

# Add mcp_servers to path
sys.path.append(str(Path(__file__).parent.parent / "mcp_servers"))

from server_rag import find_sentence_end, get_safe_chunks

def test_cricket():
    data_path = Path(__file__).parent.parent / "data" / "cricket.txt"
    text = data_path.read_text()
    
    print(f"Original word count: {len(text.split())}")
    
    # Test safe chunking with a small limit to force splits
    chunks = get_safe_chunks(text, max_words=200, overlap=20)
    
    print(f"Total chunks: {len(chunks)}")
    
    all_pass = True
    for i, chunk in enumerate(chunks):
        # Check if ends with closure
        ends_with_closure = bool(re.search(r'[.!?]$', chunk.strip()))
        print(f"Chunk {i} length: {len(chunk.split())} words. Ends with closure: {ends_with_closure}")
        if not ends_with_closure:
            print(f"  FAILED: Chunk ends with: {chunk.strip()[-20:]!r}")
            all_pass = False
            
    if all_pass:
        print("\nSUCCESS: All chunks end with proper closures!")
    else:
        print("\nFAILURE: Some chunks do not end with proper closures.")

if __name__ == "__main__":
    test_cricket()
