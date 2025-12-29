import sys
import os
import re
import asyncio
import json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import AgentLoop4
from mcp_servers.multi_mcp import MultiMCP
from core.graph_adapter import nx_to_reactflow
from memory.context import ExecutionContextManager
from remme.store import RemmeStore
from remme.extractor import RemmeExtractor
from remme.utils import get_embedding
import tempfile
import subprocess
import shutil
from core.explorer_utils import CodeSkeletonExtractor
from core.model_manager import ModelManager
from config.settings_loader import settings, save_settings, reset_settings, reload_settings

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API Starting up...")
    await multi_mcp.start()
    # Check git
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print("✅ Git found.")
    except Exception:
        print("⚠️ Git NOT found. GitHub explorer features will fail.")
    
    yield
    
    await multi_mcp.stop()

app = FastAPI(lifespan=lifespan)

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:517\d", # Allows 5170-5179
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State (Simplified for now)
# In production, use database or persistent store
active_loops = {}
multi_mcp = MultiMCP()
remme_store = RemmeStore()  # Initialize memory store

# --- Explorer Classes ---
class AnalyzeRequest(BaseModel):
    path: str
    type: str = "local" # local or github
    files: Optional[List[str]] = None # New: curated list of files

class ExplorerNode(BaseModel):
    name: str
    path: str
    type: str # file or folder
    children: Optional[List['ExplorerNode']] = None

ExplorerNode.update_forward_refs()

class RunRequest(BaseModel):
    query: str
    model: str = None  # Will use settings default if not provided
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.model is None:
            self.model = settings.get("agent", {}).get("default_model", "gemini-2.5-flash")

class RunResponse(BaseModel):
    id: str
    status: str
    created_at: str
    query: str

async def process_run(run_id: str, query: str):
    """Background task to execute the agent loop"""
    try:
        # 1. RETRIEVE MEMORIES (Remme)
        # Search for past relevant facts to injecting into this run
        memory_context = ""
        context = None # Initialize for safe access in finally block
        try:
            emb = get_embedding(query, task_type="search_query")
            results = remme_store.search(emb, query_text=query, k=10)
            if results:
                memory_str = "\n".join([f"- {r['text']} (Confidence: {r.get('score', 0):.2f})" for r in results])
                memory_context = f"PREVIOUS MEMORIES ABOUT USER:\n{memory_str}\n"
                print(f" Remme: Injected {len(results)} memories into run {run_id}")
        except Exception as e:
            print(f"⚠️ Remme Retrieval Failed: {e}")

        loop = AgentLoop4(multi_mcp=multi_mcp)
        # Register the LOOP instance immediately so we can stop it
        active_loops[run_id] = loop
        
        # Execute the loop
        # The loop will maintain its own internal context
        print(f"[{run_id}] MEMORY CONTEXT INJECTED:\n{memory_context}")
        try:
             context = await loop.run(query, [], {}, [], session_id=run_id, memory_context=memory_context)
        except asyncio.CancelledError:
             print(f"[{run_id}] Run cancelled.")
             context = loop.context # Recovery context from loop if possible
        
        # 2. EXTRACT NEW MEMORIES (Remme)
        # We put this in a finally block? No, because we want it only on success/completion of meaningful work.
        # But if user stops it, we might want to extract partials.
        # For now, let's leave it after run() but handle the stop case explicitly if context is returned.
        
    except Exception as e:
        print(f"Run {run_id} failed: {e}")
    finally:
        # Clean up
        if run_id in active_loops:
            del active_loops[run_id]
            
        # Attempt extraction if we have context (even if stopped)
        # Note: 'context' variable needs to be accessible here.
        pass 
        # After run completes, extract new facts
        try:
            # Get the history from context (Plan Graph or Session Summary)
            # For now, we don't return the full conversation history from loop.run directly
            # But context has plan_graph... 
            # Ideally we extract from the "Summary" generated by the ReportingAgent if available
            # OR we can pass the query and the FINAL output.
            
            # Simple V1: Extract from Query + Final Answer (if available)
            final_output = ""
            # Try to find final output from graph
            if context and context.plan_graph:
                # Find nodes with output
                for node_id in context.plan_graph.nodes:
                    node = context.plan_graph.nodes[node_id]
                    if node.get("status") == "completed" and node.get("output"):
                        final_output += f"{node_id} Output: {str(node['output'])}\n"

            history = [{"role": "assistant", "content": final_output}]
            
            print(f" Remme: Extracting facts from run {run_id}...")
            # Pass existing memories from earlier search to context-aware extractor
            # ⚡ RUN IN THREAD TO AVOID BLOCKING EVENT LOOP
            commands = await asyncio.to_thread(
                remme_extractor.extract, 
                query, 
                history, 
                existing_memories=results
            )
            
            if commands:
                for cmd in commands:
                    action = cmd.get("action")
                    text = cmd.get("text")
                    target_id = cmd.get("id")
                    
                    try:
                        if action == "add" and text:
                            emb = get_embedding(text, task_type="search_document")
                            remme_store.add(text, emb, category="derived", source=f"run_{run_id}")
                            print(f"✅ Remme: Added new fact: {text}")
                        elif action == "update" and target_id and text:
                            emb = get_embedding(text, task_type="search_document")
                            remme_store.update_text(target_id, text, emb)
                            print(f"🔄 Remme: Updated fact {target_id}: {text}")
                        elif action == "delete" and target_id:
                            remme_store.delete(target_id)
                            print(f"🗑️ Remme: Deleted fact {target_id}")
                    except Exception as e:
                        print(f"❌ Remme Action Failed: {e}")
                
                print(f"✅ Remme: Processed {len(commands)} memory updates.")
            else:
                 print(f"ℹ️ Remme: No new facts extracted from run {run_id}.")

        except Exception as e:
            print(f"⚠️ Remme Extraction Failed: {e}")
            import traceback
            traceback.print_exc()


@app.post("/runs")
async def create_run(request: RunRequest, background_tasks: BackgroundTasks):
    run_id = str(int(datetime.now().timestamp()))
    
    # Start background execution
    background_tasks.add_task(process_run, run_id, request.query)
    
    return {
        "id": run_id,
        "status": "starting",
        "created_at": datetime.now().isoformat(),
        "query": request.query
    }

@app.get("/runs")
async def list_runs():
    """List runs from disk"""
    summaries_dir = Path(__file__).parent / "memory" / "session_summaries_index"
    runs = []
    
    if summaries_dir.exists():
        # Walk through date folders
        for date_folder in summaries_dir.glob("*/*/*"):
            for session_file in date_folder.glob("session_*.json"):
                try:
                    data = json.loads(session_file.read_text())
                    graph_data = data
                    # Extract meta
                    graph_details = graph_data.get("graph", {})
                    
                    # Robust Query Extraction
                    query = graph_details.get("original_query")
                    if not query:
                        query = graph_details.get("globals", {}).get("original_query", "Unknown Query")

                    # Timestamp Extraction
                    created_at = graph_details.get("created_at")
                    if not created_at:
                        # Fallback to file creation time
                        created_at = datetime.fromtimestamp(session_file.stat().st_ctime).isoformat()
                    
                    # Compute status from node statuses
                    # Check nodes for their statuses
                    nodes = data.get("nodes", [])
                    node_statuses = [n.get("status", "pending") for n in nodes if n.get("id") != "ROOT"]
                    
                    if any(s == "running" for s in node_statuses):
                        computed_status = "running"
                    elif any(s == "failed" for s in node_statuses):
                        computed_status = "failed" 
                    elif all(s == "completed" for s in node_statuses) and node_statuses:
                        computed_status = "completed"
                    else:
                        # Fallback to graph-level status or completed
                        computed_status = graph_details.get("status", "completed")
                    
                    total_tokens = sum(
                        (n.get("total_tokens", 0) or 0) for n in nodes
                    )
                    
                    runs.append({
                        "id": session_file.stem.replace("session_", ""),
                        "query": query, 
                        "created_at": created_at, 
                        "status": computed_status,
                        "total_tokens": total_tokens
                    })
                except:
                    continue
    
    # Sort by recent
    return sorted(runs, key=lambda x: x['id'], reverse=True)

@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get graph state for a run"""
    # Check memory first (if running)
    # Then check disk
    
    # Search disk
    summaries_dir = Path(__file__).parent / "memory" / "session_summaries_index"
    found_file = None
    
    # Brute force search (should optimize path structure later)
    for path in summaries_dir.rglob(f"session_{run_id}.json"):
        found_file = path
        break
        
    if found_file:
        data = json.loads(found_file.read_text())
        # Reconstruct Graph to use adapter
        import networkx as nx
        G = nx.node_link_graph(data)
        react_flow = nx_to_reactflow(G)
        
        # Determine status: Running if in memory, else use file status
        status = "running" if run_id in active_loops else data.get("graph", {}).get("status", "completed")

        return {
            "id": run_id,
            "status": status,
            "graph": react_flow
        }
        
    raise HTTPException(status_code=404, detail="Run not found")

class UserInputRequest(BaseModel):
    input: str

@app.post("/runs/{run_id}/input")
async def provide_input(run_id: str, request: UserInputRequest):
    """Provide specific input to a running agent"""
    if run_id in active_loops:
        loop = active_loops[run_id]
        if loop.context:
            loop.context.provide_user_input(request.input)
            return {"id": run_id, "status": "input_received"}
        else:
            raise HTTPException(status_code=400, detail="Context not initialized")
    
    raise HTTPException(status_code=404, detail="Active run not found or not waiting for input")

@app.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    """Stop a running agent execution"""
    if run_id in active_loops:
        loop = active_loops[run_id]
        loop.stop()
        return {"id": run_id, "status": "stopping"}
    
    raise HTTPException(status_code=404, detail="Active run not found")

@app.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    """Delete a run from disk and memory"""
    # 1. Stop if running
    if run_id in active_loops:
        loop = active_loops[run_id]
        loop.stop()
        del active_loops[run_id]
        
    # 2. Delete file
    summaries_dir = Path(__file__).parent / "memory" / "session_summaries_index"
    deleted = False
    
    # Brute force search
    for path in summaries_dir.rglob(f"session_{run_id}.json"):
        try:
            path.unlink()
            deleted = True
            break
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
            
    if not deleted and run_id not in active_loops: # If wasn't running and file not found
        # Might be okay if it was just in memory? But we are memory-less persistence mostly
        # Let's return success if we stopped it at least, or warn
        pass

    return {"id": run_id, "status": "deleted"}

@app.get("/rag/documents")
async def get_rag_documents():
    """List documents in a recursive tree structure with RAG status"""
    try:
        root = Path(__file__).parent
        doc_path = root / "data"
        cache_file = root / "mcp_servers" / "faiss_index" / "doc_index_cache.json"
        
        # Load cache for status
        cache_meta = {}
        if cache_file.exists():
            try:
                cache_meta = json.loads(cache_file.read_text())
            except:
                pass

        def build_tree(path: Path):
            items = []
            # Sort: directories first, then files
            for p in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if p.name.startswith('.') or p.name == "__pycache__":
                    continue
                
                rel_p = p.relative_to(doc_path).as_posix()
                item = {
                    "name": p.name,
                    "path": rel_p,
                    "type": "folder" if p.is_dir() else p.suffix.lower().replace('.', ''),
                }
                
                if p.is_dir():
                    item["children"] = build_tree(p)
                else:
                    item["size"] = p.stat().st_size
                    item["indexed"] = rel_p in cache_meta
                    item["hash"] = cache_meta.get(rel_p, "Not Indexed")
                
                items.append(item)
            return items

        files = build_tree(doc_path) if doc_path.exists() else []
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rag/create_folder")
async def create_rag_folder(folder_path: str):
    """Create a new folder in RAG documents"""
    try:
        root = Path(__file__).parent / "data"
        # Sanitize path to prevent breaking out of documents dir
        safe_path = Path(folder_path).name
        target_path = root / safe_path
        
        if target_path.exists():
             raise HTTPException(status_code=400, detail="Folder already exists")
        
        target_path.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "path": str(safe_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import UploadFile, File, Form

@app.post("/rag/upload")
async def upload_rag_file(
    file: UploadFile = File(...), 
    path: str = Form("")
):
    """Upload a file to RAG documents"""
    try:
        root = Path(__file__).parent / "data"
        # Sanitize target directory
        target_dir = root
        if path:
            # Prevent directory traversal
            clean_path = path.strip("/").replace("..", "")
            target_dir = root / clean_path
            
        target_dir.mkdir(parents=True, exist_ok=True)
        
        file_location = target_dir / file.filename
        content = await file.read()
        
        with open(file_location, "wb") as f:
            f.write(content)
            
        return {"status": "success", "filename": file.filename, "path": str(file_location.relative_to(root))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rag/reindex")
async def reindex_rag_documents(path: str = None):
    """Trigger re-indexing of documents via RAG MCP tool"""
    try:
        # Pass the path to the tool if provided
        args = {"target_path": path} if path else {}
        result = await multi_mcp.call_tool("rag", "reindex_documents", args)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger reindex: {str(e)}")

@app.get("/rag/indexing_status")
async def get_indexing_status():
    """Get current indexing progress"""
    try:
        result = await multi_mcp.call_tool("rag", "get_indexing_status", {})
        # Parse JSON string from MCP tool
        if hasattr(result, 'content') and isinstance(result.content, list):
            for item in result.content:
                if hasattr(item, 'text'):
                    import json
                    return json.loads(item.text)
        return {"active": False, "total": 0, "completed": 0, "currentFile": ""}
    except Exception as e:
        return {"active": False, "total": 0, "completed": 0, "currentFile": ""}

def find_page_for_chunk(doc_path: str, chunk_text: str) -> int:
    """Lazily find which page contains the chunk text using pymupdf text search."""
    try:
        import pymupdf
        full_path = Path(__file__).parent / "data" / doc_path
        if not full_path.exists() or not doc_path.endswith('.pdf'):
            return 1  # Default to page 1 for non-PDFs
        
        doc = pymupdf.open(str(full_path))
        # Clean markdown formatting and use first 60 chars for search
        search_text = chunk_text[:150].strip()
        # Remove markdown formatting
        search_text = re.sub(r'\*\*|##|#|\[|\]|\(|\)|!\[|\n', ' ', search_text)
        search_text = re.sub(r'\s+', ' ', search_text).strip()[:60]
        
        if len(search_text) < 10:
            doc.close()
            return 1  # Too short to search

        print(f"DEBUG Page search: '{search_text[:40]}...' in {doc_path}")  # DEBUG
        for page_num, page in enumerate(doc):
            # Search for text on this page
            if page.search_for(search_text):
                print(f"DEBUG Found on page {page_num + 1}")  # DEBUG
                doc.close()
                return page_num + 1  # 1-indexed
        
        doc.close()
        return 1  # Default to page 1 if not found
    except Exception as e:
        print(f"Page lookup failed: {e}")
        return 1

@app.get("/rag/search")
async def rag_search(query: str):
    """Semantic search against indexed RAG documents with page numbers"""
    try:
        args = {"query": query}
        result = await multi_mcp.call_tool("rag", "search_stored_documents_rag", args)
        
        # DEBUG: Log raw MCP result
        print(f"DEBUG MCP Result type: {type(result)}")
        print(f"DEBUG MCP Result: {result}")
        
        # Extract results from CallToolResult
        raw_results = []
        if hasattr(result, 'content') and isinstance(result.content, list):
            print(f"DEBUG: Found content list with {len(result.content)} items")
            for i, item in enumerate(result.content):
                print(f"DEBUG: Item {i} type: {type(item)}, hasattr text: {hasattr(item, 'text')}")
                if hasattr(item, 'text'):
                    print(f"DEBUG: Item text (first 200 chars): {item.text[:200] if len(item.text) > 200 else item.text}")
                    try:
                        import ast
                        parsed = ast.literal_eval(item.text)
                        print(f"DEBUG: Parsed type: {type(parsed)}, is list: {isinstance(parsed, list)}")
                        if isinstance(parsed, list):
                            raw_results.extend(parsed)
                        else:
                            raw_results.append(item.text)
                    except Exception as parse_err:
                        print(f"DEBUG: Parse error: {parse_err}")
                        raw_results.append(item.text)
        else:
            print(f"DEBUG: No content list found. hasattr content: {hasattr(result, 'content')}")
        
        # Parse results - page navigation handled by frontend search
        structured_results = []
        for r in raw_results:
            # Parse "[Source: path]" format
            match = re.search(r'\[Source:\s*(.+?)\]$', r)
            if match:
                source = match.group(1)
                content = r[:match.start()].strip()
                structured_results.append({
                    "content": content,
                    "source": source,
                    "page": 1  # Frontend PDF search will navigate to correct location
                })
            else:
                structured_results.append({
                    "content": r,
                    "source": "unknown",
                    "page": 1
                })
        
        return {"status": "success", "results": structured_results}
    except Exception as e:
        import traceback
        print(f"RAG SEARCH ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rag/document_chunks")
async def get_document_chunks(path: str):
    """Get cached chunks for a document from the FAISS metadata - FAST, no re-processing."""
    try:
        meta_path = Path(__file__).parent / "mcp_servers" / "faiss_index" / "metadata.json"
        if not meta_path.exists():
            return {"status": "error", "markdown": "No index found. Please index documents first."}
        
        metadata = json.loads(meta_path.read_text())
        
        # Filter chunks for this document
        doc_chunks = [m["chunk"] for m in metadata if m.get("doc") == path]
        
        if not doc_chunks:
            return {"status": "error", "markdown": f"No chunks found for document: {path}. Try re-indexing."}
        
        # --- BACKEND CAPTION INJECTION ---
        # Load captions.json and replace ![](images/X.png) with actual captions
        try:
            captions_path = meta_path.parent / "captions.json"
            if captions_path.exists():
                captions_ledger = json.loads(captions_path.read_text())
                
                # Define replacer at this scope
                def caption_replacer(match):
                    img_path = match.group(1)  # e.g. "images/file.png"
                    filename = Path(img_path).name  # e.g. "file.png"
                    
                    if filename in captions_ledger and captions_ledger[filename]:
                        caption = captions_ledger[filename]
                        return f"**[Image Caption]:** *{caption}*"
                    return match.group(0)  # Keep original if no caption yet
                
                # Apply regex at outer scope where 're' is accessible
                image_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
                doc_chunks = [image_pattern.sub(caption_replacer, c) for c in doc_chunks]
        except Exception as e:
            print(f"Caption injection ERROR: {e}")
            import traceback
            traceback.print_exc()
        # ---------------------------------
        
        # Concatenate chunks with separators
        full_text = "\n\n---\n\n".join(doc_chunks)

        # Detect if this is a code file
        code_exts = {
            '.py': 'python', '.tsx': 'typescript', '.ts': 'typescript', 
            '.js': 'javascript', '.jsx': 'javascript', '.html': 'html', 
            '.css': 'css', '.json': 'json', '.c': 'c', '.cpp': 'cpp',
            '.h': 'c', '.hpp': 'cpp', '.md': 'markdown', '.txt': 'text'
        }
        file_ext = Path(path).suffix.lower()
        
        if file_ext in code_exts and file_ext not in ['.md', '.txt']:
            # Wrap in code block
            lang = code_exts[file_ext]
            full_text = f"```{lang}\n{full_text}\n```"
        elif file_ext not in ['.md', '.txt']:
            # Apply heuristics to restore structure from flattened text (DOCS only)
            import re
            # 1. Restore headers
            full_text = re.sub(r'\s(#{1,6})\s', r'\n\n\1 ', full_text)
            
            # 2. Add breaks before " **" if it looks like a header
            full_text = re.sub(r'(\.|\:)\s+\*\*', r'\1\n\n**', full_text)

            # 3. Restore Tables: 
            # Pattern A: Header | Separator (Space between)
            # Find pipe followed by space(s) followed by |--- or |:---
            full_text = re.sub(r'(\|\s*)(?=\|[:\-]+\|)', r'\1\n', full_text)

            # Pattern B: Separator | Row (Space between)
            # Find |---| followed by space(s) followed by |
            full_text = re.sub(r'(\|[:\-]+\|)(\s+)(?=\|)', r'\1\n', full_text)
            
            # Pattern C: Row | Row (Space between)
            # Find | ending a cell, spaces, then | starting new row
            # Use lookbehind for pipe, lookahead for pipe
            # Be careful not to match empty cells | | inside a row
            # We assume |   | (3 spaces) is empty cell, but | | (1 space) might be row break?
            # Safe bet: |<text>| <space> |<text>|
            # Let's match: Pipe, Space(s), Pipe. Replace with Pipe, Newline, Pipe.
            # But only if it's NOT an empty cell.
            # Only apply if we are "in" a table context? Hard to know.
            # Strategy: If we see `| ... | | ... |` it is likely a row break if it's a long stream.
            pass
        
        return {
            "status": "success", 
            "markdown": full_text, 
            "chunks": doc_chunks, 
            "chunk_count": len(doc_chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/keyword_search")
async def rag_keyword_search(query: str):
    """Keyword search across document chunks (exact match)"""
    try:
        args = {"query": query}
        result = await multi_mcp.call_tool("rag", "keyword_search", args)
        
        # Extract matches from CallToolResult
        matches = []
        if hasattr(result, 'content') and isinstance(result.content, list):
            for item in result.content:
                if hasattr(item, 'text'):
                    try:
                        import ast
                        parsed = ast.literal_eval(item.text)
                        if isinstance(parsed, list):
                            matches.extend(parsed)
                    except:
                        matches.append(item.text)
        
        return {"status": "success", "matches": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Keyword search failed: {str(e)}")
@app.get("/rag/document_content")
async def get_document_content(path: str):
    """Get the content of a document (binary or text)"""
    try:
        root = Path(__file__).parent / "data"
        doc_path = root / path
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        
        from fastapi.responses import FileResponse
        ext = doc_path.suffix.lower()
        
        # Binary Media
        if ext in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.docx', '.doc']:
            media_types = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.doc': 'application/msword'
            }
            return FileResponse(doc_path, media_type=media_types.get(ext, 'application/octet-stream'))
        
        # Simple text extraction for fallback
        content = doc_path.read_text(errors='replace')
        return {"status": "success", "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rag/document_preview")
async def get_document_preview(path: str):
    """Get the AI-enhanced markdown version of a document (PDF, DOCX, etc.)"""
    try:
        args = {"path": str(Path(__file__).parent / "data" / path)}
        # Call the generic preview_document tool
        result = await multi_mcp.call_tool("rag", "preview_document", args)
        
        # 1. Handle stringified JSON results (common in some MCP tool patterns)
        if isinstance(result, str):
            try:
                import json
                data = json.loads(result)
                if isinstance(data, dict) and 'markdown' in data:
                    return {"status": "success", "markdown": data['markdown']}
            except:
                pass
            return {"status": "success", "markdown": result}

        # 2. Proper handling of MCP CallToolResult object
        if hasattr(result, 'content') and isinstance(result.content, list):
            for item in result.content:
                text = ""
                if hasattr(item, 'text'):
                    text = item.text
                elif isinstance(item, dict) and 'text' in item:
                    text = item['text']
                
                if text:
                    # Check if the text itself is encoded JSON
                    try:
                        import json
                        data = json.loads(text)
                        if isinstance(data, dict) and 'markdown' in data:
                            return {"status": "success", "markdown": data['markdown']}
                    except:
                        pass
                    return {"status": "success", "markdown": text}
        
        # 3. Fallback for direct storage objects
        if hasattr(result, 'markdown'):
            return {"status": "success", "markdown": result.markdown}
        
        return {"status": "success", "markdown": str(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rag/ask")
async def ask_rag_document(request: Request):
    """Interactive chat with a document via RAG with real-time streaming (SSE)"""
    try:
        body = await request.json()
        doc_id = body.get("docId")
        query = body.get("query")
        history = body.get("history", [])
        image = body.get("image") # Base64 image
        
        if not doc_id or not query:
            raise HTTPException(status_code=400, detail="Missing docId or query")
            
        # 1. Get relevant context using MCP tool
        context_results = await multi_mcp.call_tool("rag", "search_stored_documents_rag", {"query": query, "doc_path": doc_id})
        # Extract text from CallToolResult if needed (search_stored_documents_rag returns list)
        context_list = []
        if hasattr(context_results, 'content'):
            for c in context_results.content:
                if hasattr(c, 'text'):
                    try:
                        # The tool returns a list of strings as JSON or raw text
                        import ast
                        parsed = ast.literal_eval(c.text)
                        if isinstance(parsed, list):
                            context_list.extend(parsed)
                        else:
                            context_list.append(c.text)
                    except:
                        context_list.append(c.text)
        
        context_text = "\n\n".join(context_list) if context_list else "No relevant context found in document."

        # 2. Build Ollama Prompt
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
        for msg in history[-5:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            
        user_msg = {"role": "user", "content": query}
        if image:
            # Strip data:image/png;base64, if present
            if "," in image: image = image.split(",")[1]
            user_msg["images"] = [image]
        messages.append(user_msg)

        async def token_generator():
            try:
                # Use a separate session or direct httpx for streaming
                import httpx
                async with httpx.AsyncClient(timeout=300) as client:
                    async with client.stream("POST", "http://127.0.0.1:11434/api/chat", json={
                        "model": "qwen3-vl:8b", # Consistent with server_rag.py
                        "messages": messages,
                        "stream": True
                    }) as response:
                        async for line in response.aiter_lines():
                            if not line: continue
                            try:
                                data = json.loads(line)
                                chunk = data.get("message", {}).get("content", "")
                                if chunk:
                                    # SSE format: data: <payload>\n\n
                                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                                if data.get("done"):
                                    break
                            except:
                                continue
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        from fastapi.responses import StreamingResponse
        return StreamingResponse(token_generator(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === REMME MEMORY ENDPOINTS ===

@app.get("/remme/memories")
async def get_memories():
    """Get all stored memories with source existence check"""
    try:
        memories = remme_store.get_all()
        summaries_dir = Path(__file__).parent / "memory" / "session_summaries_index"
        
        # Add source_exists flag
        for m in memories:
            source = m.get("source", "")
            # Handle multiple sources in Hubs
            sources = [s.strip() for s in source.split(",")]
            exists = False
            for s in sources:
                run_id = s.replace("backfill_", "")
                if not run_id: continue
                
                # Brute force search for session file
                found = False
                for _ in summaries_dir.rglob(f"session_{run_id}.json"):
                    found = True
                    break
                if found:
                    exists = True
                    break
            
            # Special case: manual entries or no source
            if not source or source == "manual":
                exists = True 
            
            m["source_exists"] = exists
            
        return {"status": "success", "memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/remme/cleanup_dangling")
async def cleanup_dangling_memories():
    """Delete all memories where the source session no longer exists"""
    try:
        memories = remme_store.get_all()
        summaries_dir = Path(__file__).parent / "memory" / "session_summaries_index"
        ids_to_delete = []
        
        for m in memories:
            source = m.get("source", "")
            if not source or source == "manual": continue
            
            sources = [s.strip() for s in source.split(",")]
            exists = False
            for s in sources:
                run_id = s.replace("backfill_", "")
                if not run_id: continue
                for _ in summaries_dir.rglob(f"session_{run_id}.json"):
                    exists = True; break
                if exists: break
            
            if not exists:
                ids_to_delete.append(m["id"])
        
        for mid in ids_to_delete:
            remme_store.delete(mid)
            
        return {"status": "success", "deleted_count": len(ids_to_delete)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AddMemoryRequest(BaseModel):
    text: str
    category: str = "general"

@app.post("/remme/add")
async def add_memory(request: AddMemoryRequest):
    """Manually add a memory"""
    try:
        emb = get_embedding(request.text, task_type="search_query")
        memory = remme_store.add(request.text, emb, category=request.category, source="manual")
        return {"status": "success", "memory": memory}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/remme/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory"""
    try:
        remme_store.delete(memory_id)
        return {"status": "success", "id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === SETTINGS API ENDPOINTS ===

@app.get("/settings")
async def get_settings():
    """Get all current settings from config/settings.json"""
    try:
        # Force reload to get latest from disk
        current_settings = reload_settings()
        return {"status": "success", "settings": current_settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load settings: {str(e)}")

class UpdateSettingsRequest(BaseModel):
    settings: dict

@app.put("/settings")
async def update_settings(request: UpdateSettingsRequest):
    """Update settings and save to config/settings.json
    
    Note: Some settings require re-indexing (chunk_size, chunk_overlap, etc.)
    or server restart to take effect.
    """
    try:
        global settings
        # Deep merge incoming settings with existing
        def deep_merge(base: dict, update: dict) -> dict:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        deep_merge(settings, request.settings)
        save_settings()
        
        # Identify settings that require action
        warnings = []
        rag_keys = ["chunk_size", "chunk_overlap", "max_chunk_length", "semantic_word_limit"]
        if "rag" in request.settings:
            for key in rag_keys:
                if key in request.settings["rag"]:
                    warnings.append(f"Changed '{key}' - requires re-indexing documents to take effect")
        
        if "models" in request.settings:
            warnings.append("Model changes take effect on next document processing or server restart")
        
        return {
            "status": "success",
            "message": "Settings saved successfully",
            "warnings": warnings if warnings else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")

@app.post("/settings/reset")
async def reset_to_defaults():
    """Reset all settings to default values from config/settings.defaults.json"""
    try:
        reset_settings()
        return {"status": "success", "message": "Settings reset to defaults"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")

@app.post("/settings/restart")
async def restart_server():
    """Return instructions for manual restart.
    
    Note: Automatic restart doesn't work reliably with npm run dev:all / concurrently.
    The proper way is to manually Ctrl+C and restart.
    """
    return {
        "status": "manual_required",
        "message": "Automatic restart is not supported. Please manually restart the server.",
        "instructions": [
            "1. Press Ctrl+C in the terminal running npm run dev:all",
            "2. Run: npm run dev:all",
            "3. Refresh the browser"
        ]
    }

# === OLLAMA API ENDPOINTS ===

@app.get("/ollama/models")
async def get_ollama_models():
    """Get list of available Ollama models from local instance"""
    try:
        import requests
        from config.settings_loader import get_ollama_url
        
        ollama_url = get_ollama_url("base")
        response = requests.get(f"{ollama_url}/api/tags", timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to connect to Ollama")
        
        data = response.json()
        models = []
        for model in data.get("models", []):
            name = model.get("name", "")
            size_bytes = model.get("size", 0)
            size_gb = round(size_bytes / (1024**3), 2) if size_bytes else 0
            
            # Get family info from Ollama response
            details = model.get("details", {})
            families = details.get("families", [])
            
            # Infer capabilities from model name AND family
            capabilities = set()
            name_lower = name.lower()
            
            # Embedding models
            if "embed" in name_lower or "nomic" in name_lower or "nomic-bert" in families:
                capabilities.add("embedding")
            
            # Vision/multimodal models - check for explicit vision families or name patterns
            vision_families = ["clip", "qwen3vl", "llava"]
            vision_names = ["vl", "vision", "llava", "moondream", "gemma3"]  # gemma3 supports vision
            
            if any(f in families for f in vision_families) or any(v in name_lower for v in vision_names):
                capabilities.add("text")
                capabilities.add("image")
            else:
                capabilities.add("text")
            
            models.append({
                "name": name,
                "size_gb": size_gb,
                "capabilities": list(capabilities),
                "modified_at": model.get("modified_at", "")
            })
        
        return {"status": "success", "models": models}
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Ollama server not running")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PullModelRequest(BaseModel):
    name: str

@app.post("/ollama/pull")
async def pull_ollama_model(request: PullModelRequest):
    """Pull a new model from Ollama registry (starts async download)"""
    try:
        import requests
        from config.settings_loader import get_ollama_url
        
        ollama_url = get_ollama_url("base")
        # Use streaming=False for now, just initiate the pull
        response = requests.post(
            f"{ollama_url}/api/pull",
            json={"name": request.name, "stream": False},
            timeout=600  # 10 min timeout for large models
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to pull model: {response.text}")
        
        return {"status": "success", "message": f"Model '{request.name}' pulled successfully"}
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Model pull timed out - try from terminal")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gemini/status")
async def get_gemini_status():
    """Check if Gemini API key is configured via environment variable"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        return {
            "status": "success",
            "configured": bool(api_key),
            "key_preview": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === PROMPTS API ENDPOINTS ===

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPTS_BACKUP_DIR = Path(__file__).parent / "prompts" / ".backup"

@app.get("/prompts")
async def list_prompts():
    """List all prompt files with their content"""
    try:
        prompts = []
        if PROMPTS_DIR.exists():
            for f in PROMPTS_DIR.glob("*.md"):
                content = f.read_text()
                # Check if backup exists (means original can be restored)
                backup_file = PROMPTS_BACKUP_DIR / f.name
                prompts.append({
                    "name": f.stem,
                    "filename": f.name,
                    "content": content,
                    "lines": len(content.splitlines()),
                    "has_backup": backup_file.exists()
                })
        return {"status": "success", "prompts": sorted(prompts, key=lambda x: x["name"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdatePromptRequest(BaseModel):
    content: str

@app.put("/prompts/{prompt_name}")
async def update_prompt(prompt_name: str, request: UpdatePromptRequest):
    """Update a prompt file's content. Creates backup on first edit."""
    try:
        prompt_file = PROMPTS_DIR / f"{prompt_name}.md"
        if not prompt_file.exists():
            raise HTTPException(status_code=404, detail=f"Prompt '{prompt_name}' not found")
        
        # Create backup on first edit (if doesn't exist)
        PROMPTS_BACKUP_DIR.mkdir(exist_ok=True)
        backup_file = PROMPTS_BACKUP_DIR / f"{prompt_name}.md"
        if not backup_file.exists():
            backup_file.write_text(prompt_file.read_text())
        
        prompt_file.write_text(request.content)
        return {"status": "success", "message": f"Prompt '{prompt_name}' updated", "has_backup": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/prompts/{prompt_name}/reset")
async def reset_prompt(prompt_name: str):
    """Reset a prompt to its original content from backup"""
    try:
        prompt_file = PROMPTS_DIR / f"{prompt_name}.md"
        backup_file = PROMPTS_BACKUP_DIR / f"{prompt_name}.md"
        
        if not backup_file.exists():
            raise HTTPException(status_code=404, detail=f"No backup found for '{prompt_name}'")
        
        # Restore from backup
        original_content = backup_file.read_text()
        prompt_file.write_text(original_content)
        
        # Remove backup after restore
        backup_file.unlink()
        
        return {"status": "success", "message": f"Prompt '{prompt_name}' reset to original", "content": original_content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === APP PERSISTENCE ENDPOINTS ===

class CreateAppRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    cards: List[dict] = []
    layout: List[dict] = []

@app.get("/apps")
async def list_apps():
    """List all saved apps from apps/ directory"""
    try:
        apps_dir = Path(__file__).parent / "apps"
        if not apps_dir.exists():
            return []
        
        apps = []
        for app_folder in apps_dir.iterdir():
            if app_folder.is_dir():
                ui_file = app_folder / "ui.json"
                if ui_file.exists():
                    try:
                        data = json.loads(ui_file.read_text())
                        apps.append({
                            "id": app_folder.name,
                            "name": data.get("name", "Untitled App"),
                            "description": data.get("description", ""),
                            "lastModified": data.get("lastModified", 0)
                        })
                    except:
                        continue
        # Sort by recently modified
        return sorted(apps, key=lambda x: x['lastModified'], reverse=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/apps/{app_id}")
async def get_app(app_id: str):
    """Get full app configuration"""
    try:
        ui_file = Path(__file__).parent / "apps" / app_id / "ui.json"
        if not ui_file.exists():
            raise HTTPException(status_code=404, detail="App not found")
        
        return json.loads(ui_file.read_text())
    except Exception as e:
        # Re-raise HTTP exceptions, wrap others
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/apps")
async def save_app(request: CreateAppRequest):
    """Create or Update an app"""
    try:
        apps_dir = Path(__file__).parent / "apps"
        apps_dir.mkdir(exist_ok=True)
        
        # ID generation: use name-timestamp if new, else assume standard ID format handling in frontend?
        # Actually frontend usually manages state, but here backend should probably own ID if creating new.
        # But we want to support overlapping saves.
        
        # Let's say if we pass an ID in the request it updates, otherwise creates?
        # The request schema above matches what we send from store usually.
        # For simplicity, we'll auto-generate ID if it's a "create" action concept, 
        # but usually frontend sends the whole object. 
        # Let's adjust schema to accept optional ID, or just handle filename generation here.
        
        # Actually, let's look at how frontend works. It generates UUIDs.
        # So we should probably accept ID in the body or URL.
        # NOTE: Using a separate endpoint for creation vs update is cleaner, 
        # but upsert is fine too. Let's assume the ID is part of the request logic in frontend.
        # Wait, the `CreateAppRequest` doesn't have ID.
        # We will generate one based on name + salt if not provided?
        # Let's change the pattern: Frontend generates ID for new apps.
        # So we really want `PUT /apps/{app_id}` or include `id` in body.
        
        # Re-defining request to include ID
        pass
    except:
        pass

# Redefining to be more robust
class SaveAppRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    cards: List[dict]
    layout: List[dict]
    lastModified: int

@app.post("/apps/save")
async def save_app_endpoint(request: SaveAppRequest):
    try:
        apps_dir = Path(__file__).parent / "apps"
        apps_dir.mkdir(exist_ok=True)
        
        app_folder = apps_dir / request.id
        app_folder.mkdir(exist_ok=True)
        
        ui_file = app_folder / "ui.json"
        data = request.dict()
        
        # Check if exists to preserve creation time if we tracked it? 
        # Current schema only has lastModified.
        
        ui_file.write_text(json.dumps(data, indent=2))
        return {"status": "success", "id": request.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/apps/{app_id}")
async def delete_app(app_id: str):
    try:
        app_folder = Path(__file__).parent / "apps" / app_id
        if app_folder.exists():
            import shutil
            shutil.rmtree(app_folder)
        return {"status": "success", "id": app_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rag/images/{filename}")
async def get_rag_image(filename: str):
    """Serve images extracted by MuPDF/indexing process"""
    try:
        image_path = Path(__file__).parent / "mcp_servers" / "documents" / "images" / filename
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        from fastapi.responses import FileResponse
        return FileResponse(image_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mcp/tools")
async def get_mcp_tools():
    """List available MCP tools by scanning files using regex for robustness"""
    import re
    tools = []
    try:
        server_path = (Path(__file__).parent / "mcp_servers").resolve()
        print(f"🔍 Scanning for MCP tools in: {server_path}")
        
        if not server_path.exists():
            print(f"❌ server_path DOES NOT EXIST: {server_path}")
            return {"tools": []}

        # More robust regex:
        # 1. Matches @mcp.tool or @tool
        # 2. Handles optional parentheses/args
        # 3. Matches optional async
        # 4. Captures function name
        # 5. Correctly handles type hints and arrows
        tool_pattern = re.compile(
            r'@(?:mcp\.)?tool\s*(?:\(.*?\))?\s*'
            r'(?:async\s+)?def\s+(\w+)\s*\(.*?\)\s*(?:->\s*[\w\[\], \.]+)?\s*:'
            r'(?:\s*"""(.*?)""")?',
            re.DOTALL
        )
        
        for py_file in server_path.glob("*.py"):
            print(f"  📄 Scanning file: {py_file.name}")
            try:
                content = py_file.read_text()
                matches = list(tool_pattern.finditer(content))
                print(f"    - Found {len(matches)} tools")
                
                for match in matches:
                    name = match.group(1)
                    docstring = match.group(2)
                    
                    tools.append({
                        "name": name,
                        "description": (docstring or "No description").strip(),
                        "file": py_file.name
                    })

            except Exception as ex:
                print(f"Failed to scan {py_file}: {ex}")
                continue
                
        return {"tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mcp/connected_tools")
async def get_connected_mcp_tools():
    """List tools from all connected MCP sessions"""
    try:
        tools_by_server = {}
        for server_name, tools in multi_mcp.tools.items():
            tools_by_server[server_name] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema
                } for t in tools
            ]
        return {"servers": tools_by_server}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/refresh/{server_name}")
async def refresh_mcp_server(server_name: str):
    """Force refresh tool metadata for a specific MCP server"""
    success = await multi_mcp.refresh_server(server_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found or not connected")
    return {"status": "success", "message": f"Metadata for {server_name} refreshed and cached"}

# --- Explorer Endpoints ---
@app.get("/explorer/scan")
async def scan_project_files(path: str):
    """Scan project files for the context selector"""
    try:
        abs_path = path
        if not os.path.isabs(abs_path):
            abs_path = os.path.abspath(abs_path)
            
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Path not found")
            
        extractor = CodeSkeletonExtractor(abs_path)
        scan_results = extractor.scan_project()
        
        return {
            "success": True,
            "scan": scan_results,
            "root_path": abs_path
        }
    except Exception as e:
        print(f"  ❌ Scan Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/explorer/list")
async def list_files(path: str):
    """Recursively list files for the explorer panel"""
    try:
        abs_path = path
        if not os.path.isabs(abs_path):
            abs_path = os.path.abspath(abs_path)
            
        print(f"📁 Explorer: Listing files for {abs_path}")
            
        if not os.path.exists(abs_path):
            print(f"  ⚠️ Path not found: {abs_path}")
            return { "files": [], "root_path": abs_path, "error": "Path not found" }
        
        extractor = CodeSkeletonExtractor(abs_path)
        
        def build_tree(current_path):
            nodes = []
            try:
                items = os.listdir(current_path)
            except (PermissionError, FileNotFoundError):
                return []
                
            for item in items:
                full_path = os.path.join(current_path, item)
                try:
                    if extractor.is_ignored(full_path):
                        continue
                        
                    node = {
                        "name": item,
                        "path": full_path,
                        "type": "folder" if os.path.isdir(full_path) else "file"
                    }
                    if os.path.isdir(full_path):
                        children = build_tree(full_path)
                        if children:
                            node["children"] = children
                    nodes.append(node)
                except:
                    continue
            
            nodes.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))
            return nodes

        return {
            "files": build_tree(abs_path),
            "root_path": abs_path
        }
    except Exception as e:
        print(f"  ❌ List Files Failed: {e}")
        return { "files": [], "root_path": path, "error": str(e) }

@app.post("/explorer/analyze")
async def analyze_project(request: AnalyzeRequest):
    """Analyze a project and generate an architecture map"""
    target_path = request.path
    is_temp = False
    print(f"🧠 Explorer: Analyzing {target_path} (Type: {request.type})")
    
    try:
        # 1. HANDLE GITHUB
        if request.type == "github" or target_path.startswith("http"):
            is_temp = True
            temp_dir = tempfile.mkdtemp()
            print(f"  🔗 Cloning GitHub Repo {target_path} to {temp_dir}...")
            try:
                # Add --depth 1 for speed
                subprocess.run(["git", "clone", "--depth", "1", target_path, temp_dir], check=True, capture_output=True)
                target_path = temp_dir
                print("  ✅ Clone Successful.")
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode() if e.stderr else str(e)
                print(f"  ❌ Clone Failed: {err_msg}")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                raise HTTPException(status_code=400, detail=f"Git clone failed: {err_msg}")
        else:
            # Resolve local path
            target_path = os.path.abspath(target_path)
            if not os.path.exists(target_path):
                print(f"  ⚠️ Local path not found: {target_path}")
                raise HTTPException(status_code=404, detail=f"Local path not found: {target_path}")

        if request.files:
            # Context Analysis Mode: We have a selected list of files
            # Read full content of selected files
            print(f"  📚 Analying {len(request.files)} selected files with Full Context...")
            context_str = ""
            for rel_path in request.files:
                full_path = os.path.join(target_path, rel_path)
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        context_str += f"--- FILE: {rel_path} ---\n{content}\n\n"
                except Exception as e:
                    print(f"  ⚠️ Could not read {rel_path}: {e}")
        else:
            # Fallback to Skeleton Mode (Legacy/Auto)
            # 2. EXTRACT SKELETON
            print("  💀 Extracting Skeletons (Blind Mode)...")
            extractor = CodeSkeletonExtractor(target_path)
            skeletons = extractor.extract_all()
            
            # Combine into a single prompt context
            context_str = ""
            for file_path, skel in skeletons.items():
                context_str += f"--- FILE: {file_path} ---\n{skel}\n\n"
        
        if not context_str:
            raise HTTPException(status_code=400, detail="No content found in the specified path/files for analysis.")

        # 3. LLM ANALYSIS
        model = ModelManager("gemini")
        prompt = f"""
        You are an elite software architect. Analyze the following code skeleton and generate a high-level architecture map in FlowStep format.
        
        CODE CONTEXT:
        {context_str}
        
        GOAL:
        1. Identify the core logical components (Manager classes, API layers, UI components, Utilities).
        2. Group related functionality into thematic blocks.
        3. Map how data flows between these components.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "nodes": [
                {{ 
                    "id": "1", 
                    "type": "agent", 
                    "position": {{ "x": 250, "y": 0 }}, 
                    "data": {{ 
                        "label": "ComponentName", 
                        "description": "Short explanation of what this component does.",
                        "details": ["Key Function A", "Key class B"], 
                        "attributes": ["Async", "Priority: High", "Stateful"]
                    }} 
                }}
            ],
            "edges": [
                {{ "id": "e1-2", "source": "1", "target": "2", "type": "smoothstep" }}
            ],
            "sequence": ["1", "2"]
        }}
        
        LAYOUT RULES:
        - Increment Y by ~250 for each layer to create a vertical flow.
        - X should be around 250 for center, or +/- 200 for side-branches.

        Be technical and precise. Focus on architectural intent.
        """
        
        response_text = await model.generate_text(prompt)
        print(f"  🤖 LLM Response (Raw): {response_text[:200]}...")
        
        # Clean response if it contains markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        try:
            flow_data = json.loads(response_text)
        except json.JSONDecodeError as je:
            print(f"  ❌ JSON Parse Error: {je}")
            raise HTTPException(status_code=500, detail=f"LLM returned invalid JSON: {str(je)}")
            
        return {
            "success": True, 
            "flow_data": flow_data,
            "root_path": request.path if (request.type == "github" or request.path.startswith("http")) else target_path
        }
        
    except Exception as e:
        print(f"Analysis Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if is_temp and os.path.exists(target_path):
            shutil.rmtree(target_path)


# --- MCP Server Management Endpoints ---

class AddServerRequest(BaseModel):
    name: str
    config: dict

@app.get("/mcp/servers")
async def list_mcp_servers():
    """List all configured MCP servers and their status"""
    try:
        # Get configured servers from config file
        config = multi_mcp.server_configs
        # Get connection status
        connected = multi_mcp.get_connected_servers()
        
        servers = []
        for name, cfg in config.items():
            servers.append({
                "name": name,
                "config": cfg,
                "status": "connected" if name in connected else "disconnected"
            })
        return {"servers": servers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/servers")
async def add_mcp_server(request: AddServerRequest):
    """Add a new MCP server dynamically"""
    try:
        await multi_mcp.add_server(request.name, request.config)
        
        # --- Auto-Assign to Agents ---
        try:
            import yaml
            
            AGENT_CONFIG_PATH = Path('config/agent_config.yaml')
            if AGENT_CONFIG_PATH.exists():
                with open(AGENT_CONFIG_PATH, 'r') as f:
                    agent_config = yaml.safe_load(f)
                
                updated = False
                # Add to RetrieverAgent and CoderAgent by default
                targets = ['RetrieverAgent', 'CoderAgent']
                
                for agent_name in targets:
                    if agent_name in agent_config['agents']:
                        servers = agent_config['agents'][agent_name].get('mcp_servers', [])
                        if request.name not in servers:
                            servers.append(request.name)
                            agent_config['agents'][agent_name]['mcp_servers'] = servers
                            updated = True
                            print(f"  🤖 Auto-assigned {request.name} to {agent_name}")
                
                if updated:
                    with open(AGENT_CONFIG_PATH, 'w') as f:
                        yaml.dump(agent_config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"  ⚠️ Failed to auto-assign server to agents: {e}")
            # Don't fail the whole request, just log warning

        return {"status": "success", "message": f"Server {request.name} added and assigned to agents"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/mcp/servers/{name}")
async def remove_mcp_server(name: str):
    """Remove an MCP server"""
    try:
        success = await multi_mcp.remove_server(name)
        if success:
            return {"status": "success", "message": f"Server {name} removed"}
        raise HTTPException(status_code=404, detail="Server not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mcp/connected_tools")
async def get_connected_tools():
    """Get tools grouped by server (Optimized)"""
    # Use cached tools from multi_mcp
    return {"servers": multi_mcp.tools}

class ToolStateRequest(BaseModel):
    server_name: str
    tool_name: str
    enabled: bool

@app.post("/mcp/tool_state")
async def set_tool_state(request: ToolStateRequest):
    """Enable or disable a specific tool"""
    multi_mcp.set_tool_state(request.server_name, request.tool_name, request.enabled)
    return {"status": "success"}

@app.get("/mcp/readme/{name}")
async def get_mcp_readme(name: str):
    """Get the README content for a server"""
    content = multi_mcp.get_server_readme(name)
    if content:
        return {"content": content}
    # Return empty or specific message if not found, don't 404 to avoid frontend console spam
    return {"content": f"# {name}\n\nNo documentation found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
