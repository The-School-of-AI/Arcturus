"""
COMPARISON: Old Sequential vs New Parallel Semantic Chunking
Tests both approaches separately and compares chunk quality + performance.
"""
import requests
import time
from pathlib import Path
import pymupdf4llm
import concurrent.futures

# Config
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
RAG_LLM_MODEL = "gemma3:1b"

# Convert PDF to markdown
pdf_path = Path(__file__).parent / "data" / "DLF_13072023190044_BRSR.pdf"
print(f"📄 Converting PDF to Markdown: {pdf_path.name}")
text = pymupdf4llm.to_markdown(str(pdf_path))
words = text.split()
print(f"📏 PDF converted: {len(words)} words total")
test_text = " ".join(words[:4000])
print(f"🔬 Using first 4000 words for benchmark\n")


# ============================================================
# OLD APPROACH: Sequential, 1024 word chunks, full text in prompt
# ============================================================
def semantic_merge_OLD(text: str) -> list[str]:
    """ORIGINAL: Sequential semantic chunking."""
    WORD_LIMIT = 1024
    words = text.split()
    i = 0
    final_chunks = []

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
                "model": RAG_LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0}
            }, timeout=120)
            reply = result.json().get("message", {}).get("content", "").strip()

            if reply:
                split_point = chunk_text.find(reply)
                if split_point != -1:
                    first_part = chunk_text[:split_point].strip()
                    second_part = reply.strip()
                    final_chunks.append(first_part)
                    leftover_words = second_part.split()
                    words = leftover_words + words[i + WORD_LIMIT:]
                    i = 0
                    continue
                else:
                    final_chunks.append(chunk_text)
            else:
                final_chunks.append(chunk_text)

        except Exception as e:
            print(f"   ❌ Error: {e}")
            final_chunks.append(chunk_text)

        i += WORD_LIMIT

    return final_chunks


# ============================================================
# NEW APPROACH: Parallel, 512 word chunks, optimized prompt
# ============================================================
def semantic_merge_NEW(text: str) -> list[str]:
    """OPTIMIZED: Parallel semantic chunking."""
    WORD_LIMIT = 512
    words = text.split()
    
    # Pre-split text into chunks
    chunk_texts = []
    for i in range(0, len(words), WORD_LIMIT):
        chunk_words = words[i:i + WORD_LIMIT]
        chunk_texts.append(" ".join(chunk_words).strip())
    
    if not chunk_texts:
        return [text]
    
    def check_split(chunk_text: str) -> tuple:
        """Check if chunk needs splitting."""
        prompt = f"""Is this text about ONE topic or MULTIPLE topics?
If MULTIPLE: Reply with ONLY the first 10 words where the second topic starts.
If ONE topic: Reply "SINGLE"

Text start: {chunk_text[:500]}
Text end: ...{chunk_text[-200:] if len(chunk_text) > 200 else ''}
"""
        try:
            result = requests.post(OLLAMA_CHAT_URL, json={
                "model": RAG_LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 30}
            }, timeout=60)
            reply = result.json().get("message", {}).get("content", "").strip()
            return (chunk_text, reply)
        except Exception as e:
            return (chunk_text, "SINGLE")
    
    # Parallel processing
    final_chunks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(check_split, chunk_texts))
    
    for chunk_text, reply in results:
        if reply and reply.upper() != "SINGLE" and len(reply) > 10:
            split_idx = chunk_text.find(reply[:30])
            if split_idx > 50:
                final_chunks.append(chunk_text[:split_idx].strip())
                final_chunks.append(chunk_text[split_idx:].strip())
            else:
                final_chunks.append(chunk_text)
        else:
            final_chunks.append(chunk_text)
    
    return [c for c in final_chunks if c.strip()]


def show_chunk_preview(chunks: list, name: str):
    """Display chunk previews for comparison."""
    print(f"\n📚 {name} - {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks[:5]):
        preview = chunk[:80].replace('\n', ' ')
        word_count = len(chunk.split())
        print(f"   [{i+1}] ({word_count}w) {preview}...")
    if len(chunks) > 5:
        print(f"   ... and {len(chunks) - 5} more chunks")


if __name__ == "__main__":
    print("=" * 70)
    print("🔬 COMPARISON: Old Sequential vs New Parallel Semantic Chunking")
    print("=" * 70)
    
    # Test OLD approach
    print("\n" + "=" * 70)
    print("📜 OLD APPROACH: Sequential, 1024 word chunks, full prompt")
    print("=" * 70)
    start = time.time()
    old_chunks = semantic_merge_OLD(test_text)
    old_time = time.time() - start
    print(f"   ⏱️  Time: {old_time:.2f}s")
    show_chunk_preview(old_chunks, "OLD")
    
    # Test NEW approach
    print("\n" + "=" * 70)
    print("🚀 NEW APPROACH: Parallel, 512 word chunks, optimized prompt")
    print("=" * 70)
    start = time.time()
    new_chunks = semantic_merge_NEW(test_text)
    new_time = time.time() - start
    print(f"   ⏱️  Time: {new_time:.2f}s")
    show_chunk_preview(new_chunks, "NEW")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"\n{'Metric':<25} {'OLD':<15} {'NEW':<15}")
    print("-" * 55)
    print(f"{'Time (seconds)':<25} {old_time:<15.2f} {new_time:<15.2f}")
    print(f"{'Chunks created':<25} {len(old_chunks):<15} {len(new_chunks):<15}")
    print(f"{'Avg words/chunk':<25} {sum(len(c.split()) for c in old_chunks)//len(old_chunks):<15} {sum(len(c.split()) for c in new_chunks)//len(new_chunks):<15}")
    
    speedup = old_time / new_time if new_time > 0 else 0
    print(f"\n⚡ SPEEDUP: NEW is {speedup:.2f}x faster than OLD")
    
    # Quality comparison - show first chunk from each
    print("\n" + "=" * 70)
    print("📝 CHUNK QUALITY COMPARISON (First chunk)")
    print("=" * 70)
    print(f"\nOLD first chunk ({len(old_chunks[0].split())} words):")
    print(f"   {old_chunks[0][:200]}...")
    print(f"\nNEW first chunk ({len(new_chunks[0].split())} words):")
    print(f"   {new_chunks[0][:200]}...")
