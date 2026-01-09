import sys
import os
from pathlib import Path
import re
import json

# Add paths
sys.path.append(str(Path(__file__).parent.parent / "mcp_servers"))
sys.path.append(str(Path(__file__).parent.parent))

from server_rag import convert_pdf_to_markdown, semantic_merge, get_safe_chunks

def test_pdf_chunking_fast():
    pdf_path = "/Users/rohanshravan/TSAI/Arcturus/data/pdfs/1706.03762v7.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    print(f"Processing PDF: {pdf_path}")
    
    # 1. Extraction
    markdown_output = convert_pdf_to_markdown(pdf_path)
    full_markdown = markdown_output.markdown
    
    # Use first 5000 chars
    markdown = full_markdown[:5000]
    print(f"Using sliced markdown (first 5000 chars)")
    
    # 2. Semantic Merge
    print("\nRunning semantic merging...")
    chunks = semantic_merge(markdown)
    print(f"Number of semantic chunks: {len(chunks)}")
    
    # 3. Safe Chunking
    # Set max_words higher to see the impact of sentence closures
    print("\nRunning safety chunking on largest chunks (max_words=256)...")
    final_chunks = []
    for c in chunks:
        final_chunks.extend(get_safe_chunks(c, max_words=256, overlap=40))
    
    print(f"Final number of chunks: {len(final_chunks)}")
    
    # 4. Report Results
    print("\n--- RESULTS ANALYSIS ---")
    for i, chunk in enumerate(final_chunks):
        words = chunk.split()
        # Check for closure: punct followed by space or end
        ends_with_closure = bool(re.search(r'[.!?](\s+|$)', chunk.strip()))
        
        snippet = chunk.strip()[-60:]
        print(f"Chunk {i}: {len(words)} words. Ends with closure: {ends_with_closure}")
        print(f"  Ending: {snippet!r}")

if __name__ == "__main__":
    test_pdf_chunking_fast()
