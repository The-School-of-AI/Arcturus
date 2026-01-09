import sys
import os
from pathlib import Path
import re
import json

# Add mcp_servers to path
sys.path.append(str(Path(__file__).parent.parent / "mcp_servers"))
sys.path.append(str(Path(__file__).parent.parent))

from server_rag import convert_pdf_to_markdown, semantic_merge, get_safe_chunks

def test_pdf_chunking():
    pdf_path = "/Users/rohanshravan/TSAI/Arcturus/data/pdfs/1706.03762v7.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    print(f"Processing PDF: {pdf_path}")
    
    # 1. Extraction
    markdown_output = convert_pdf_to_markdown(pdf_path)
    markdown = markdown_output.markdown
    print(f"Extracted markdown length: {len(markdown)} chars")
    
    # 2. Semantic Merge
    print("\nRunning semantic merging...")
    chunks = semantic_merge(markdown)
    print(f"Number of semantic chunks: {len(chunks)}")
    
    # 3. Safe Chunking
    print("\nRunning safety chunking on largest chunks...")
    final_chunks = []
    for c in chunks:
        final_chunks.extend(get_safe_chunks(c))
    
    print(f"Final number of chunks: {len(final_chunks)}")
    
    # 4. Report Results
    print("\n--- RESULTS ANALYSIS ---")
    all_pass = True
    for i, chunk in enumerate(final_chunks[:10]): # Show first 10
        words = chunk.split()
        ends_with_closure = bool(re.search(r'[.!?](\s+|$|(\s*\*\*)|(\s*\*)|(\s*_)|(\s*__)|(\s*\]))', chunk.strip()))
        
        # More flexible check for PDF/Markdown content
        # Sometimes it might end with a reference [1] or bold text **text**
        # But we really want to check for punctuation relative to text.
        
        snippet = chunk.strip()[-50:]
        print(f"Chunk {i}: {len(words)} words. Ends with closure: {ends_with_closure}")
        print(f"  Ending: {snippet!r}")
        
        if not ends_with_closure:
            # Check if it's a list item or something that logically doesn't end in punctuation
            # For this test, we are strict to see the fix in action.
            all_pass = False
            
    if all_pass:
        print("\nSUCCESS: Sample chunks end with proper closures!")
    else:
        print("\nWARNING: Some chunks might still cut mid-sentence or at non-punctuation points.")

if __name__ == "__main__":
    test_pdf_chunking()
