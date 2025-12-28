"""
OPTIMIZED Benchmark: Parallel + Reduced Token Semantic Chunking
Tests parallel processing and optimized prompts.
"""
import requests
import time
from pathlib import Path
import pymupdf4llm
import concurrent.futures

# Config
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
WORD_LIMIT = 512  # Smaller chunks = faster processing

# Convert large PDF to markdown
pdf_path = Path(__file__).parent / "data" / "DLF_13072023190044_BRSR.pdf"
print(f"📄 Converting PDF to Markdown: {pdf_path.name}")
text = pymupdf4llm.to_markdown(str(pdf_path))
words = text.split()
print(f"📏 PDF converted: {len(words)} words total")

# Take first 4000 tokens (words)
test_text = " ".join(words[:4000])
print(f"🔬 Using first 4000 words for benchmark\n")


def llm_split_check(chunk_text: str, model: str) -> str:
    """Single LLM call to check if chunk needs splitting. Returns split point or empty."""
    # OPTIMIZED PROMPT - shorter, asks for position not full text
    prompt = f"""Check if this text has 2+ distinct topics. If yes, reply with ONLY the first 10 words of the second topic. If single topic, reply "NONE".

Text:
{chunk_text[:500]}...{chunk_text[-200:]}
"""
    try:
        result = requests.post(OLLAMA_CHAT_URL, json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 50}  # Limit output tokens
        }, timeout=60)
        return result.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        return "ERROR"


def semantic_merge_sequential(text: str, model: str) -> tuple:
    """Original sequential approach."""
    words = text.split()
    chunks = []
    i = 0
    calls = 0
    
    while i < len(words):
        chunk_words = words[i:i + WORD_LIMIT]
        chunk_text = " ".join(chunk_words).strip()
        result = llm_split_check(chunk_text, model)
        calls += 1
        
        if result and result != "NONE" and len(result) > 10:
            # Found split point
            chunks.append(chunk_text)  # Simplified - keep whole chunk
        else:
            chunks.append(chunk_text)
        i += WORD_LIMIT
    
    return chunks, calls


def semantic_merge_parallel(text: str, model: str) -> tuple:
    """PARALLEL approach - process all chunks simultaneously."""
    words = text.split()
    chunk_texts = []
    
    # Pre-split into chunks
    for i in range(0, len(words), WORD_LIMIT):
        chunk_words = words[i:i + WORD_LIMIT]
        chunk_texts.append(" ".join(chunk_words).strip())
    
    # Process ALL chunks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(llm_split_check, chunk, model) for chunk in chunk_texts]
        results = [f.result() for f in futures]
    
    return chunk_texts, len(chunk_texts)


def benchmark(name: str, func, text: str, model: str):
    """Run benchmark and print results."""
    print(f"\n🔬 {name} with {model}")
    start = time.time()
    chunks, calls = func(text, model)
    elapsed = time.time() - start
    print(f"   ⏱️  Time: {elapsed:.2f}s | Calls: {calls} | Chunks: {len(chunks)}")
    return elapsed


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 OPTIMIZED Semantic Chunking Benchmark")
    print("=" * 60)
    
    model = "gemma3:1b"
    
    # Test 1: Original Sequential
    t1 = benchmark("Sequential", semantic_merge_sequential, test_text, model)
    
    # Test 2: Parallel
    t2 = benchmark("Parallel", semantic_merge_parallel, test_text, model)
    
    print(f"\n{'='*60}")
    print(f"📈 SPEEDUP: Parallel is {t1/t2:.2f}x faster than Sequential")
    print(f"{'='*60}")
