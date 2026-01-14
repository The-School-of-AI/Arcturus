import json
import os
import shutil
import time
import uuid
import hashlib
from pathlib import Path
from typing import List, Optional, Literal
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from shared.state import PROJECT_ROOT

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: float
    images: Optional[List[str]] = None

class ChatSession(BaseModel):
    id: str
    target_type: Literal['rag', 'ide']
    target_id: str
    title: str
    messages: List[ChatMessage]
    created_at: float
    updated_at: float
    model: Optional[str] = None

# --- Helpers ---

def get_chat_storage_path(target_type: str, target_id: str) -> Path:
    """Determine where to store chats based on target."""
    if target_type == 'rag':
        # Store in data/.meta/chats/{doc_hash}
        # We hash the doc path to avoid filesystem issues with long/complex paths
        doc_hash = hashlib.md5(target_id.encode()).hexdigest()
        path = PROJECT_ROOT / "data" / ".meta" / "chats" / doc_hash
    else:
        # For IDE, we expect target_id to be the absolute path to the project root
        # We store in {project_root}/.gemini/chats
        path = Path(target_id) / ".gemini" / "chats"
    
    path.mkdir(parents=True, exist_ok=True)
    return path

# --- Endpoints ---

@router.get("/sessions")
async def list_chat_sessions(target_type: str, target_id: str):
    """List all chat sessions for a specific document or project."""
    try:
        storage_path = get_chat_storage_path(target_type, target_id)
        sessions = []
        
        if storage_path.exists():
            for file in storage_path.glob("*.json"):
                try:
                    data = json.loads(file.read_text())
                    # Lightweight list (exclude messages for speed if needed, but including for now)
                    sessions.append({
                        "id": data["id"],
                        "title": data.get("title", "New Chat"),
                        "created_at": data.get("created_at", 0),
                        "updated_at": data.get("updated_at", 0),
                        "model": data.get("model"),
                        "preview": data["messages"][-1]["content"][:50] if data["messages"] else ""
                    })
                except:
                    continue
                    
        # Sort by updated_at desc
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return {"status": "success", "sessions": sessions}
    except Exception as e:
        print(f"Error listing sessions: {e}")
        return {"status": "success", "sessions": []} # Fallback to empty

@router.get("/session/{session_id}")
async def get_chat_session(session_id: str, target_type: str, target_id: str):
    """Load a specific chat session."""
    try:
        storage_path = get_chat_storage_path(target_type, target_id)
        session_file = storage_path / f"{session_id}.json"
        
        if not session_file.exists():
            raise HTTPException(status_code=404, detail="Session not found")
            
        data = json.loads(session_file.read_text())
        return {"status": "success", "session": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/session")
async def save_chat_session(session: ChatSession):
    """Create or update a chat session."""
    try:
        storage_path = get_chat_storage_path(session.target_type, session.target_id)
        session_file = storage_path / f"{session.id}.json"
        
        # Determine title if new or default
        if session.title == "New Chat" and len(session.messages) > 0:
            # Generate title from first user message
            first_msg = next((m for m in session.messages if m.role == 'user'), None)
            if first_msg:
                # Simple truncation
                session.title = first_msg.content[:30] + "..."
        
        session.updated_at = time.time()
        
        # Save
        session_file.write_text(session.model_dump_json(indent=2))
        
        return {"status": "success", "session": session}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}")
async def delete_chat_session(session_id: str, target_type: str, target_id: str):
    """Delete a chat session."""
    try:
        storage_path = get_chat_storage_path(target_type, target_id)
        session_file = storage_path / f"{session_id}.json"
        
        if session_file.exists():
            session_file.unlink()
            
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
