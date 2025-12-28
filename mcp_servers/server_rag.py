from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.prompts import base
from mcp.types import TextContent
from mcp import types
from PIL import Image as PILImage
import math
import sys
import os
import json
import faiss
import numpy as np
from pathlib import Path
import requests
from markitdown import MarkItDown
import time
from models import AddInput, AddOutput, SqrtInput, SqrtOutput, StringsToIntsInput, StringsToIntsOutput, ExpSumInput, ExpSumOutput, PythonCodeInput, PythonCodeOutput, UrlInput, FilePathInput, MarkdownInput, MarkdownOutput, ChunkListOutput, SearchDocumentsInput
from tqdm import tqdm
import hashlib
from pydantic import BaseModel
import subprocess
import sqlite3
import trafilatura
import pymupdf4llm
import re
import base64 # ollama needs base64-encoded-image
import asyncio
import concurrent.futures



mcp = FastMCP("Local Storage RAG")

EMBED_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
EMBED_MODEL = "nomic-embed-text"
RAG_LLM_MODEL = "gemma3:1b" # Faster than Qwen/Llama3, better for parallel semantic chunking
QWEN_MODEL = "qwen3-vl:8b" # Keep for vision and continuity
CHUNK_SIZE = 256
CHUNK_OVERLAP = 40
MAX_CHUNK_LENGTH = 512  # characters
TOP_K = 3  # FAISS top-K matches
OLLAMA_TIMEOUT = 300 # Seconds
ROOT = Path(__file__).parent.resolve()

# Global indexing status for progress tracking
INDEXING_STATUS = {
    "active": False,
    "total": 0,
    "completed": 0,
    "currentFile": ""
}


def get_embedding(text: str) -> np.ndarray:
    result = requests.post(EMBED_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=OLLAMA_TIMEOUT)
    result.raise_for_status()
    return np.array(result.json()["embedding"], dtype=np.float32)

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    for i in range(0, len(words), size - overlap):
        yield " ".join(words[i:i+size])

def mcp_log(level: str, message: str) -> None:
    sys.stderr.write(f"{level}: {message}\n")
    sys.stderr.flush()

def get_safe_chunks(text: str, max_words=512, overlap=50) -> list[str]:
    """Sub-splits a large semantic chunk technically to fit embedding context limits."""
    words = text.split()
    if len(words) <= max_words:
        return [text]
    
    sub_chunks = []
    for i in range(0, len(words), max_words - overlap):
        chunk = " ".join(words[i : i + max_words])
        if chunk.strip():
            sub_chunks.append(chunk)
        if i + max_words >= len(words):
            break
    return sub_chunks

# === CHUNKING ===





def are_related(chunk1: str, chunk2: str, index: int) -> bool:
    prompt = f"""
You are helping to segment a document into topic-based chunks. Unfortunately, the sentences are mixed up.

CHUNK 1: "{chunk1}"
CHUNK 2: "{chunk2}"

Should these two chunks appear in the **same paragraph or flow of writing**?

Even if the subject changes slightly (e.g., One person to another), treat them as related **if they belong to the same broader context or topic** (like cricket, AI, or real estate). 

Also consider cues like continuity words (e.g., "However", "But", "Also") or references that link the sentences.

Answer with:
Yes – if the chunks should appear together in the same paragraph or section  
No – if they are about different topics and should be separated

Just respond in one word (Yes or No), and do not provide any further explanation.
"""
    print(f"\nComparing chunk {index} and {index+1}")
    print(f"  Chunk {index} → {chunk1[:60]}{'...' if len(chunk1) > 60 else ''}")
    print(f"  Chunk {index+1} → {chunk2[:60]}{'...' if len(chunk2) > 60 else ''}")

    result = requests.post(OLLAMA_CHAT_URL, json={
        "model": QWEN_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }, timeout=OLLAMA_TIMEOUT)
    result.raise_for_status()
    reply = result.json().get("message", {}).get("content", "").strip().lower()
    print(f"Model reply: {reply}")
    return reply.startswith("yes")



@mcp.tool()
def preview_document(path: str) -> MarkdownOutput:
    """Preview a document using the AI-enhanced extraction logic used for indexing."""
    file = Path(path)
    if not file.exists():
        return MarkdownOutput(markdown=f"### ❌ Error\nFile not found: `{path}`")
    
    ext = file.suffix.lower()
    mcp_log("INFO", f"Previewing {file.name} (ext: {ext})")
    
    try:
        if ext == ".pdf":
            return convert_pdf_to_markdown(str(file))
        elif ext in [".html", ".htm", ".url"]:
            return extract_webpage(UrlInput(url=file.read_text().strip()))
        elif ext == ".py":
            return MarkdownOutput(markdown=f"```python\n{file.read_text()}\n```")
        elif ext in [".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"]:
            # markitdown is quite robust for these
            try:
                converter = MarkItDown()
                result = converter.convert(str(file))
                return MarkdownOutput(markdown=result.text_content)
            except Exception as e:
                return MarkdownOutput(markdown=f"### ⚠️ Extraction Failed\nCould not convert office document: {str(e)}\n\n**Tip:** Try checking if the file is password protected.")
        else:
            # Fallback to raw text for everything else
            text = file.read_text(errors='replace')
            return MarkdownOutput(markdown=f"### 📖 Raw View (Fallback)\n\n{text}")
    except Exception as e:
        mcp_log("ERROR", f"Preview failed: {str(e)}")
        return MarkdownOutput(markdown=f"### ❌ Critical Error\nExtraction failed: {str(e)}")
@mcp.tool()
async def ask_document(query: str, doc_id: str, history: list[dict] = [], image: str = None) -> str:
    """Ask a question about a specific document.
    Incorporates chat history, relevant document extracts, and optional image input.
    """
    mcp_log("ASK", f"Query: {query} for Doc: {doc_id} (Has Image: {bool(image)})")
    
    # 1. Get relevant context
    context_results = search_stored_documents_rag(query, doc_path=doc_id)
    context_text = "\n\n".join(context_results) if context_results else "No relevant context found in document."
    
    # 2. Build Prompt
    system_prompt = f"""You are a helpful document assistant. 
Answer the user's question based strictly on the provided context from the document.
If the context doesn't contain the answer, say so, but try to be helpful based on what is available.

CRITICAL: Always start your response with a thinking process enclosed in <think> tags. 
Analyze the context, identify key sections, and plan your answer before providing the final response.

CONTEXT FROM DOCUMENT:
---
{context_text}
---
"""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add truncated history (last 5 messages)
    for msg in history[-5:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
    # Add current query with image if present
    user_content = query
    user_msg = {"role": "user", "content": user_content}
    if image:
        # Ollama expects images in the message object for multimodal models
        user_msg["images"] = [image]
    
    messages.append(user_msg)
    
    try:
        # Using a direct requests post with stream=True for SSE-like delivery
        # Note: MCP tool return will be captured as a string initially, 
        # but we'll optimize the API layer to handle the generator if possible.
        # For now, let's make it yield chunks.
        
        response = requests.post(OLLAMA_CHAT_URL, json={
            "model": QWEN_MODEL,
            "messages": messages,
            "stream": True # Enable streaming
        }, timeout=OLLAMA_TIMEOUT, stream=True)
        response.raise_for_status()
        
        full_response = ""
        for line in response.iter_lines():
            if not line: continue
            try:
                data = json.loads(line)
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    full_response += chunk
                    # In a real MCP streaming setup, we might need a different pattern,
                    # but for this tight integration, we'll return the full text for now
                    # while building the SSE bridge in api.py.
                if data.get("done"): break
            except json.JSONDecodeError:
                continue
        
        return full_response
        
    except Exception as e:
        mcp_log("ERROR", f"Ollama ask failed: {e}")
        return f"Error: Could not reach the AI model for this document query. ({str(e)})"

@mcp.tool()
def search_stored_documents_rag(query: str, doc_path: str = None) -> list[str]:
    """Search old stored documents like PDF, DOCX, TXT, etc. to get relevant extracts. 
    Optionally provide doc_path to search within a specific document only.
    """
    ensure_faiss_ready()
    mcp_log("SEARCH", f"Query: {query} (Doc: {doc_path})")
    try:
        index = faiss.read_index(str(ROOT / "faiss_index" / "index.bin"))
        metadata = json.loads((ROOT / "faiss_index" / "metadata.json").read_text())
        query_vec = get_embedding(query).reshape(1, -1)
        # Increase k to get more candidates (filtering reduces final count)
        D, I = index.search(query_vec, k=50 if doc_path else 20)
        results = []
        for idx in I[0]:
            if idx < 0 or idx >= len(metadata): continue
            data = metadata[idx]
            
            # Filtering
            if doc_path and data.get('doc') != doc_path:
                continue
            
            # Runtime Filtering: Check if file still exists
            doc_rel_path = data.get('doc') # This is now relative path
            if not doc_rel_path: continue
            
            # Use data dir relative check
            full_path = ROOT.parent / "data" / doc_rel_path
            mcp_log("DEBUG", f"Checking path: {full_path} - exists: {full_path.exists()}")
            if not full_path.exists():
                # Removed/Renamed file -> Skip
                continue

            results.append(f"{data['chunk']}\n[Source: {doc_rel_path}]")
        mcp_log("DEBUG", f"Returning {len(results)} results")
        return results
    except Exception as e:
        return [f"ERROR: Failed to search: {str(e)}"]

@mcp.tool()
def keyword_search(query: str) -> list[str]:
    """Search for exact keyword matches across all indexed document chunks.
    Returns a list of document paths that contain the matching text.
    """
    mcp_log("KEYWORD_SEARCH", f"Query: {query}")
    try:
        meta_path = ROOT / "faiss_index" / "metadata.json"
        if not meta_path.exists():
            return []
            
        metadata = json.loads(meta_path.read_text())
        query_lower = query.lower()
        matching_docs = set()
        
        for entry in metadata:
            if query_lower in entry.get('chunk', '').lower():
                doc_path = entry.get('doc')
                if doc_path:
                    matching_docs.add(doc_path)
                    
        mcp_log("KEYWORD_SEARCH", f"Found matches in {len(matching_docs)} documents")
        return list(matching_docs)
    except Exception as e:
        mcp_log("ERROR", f"Keyword search failed: {e}")
        return []


def caption_image(img_url_or_path: str) -> str:
    mcp_log("CAPTION", f"Attempting to caption image: {img_url_or_path}")

    # Check if input is a URL
    if img_url_or_path.startswith("http://") or img_url_or_path.startswith("https://"):
        try:
            result = requests.get(img_url_or_path)
            if result.status_code != 200:
                raise Exception(f"HTTP {result.status_code}")
            encoded_image = base64.b64encode(result.content).decode("utf-8")
        except Exception as e:
            mcp_log("ERROR", f"Failed to download image from URL: {e}")
            return f"[Image could not be downloaded: {img_url_or_path}]"
    else:
        full_path = Path(__file__).parent / "documents" / img_url_or_path
        full_path = full_path.resolve()

        if not full_path.exists():
            mcp_log("ERROR", f"Image file not found: {full_path}")
            return f"[Image file not found: {img_url_or_path}]"

        with open(full_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode("utf-8")


    try:
        if img_url_or_path.startswith("http"): # for extract_web_pages
            result = requests.get(img_url_or_path)
            encoded_image = base64.b64encode(result.content).decode("utf-8")
        else:
            with open(full_path, "rb") as img_file:
                encoded_image = base64.b64encode(img_file.read()).decode("utf-8")

        # Set stream=True to get the full generator-style output
        with requests.post(OLLAMA_URL, json={
                "model": QWEN_MODEL,
                "prompt": "Look only at the attached image. If it's code, output it exactly as text. If it's a visual scene, describe it as you would for an image alt-text. Never generate new code. Return only the contents of the image.",
                "images": [encoded_image],
                "stream": True
            }, stream=True, timeout=OLLAMA_TIMEOUT) as result:

            caption_parts = []
            for line in result.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    caption_parts.append(data.get("response", ""))  # ✅ fixed key
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue  # skip malformed lines

            caption = "".join(caption_parts).strip()
            mcp_log("CAPTION", f"Caption generated: {caption}")
            return caption if caption else "[No caption returned]"

    except Exception as e:
        mcp_log("ERROR", f"Failed to caption image {img_url_or_path}: {e}")
        return f"[Image could not be processed: {img_url_or_path}]"





def replace_images_with_captions(markdown: str) -> str:
    def replace(match):
        alt, src = match.group(1), match.group(2)
        try:
            caption = caption_image(src)
            # Attempt to delete only if local and file exists
            if not src.startswith("http"):
                img_path = Path(__file__).parent / "documents" / src
                if img_path.exists():
                    img_path.unlink()
                    mcp_log("INFO", f"Deleted image after captioning: {img_path}")
            return f"**Image:** {caption}"
        except Exception as e:
            mcp_log("WARN", f"Image deletion failed: {e}")
            return f"[Image could not be processed: {src}]"

    return re.sub(r'!\[(.*?)\]\((.*?)\)', replace, markdown)


# @mcp.tool()
# def convert_webpage_url_into_markdown(input: UrlInput) -> MarkdownOutput:
#     """Return clean webpage content without Ads, and clutter. """

#     downloaded = trafilatura.fetch_url(input.url)
#     if not downloaded:
#         return MarkdownOut@mcp.tool()
def convert_pdf_to_markdown(string: str) -> MarkdownOutput:
    """Convert PDF to markdown. """


    if not os.path.exists(string):
        return MarkdownOutput(markdown=f"File not found: {string}")

    ROOT = Path(__file__).parent.resolve()
    global_image_dir = ROOT / "documents" / "images"
    global_image_dir.mkdir(parents=True, exist_ok=True)

    # Actual markdown with relative image paths
    markdown = pymupdf4llm.to_markdown(
        string,
        write_images=True,
        image_path=str(global_image_dir)
    )


    # Re-point image links in the markdown
    markdown = re.sub(
        r'!\[\]\((.*?/images/)([^)]+)\)',
        r'![](images/\2)',
        markdown.replace("\\", "/")
    )

    # DEFERRED VISION: Disable inline captioning to speed up ingestion
    # markdown = replace_images_with_captions(markdown)
    mcp_log("INFO", f"Skipped inline captioning for {string}. Images are saved.")
    return MarkdownOutput(markdown=markdown)


@mcp.tool()
def caption_images(img_url_or_path: str) -> str:
    caption = caption_image(img_url_or_path)
    return "The contents of this image are: " + caption


def semantic_merge(text: str) -> list[str]:
    """Splits text semantically using LLM: detects second topic and reuses leftover intelligently."""
    WORD_LIMIT = 1024
    words = text.split()
    i = 0
    final_chunks = []

    while i < len(words):
        # 1. Take next chunk of words (and prepend leftovers if any)
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
                "options": {"temperature": 0.0} # Absolute determinism
            }, timeout=OLLAMA_TIMEOUT)
            result.raise_for_status()
            reply = result.json().get("message", {}).get("content", "").strip()

            if reply:
                # If LLM returned second part, separate it
                split_point = chunk_text.find(reply)
                if split_point != -1:
                    first_part = chunk_text[:split_point].strip()
                    second_part = reply.strip()

                    final_chunks.append(first_part)

                    # Get remaining words from second_part and re-use them in next batch
                    leftover_words = second_part.split()
                    words = leftover_words + words[i + WORD_LIMIT:]
                    i = 0  # restart loop with leftover + remaining
                    continue
                else:
                    # fallback: if split point not found
                    final_chunks.append(chunk_text)
            else:
                final_chunks.append(chunk_text)

        except Exception as e:
            mcp_log("WARN", f"Semantic chunking LLM error: {e}")
            final_chunks.append(chunk_text)

        i += WORD_LIMIT

    return final_chunks







def file_hash(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()

def process_single_file(file: Path, doc_path_root: Path, cache_meta: dict):
    """Worker function to process a single file: Extract -> Chunk -> Embed."""
    try:
        rel_path = file.relative_to(doc_path_root).as_posix()
        fhash = file_hash(file)
        
        # Cache Check
        if rel_path in cache_meta:
            if cache_meta[rel_path] == fhash:
                return {"status": "SKIP", "rel_path": rel_path, "hash": fhash}
            else:
                mcp_log("INFO", f"Change detected: {rel_path} (re-indexing)")
        else:
            mcp_log("INFO", f"New file: {rel_path}")

        mcp_log("PROC", f"Processing: {rel_path}")

        # Extraction
        ext = file.suffix.lower()
        markdown = ""

        if ext == ".pdf":
            markdown = convert_pdf_to_markdown(str(file)).markdown
        elif ext in [".html", ".htm", ".url"]:
            markdown = extract_webpage(UrlInput(url=file.read_text().strip())).markdown
        elif ext == ".py":
            text = file.read_text()
            markdown = f"```python\n{text}\n```"
        else:
            # Fallback
            converter = MarkItDown()
            markdown = converter.convert(str(file)).text_content

        if not markdown.strip():
            return {"status": "WARN", "rel_path": rel_path, "message": "No content extracted"}

        # Semantic Chunking
        try:
            if len(markdown.split()) < 50:
                chunks = [markdown.strip()]
            else:
                chunks = semantic_merge(markdown)
        except Exception as e:
            chunks = list(chunk_text(markdown))

        embeddings_for_file = []
        new_metadata_entries = []
        
        final_safe_chunks = []
        for c in chunks:
            final_safe_chunks.extend(get_safe_chunks(c))

        # Batch Embedding (Local)
        BATCH_SIZE = 32
        
        # Process in batches
        for i in range(0, len(final_safe_chunks), BATCH_SIZE):
            batch = final_safe_chunks[i : i + BATCH_SIZE]
            
            # Call batch API
            try:
                batch_url = EMBED_URL.replace("/api/embeddings", "/api/embed")
                res = requests.post(batch_url, json={
                    "model": EMBED_MODEL,
                    "input": batch
                }, timeout=OLLAMA_TIMEOUT)
                res.raise_for_status()
                embeddings_list = [np.array(e, dtype=np.float32) for e in res.json()["embeddings"]]
            except Exception as e:
                # Fallback
                embeddings_list = [get_embedding(t) for t in batch]

            # Add to results
            for j, embedding in enumerate(embeddings_list):
                real_idx = i + j
                chunk = batch[j]
                embeddings_for_file.append(embedding)
                new_metadata_entries.append({
                    "doc": rel_path,
                    "chunk": chunk,
                    "chunk_id": f"{rel_path}_{real_idx}"
                })
        
        return {
            "status": "SUCCESS",
            "rel_path": rel_path,
            "hash": fhash,
            "embeddings": embeddings_for_file,
            "metadata": new_metadata_entries
        }

    except Exception as e:
        return {"status": "ERROR", "rel_path": str(file), "message": str(e)}


def process_documents(target_path: str = None, specific_files: list[Path] = None):
    """Process documents and create FAISS index using Parallel Processing (ThreadPoolExecutor)."""
    mcp_log("INFO", f"Indexing documents... {'(Target: ' + target_path + ')' if target_path else ''}")
    ROOT = Path(__file__).parent.resolve()
    DOC_PATH = ROOT.parent / "data"
    INDEX_CACHE = ROOT / "faiss_index"
    INDEX_CACHE.mkdir(exist_ok=True)
    INDEX_FILE = INDEX_CACHE / "index.bin"
    METADATA_FILE = INDEX_CACHE / "metadata.json"
    CACHE_FILE = INDEX_CACHE / "doc_index_cache.json"

    CACHE_META = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    metadata = json.loads(METADATA_FILE.read_text()) if METADATA_FILE.exists() else []

    mcp_log("INFO", f"Loaded cache with {len(CACHE_META)} files")

    index = faiss.read_index(str(INDEX_FILE)) if INDEX_FILE.exists() else None

    files_to_process = []
    if specific_files:
        files_to_process = specific_files
    elif target_path:
        target_file = DOC_PATH / target_path
        if target_file.exists() and target_file.is_file():
            files_to_process = [target_file]
        else:
            mcp_log("ERROR", f"Target path not found: {target_path}")
            return
    else:
        # Glob first, filter images
        all_files = DOC_PATH.rglob("*.*")
        files_to_process = [f for f in all_files if f.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']]

    # PARALLEL EXECUTION
    # Max workers = 2 (reduced from 4 to prevent Ollama timeouts)
    MAX_WORKERS = 2
    mcp_log("INFO", f"Starting parallel ingestion with {MAX_WORKERS} workers on {len(files_to_process)} files")
    
    # Initialize progress tracking
    global INDEXING_STATUS
    INDEXING_STATUS = {
        "active": True,
        "total": len(files_to_process),
        "completed": 0,
        "currentFile": ""
    }
    
    param_cache_meta = CACHE_META.copy() # Read-only for threads
    
    # Thread-safe lock for incremental saves
    import threading
    index_lock = threading.Lock()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Map futures
        futures = {executor.submit(process_single_file, f, DOC_PATH, param_cache_meta): f for f in files_to_process}
        
        # Collect results as they complete
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(files_to_process), desc="Indexing"):
            result = future.result()
            status = result.get("status")
            rel_path = result.get("rel_path")
            
            if status == "SKIP":
                # mcp_log("SKIP", f"Skipping {rel_path}")
                pass
            
            elif status == "SUCCESS":
                fhash = result.get("hash")
                new_embs = result.get("embeddings")
                new_meta = result.get("metadata")
                
                if new_embs:
                    # Thread-safe index update and save
                    with index_lock:
                        # 1. Cleanup old entries if exist
                        if rel_path in CACHE_META:
                            metadata = [m for m in metadata if m.get("doc") != rel_path]
                            
                        # 2. Add new
                        if index is None:
                            dim = len(new_embs[0])
                            index = faiss.IndexFlatL2(dim)
                        
                        index.add(np.stack(new_embs))
                        metadata.extend(new_meta)
                        CACHE_META[rel_path] = fhash # Update cache
                        
                        # 3. INCREMENTAL SAVE (Crash-safe)
                        try:
                            CACHE_FILE.write_text(json.dumps(CACHE_META, indent=2))
                            METADATA_FILE.write_text(json.dumps(metadata, indent=2))
                            faiss.write_index(index, str(INDEX_FILE))
                        except Exception as e:
                            mcp_log("WARN", f"Incremental save failed: {e}")
                        
                        mcp_log("DONE", f"Indexed {rel_path} ({len(new_embs)} chunks)")
                        
                        # Update progress
                        INDEXING_STATUS["completed"] += 1
                        INDEXING_STATUS["currentFile"] = Path(rel_path).name
            
            elif status == "WARN":
                mcp_log("WARN", f"{rel_path}: {result.get('message')}")
                
            elif status == "ERROR":
                mcp_log("ERROR", f"Failed {rel_path}: {result.get('message')}")

    # Reset indexing status
    INDEXING_STATUS["active"] = False
    INDEXING_STATUS["currentFile"] = ""
    mcp_log("INFO", "READY")


@mcp.tool()
async def reindex_documents(target_path: str = None) -> str:
    """Trigger a manual re-index of the RAG documents. 
    Optionally provide a target_path (relative to data/ folder) to index a specific file.
    """
    mcp_log("INFO", f"Re-indexing request received (target: {target_path})")
    # Run the blocking process_documents in a separate thread
    await asyncio.to_thread(process_documents, target_path)
    return f"Re-indexing {'for ' + target_path if target_path else 'all documents'} completed successfully."


@mcp.tool()
async def get_indexing_status() -> str:
    """Get the current indexing progress status as JSON."""
    return json.dumps(INDEXING_STATUS)


@mcp.tool()
async def index_images() -> str:
    """Background Worker: Scans for un-captioned images, captions them using Vision Model, and updates the index."""
    ROOT = Path(__file__).parent.resolve()
    IMG_DIR = ROOT / "documents" / "images"
    CAPTIONS_FILE = ROOT / "faiss_index" / "captions.json"
    INDEX_CACHE = ROOT / "faiss_index"
    INDEX_FILE = INDEX_CACHE / "index.bin"
    METADATA_FILE = INDEX_CACHE / "metadata.json"
    
    if not IMG_DIR.exists():
        return "No images directory found."

    captions_ledger = json.loads(CAPTIONS_FILE.read_text()) if CAPTIONS_FILE.exists() else {}
    metadata = json.loads(METADATA_FILE.read_text()) if METADATA_FILE.exists() else []
    index = faiss.read_index(str(INDEX_FILE)) if INDEX_FILE.exists() else None

    # Find pending images
    all_images = list(IMG_DIR.glob("*.png")) + list(IMG_DIR.glob("*.jpg"))
    pending_images = [img for img in all_images if img.name not in captions_ledger]
    
    if not pending_images:
        return "No new images to caption."
    
    # Sort to keep order deterministic
    pending_images.sort(key=lambda x: x.name)
    
    mcp_log("INFO", f"Found {len(pending_images)} images to caption in background.")
    
    new_embeddings = []
    new_meta = []
    
    # Process in batches or one by one (caption_image is sequential due to VRAM)
    for img in pending_images:
        try:
            mcp_log("PROC", f"Captioning {img.name}...")
            # 1. Generate Caption (Vision Model)
            # using sync call inside async tool might block loop, but acceptable for background worker
            caption = caption_image(str(img))
            
            # 2. Add to Ledger
            captions_ledger[img.name] = caption
            
            # 3. Create Semantic Chunk (Additive)
            # Try to infer original doc: filename.pdf-page-imgIdx
            try:
                original_doc = img.stem.rsplit("-", 2)[0] 
            except:
                original_doc = img.stem

            chunk_text = f"Image Context from {original_doc} (Page {img.stem.split('-')[-2]}): {caption}"
            
            # 4. Embed
            embedding = get_embedding(chunk_text)
            new_embeddings.append(embedding)
            
            new_meta.append({
                "doc": str(img.name), # We link to the image file so UI can show it
                "chunk": chunk_text,
                "chunk_id": f"IMG_{img.name}",
                "type": "image_caption",
                "source_doc": original_doc
            })
            
        except Exception as e:
            mcp_log("ERROR", f"Failed to caption {img.name}: {e}")

    # Save Updates
    if new_embeddings:
        if index is None:
             index = faiss.IndexFlatL2(len(new_embeddings[0]))
        index.add(np.stack(new_embeddings))
        metadata.extend(new_meta)
        
        CAPTIONS_FILE.write_text(json.dumps(captions_ledger, indent=2))
        METADATA_FILE.write_text(json.dumps(metadata, indent=2))
        faiss.write_index(index, str(INDEX_FILE))
        
        return f"Successfully processed {len(new_embeddings)} images. Index updated."
    
    return "Processed images but no valid captions generated."


def ensure_faiss_ready():
    index_path = ROOT / "faiss_index" / "index.bin"
    meta_path = ROOT / "faiss_index" / "metadata.json"
    if not (index_path.exists() and meta_path.exists()):
        mcp_log("INFO", "Index not found — running process_documents()...")
        process_documents()
    else:
        mcp_log("INFO", "Index already exists. Skipping regeneration.")


if __name__ == "__main__":
    mcp_log("INFO", "🚀 Starting RAG MCP Server...")
    mcp.run()
