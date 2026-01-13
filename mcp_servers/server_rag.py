from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.prompts import base
from mcp.types import TextContent
from mcp import types
from PIL import Image as PILImage
import math
import sys
import os
import json
from pathlib import Path

# Fix attributes/imports pathing
# 1. Add current directory (mcp_servers) to path so 'import models' works
sys.path.append(str(Path(__file__).parent))
# 2. Add project root to path so 'config.settings_loader' works
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import local models
try:
    from models import AddInput, AddOutput, SqrtInput, SqrtOutput, StringsToIntsInput, StringsToIntsOutput, ExpSumInput, ExpSumOutput, PythonCodeInput, PythonCodeOutput, UrlInput, FilePathInput, MarkdownInput, MarkdownOutput, ChunkListOutput, SearchDocumentsInput
except ImportError:
    # Fallback if running from root without path setup (safety)
    from mcp_servers.models import AddInput, AddOutput, SqrtInput, SqrtOutput, StringsToIntsInput, StringsToIntsOutput, ExpSumInput, ExpSumOutput, PythonCodeInput, PythonCodeOutput, UrlInput, FilePathInput, MarkdownInput, MarkdownOutput, ChunkListOutput, SearchDocumentsInput

import faiss
import numpy as np
import requests
from markitdown import MarkItDown
import time

# MCP Protocol Safety: Redirect print to stderr
def print(*args, **kwargs):
    sys.stderr.write(" ".join(map(str, args)) + "\n")
    sys.stderr.flush()

from tqdm import tqdm
import hashlib
from pydantic import BaseModel
import subprocess
import sqlite3
import trafilatura
import pymupdf4llm
import fitz # Silencing library logs
try:
    fitz.TOOLS.mupdf_display_errors(False) # Newer versions
    fitz.TOOLS.set_stderr_log(False)
except:
    pass
import re
import base64 # ollama needs base64-encoded-image
import asyncio
import concurrent.futures
import threading
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# Import the new index scheduler
from index_scheduler import init_scheduler, get_scheduler, shutdown_scheduler

# BM25 for hybrid search
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False

from config.settings_loader import settings, get_ollama_url, get_model, get_timeout

mcp = FastMCP("Local Storage RAG")

# --- Settings from centralized config ---
EMBED_URL = get_ollama_url("embeddings")
OLLAMA_CHAT_URL = get_ollama_url("chat")
OLLAMA_URL = get_ollama_url("generate")
EMBED_MODEL = get_model("embedding")
RAG_LLM_MODEL = get_model("semantic_chunking")
VISION_MODEL = get_model("image_captioning")
CHUNK_SIZE = settings["rag"]["chunk_size"]
CHUNK_OVERLAP = settings["rag"]["chunk_overlap"]
MAX_CHUNK_LENGTH = settings["rag"]["max_chunk_length"]
TOP_K = settings["rag"]["top_k"]
OLLAMA_TIMEOUT = get_timeout()
ROOT = Path(__file__).parent.resolve()
BASE_DATA_DIR = ROOT.parent / "data"
MEMORY_SUMMARIES_DIR = ROOT.parent / "memory" / "session_summaries_index"
SYNC_TARGET_DIR = BASE_DATA_DIR / "conversation_history"

# Global indexing status for progress tracking
INDEXING_STATUS = {
    "active": False,
    "total": 0,
    "completed": 0,
    "currentFile": ""
}
INDEXING_LOCK = threading.Lock()
REINDEX_BUSY_LOCK = threading.Lock()

def get_rg_path():
    """Find the ripgrep binary. Checks .bin/ folder first, then system path."""
    project_bin = ROOT.parent / ".bin" / "rg"
    if project_bin.exists():
        return str(project_bin)
    
    # Fallback to system path
    try:
        import subprocess
        result = subprocess.run(["which", "rg"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    return None


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

def find_sentence_end(text: str, target_pos: int, direction: str = 'back', window: int = 150) -> int:
    """Finds the nearest sentence boundary (.!? followed by space or newline).
    
    Args:
        text: The text to search in.
        target_pos: The desired split point (index).
        direction: 'back' to look before target_pos, 'forward' to look after.
        window: How many characters to look in either direction.
    
    Returns:
        The index of the end of the sentence (including punctuation and trailing space),
        or target_pos if no boundary is found within the window.
    """
    if direction == 'back':
        start = max(0, target_pos - window)
        search_area = text[start:target_pos]
        # Find all sentence endings in the search area
        matches = list(re.finditer(r'[.!?](\s+|$)', search_area))
        if matches:
            # Take the last one (closest to target_pos)
            return start + matches[-1].end()
    else:
        end = min(len(text), target_pos + window)
        search_area = text[target_pos:end]
        match = re.search(r'[.!?](\s+|$)', search_area)
        if match:
            return target_pos + match.end()
            
    return target_pos

def get_safe_chunks(text: str, max_words=512, overlap=50) -> list[str]:
    """Sub-splits a large semantic chunk technically to fit embedding context limits.
    Now more sentence-aware to prevent mid-sentence cropping.
    """
    words = text.split()
    if len(words) <= max_words:
        return [text]
    
    # We use a character-based approach for more precision with sentence boundaries
    chunks = []
    start_char = 0
    total_len = len(text)
    
    # Approx characters per word (rough estimate)
    avg_chars_per_word = 6
    target_chunk_len = max_words * avg_chars_per_word
    
    while start_char < total_len:
        # If remaining text is small enough, just take it all
        remaining = text[start_char:]
        if not remaining.strip():
            break
            
        if len(remaining.split()) <= max_words:
            chunks.append(remaining.strip())
            break
            
        # 1. Start with target length
        end_pos = min(start_char + target_chunk_len, total_len)
        
        # 2. Look BACK for a sentence end
        # Look back up to 30% of the target length
        lookback_window = int(target_chunk_len * 0.3)
        new_end = find_sentence_end(text, end_pos, direction='back', window=lookback_window)
        
        if new_end == end_pos:
            # 3. Look FORWARD if back look failed
            lookforward_window = int(target_chunk_len * 0.2)
            new_end = find_sentence_end(text, end_pos, direction='forward', window=lookforward_window)
            
        # 4. Final fallback: find nearest space to avoid cutting words
        if new_end == end_pos:
            space_match = re.search(r'\s', text[end_pos:])
            if space_match:
                new_end = end_pos + space_match.start() + 1
            else:
                new_end = total_len # Take the rest
        
        chunk = text[start_char:new_end].strip()
        if chunk:
            chunks.append(chunk)
            
        # Advance with overlap
        # Calculate overlap in characters (rough estimate)
        overlap_chars = overlap * avg_chars_per_word
        
        # CRITICAL: Always advance start_char significantly to avoid infinite loops or micro-steps
        next_start_target = new_end - overlap_chars
        start_char = max(start_char + (target_chunk_len // 2), next_start_target)
        
        # Safety: Ensure start_char never moves backward and always moves at least 1
        if start_char <= (new_end - target_chunk_len + 1):
             start_char = new_end - overlap_chars
        
        if start_char >= total_len:
            break

        # Ensure we find a space to start the next chunk cleanly
        next_space = text.find(' ', start_char)
        if next_space != -1 and next_space < (new_end + target_chunk_len):
            start_char = next_space + 1
        else:
            # If no space found soon, just use start_char as is
            pass
            
    return chunks

# =============================================================================
# HYBRID SEARCH COMPONENTS
# =============================================================================

@dataclass
class QueryAnalysis:
    """Result of query analysis for hybrid search."""
    original_query: str
    intent: str  # LEXICAL_REQUIRED, LEXICAL_PREFERRED, SEMANTIC
    entities: list = field(default_factory=list)
    quoted_phrases: list = field(default_factory=list)
    proper_nouns: list = field(default_factory=list)

def analyze_query(query: str) -> QueryAnalysis:
    """Analyze query to determine intent and extract entities.
    
    Case-insensitive proper noun detection: We look for multi-word sequences
    that appear to be names (e.g., "anmol singh", "Anmol Singh") by checking
    if they look like proper nouns after title-casing.
    """
    analysis = QueryAnalysis(original_query=query, intent="SEMANTIC")
    
    # 1. Extract quoted phrases
    quoted_pattern = r'"([^"]+)"|\'([^\']+)\''
    quoted_matches = re.findall(quoted_pattern, query)
    analysis.quoted_phrases = [m[0] or m[1] for m in quoted_matches]
    
    # 2. Extract emails/IDs
    ids_emails = []
    ids_emails.extend(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', query))
    ids_emails.extend(re.findall(r'\b[A-Z]{2,4}[-]?\d{4,}\b', query))
    
    # 3. Extract proper nouns - CASE INSENSITIVE detection
    # Look for multi-word sequences that appear to be names
    clean_query = re.sub(quoted_pattern, '', query)
    words = clean_query.split()
    skip_words = {'the', 'a', 'an', 'this', 'find', 'search', 'show', 'get', 'about', 'for', 'documents', 
                  'what', 'who', 'where', 'when', 'how', 'is', 'are', 'was', 'were', 'in', 'on', 'at',
                  'to', 'from', 'with', 'by', 'of', 'and', 'or', 'but', 'if', 'then', 'else'}
    
    proper_nouns = []
    current_noun = []
    
    for word in words:
        clean_word = re.sub(r'[^\w]', '', word)
        if not clean_word or len(clean_word) < 2:
            if current_noun:
                proper_nouns.append(' '.join(current_noun))
                current_noun = []
            continue
        
        # Case-insensitive check: skip common words
        if clean_word.lower() in skip_words:
            if current_noun:
                proper_nouns.append(' '.join(current_noun))
                current_noun = []
            continue
        
        # Any consecutive non-skip word is a potential name component
        # This covers both "Anmol Singh" (capitalized) and "anmol singh" (lowercase)
        current_noun.append(clean_word)
    
    if current_noun:
        proper_nouns.append(' '.join(current_noun))
    
    # Filter: keep multi-word names OR single words with 3+ chars that were capitalized
    analysis.proper_nouns = [pn for pn in proper_nouns if len(pn.split()) >= 2 or len(pn) > 2]
    
    # 4. Determine intent
    all_entities = analysis.quoted_phrases + ids_emails + analysis.proper_nouns
    analysis.entities = list(set(all_entities))
    
    if analysis.quoted_phrases or ids_emails:
        analysis.intent = "LEXICAL_REQUIRED"
    elif analysis.proper_nouns:
        # Proper nouns trigger LEXICAL_PREFERRED - entity gate filters but allows fuzzy matching
        # This ensures "anmol singh" only returns docs containing those terms
        analysis.intent = "LEXICAL_PREFERRED"
    else:
        # Pure semantic search - no entity filtering
        analysis.intent = "SEMANTIC"
    
    return analysis

class BM25Index:
    """BM25 keyword search index for hybrid search."""
    
    def __init__(self):
        self.bm25 = None
        self.corpus = []
        self.chunk_ids = []
        self.metadata = []
    
    def tokenize(self, text: str) -> list:
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        return [t for t in text.split() if len(t) > 1]
    
    def build_from_metadata(self, metadata: list):
        if not BM25_AVAILABLE:
            mcp_log("WARN", "BM25 not available - install rank-bm25")
            return
        self.corpus = []
        self.chunk_ids = []
        self.metadata = metadata
        for entry in metadata:
            self.corpus.append(self.tokenize(entry.get('chunk', '')))
            self.chunk_ids.append(entry.get('chunk_id', ''))
        self.bm25 = BM25Okapi(self.corpus)
        mcp_log("INFO", f"BM25 index built with {len(self.corpus)} chunks")
    
    def search(self, query: str, top_k: int = 20) -> list:
        if not self.bm25:
            return []
        tokens = self.tokenize(query)
        scores = self.bm25.get_scores(tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.chunk_ids[i], float(scores[i])) for i in top_indices if scores[i] > 0]
    
    def save(self, path: str):
        with open(path, 'wb') as f:
            pickle.dump({'bm25': self.bm25, 'corpus': self.corpus, 'chunk_ids': self.chunk_ids}, f)
    
    def load(self, path: str) -> bool:
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
            self.bm25 = data['bm25']
            self.corpus = data['corpus']
            self.chunk_ids = data['chunk_ids']
            return True
        except:
            return False

# Global BM25 index instance
_bm25_index = BM25Index()

def rrf_fuse(bm25_results: list, faiss_results: list, k: int = 60) -> list:
    """Reciprocal Rank Fusion of BM25 and FAISS results."""
    scores = defaultdict(float)
    for rank, (chunk_id, _) in enumerate(bm25_results):
        scores[chunk_id] += 1.0 / (k + rank + 1)
    for rank, (chunk_id, _) in enumerate(faiss_results):
        scores[chunk_id] += 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def entity_gate(results: list, metadata: list, analysis: QueryAnalysis) -> tuple:
    """Filter results based on query entities. Returns (filtered_results, gate_applied)."""
    if analysis.intent == "SEMANTIC" or not analysis.entities:
        return results, False
    
    chunk_lookup = {e['chunk_id']: e['chunk'].lower() for e in metadata}
    filtered = []
    
    for chunk_id, score in results:
        chunk_text = chunk_lookup.get(chunk_id, '')
        
        # For quoted phrases - exact match
        if analysis.quoted_phrases:
            if all(p.lower() in chunk_text for p in analysis.quoted_phrases):
                filtered.append((chunk_id, score))
            continue
        
        # For proper nouns - all tokens must appear
        for noun in analysis.proper_nouns:
            tokens = noun.lower().split()
            if all(t in chunk_text for t in tokens):
                filtered.append((chunk_id, score))
                break
    
    return filtered, True

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
            "model": VISION_MODEL,
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
    """Search stored documents using HYBRID search (BM25 + vector + entity gating).
    Returns relevant chunks with source information.
    Optionally provide doc_path to search within a specific document only.
    """
    global _bm25_index
    ensure_faiss_ready()
    mcp_log("SEARCH", f"Query: {query} (Doc: {doc_path})")
    
    try:
        metadata = json.loads((ROOT / "faiss_index" / "metadata.json").read_text())
        
        # 1. Analyze query for intent and entities
        analysis = analyze_query(query)
        mcp_log("SEARCH", f"Intent: {analysis.intent}, Entities: {analysis.entities}")
        
        # 2. FAISS vector search
        index = faiss.read_index(str(ROOT / "faiss_index" / "index.bin"))
        query_vec = get_embedding(query).reshape(1, -1)
        D, I = index.search(query_vec, k=50 if doc_path else 30)
        
        faiss_results = []
        for rank, idx in enumerate(I[0]):
            if idx < 0 or idx >= len(metadata):
                continue
            chunk_id = metadata[idx].get('chunk_id', f'idx_{idx}')
            faiss_results.append((chunk_id, float(D[0][rank])))
        
        # 3. BM25 keyword search (if available)
        bm25_results = []
        if BM25_AVAILABLE:
            bm25_path = ROOT / "faiss_index" / "bm25_index.pkl"
            if not _bm25_index.bm25:
                if bm25_path.exists():
                    _bm25_index.load(str(bm25_path))
                else:
                    _bm25_index.build_from_metadata(metadata)
                    _bm25_index.save(str(bm25_path))
            bm25_results = _bm25_index.search(query, top_k=30)
        
        # 4. RRF Fusion
        if bm25_results:
            fused_results = rrf_fuse(bm25_results, faiss_results)
        else:
            fused_results = [(cid, score) for cid, score in faiss_results]
        
        # 5. Entity Gate (for lexical-intent queries)
        gated_results, gate_applied = entity_gate(fused_results, metadata, analysis)
        
        if gate_applied:
            mcp_log("SEARCH", f"Entity gate applied: {len(fused_results)} -> {len(gated_results)} results")
            if not gated_results and analysis.entities:
                # No exact matches - return message indicating this
                mcp_log("SEARCH", f"No documents contain '{analysis.entities}'")
                return [f"⚠️ No documents contain '{', '.join(analysis.entities)}' exactly. Try a broader search."]
        
        # 6. Build result list
        chunk_lookup = {e['chunk_id']: e for e in metadata}
        results = []
        seen_docs = set()
        
        for chunk_id, score in (gated_results if gate_applied else fused_results)[:TOP_K * 2]:
            data = chunk_lookup.get(chunk_id)
            if not data:
                continue
            
            # Doc path filtering
            if doc_path and data.get('doc') != doc_path:
                continue
            
            # File existence check
            doc_rel_path = data.get('doc', '')
            if not doc_rel_path:
                continue
            full_path = ROOT.parent / "data" / doc_rel_path
            if not full_path.exists():
                continue
            
            # Skip empty chunks
            chunk_text = data.get('chunk', '').strip()
            if not chunk_text:
                continue
            
            # Include page if available
            page = data.get('page', 1)
            results.append(f"{chunk_text}\n[Source: {doc_rel_path} p{page}]")
            seen_docs.add(doc_rel_path)
            
            if len(results) >= TOP_K:
                break
        
        mcp_log("SEARCH", f"Returning {len(results)} results from {len(seen_docs)} docs")
        return results if results else ["No relevant documents found."]
        
    except Exception as e:
        mcp_log("ERROR", f"Hybrid search failed: {e}")
        return [f"ERROR: Failed to search: {str(e)}"]

@mcp.tool()
def keyword_search(query: str) -> list[str]:
    """Search for exact keyword matches across all indexed document chunks.
    Returns a list of document paths that contain the matching text.
    """
    mcp_log("KEYWORD_SEARCH", f"Query: {query}")
    
    # Try Ripgrep first if available for live file search
    rg_path = get_rg_path()
    if rg_path:
        try:
            mcp_log("INFO", f"Using Ripgrep for keyword search: {rg_path}")
            # Search in the data directory
            search_path = str(BASE_DATA_DIR)
            cmd = [rg_path, "-l", "-i", query, search_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                paths = [os.path.relpath(p, BASE_DATA_DIR) for p in result.stdout.splitlines() if p.strip()]
                return paths
        except Exception as e:
            mcp_log("WARN", f"Ripgrep search failed, falling back to metadata: {e}")

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

@mcp.tool()
def advanced_ripgrep_search(query: str, regex: bool = False, case_sensitive: bool = False, max_results: int = 50, target_dir: Optional[str] = None) -> list[dict]:
    """Powerful regex/keyword search using Ripgrep.
    Returns structured results with file, line number, and match content.
    Set regex=True for pattern matching (e.g. r"error:.*").
    Optionally provide target_dir to search within a specific subdirectory of data/.
    """
    rg_path = get_rg_path()
    if not rg_path:
        return [{"error": "Ripgrep binary not found. Please install it or check .bin/rg"}]
    
    mcp_log("RG_SEARCH", f"Query: {query} (regex={regex}, target_dir={target_dir})")
    
    try:
        cmd = [rg_path, "--json", "-M", "500", "--no-ignore"] # Max columns, search everything even if ignored
        if not case_sensitive:
            cmd.append("-i")
        if not regex:
            cmd.append("-F") # Fixed strings
        
        search_path = BASE_DATA_DIR
        if target_dir:
            clean_target = target_dir.strip("/").replace("..", "")
            if clean_target.startswith("memory"):
                # Search in PROJECT_ROOT/memory/...
                search_path = PROJECT_ROOT / clean_target
            else:
                # Search in PROJECT_ROOT/data/...
                search_path = BASE_DATA_DIR / clean_target
        
        cmd.extend([query, str(search_path)])
        
        # We need to run with Popen to manage the potential output size
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        results = []
        
        for line in process.stdout:
            try:
                data = json.loads(line)
                if data["type"] == "match":
                    match_data = data["data"]
                    # Calculate rel_path relative to PROJECT_ROOT to be safe
                    abs_path = match_data["path"]["text"]
                    try:
                        rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                    except:
                        rel_path = os.path.basename(abs_path)

                    # Enforce target_dir filtering on results (extra safety)
                    if target_dir:
                        clean_target = target_dir.strip("/").replace("..", "")
                        norm_path = rel_path.replace("\\", "/").strip("/")
                        if not (norm_path == clean_target or norm_path.startswith(clean_target + "/")):
                            continue
                            
                    # Enforce .md only if we are in Notes
                    if target_dir == "Notes" and not rel_path.lower().endswith(".md"):
                        continue

                    results.append({
                        "file": rel_path,
                        "line": match_data["line_number"],
                        "content": match_data["lines"]["text"].strip(),
                        "submatches": match_data["submatches"]
                    })
                if len(results) >= max_results:
                    process.terminate()
                    break
            except:
                continue
        
        process.wait(timeout=5)
        mcp_log("RG_SEARCH", f"Found {len(results)} structured matches")
        # return results REMOVED for hybrid search flow
        
    except Exception as e:
        mcp_log("ERROR", f"Ripgrep advanced search failed: {e}")
        # Don't return error immediately, try metadata fallback at least
        # return [{"error": str(e)}]
        pass

    # --- Hybrid Search: Scan Metadata for PDFs/Binaries ---
    try:
        # Load metadata
        meta_path = ROOT / "faiss_index" / "metadata.json"
        
        # Only proceed if we haven't hit max results
        if len(results) < max_results and meta_path.exists():
            metadata = json.loads(meta_path.read_text())
            
            # Prepare Regex
            import re
            flags = 0 if case_sensitive else re.IGNORECASE
            
            if not regex:
                # Escape for literal match if not regex mode
                pattern = re.escape(query)
            else:
                pattern = query
                
            compiled_re = re.compile(pattern, flags)
            
            seen_files = {r['file'] for r in results}
            
            for entry in metadata:
                doc_path_raw = entry.get('doc')
                if not doc_path_raw: continue
                
                # Filter by target_dir if provided
                if target_dir:
                    clean_target = target_dir.strip("/").replace("..", "")
                    norm_doc_path = doc_path_raw.replace("\\", "/").strip("/")
                    if not (norm_doc_path == clean_target or norm_doc_path.startswith(clean_target + "/")):
                        continue
                    
                    # Enforce .md only if we are in Notes
                    if target_dir == "Notes" and not doc_path_raw.lower().endswith(".md"):
                        continue

                # Intelligent Path Handling
                if os.path.isabs(doc_path_raw):
                    try:
                        rel_path = os.path.relpath(doc_path_raw, BASE_DATA_DIR)
                    except:
                        rel_path = os.path.basename(doc_path_raw)
                else:
                    # It's already relative or just a filename
                    rel_path = doc_path_raw
                
                # Debug specific file
                if "INVG" in rel_path:
                    mcp_log("DEBUG", f"Checking metadata for {rel_path}. Seen? {rel_path in seen_files}")

                # If we already have this file from Ripgrep, skip it
                if rel_path in seen_files:
                    continue
                    
                content_chunk = entry.get('chunk', '')
                
                # Search in chunk
                matches = list(compiled_re.finditer(content_chunk))
                if matches:
                    if "INVG" in rel_path:
                        mcp_log("DEBUG", f"Found {len(matches)} matches in {rel_path}")

                    for m in matches:
                        # Extract context
                        start, end = m.span()
                        
                        # Find line boundaries
                        line_start = content_chunk.rfind('\n', 0, start) + 1
                        line_end = content_chunk.find('\n', end)
                        if line_end == -1: line_end = len(content_chunk)
                        
                        line_content = content_chunk[line_start:line_end].strip()
                        
                        # Metadata page to line mapping
                        page_num = entry.get('page', 1) 
                        
                        result_obj = {
                            "file": rel_path,
                            "line": int(page_num) if isinstance(page_num, (int, str)) and str(page_num).isdigit() else 1,
                            "content": line_content,
                            "submatches": [{"match":{"text": m.group()}, "start": start - line_start, "end": end - line_start}]
                        }
                        
                        results.append(result_obj)
                        seen_files.add(rel_path) 
                        
                        if len(results) >= max_results:
                            break
                
                if len(results) >= max_results:
                    break
                    
    except Exception as e:
        mcp_log("ERROR", f"Metadata fallback search failed: {e}")
        
    mcp_log("RG_SEARCH", f"Found {len(results)} structured matches (Hybrid)")
    return results


def caption_image(img_url_or_path: str) -> str:
    mcp_log("CAPTION", f"Attempting to caption image: {img_url_or_path}")

    # Load image data
    image_data = None
    try:
        if img_url_or_path.startswith("http://") or img_url_or_path.startswith("https://"):
            resp = requests.get(img_url_or_path, timeout=10)
            if resp.status_code == 200:
                image_data = resp.content
            else:
                mcp_log("ERROR", f"Failed to fetch image URL: {resp.status_code}")
                return f"[Image download failed: {img_url_or_path}]"
        else:
            # Flexible path resolution
            if Path(img_url_or_path).is_absolute():
                full_path = Path(img_url_or_path)
            else:
                # Try relative to BASE_DATA_DIR first, then relative to current mcp_servers/
                full_path = BASE_DATA_DIR / img_url_or_path
                if not full_path.exists():
                    full_path = Path(__file__).parent / img_url_or_path
            
            full_path = full_path.resolve()
            if full_path.exists():
                image_data = full_path.read_bytes()
            else:
                mcp_log("ERROR", f"Image file not found: {full_path}")
                return f"[Image file not found: {img_url_or_path}]"

        if not image_data:
            return "[No image data]"

        # Process Image with PIL (Resize if needed)
        try:
            from PIL import Image
            import io
            
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB (in case of RGBA/P)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Check dimensions
                width, height = img.size
                MAX_DIM = 1024
                
                if width > MAX_DIM or height > MAX_DIM:
                    mcp_log("INFO", f"Resizing image from {width}x{height} to max {MAX_DIM}px")
                    img.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)
                
                # Save to buffer for encoding
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                encoded_image = base64.b64encode(buf.getvalue()).decode("utf-8")
        
        except ImportError:
            mcp_log("WARN", "PIL (Pillow) not installed, sending raw image.")
            encoded_image = base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
             mcp_log("WARN", f"Image processing error: {e}, sending raw.")
             encoded_image = base64.b64encode(image_data).decode("utf-8")

    except Exception as e:
        mcp_log("ERROR", f"Failed to prepare image: {e}")
        return f"[Image error: {img_url_or_path}]"


    try:
        # V4 CONTEXT AWARE PROMPT - Fast and produces searchable keywords
        caption_prompt = """Describe what this image shows. Focus on:
1. Any text or labels visible in the image.
2. The type of visual (diagram, chart, photo, table, code).
3. Key terms that would help retrieve this image in a search.

Keep your response concise (2-3 sentences max)."""
        
        # Set stream=True to get the full generator-style output
        with requests.post(OLLAMA_URL, json={
                "model": VISION_MODEL,
                "prompt": caption_prompt,
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









# Global lock for PDF processing (PyMuPDF is not thread-safe in some contexts)
pdf_lock = threading.Lock()

def convert_pdf_to_markdown(string: str) -> MarkdownOutput:
    """Convert PDF to markdown (Thread-Safe) with page markers. """

    if not os.path.exists(string):
        return MarkdownOutput(markdown=f"File not found: {string}")

    ROOT = Path(__file__).parent.resolve()
    global_image_dir = ROOT / "documents" / "images"
    global_image_dir.mkdir(parents=True, exist_ok=True)

    # Acquire lock for PDF processing
    with pdf_lock:
        try:
            import pymupdf
            doc = pymupdf.open(string)
            full_markdown = ""
            
            for i in range(len(doc)):
                page_num = i + 1
                try:
                    # Extract markdown for a single page
                    page_md = pymupdf4llm.to_markdown(
                        doc,
                        pages=[i],
                        write_images=True,
                        image_path=str(global_image_dir)
                    )
                    # Inject page markers
                    full_markdown += f"\n\n<!-- PAGE_START: {page_num} -->\n{page_md}\n<!-- PAGE_END: {page_num} -->\n\n"
                except Exception as page_e:
                    mcp_log("WARN", f"Failed to convert page {page_num}: {page_e}")
                    full_markdown += f"\n\n<!-- PAGE_START: {page_num} -->\n[Extraction Failed for Page {page_num}]\n<!-- PAGE_END: {page_num} -->\n\n"
            
            doc.close()
            markdown = full_markdown
        except Exception as e:
            mcp_log("ERROR", f"PDF conversion completely failed: {e}")
            return MarkdownOutput(markdown=f"Failed to extract text from PDF: {string}")

    # Re-point image links in the markdown
    markdown = re.sub(
        r'!\[\]\((.*?/images/)([^)]+)\)',
        r'![](images/\2)',
        markdown.replace("\\", "/")
    )

    mcp_log("INFO", f"Preserved page marks for {string}. Images are saved.")
    return MarkdownOutput(markdown=markdown)





def get_numbered_sentences(text: str, max_sentences: int = 15) -> str:
    """Convert text to numbered sentences for V2 boundary detection prompt."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10][:max_sentences]
    return "\n".join([f"{i+1}. {s}" for i, s in enumerate(sentences)])

def semantic_merge(text: str) -> list[str]:
    """V2 BOUNDARY DETECTION semantic chunking.
    
    Uses numbered sentences and asks LLM to identify split point by sentence number.
    Faster and more reliable than the old text_preview approach.
    """
    WORD_LIMIT = 1024
    words = text.split()
    position = 0
    final_chunks = []

    while position < len(words):
        chunk_words = words[position:position + WORD_LIMIT]
        chunk_text = " ".join(chunk_words).strip()
        
        if len(chunk_words) < 50:
            # Too small, just append
            if chunk_text.strip():
                final_chunks.append(chunk_text)
            break
        
        # V2: Create numbered sentences for the prompt
        numbered_sentences = get_numbered_sentences(chunk_text)
        
        try:
            # Try to load prompt from file
            prompt_path = ROOT.parent / "prompts" / "rag_semantic_chunking.md"
            base_prompt = prompt_path.read_text().strip()
            prompt = base_prompt.replace("{numbered_sentences}", numbered_sentences)
        except Exception as e:
            mcp_log("WARN", f"Failed to load prompt file: {e}")
            # Fallback prompt (V2 style)
            prompt = f"""You are a document segmentation assistant.

Below is an ordered list of sentences from a document. Your task is to find where the topic clearly changes.

INSTRUCTIONS:
1. Read the sentences carefully.
2. If there is a clear topic shift, reply with ONLY the sentence number where the NEW topic begins (e.g., "7").
3. If all sentences belong to the same topic, reply with "NONE".

SENTENCES:
{numbered_sentences}

ANSWER (number or NONE):"""

        try:
            result = requests.post(OLLAMA_CHAT_URL, json={
                "model": RAG_LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 20}  # V2: Very short output expected
            }, timeout=OLLAMA_TIMEOUT)
            reply = result.json().get("message", {}).get("content", "").strip()

            # V2: Parse sentence number response
            # Clean the reply (remove any non-numeric prefix like "Answer: ")
            clean_reply = re.sub(r'^[^0-9]*', '', reply).strip()
            
            if clean_reply.upper() == "NONE" or reply.upper() == "NONE":
                # No split needed - single topic
                # Use sentence-aware boundary detection for clean ending
                end_pos = len(chunk_text)
                lookback_window = int(len(chunk_text) * 0.2)
                safe_split = find_sentence_end(chunk_text, end_pos, direction='back', window=lookback_window)
                
                if safe_split < end_pos:
                    safe_chunk = chunk_text[:safe_split].strip()
                    final_chunks.append(safe_chunk)
                    position += len(safe_chunk.split())
                else:
                    final_chunks.append(chunk_text)
                    position += WORD_LIMIT
                    
            elif clean_reply.isdigit():
                # LLM found a split point at sentence N
                split_sentence_num = int(clean_reply)
                
                # Find the character position of sentence N in the original text
                sentences = re.split(r'(?<=[.!?])\s+', chunk_text.strip())
                sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
                
                if 1 <= split_sentence_num <= len(sentences):
                    # Calculate character offset for sentences 1 to (N-1)
                    first_part_sentences = sentences[:split_sentence_num - 1]
                    first_part = " ".join(first_part_sentences).strip()
                    
                    if first_part:
                        # Ensure clean sentence ending
                        adjusted_split = find_sentence_end(first_part, len(first_part), direction='back', window=100)
                        first_part = first_part[:adjusted_split].strip() if adjusted_split < len(first_part) else first_part
                        
                        final_chunks.append(first_part)
                        
                        # Feed remainder for next iteration
                        remainder = " ".join(sentences[split_sentence_num - 1:]).strip()
                        words = words[:position] + remainder.split() + words[position + WORD_LIMIT:]
                        continue
                    else:
                        # Split at sentence 1 means no first part, just continue
                        final_chunks.append(chunk_text)
                        position += WORD_LIMIT
                else:
                    # Invalid sentence number, fallback
                    final_chunks.append(chunk_text)
                    position += WORD_LIMIT
            else:
                # Unexpected response format, fallback
                mcp_log("WARN", f"Unexpected chunking response: {reply}")
                final_chunks.append(chunk_text)
                position += WORD_LIMIT

        except Exception as e:
            mcp_log("WARN", f"Semantic chunking LLM error: {e}")
            final_chunks.append(chunk_text)
            position += WORD_LIMIT

    return [c for c in final_chunks if c.strip()]







def file_hash(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()

def log_debug(msg):
    try:
        debug_log = Path(__file__).parent / "rag_debug.log"
        with open(debug_log, "a") as f:
            f.write(f"{msg}\n")
    except:
        pass

def process_single_file(file: Path, doc_path_root: Path, cache_meta: dict):
    """Worker function to process a single file: Extract -> Chunk -> Embed."""
    try:
        rel_path = file.relative_to(doc_path_root).as_posix()
        try:
            fhash = file_hash(file)
        except Exception as e:
            log_debug(f"HASH FAIL {rel_path}: {e}")
            raise e
        
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
        elif ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"]:
            # Dedicated image processing branch
            mcp_log("IMG", f"Captioning standalone image: {rel_path}")
            caption = caption_image(str(file))
            if not caption.startswith("["):
                markdown = f"# Image Analysis: {file.name}\n\n**Description:** {caption}\n\n![{file.name}]({rel_path})"
            else:
                return {"status": "ERROR", "rel_path": rel_path, "message": caption}
        elif ext == ".json":
            try:
                data = json.loads(file.read_text())
                # Specific Handling: Session Summaries (Arcturus format)
                if "graph" in data and "nodes" in data:
                    summary_parts = []
                    summary_parts.append(f"# Session Summary: {data['graph'].get('session_id', 'Unknown')}")
                    summary_parts.append(f"**Original Query:** {data['graph'].get('original_query', 'N/A')}")
                    if "created_at" in data["graph"]:
                        summary_parts.append(f"*Date: {data['graph']['created_at']}*")
                    
                    for node in data.get("nodes", []):
                        agent = node.get("agent", "Unknown Agent")
                        desc = node.get("description", "Unnamed Step")
                        output = node.get("output", {})
                        
                        summary_parts.append(f"---")
                        summary_parts.append(f"### Step: {desc} (by {agent})")
                        
                        if isinstance(output, dict):
                            # Try to find meaningful text output
                            text_val = output.get("fallback_markdown") or output.get("summary") or output.get("answer")
                            if not text_val:
                                # Look into nested keys
                                for k, v in output.items():
                                    if isinstance(v, str) and len(v) > 20: # Long string likely contains info
                                        text_val = v
                                        break
                            
                            if text_val:
                                summary_parts.append(text_val)
                            else:
                                # Final fallback for dict output
                                summary_parts.append(f"```json\n{json.dumps(output, indent=2)}\n```")
                        elif output:
                            summary_parts.append(str(output))
                            
                    markdown = "\n\n".join(summary_parts)
                else:
                    # Fallback for generic JSON: wrap in code block for literal search
                    markdown = f"```json\n{json.dumps(data, indent=2)}\n```"
            except Exception as e:
                mcp_log("WARN", f"JSON parse failed for {rel_path}: {e}")
                markdown = f"```json\n{file.read_text()}\n```"
        else:
            # Fallback
            converter = MarkItDown()
            markdown = converter.convert(str(file)).text_content

        if not markdown.strip():
            return {"status": "WARN", "rel_path": rel_path, "message": "No content extracted"}

        # === CAPTION-FIRST: Replace image placeholders with actual captions ===
        # This ensures the FAISS index contains searchable image content
        image_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
        images_found = image_pattern.findall(markdown)
        
        if images_found:
            mcp_log("IMG", f"Found {len(images_found)} images in {rel_path}, captioning inline...")
            
            # Load/create captions ledger
            captions_file = ROOT / "faiss_index" / "captions.json"
            captions_ledger = json.loads(captions_file.read_text()) if captions_file.exists() else {}
            
            def caption_replacer(match):
                img_path = match.group(1)  # e.g. "images/file.png" or "https://..."
                
                # SKIP: Remote URLs (badges, shields, external images)
                if img_path.startswith("http://") or img_path.startswith("https://"):
                    return match.group(0)  # Keep as-is
                
                filename = Path(img_path).name
                
                # Check ledger first (skip if already captioned)
                if filename in captions_ledger and captions_ledger[filename]:
                    caption = captions_ledger[filename]
                    return f"**[Image Caption]:** *{caption}*"
                
                # Generate new caption
                try:
                    caption = caption_image(img_path)
                    if caption and caption.strip() and not caption.startswith("["):  # Skip error/empty
                        captions_ledger[filename] = caption
                        # Incremental save
                        captions_file.parent.mkdir(exist_ok=True)
                        captions_file.write_text(json.dumps(captions_ledger, indent=2))
                        return f"**[Image Caption]:** *{caption}*"
                except Exception as e:
                    mcp_log("WARN", f"Caption failed for {filename}: {e}")
                
                return match.group(0)  # Keep original if failed
            
            # Apply captioning to markdown
            markdown = image_pattern.sub(caption_replacer, markdown)
        # === END CAPTION-FIRST ===

        # Semantic Chunking per Page
        final_safe_chunks_with_pages = []
        if "<!-- PAGE_START:" in markdown:
            # re.split with capturing group returns the group matches too
            parts = re.split(r'<!-- PAGE_START: (\d+) -->', markdown)
            # parts: [prefix, page_1_num, page_1_body, page_2_num, page_2_body, ...]
            for i in range(1, len(parts), 2):
                page_num = int(parts[i])
                page_text = parts[i+1].split("<!-- PAGE_END:")[0].strip()
                if not page_text:
                    continue
                
                # Chunk this page
                try:
                    if len(page_text.split()) < 50:
                        page_chunks = [page_text]
                    else:
                        page_chunks = semantic_merge(page_text)
                except:
                    page_chunks = list(chunk_text(page_text))
                
                for pc in page_chunks:
                    for sc in get_safe_chunks(pc):
                        final_safe_chunks_with_pages.append((sc, page_num))
        else:
            # Fallback for non-PDF or failed marker injection
            try:
                if len(markdown.split()) < 50:
                    chunks = [markdown.strip()]
                else:
                    chunks = semantic_merge(markdown)
            except:
                chunks = list(chunk_text(markdown))
            
            for c in chunks:
                for sc in get_safe_chunks(c):
                    final_safe_chunks_with_pages.append((sc, 1))

        embeddings_for_file = []
        new_metadata_entries = []
        
        # Batch Embedding (Local)
        BATCH_SIZE = 32
        
        # Extract just text for batching
        batch_texts = [item[0] for item in final_safe_chunks_with_pages]
        
        for i in range(0, len(batch_texts), BATCH_SIZE):
            batch = batch_texts[i : i + BATCH_SIZE]
            
            try:
                batch_url = EMBED_URL.replace("/api/embeddings", "/api/embed")
                res = requests.post(batch_url, json={
                    "model": EMBED_MODEL,
                    "input": batch
                }, timeout=OLLAMA_TIMEOUT)
                res.raise_for_status()
                embeddings_list = [np.array(e, dtype=np.float32) for e in res.json()["embeddings"]]
            except Exception as e:
                embeddings_list = [get_embedding(t) for t in batch]

            for j, embedding in enumerate(embeddings_list):
                real_idx = i + j
                chunk_text_val, page_num = final_safe_chunks_with_pages[real_idx]
                embeddings_for_file.append(embedding)
                new_metadata_entries.append({
                    "doc": rel_path,
                    "chunk": chunk_text_val,
                    "chunk_id": f"{rel_path}_{real_idx}",
                    "page": page_num
                })
        
        return {
            "status": "SUCCESS",
            "rel_path": rel_path,
            "hash": fhash,
            "embeddings": embeddings_for_file,
            "metadata": new_metadata_entries
        }

    except Exception as e:
        log_debug(f"CRITICAL FAIL {file}: {e}")
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
    LEDGER_FILE = INDEX_CACHE / "ledger.json"

    CACHE_META = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    metadata = json.loads(METADATA_FILE.read_text()) if METADATA_FILE.exists() else []
    
    # Load or create ledger
    if LEDGER_FILE.exists():
        ledger_data = json.loads(LEDGER_FILE.read_text())
    else:
        ledger_data = {"version": 2, "last_reconcile": None, "files": {}}
    
    # IMPORTANT: If CACHE_META is empty but ledger has entries, populate from ledger
    # This ensures we don't re-index everything after migration
    if not CACHE_META and ledger_data.get("files"):
        mcp_log("INFO", "CACHE_META empty, populating from ledger...")
        for path, entry in ledger_data.get("files", {}).items():
            if entry.get("status") == "complete" and entry.get("hash"):
                CACHE_META[path] = entry["hash"]
        mcp_log("INFO", f"Restored {len(CACHE_META)} entries from ledger")

    mcp_log("INFO", f"Loaded cache with {len(CACHE_META)} files, ledger with {len(ledger_data.get('files', {}))} files")

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
        # Improved file discovery: walk and filter
        files_to_process = []
        skip_dirs = {'.git', '.github', 'node_modules', '__pycache__', 'mcp_repos', 'faiss_index'}
        skip_exts = {'.mp4', '.mov', '.wav', '.mp3', '.bin', '.exe', '.pyc'}
        
        for root, dirs, filenames in os.walk(DOC_PATH):
            # Skip junk directories in-place
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
            
            for f in filenames:
                if f.startswith('.'): continue
                if Path(f).suffix.lower() in skip_exts: continue
                
                files_to_process.append(Path(root) / f)

    # PARALLEL EXECUTION
    # Max workers = 2 (reduced from 4 to prevent Ollama timeouts)
    MAX_WORKERS = 2
    mcp_log("INFO", f"Starting parallel ingestion with {MAX_WORKERS} workers on {len(files_to_process)} files")
    
    with INDEXING_LOCK:
        INDEXING_STATUS["total"] = len(files_to_process)
        INDEXING_STATUS["currentFile"] = "Checking cache..."
    
    param_cache_meta = CACHE_META.copy() # Read-only for threads
    
    # Thread-safe lock for incremental saves
    import threading
    index_lock = threading.Lock()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Map futures
        futures = {executor.submit(process_single_file, f, DOC_PATH, param_cache_meta): f for f in files_to_process}
        
        # Collect results as they complete
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(files_to_process), desc="Indexing", file=sys.stderr):
            result = future.result()
            status = result.get("status")
            rel_path = result.get("rel_path")
            
            if status == "SKIP":
                # Increment progress for skipped files too
                with INDEXING_LOCK:
                    INDEXING_STATUS["completed"] += 1
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
                        
                        # Update ledger with new format
                        from datetime import datetime
                        ledger_data["files"][rel_path] = {
                            "hash": fhash,
                            "status": "complete",
                            "indexed_at": datetime.utcnow().isoformat() + "Z",
                            "chunk_count": len(new_embs),
                            "error": None
                        }
                        
                        # 3. INCREMENTAL SAVE (Crash-safe)
                        try:
                            CACHE_FILE.write_text(json.dumps(CACHE_META, indent=2))
                            METADATA_FILE.write_text(json.dumps(metadata, indent=2))
                            faiss.write_index(index, str(INDEX_FILE))
                            # Also save ledger
                            LEDGER_FILE.write_text(json.dumps(ledger_data, indent=2))
                        except Exception as e:
                            mcp_log("WARN", f"Incremental save failed: {e}")
                        
                        mcp_log("DONE", f"Indexed {rel_path} ({len(new_embs)} chunks)")
                        
                        # Update progress
                        with INDEXING_LOCK:
                            INDEXING_STATUS["completed"] += 1
                            INDEXING_STATUS["currentFile"] = Path(rel_path).name
            
            elif status == "WARN":
                mcp_log("WARN", f"{rel_path}: {result.get('message')}")
                with INDEXING_LOCK:
                    INDEXING_STATUS["completed"] += 1
                
            elif status == "ERROR":
                mcp_log("ERROR", f"Failed {rel_path}: {result.get('message')}")
                with INDEXING_LOCK:
                    INDEXING_STATUS["completed"] += 1

    # Reset indexing status
    with INDEXING_LOCK:
        INDEXING_STATUS["active"] = False
        INDEXING_STATUS["currentFile"] = ""
    
    # Release re-indexing busy lock if held
    try:
        REINDEX_BUSY_LOCK.release()
    except:
        pass
        
    mcp_log("INFO", "READY")


@mcp.tool()
async def reindex_documents(target_path: str = None, force: bool = False) -> str:
    """Trigger a manual re-index of the RAG documents. 
    Optionally provide a target_path (relative to data/ folder) to index a specific file.
    If force is True, it wipes the index and performs a full fresh scan.
    """
    # SIMPLIFIED: Always use the legacy process_documents with ledger updates
    # The scheduler-based approach had issues with process isolation
    
    if not REINDEX_BUSY_LOCK.acquire(blocking=False):
        mcp_log("WARN", "Re-indexing already in progress, skipping new request.")
        return "Indexing already in progress."
    
    # Initialize status IMMEDIATELY so polling sees it active
    with INDEXING_LOCK:
        INDEXING_STATUS["active"] = True
        INDEXING_STATUS["completed"] = 0
        INDEXING_STATUS["total"] = 0
        INDEXING_STATUS["currentFile"] = "Initializing scan..."

    try:
        INDEX_CACHE = ROOT / "faiss_index"
        
        if force and not target_path:
            # Full Rescan: Wipe existing data
            mcp_log("INFO", "Force Rescan - Wiping existing index...")
            
            for f in ["index.bin", "metadata.json", "doc_index_cache.json", "ledger.json"]:
                path = INDEX_CACHE / f
                if path.exists():
                    try:
                        path.unlink()
                    except Exception as e:
                        mcp_log("WARN", f"Failed to delete {f}: {e}")
                        
        # Run process_documents in a separate thread 
        # It will now update the new ledger format
        threading.Thread(target=process_documents, args=(target_path,), daemon=True).start()
        return f"Re-indexing started {'for ' + target_path if target_path else 'for all documents'}."
    except Exception as e:
        with INDEXING_LOCK:
            INDEXING_STATUS["active"] = False
        try:
            REINDEX_BUSY_LOCK.release()
        except:
            pass
        return f"Error starting indexing: {str(e)}"


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
            
            # INCREMENTAL SAVE: Save ledger after each caption so progress is not lost
            CAPTIONS_FILE.write_text(json.dumps(captions_ledger, indent=2))
            
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


# =============================================================================
# SESSION SUMMARY SYNC SERVICE
# =============================================================================

class SessionSummarySyncService:
    """Service to mirror session summaries into the RAG data directory."""
    
    def __init__(self, source_dir: Path, target_dir: Path):
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.stop_event = threading.Event()
        
    def get_file_hash(self, path: Path) -> str:
        """Calculate MD5 hash of a file."""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def sync(self):
        """Mirror files from source to target if changed."""
        if not self.source_dir.exists():
            return

        self.target_dir.mkdir(parents=True, exist_ok=True)
        changes_detected = False

        # Recursive sync
        for src_path in self.source_dir.rglob("*.json"):
            if not src_path.is_file():
                continue
            
            # Create relative target path
            rel_path = src_path.relative_to(self.source_dir)
            dest_path = self.target_dir / rel_path
            
            # Check if sync is needed
            should_copy = False
            if not dest_path.exists():
                should_copy = True
            else:
                # Compare hashes if file exists
                if self.get_file_hash(src_path) != self.get_file_hash(dest_path):
                    should_copy = True
            
            if should_copy:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(src_path, dest_path)
                mcp_log("SYNC", f"Mirrored {rel_path} to RAG")
                changes_detected = True
        
        return changes_detected

    def run_forever(self, interval_sec: int = 60):
        """Background loop for syncing."""
        mcp_log("INFO", f"🚀 Session Summary Sync Service started (monitoring {self.source_dir})")
        while not self.stop_event.is_set():
            try:
                self.sync()
            except Exception as e:
                mcp_log("ERROR", f"Sync failed: {e}")
            
            # Wait for next interval
            self.stop_event.wait(interval_sec)

def start_background_services():
    """Initialize and start background threads."""
    sync_service = SessionSummarySyncService(MEMORY_SUMMARIES_DIR, SYNC_TARGET_DIR)
    
    # Start sync thread
    sync_thread = threading.Thread(
        target=sync_service.run_forever, 
        args=(60,), # Check every minute
        daemon=True,
        name="SessionSyncThread"
    )
    sync_thread.start()
    
    # Initialize the index scheduler with callbacks
    INDEX_CACHE = ROOT / "faiss_index"
    INDEX_CACHE.mkdir(exist_ok=True)
    
    def process_file_callback(abs_path: Path, rel_path: str) -> dict:
        """Callback for scheduler to process a single file."""
        try:
            # Load existing index and metadata
            INDEX_FILE = INDEX_CACHE / "index.bin"
            METADATA_FILE = INDEX_CACHE / "metadata.json"
            
            metadata = json.loads(METADATA_FILE.read_text()) if METADATA_FILE.exists() else []
            index = faiss.read_index(str(INDEX_FILE)) if INDEX_FILE.exists() else None
            
            # Remove old entries for this file
            metadata = [m for m in metadata if m.get("doc") != rel_path]
            
            # Process the file
            result = process_single_file(abs_path, BASE_DATA_DIR, {})
            
            if result.get("status") == "SUCCESS":
                new_embs = result.get("embeddings", [])
                new_meta = result.get("metadata", [])
                
                if new_embs:
                    if index is None:
                        dim = len(new_embs[0])
                        index = faiss.IndexFlatL2(dim)
                    
                    index.add(np.stack(new_embs))
                    metadata.extend(new_meta)
                    
                    # Save atomically
                    METADATA_FILE.write_text(json.dumps(metadata, indent=2))
                    faiss.write_index(index, str(INDEX_FILE))
                    
                    # Rebuild BM25 index
                    if BM25_AVAILABLE:
                        _bm25_index.build_from_metadata(metadata)
                        _bm25_index.save(str(INDEX_CACHE / "bm25_index.pkl"))
                    
                    return {"chunk_count": len(new_embs)}
            
            return {"chunk_count": 0}
        except Exception as e:
            mcp_log("ERROR", f"Process callback failed for {rel_path}: {e}")
            raise
    
    def delete_file_callback(rel_path: str):
        """Callback for scheduler to remove a file from the index."""
        try:
            METADATA_FILE = INDEX_CACHE / "metadata.json"
            
            if METADATA_FILE.exists():
                metadata = json.loads(METADATA_FILE.read_text())
                new_metadata = [m for m in metadata if m.get("doc") != rel_path]
                
                if len(new_metadata) != len(metadata):
                    METADATA_FILE.write_text(json.dumps(new_metadata, indent=2))
                    mcp_log("INFO", f"Removed {rel_path} from metadata ({len(metadata) - len(new_metadata)} chunks)")
                    
                    # Rebuild BM25
                    if BM25_AVAILABLE:
                        _bm25_index.build_from_metadata(new_metadata)
                        _bm25_index.save(str(INDEX_CACHE / "bm25_index.pkl"))
        except Exception as e:
            mcp_log("ERROR", f"Delete callback failed for {rel_path}: {e}")
    
    init_scheduler(
        data_dir=BASE_DATA_DIR,
        index_dir=INDEX_CACHE,
        process_callback=process_file_callback,
        delete_callback=delete_file_callback
    )
    mcp_log("INFO", "Index Scheduler initialized")


if __name__ == "__main__":
    mcp_log("INFO", "🚀 Starting RAG MCP Server...")
    # Start background tasks
    start_background_services()
    # Run server
    mcp.run()
