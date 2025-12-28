"""
ISOLATED TEST: num_predict=30 (short response) vs unlimited (full text)
This tests the specific impact of limiting output tokens.
"""
import requests
import time
from pathlib import Path
import pymupdf4llm

# Config
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
RAG_LLM_MODEL = "gemma3:1b"

# Get a single 1024 word chunk to test
pdf_path = Path(__file__).parent / "data" / "DLF_13072023190044_BRSR.pdf"
print(f"📄 Converting PDF to Markdown...")
text = pymupdf4llm.to_markdown(str(pdf_path))
words = text.split()
test_chunk = " ".join(words[:1024])  # Single 1024 word chunk
print(f"📏 Test chunk: {len(words[:1024])} words\n")


def test_old_prompt():
    """OLD: Ask for FULL second part of text."""
    prompt = f"""
You are a markdown document segmenter.

Here is a portion of a markdown document:

---
{test_chunk}
---

If this chunk clearly contains **more than one distinct topic or section**, reply ONLY with the **second part**, starting from the first sentence or heading of the new topic.

If it's only one topic, reply with NOTHING.

Keep markdown formatting intact.
"""
    start = time.time()
    result = requests.post(OLLAMA_CHAT_URL, json={
        "model": RAG_LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0}  # No num_predict limit
    }, timeout=120)
    elapsed = time.time() - start
    reply = result.json().get("message", {}).get("content", "").strip()
    return elapsed, len(reply.split()), reply[:100]


def test_new_prompt():
    """NEW: Ask for only first 10 words of second topic (30 tokens max)."""
    prompt = f"""Is this text about ONE topic or MULTIPLE topics?
If MULTIPLE: Reply with ONLY the first 10 words where the second topic starts.
If ONE topic: Reply "SINGLE"

Text start: {test_chunk[:500]}
Text end: ...{test_chunk[-200:]}
"""
    start = time.time()
    result = requests.post(OLLAMA_CHAT_URL, json={
        "model": RAG_LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 30}  # LIMIT OUTPUT
    }, timeout=60)
    elapsed = time.time() - start
    reply = result.json().get("message", {}).get("content", "").strip()
    return elapsed, len(reply.split()), reply[:100]


if __name__ == "__main__":
    print("=" * 70)
    print("🔬 ISOLATED TEST: num_predict=30 vs Unlimited Output")
    print("=" * 70)
    
    print("\n📜 OLD PROMPT (unlimited output)...")
    old_time, old_words, old_preview = test_old_prompt()
    print(f"   ⏱️  Time: {old_time:.2f}s")
    print(f"   📝 Output length: {old_words} words")
    print(f"   💬 Preview: {old_preview}...")
    
    print("\n🚀 NEW PROMPT (num_predict=30)...")
    new_time, new_words, new_preview = test_new_prompt()
    print(f"   ⏱️  Time: {new_time:.2f}s")
    print(f"   📝 Output length: {new_words} words")  
    print(f"   💬 Preview: {new_preview}...")
    
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print(f"\n{'Metric':<25} {'OLD':<15} {'NEW':<15}")
    print("-" * 55)
    print(f"{'Time (seconds)':<25} {old_time:<15.2f} {new_time:<15.2f}")
    print(f"{'Output words':<25} {old_words:<15} {new_words:<15}")
    
    speedup = old_time / new_time if new_time > 0 else 0
    print(f"\n⚡ SPEEDUP from limited output: {speedup:.2f}x faster")
    print(f"📉 Token reduction: {old_words} → {new_words} words ({100*(1-new_words/max(1,old_words)):.0f}% fewer)")
