"""
FIXED Benchmark: Shortened INPUT + 50-token OUTPUT
The real speedup comes from reducing BOTH input and output tokens.
"""
import requests
import time
from pathlib import Path
import pymupdf4llm
import concurrent.futures

# Config
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
RAG_LLM_MODEL = "gemma3:1b"
WORD_LIMIT = 1024

# Load PDF
pdf1 = Path(__file__).parent / "data" / "DLF_13072023190044_BRSR.pdf"
print("📄 Converting PDF to Markdown...")
doc1 = " ".join(pymupdf4llm.to_markdown(str(pdf1)).split()[:4000])
print(f"   Doc: {len(doc1.split())} words\n")


def chunk_old(text: str) -> tuple:
    """OLD: Full text in prompt, unlimited output."""
    words = text.split()
    chunks = []
    position = 0
    calls = 0
    
    while position < len(words):
        chunk_words = words[position:position + WORD_LIMIT]
        chunk_text = " ".join(chunk_words).strip()
        
        if len(chunk_words) < 50:
            chunks.append(chunk_text)
            break
        
        # FULL TEXT in prompt
        prompt = f"""You are a markdown document segmenter.

Here is a portion of a markdown document:
---
{chunk_text}
---

If this chunk clearly contains **more than one distinct topic or section**, reply ONLY with the **second part**, starting from the first sentence or heading of the new topic.

If it's only one topic, reply with NOTHING.
"""
        calls += 1
        result = requests.post(OLLAMA_CHAT_URL, json={
            "model": RAG_LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.0}
        }, timeout=120)
        reply = result.json().get("message", {}).get("content", "").strip()
        
        if reply and len(reply) > 50:
            split_idx = chunk_text.find(reply[:50])
            if split_idx > 50:
                chunks.append(chunk_text[:split_idx].strip())
                remainder = chunk_text[split_idx:]
                words = words[:position] + remainder.split() + words[position + WORD_LIMIT:]
                continue
        
        chunks.append(chunk_text)
        position += WORD_LIMIT
    
    return chunks, calls


def chunk_new(text: str) -> tuple:
    """NEW: Shortened input (first 600 + last 300 chars) + 50 token output."""
    words = text.split()
    chunks = []
    position = 0
    calls = 0
    
    while position < len(words):
        chunk_words = words[position:position + WORD_LIMIT]
        chunk_text = " ".join(chunk_words).strip()
        
        if len(chunk_words) < 50:
            chunks.append(chunk_text)
            break
        
        # SHORTENED INPUT - only first 600 + last 300 chars
        text_preview = chunk_text[:600] + "\n...[MIDDLE CONTENT]...\n" + chunk_text[-300:]
        
        prompt = f"""Does this text have 2+ topics?
YES: First 15 words of second topic.
NO: Reply "SINGLE"

{text_preview}"""
        
        calls += 1
        result = requests.post(OLLAMA_CHAT_URL, json={
            "model": RAG_LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 50}
        }, timeout=120)
        reply = result.json().get("message", {}).get("content", "").strip()
        
        if reply.upper() != "SINGLE" and len(reply) > 10:
            split_idx = chunk_text.find(reply[:40])
            if split_idx > 50:
                chunks.append(chunk_text[:split_idx].strip())
                remainder = chunk_text[split_idx:]
                words = words[:position] + remainder.split() + words[position + WORD_LIMIT:]
                continue
        
        chunks.append(chunk_text)
        position += WORD_LIMIT
    
    return chunks, calls


if __name__ == "__main__":
    print("=" * 70)
    print("🔬 FIXED Benchmark: Shortened Input + 50-token Output")
    print("=" * 70)
    print("OLD: Full 1024 words in prompt + unlimited output")
    print("NEW: 600+300 chars in prompt + 50 token output limit")
    print("=" * 70)
    
    print("\n📜 Running OLD approach...")
    start = time.time()
    old_chunks, old_calls = chunk_old(doc1)
    old_time = time.time() - start
    print(f"   ✓ Time: {old_time:.2f}s | Calls: {old_calls} | Chunks: {len(old_chunks)}")
    
    print("\n🚀 Running NEW approach...")
    start = time.time()
    new_chunks, new_calls = chunk_new(doc1)
    new_time = time.time() - start
    print(f"   ✓ Time: {new_time:.2f}s | Calls: {new_calls} | Chunks: {len(new_chunks)}")
    
    print("\n" + "=" * 70)
    print("📈 RESULTS")
    print("=" * 70)
    speedup = old_time / new_time if new_time > 0 else 0
    print(f"⚡ SPEEDUP: {speedup:.2f}x faster")
    print(f"📦 OLD chunks: {len(old_chunks)} | NEW chunks: {len(new_chunks)}")
    
    # Show chunk comparison
    print("\n📚 Chunk Comparison:")
    print(f"OLD: {[len(c.split()) for c in old_chunks]} words each")
    print(f"NEW: {[len(c.split()) for c in new_chunks]} words each")
