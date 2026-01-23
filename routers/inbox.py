import sqlite3
import json
import uuid
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path

# --- Configuration ---
DB_PATH = Path("data/inbox/notifications.db")
router = APIRouter(prefix="/inbox", tags=["Inbox"])

# --- Schema ---
class Notification(BaseModel):
    id: str
    source: str
    title: str
    body: str  # Markdown support
    priority: int = 1  # 1=Normal, 2=High, 3=Critical
    is_read: bool = False
    timestamp: str
    metadata: Optional[Dict[str, Any]] = {}

class CreateNotificationRequest(BaseModel):
    source: str
    title: str
    body: str
    priority: int = 1
    metadata: Optional[Dict[str, Any]] = {}

# --- Database Helper ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the SQLite database if it doesn't exist."""
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            is_read BOOLEAN DEFAULT 0,
            timestamp TEXT NOT NULL,
            metadata TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Initialize on module load
init_db()

# --- Helper Function for Internal Use ---
def send_to_inbox(source: str, title: str, body: str, priority: int = 1, metadata: dict = None) -> str:
    """
    Internal Python API to send a notification to the Inbox.
    Agents and backend services should use this.
    """
    notif_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    meta_json = json.dumps(metadata) if metadata else "{}"
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO notifications (id, source, title, body, priority, is_read, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (notif_id, source, title, body, priority, False, timestamp, meta_json)
    )
    conn.commit()
    conn.close()
    return notif_id

# --- Endpoints ---

@router.get("/", response_model=List[Notification])
async def get_notifications(unread_only: bool = False, limit: int = 50):
    """Fetch notifications, optionally filtering by unread status."""
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT * FROM notifications"
    params = []
    
    if unread_only:
        query += " WHERE is_read = 0"
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append(Notification(
            id=row["id"],
            source=row["source"],
            title=row["title"],
            body=row["body"],
            priority=row["priority"],
            is_read=bool(row["is_read"]),
            timestamp=row["timestamp"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        ))
    return results

@router.post("/", response_model=Dict[str, str])
async def create_notification(request: CreateNotificationRequest):
    """Create a new notification (API Endpoint)."""
    notif_id = send_to_inbox(
        source=request.source,
        title=request.title,
        body=request.body,
        priority=request.priority,
        metadata=request.metadata
    )
    return {"id": notif_id, "status": "created"}

@router.patch("/{notif_id}/read")
async def mark_as_read(notif_id: str):
    """Mark a notification as read."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    found = c.rowcount > 0
    conn.close()
    
    if not found:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "updated"}

@router.delete("/{notif_id}")
async def delete_notification(notif_id: str):
    """Delete a notification."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
    conn.commit()
    found = c.rowcount > 0
    conn.close()
    
    if not found:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "deleted"}
