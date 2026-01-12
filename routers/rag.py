# RAG Router - Handles document management, indexing, and search
import json
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse

from shared.state import get_multi_mcp, PROJECT_ROOT

router = APIRouter(prefix="/rag", tags=["RAG"])

# Get shared instances
multi_mcp = get_multi_mcp()


# === Document Management Endpoints ===

@router.get("/documents")
async def get_rag_documents():
    """List documents in a recursive tree structure with RAG status"""
    try:
        doc_path = PROJECT_ROOT / "data"
        index_dir = PROJECT_ROOT / "mcp_servers" / "faiss_index"
        
        # Try new ledger format first, fall back to legacy cache
        ledger_file = index_dir / "ledger.json"
        cache_file = index_dir / "doc_index_cache.json"
        
        file_entries = {}  # {path: {hash, status, indexed_at, ...}}
        
        if ledger_file.exists():
            try:
                ledger_data = json.loads(ledger_file.read_text())
                file_entries = ledger_data.get("files", {})
            except:
                pass
        elif cache_file.exists():
            # Legacy format: {"path": "hash"}
            try:
                legacy_cache = json.loads(cache_file.read_text())
                for path, file_hash in legacy_cache.items():
                    file_entries[path] = {
                        "hash": file_hash,
                        "status": "complete",
                        "indexed_at": None,
                        "chunk_count": 0
                    }
            except:
                pass

        def build_tree(path: Path):
            items = []
            # Sort: directories first, then files
            for p in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if p.name.startswith('.') or p.name in ["__pycache__", "mcp_repos", "faiss_index"]:
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
                    entry = file_entries.get(rel_p, {})
                    item["indexed"] = entry.get("status") == "complete" if entry else False
                    item["status"] = entry.get("status", "unindexed")  # New field
                    item["hash"] = entry.get("hash", "Not Indexed")
                    item["chunk_count"] = entry.get("chunk_count", 0)
                    item["error"] = entry.get("error")
                
                items.append(item)
            return items

        files = build_tree(doc_path) if doc_path.exists() else []
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create_folder")
async def create_rag_folder(folder_path: str):
    """Create a new folder in RAG documents"""
    try:
        root = PROJECT_ROOT / "data"
        # Sanitize path to allow nested folders but prevent traversal
        clean_path = folder_path.strip("/").replace("..", "")
        target_path = root / clean_path
        
        if target_path.exists():
             raise HTTPException(status_code=400, detail="Folder already exists")
        
        target_path.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "path": str(clean_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete")
async def delete_rag_item(path: str = Form(...)):
    """Delete a file or folder in RAG documents"""
    try:
        root = PROJECT_ROOT / "data"
        # Sanitize
        clean_path = path.strip("/").replace("..", "")
        target_path = root / clean_path
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Item not found")
            
        # Security check: ensure we are deleting something inside data
        if not str(target_path.resolve()).startswith(str(root.resolve())):
             raise HTTPException(status_code=403, detail="Access denied")

        if target_path.is_dir():
            import shutil
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
            
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_file")
async def create_rag_file(path: str = Form(...), content: str = Form("")):
    """Create a new file in RAG documents"""
    try:
        root = PROJECT_ROOT / "data"
        clean_path = path.strip("/").replace("..", "")
        target_path = root / clean_path
        
        if target_path.exists():
            raise HTTPException(status_code=400, detail="File already exists")
            
        # Ensure parent dir exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        target_path.write_text(content)
        return {"status": "success", "path": str(clean_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/save_file")
async def save_rag_file(path: str = Form(...), content: str = Form(...)):
    """Save/Overwrite file content"""
    try:
        root = PROJECT_ROOT / "data"
        clean_path = path.strip("/").replace("..", "")
        target_path = root / clean_path
        
        # Security check
        if not str(target_path.resolve()).startswith(str(root.resolve())):
             raise HTTPException(status_code=403, detail="Access denied")
        
        target_path.write_text(content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_rag_file(
    file: UploadFile = File(...), 
    path: str = Form("")
):
    """Upload a file to RAG documents"""
    try:
        root = PROJECT_ROOT / "data"
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


# === Indexing Endpoints ===

@router.post("/reindex")
async def reindex_rag_documents(path: str = None, force: bool = False):
    """Trigger re-indexing of documents via RAG MCP tool"""
    try:
        # Pass the path to the tool if provided
        args = {"target_path": path, "force": force}
        result = await multi_mcp.call_tool("rag", "reindex_documents", args)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger reindex: {str(e)}")


@router.get("/indexing_status")
async def get_indexing_status():
    """Get current indexing progress"""
    try:
        result = await multi_mcp.call_tool("rag", "get_indexing_status", {})
        # Parse JSON string from MCP tool
        if hasattr(result, 'content') and isinstance(result.content, list):
            for item in result.content:
                if hasattr(item, 'text'):
                    return json.loads(item.text)
        return {"active": False, "total": 0, "completed": 0, "currentFile": ""}
    except Exception as e:
        return {"active": False, "total": 0, "completed": 0, "currentFile": ""}


# === Search Endpoints ===

def find_page_for_chunk(doc_path: str, chunk_text: str) -> int:
    """Lazily find which page contains the chunk text using pymupdf text search."""
    try:
        import pymupdf
        full_path = PROJECT_ROOT / "data" / doc_path
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


@router.get("/search")
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
            # Parse "[Source: path p123]" format
            match = re.search(r'\[Source:\s*(.+?)(?:\s+p(\d+))?\]$', r)
            if match:
                source = match.group(1)
                page_str = match.group(2)
                content = r[:match.start()].strip()
                structured_results.append({
                    "content": content,
                    "source": source,
                    "page": int(page_str) if page_str else 1
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


@router.get("/keyword_search")
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

@router.get("/ripgrep_search")
async def rag_ripgrep_search(query: str, regex: bool = False, case_sensitive: bool = False):
    """Deep pattern search using ripgrep"""
    try:
        args = {"query": query, "regex": regex, "case_sensitive": case_sensitive}
        result = await multi_mcp.call_tool("rag", "advanced_ripgrep_search", args)
        
        # Extract results from CallToolResult - ROBUST NOISE-RESISTANT PARSER
        results = []
        
        def extract_json_list(text):
            """Helpful regex to find and extract the JSON list even if there's noise"""
            # Try finding something that looks like a JSON list: [...]
            import re
            match = re.search(r'\[\s*{.*}\s*\]', text, re.DOTALL)
            if match:
                 try:
                     return json.loads(match.group(0))
                 except:
                     pass
            
            # Try ast if it looks like a Python list with single quotes
            match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
            if match:
                 try:
                     import ast
                     return ast.literal_eval(match.group(0))
                 except:
                     pass
            return None

        # 1. Try to find content in 'content' list
        if hasattr(result, 'content') and isinstance(result.content, list):
            for item in result.content:
                text_content = ""
                if hasattr(item, 'text'):
                    text_content = item.text
                elif isinstance(item, dict) and 'text' in item:
                    text_content = item['text']
                
                if text_content:
                    # DEBUG: Print snippet
                    print(f"DEBUG: MCP Text Content Start: {text_content[:100]}...")
                    
                    extracted = extract_json_list(text_content)
                    
                    # Validate matches
                    valid_items = []
                    if extracted and isinstance(extracted, list):
                        for x in extracted:
                            if isinstance(x, dict) and "file" in x and "line" in x:
                                valid_items.append(x)
                    
                    if valid_items:
                        results.extend(valid_items)
                    else:
                        # Direct try as fallback
                        try:
                            parsed = json.loads(text_content)
                            if isinstance(parsed, list):
                                valid = [x for x in parsed if isinstance(x, dict) and "file" in x]
                                results.extend(valid)
                            elif isinstance(parsed, dict) and "file" in parsed:
                                results.append(parsed)
                        except:
                            try:
                                import ast
                                parsed = ast.literal_eval(text_content)
                                if isinstance(parsed, list): 
                                    valid = [x for x in parsed if isinstance(x, dict) and "file" in x]
                                    results.extend(valid)
                                elif isinstance(parsed, dict) and "file" in parsed:
                                    results.append(parsed)
                            except:
                                pass
        
        # 2. Fallback: If result itself is already a list (direct return)
        elif isinstance(result, list):
            results = result
            
        print(f"DEBUG: Ripgrep router returning {len(results)} structured results")
        if len(results) > 0:
            print(f"DEBUG: First result sample: {results[0]}")
            
        return {"status": "success", "results": results}
    except Exception as e:
        import traceback
        print(f"Ripgrep router error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ripgrep search failed: {str(e)}")


# === Document Content Endpoints ===

@router.get("/document_chunks")
async def get_document_chunks(path: str):
    """Get cached chunks for a document from the FAISS metadata - FAST, no re-processing."""
    try:
        meta_path = PROJECT_ROOT / "mcp_servers" / "faiss_index" / "metadata.json"
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
            # 1. Restore headers
            full_text = re.sub(r'\s(#{1,6})\s', r'\n\n\1 ', full_text)
            
            # 2. Add breaks before " **" if it looks like a header
            full_text = re.sub(r'(\.|\:)\s+\*\*', r'\1\n\n**', full_text)

            # 3. Restore Tables: 
            # Pattern A: Header | Separator (Space between)
            full_text = re.sub(r'(\|\s*)(?=\|[:\-]+\|)', r'\1\n', full_text)

            # Pattern B: Separator | Row (Space between)
            full_text = re.sub(r'(\|[:\-]+\|)(\s+)(?=\|)', r'\1\n', full_text)
        
        return {
            "status": "success", 
            "markdown": full_text, 
            "chunks": doc_chunks, 
            "chunk_count": len(doc_chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document_content")
async def get_document_content(path: str):
    """Get the content of a document (binary or text)"""
    try:
        root = PROJECT_ROOT / "data"
        doc_path = root / path
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        
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


@router.get("/document_preview")
async def get_document_preview(path: str):
    """Get the AI-enhanced markdown version of a document (PDF, DOCX, etc.)"""
    try:
        args = {"path": str(PROJECT_ROOT / "data" / path)}
        # Call the generic preview_document tool
        result = await multi_mcp.call_tool("rag", "preview_document", args)
        
        # 1. Handle stringified JSON results (common in some MCP tool patterns)
        if isinstance(result, str):
            try:
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


@router.post("/ask")
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

        return StreamingResponse(token_generator(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Image Serving ===

@router.get("/images/{filename}")
async def get_rag_image(filename: str):
    """Serve images extracted by MuPDF/indexing process"""
    try:
        image_path = PROJECT_ROOT / "mcp_servers" / "documents" / "images" / filename
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        return FileResponse(image_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
