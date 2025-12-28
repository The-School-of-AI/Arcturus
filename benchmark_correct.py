"""
CORRECT Semantic Chunking Implementation
- Sequential within document (preserves semantic cohesion)
- Gets 50 tokens for split point, then feeds remainder back
- Iterates until no more splits found
"""
import requests
import time
from pathlib import Path
import pymupdf4llm

# Config
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
RAG_LLM_MODEL = "gemma3:1b"
WORD_LIMIT = 1024  # Max words per LLM call

# Load test document
pdf_path = Path(__file__).parent / "data" / "DLF_13072023190044_BRSR.pdf"
print(f"📄 Converting PDF to Markdown...")
text = pymupdf4llm.to_markdown(str(pdf_path))
words = text.split()
test_text = " ".join(words[:4000])  # First 4000 words
print(f"📏 Test document: {len(words[:4000])} words\n")


def find_split_point(chunk_text: str) -> str:
    """Ask LLM: Where does second topic start? Returns first 50 tokens of split point."""
    prompt = f"""Analyze this markdown text for topic changes.

TEXT:
---
{chunk_text}
---

TASK: Does this text contain MORE THAN ONE distinct topic or section?

If YES: Reply with ONLY the first 15 words where the SECOND topic/section begins.
If NO (single topic): Reply exactly "SINGLE"

Your response (first 15 words of second topic, or "SINGLE"):"""

    result = requests.post(OLLAMA_CHAT_URL, json={
        "model": RAG_LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 50}  # 50 tokens max
    }, timeout=120)
    
    reply = result.json().get("message", {}).get("content", "").strip()
    return reply


def semantic_chunk_iterative(text: str) -> list[str]:
    """
    CORRECT iterative semantic chunking:
    1. Take first 1024 words
    2. Ask LLM for split point (50 tokens)
    3. If split found: split text, keep first part, feed second part back
    4. If no split: keep whole chunk, move to next 1024 words
    5. Repeat until text exhausted
    """
    words = text.split()
    final_chunks = []
    position = 0
    llm_calls = 0
    
    while position < len(words):
        # Take next 1024 words (or remaining)
        chunk_words = words[position:position + WORD_LIMIT]
        chunk_text = " ".join(chunk_words).strip()
        
        if len(chunk_words) < 50:
            # Too small, just append
            final_chunks.append(chunk_text)
            break
        
        print(f"   🔍 Analyzing words {position}-{position + len(chunk_words)}...")
        llm_calls += 1
        
        reply = find_split_point(chunk_text)
        print(f"      LLM reply: '{reply[:60]}...'")
        
        if reply.upper() == "SINGLE" or len(reply) < 10:
            # No split found - keep whole chunk, move forward
            final_chunks.append(chunk_text)
            position += WORD_LIMIT
        else:
            # Split found! Find the split point in text
            split_marker = reply[:50].strip()
            split_idx = chunk_text.find(split_marker)
            
            if split_idx > 50:  # Valid split
                first_part = chunk_text[:split_idx].strip()
                final_chunks.append(first_part)
                
                # KEY: Prepend remainder to continue processing
                remainder = chunk_text[split_idx:]
                remainder_words = remainder.split()
                # Insert remainder back at current position
                words = words[:position] + remainder_words + words[position + WORD_LIMIT:]
                # Don't advance position - we'll process the remainder
                print(f"      ✂️  Split! First part: {len(first_part.split())}w, Remainder: {len(remainder_words)}w")
            else:
                # Split point not found in text, keep whole chunk
                final_chunks.append(chunk_text)
                position += WORD_LIMIT
    
    return final_chunks, llm_calls


if __name__ == "__main__":
    print("=" * 70)
    print("🔬 CORRECT Iterative Semantic Chunking Test")
    print("=" * 70)
    print("Algorithm:")
    print("  1. Take 1024-word block")
    print("  2. Ask LLM for split point (50 tokens max)")
    print("  3. If split: separate, feed remainder back")
    print("  4. If no split: keep chunk, move to next block")
    print("=" * 70)
    
    start = time.time()
    chunks, calls = semantic_chunk_iterative(test_text)
    elapsed = time.time() - start
    
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print(f"⏱️  Total Time: {elapsed:.2f}s")
    print(f"📞 LLM Calls: {calls}")
    print(f"📦 Chunks Created: {len(chunks)}")
    print(f"📏 Avg words/chunk: {sum(len(c.split()) for c in chunks) // len(chunks)}")
    
    print("\n📚 Chunk Breakdown:")
    for i, chunk in enumerate(chunks):
        word_count = len(chunk.split())
        preview = chunk[:80].replace('\n', ' ')
        print(f"   [{i+1}] ({word_count}w) {preview}...")
