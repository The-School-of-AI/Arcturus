import sys
import os
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

app = FastAPI()

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

@app.on_event("startup")
async def startup_event():
    await multi_mcp.start()

@app.on_event("shutdown")
async def shutdown_event():
    await multi_mcp.stop()

class RunRequest(BaseModel):
    query: str
    model: str = "gemini-2.0-pro"

class RunResponse(BaseModel):
    id: str
    status: str
    created_at: str
    query: str

async def process_run(run_id: str, query: str):
    """Background task to execute the agent loop"""
    try:
        loop = AgentLoop4(multi_mcp=multi_mcp)
        # Register the LOOP instance immediately so we can stop it
        active_loops[run_id] = loop
        
        # Execute the loop
        # The loop will maintain its own internal context
        context = await loop.run(query, [], {}, [], session_id=run_id)
        
    except Exception as e:
        print(f"Run {run_id} failed: {e}")
        # Clean up on failure
        if run_id in active_loops:
            del active_loops[run_id]

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
                    
                    runs.append({
                        "id": session_file.stem.replace("session_", ""),
                        "query": query, 
                        "created_at": created_at, 
                        "status": computed_status
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
        return {
            "id": run_id,
            "status": "completed", # simplistic
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

@app.get("/rag/search")
async def rag_search(query: str):
    """Semantic search against indexed RAG documents"""
    try:
        args = {"query": query}
        result = await multi_mcp.call_tool("rag", "search_stored_documents_rag", args)
        # Result is already a list of strings from the tool
        return {"status": "success", "results": result}
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
        server_path = Path(__file__).parent / "mcp_servers"
        # Robust regex: 
        # 1. Matches @mcp.tool or @tool
        # 2. Handles optional parentheses/args: (?:\(.*?\))?
        # 3. Handles newlines/whitespace before def
        # 4. Matches optional async
        # 5. Captures function name
        # 6. Matches arguments
        # 7. Optionally captures docstring
        
        tool_pattern = re.compile(
            r'@(?:mcp\.)?tool\s*(?:\(.*?\))?\s*'  # Decorator
            r'(?:async\s+)?def\s+(\w+)\s*\(.*?\).*?:' # Function sig
            r'(?:\s*"""(.*?)""")?', # Docstring
            re.DOTALL | re.VERBOSE
        )
        
        for py_file in server_path.glob("*.py"):
            try:
                content = py_file.read_text()
                matches = tool_pattern.finditer(content)
                
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
