"""
COMPREHENSIVE Benchmark: OLD vs NEW Semantic Chunking
- Compares: Full output vs 50-token limit
- Tests: Sequential within doc, Parallel across docs
- Uses: 2 large PDFs
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

# Load 2 large PDFs
pdf1 = Path(__file__).parent / "data" / "DLF_13072023190044_BRSR.pdf"
pdf2 = Path(__file__).parent / "data" / "INVG67564.pdf"

print("📄 Converting PDFs to Markdown...")
doc1 = " ".join(pymupdf4llm.to_markdown(str(pdf1)).split()[:4000])
doc2 = " ".join(pymupdf4llm.to_markdown(str(pdf2)).split()[:4000])
print(f"   Doc1 (DLF_BRSR): {len(doc1.split())} words")
print(f"   Doc2 (INVG): {len(doc2.split())} words")


# ============================================================
# OLD APPROACH: Ask for FULL second part (unlimited tokens)
# ============================================================
def chunk_old(text: str) -> tuple:
    """OLD: Sequential, asks for full second part."""
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
            "options": {"temperature": 0.0}  # NO num_predict limit
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


# ============================================================
# NEW APPROACH: Ask for 50 tokens (first 15 words of split)
# ============================================================
def chunk_new(text: str) -> tuple:
    """NEW: Sequential, asks for 50 tokens max."""
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
        
        prompt = f"""Does this text contain MORE THAN ONE topic?
If YES: Reply with first 15 words where second topic starts.
If NO: Reply "SINGLE"

TEXT:
{chunk_text}
"""
        calls += 1
        result = requests.post(OLLAMA_CHAT_URL, json={
            "model": RAG_LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 50}  # LIMITED OUTPUT
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


def benchmark_single(name: str, func, text: str):
    """Benchmark a single document."""
    start = time.time()
    chunks, calls = func(text)
    elapsed = time.time() - start
    return {
        "name": name,
        "time": elapsed,
        "calls": calls,
        "chunks": len(chunks)
    }


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🔬 COMPREHENSIVE BENCHMARK: OLD vs NEW Semantic Chunking")
    print("=" * 70)
    
    # ============================================================
    # TEST 1: Single document comparison
    # ============================================================
    print("\n📊 TEST 1: Single Document (DLF_BRSR - 4000 words)")
    print("-" * 50)
    
    print("   Running OLD approach (unlimited output)...")
    r1 = benchmark_single("OLD", chunk_old, doc1)
    print(f"   ✓ OLD: {r1['time']:.2f}s, {r1['calls']} calls, {r1['chunks']} chunks")
    
    print("   Running NEW approach (50 token limit)...")
    r2 = benchmark_single("NEW", chunk_new, doc1)
    print(f"   ✓ NEW: {r2['time']:.2f}s, {r2['calls']} calls, {r2['chunks']} chunks")
    
    speedup1 = r1['time'] / r2['time'] if r2['time'] > 0 else 0
    print(f"   ⚡ Speedup: {speedup1:.2f}x faster")
    
    # ============================================================
    # TEST 2: Parallel processing of 2 documents
    # ============================================================
    print("\n📊 TEST 2: Parallel Processing (2 Documents)")
    print("-" * 50)
    
    # Sequential (process one after another)
    print("   Running SEQUENTIAL (2 docs one after another)...")
    start = time.time()
    seq_r1, _ = chunk_new(doc1)
    seq_r2, _ = chunk_new(doc2)
    seq_time = time.time() - start
    print(f"   ✓ Sequential: {seq_time:.2f}s")
    
    # Parallel (process both at same time)
    print("   Running PARALLEL (2 docs simultaneously)...")
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(chunk_new, doc1),
            executor.submit(chunk_new, doc2)
        ]
        results = [f.result() for f in futures]
    par_time = time.time() - start
    print(f"   ✓ Parallel: {par_time:.2f}s")
    
    speedup2 = seq_time / par_time if par_time > 0 else 0
    print(f"   ⚡ Parallel Speedup: {speedup2:.2f}x faster")
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print("📈 SUMMARY")
    print("=" * 70)
    print(f"\n{'Optimization':<35} {'Speedup':<15}")
    print("-" * 50)
    print(f"{'50-token limit vs unlimited':<35} {speedup1:.2f}x")
    print(f"{'Parallel docs vs sequential':<35} {speedup2:.2f}x")
    print(f"{'COMBINED (estimated)':<35} {speedup1 * speedup2:.2f}x")
