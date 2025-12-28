"""
Benchmark: Gemma 3 1B vs Llama 3.2 for Semantic Chunking
Tests chunking quality and speed on large PDF converted to markdown.
"""
import requests
import time
from pathlib import Path
import pymupdf4llm

# Config
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
WORD_LIMIT = 1024  # Same as in server_rag.py

# Convert large PDF to markdown
pdf_path = Path(__file__).parent / "data" / "DLF_13072023190044_BRSR.pdf"
print(f"📄 Converting PDF to Markdown: {pdf_path.name}")
text = pymupdf4llm.to_markdown(str(pdf_path))
words = text.split()
print(f"📏 PDF converted: {len(words)} words total")

# Take first 4000 tokens (words)
test_text = " ".join(words[:4000])
print(f"🔬 Using first 4000 words for benchmark\n")


def semantic_merge(text: str, model: str, verbose: bool = False) -> list[str]:
    """Splits text semantically using LLM."""
    words = text.split()
    i = 0
    final_chunks = []
    call_count = 0
    
    while i < len(words):
        chunk_words = words[i:i + WORD_LIMIT]
        chunk_text = " ".join(chunk_words).strip()

        prompt = f"""
You are a markdown document segmenter.

Here is a portion of a markdown document:

---
{chunk_text}
---

If this chunk clearly contains **more than one distinct topic or section**, reply ONLY with the **second part**, starting from the first sentence or heading of the new topic.

If it's only one topic, reply with NOTHING.

Keep markdown formatting intact.
"""

        try:
            result = requests.post(OLLAMA_CHAT_URL, json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }, timeout=120)
            call_count += 1
            
            response = result.json()
            reply = response.get("message", {}).get("content", "").strip()
            
            # Check if model found a split point
            if reply and len(reply) > 50:
                # Found second part - store first part and continue with second
                split_idx = chunk_text.find(reply[:50])
                if split_idx > 0:
                    first_part = chunk_text[:split_idx].strip()
                    if first_part:
                        final_chunks.append(first_part)
                    # Recalculate word position for leftover
                    i += len(first_part.split())
                    if verbose:
                        print(f"  🔀 Split found at word {i}")
                else:
                    # Couldn't find exact match, take whole chunk
                    final_chunks.append(chunk_text)
                    i += len(chunk_words)
            else:
                # Single topic, keep as one chunk
                final_chunks.append(chunk_text)
                i += len(chunk_words)
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            final_chunks.append(chunk_text)
            i += len(chunk_words)
    
    return final_chunks, call_count


def benchmark_model(model_name: str, text: str):
    """Run chunking benchmark for a model."""
    print(f"\n{'='*60}")
    print(f"🧠 Model: {model_name}")
    print(f"{'='*60}")
    
    start = time.time()
    chunks, calls = semantic_merge(text, model_name, verbose=True)
    elapsed = time.time() - start
    
    print(f"\n📊 Results:")
    print(f"   ⏱️  Time: {elapsed:.2f}s")
    print(f"   📞 LLM Calls: {calls}")
    print(f"   📦 Chunks Created: {len(chunks)}")
    print(f"   📏 Avg Chunk Size: {sum(len(c.split()) for c in chunks) / len(chunks):.0f} words")
    
    print(f"\n📝 Chunk Previews (first 100 chars each):")
    for i, chunk in enumerate(chunks[:5]):  # Show first 5 chunks
        preview = chunk[:100].replace('\n', ' ')
        print(f"   [{i+1}] {preview}...")
    
    if len(chunks) > 5:
        print(f"   ... and {len(chunks) - 5} more chunks")
    
    return {
        "model": model_name,
        "time": elapsed,
        "calls": calls,
        "chunks": len(chunks),
        "avg_size": sum(len(c.split()) for c in chunks) / len(chunks)
    }


if __name__ == "__main__":
    print("=" * 60)
    print("🏁 Semantic Chunking Benchmark: Gemma 3 vs Llama 3.2")
    print("=" * 60)
    
    results = []
    
    # Test both models
    for model in ["gemma3:1b", "llama3.2:latest"]:
        try:
            result = benchmark_model(model, test_text)
            results.append(result)
        except Exception as e:
            print(f"❌ Failed to test {model}: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📈 SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"\n{r['model']}:")
        print(f"   Time: {r['time']:.2f}s | Chunks: {r['chunks']} | Avg Size: {r['avg_size']:.0f} words")
    
    if len(results) == 2:
        speedup = results[1]['time'] / results[0]['time'] if results[0]['time'] > 0 else 0
        print(f"\n⚡ Gemma is {speedup:.2f}x {'faster' if speedup > 1 else 'slower'} than Llama")
