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
    contexts: Optional[List[str]] = None
    fileContexts: Optional[List[dict]] = None

class ChatSession(BaseModel):
    id: str
    target_type: Literal['rag', 'ide', 'notes']
    target_id: str
    title: str
    messages: List[ChatMessage]
    created_at: float
    updated_at: float
    model: Optional[str] = None
    # Debug/logging fields for agent troubleshooting
    system_prompt: Optional[str] = None
    tools: Optional[List[dict]] = None

# --- Helpers ---

def get_chat_storage_path(target_type: str, target_id: str) -> Path:
    """Determine where to store chats based on target."""
    doc_hash = hashlib.md5(target_id.encode()).hexdigest()
    
    if target_type == 'rag':
        # Store in data/.meta/chats/{doc_hash}
        path = PROJECT_ROOT / "data" / ".meta" / "chats" / doc_hash
    else:
        # For IDE, find base directory
        target_path = Path(target_id)
        if target_path.is_dir():
            # If target_id is the project root (dir), store in a fixed subfolder
            # This allows all project-linked chats to be in one place
            path = target_path / ".arcturus" / "chats" / "project"
        elif target_path.is_file():
            # Legacy file-based storage
            base_dir = target_path.parent
            path = base_dir / ".arcturus" / "chats" / doc_hash
        else:
            # Fallback for non-existent paths (still might be a dir in intent)
            path = target_path / ".arcturus" / "chats" / doc_hash
    
    path.mkdir(parents=True, exist_ok=True)
    return path

def find_session_file(session_id: str, target_type: str, target_id: str) -> Optional[Path]:
    """Find a session file, checking legacy locations if needed."""
    main_storage = get_chat_storage_path(target_type, target_id)
    session_file = main_storage / f"{session_id}.json"
    
    if session_file.exists():
        return session_file
        
    if target_type == 'ide':
        # Search sibling folders in .arcturus/chats
        root_arcturus = Path(target_id) / ".arcturus" / "chats"
        if root_arcturus.exists() and root_arcturus.is_dir():
            for p in root_arcturus.iterdir():
                if p.is_dir() and (p / f"{session_id}.json").exists():
                    return p / f"{session_id}.json"
    
    return None

# --- Endpoints ---

@router.get("/sessions")
async def list_chat_sessions(target_type: str, target_id: str):
    """List all chat sessions for a specific document or project."""
    try:
        sessions = []
        paths_to_scan = []
        
        main_storage = get_chat_storage_path(target_type, target_id)
        paths_to_scan.append(main_storage)
        
        # IDE Discovery: If we are in IDE mode and target_id is a project root,
        # we also look for legacy chats in other subfolders of the same .arcturus/chats
        if target_type == 'ide':
            root_arcturus = Path(target_id) / ".arcturus" / "chats"
            if root_arcturus.exists() and root_arcturus.is_dir():
                for p in root_arcturus.iterdir():
                    if p.is_dir() and p.name != "project" and p != main_storage:
                        paths_to_scan.append(p)

        for storage_path in paths_to_scan:
            if storage_path.exists():
                for file in storage_path.glob("*.json"):
                    try:
                        data = json.loads(file.read_text())
                        # Lightweight list
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
        session_file = find_session_file(session_id, target_type, target_id)
        
        if not session_file:
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
        
        # If it already exists elsewhere (legacy), we might want to keep it there?
        # Actually, for simplicity, if it's already in a legacy folder, we use that.
        existing = find_session_file(session.id, session.target_type, session.target_id)
        if existing:
            session_file = existing
            
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
        session_file = find_session_file(session_id, target_type, target_id)
        
        if session_file and session_file.exists():
            session_file.unlink()
            
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
