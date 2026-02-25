from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import json

router = APIRouter(tags=["voice"])


class SetPersonaRequest(BaseModel):
    persona: str  # e.g. "professional", "casual", "energetic"


class AddPersonaRequest(BaseModel):
    name: str
    voice_name: str = "en-US-JennyNeural"
    rate: str = "1.0"
    pitch: str = "+0Hz"
    volume: str = "default"
    description: str = ""


# ── Existing endpoint ──────────────────────────────────────────

@router.post("/voice/start")
async def start_listening(request: Request):
    orch = request.app.state.orchestrator
    orch.on_wake(None)
    return {"status": "listening"}


# ── Voice Personas ─────────────────────────────────────────────

@router.get("/voice/personas")
async def list_personas(request: Request):
    """
    Return all available voice personas and which one is active.

    Response:
    {
        "active": "professional",
        "personas": {
            "professional": { "voice_name": "...", "rate": "...", ... },
            ...
        }
    }
    """
    tts = request.app.state.orchestrator.tts
    return {
        "active": tts.active_persona,
        "personas": tts.list_personas(),
    }


@router.put("/voice/persona")
async def set_persona(request: Request, body: SetPersonaRequest):
    """
    Switch the active voice persona at runtime.

    Body: { "persona": "casual" }
    """
    tts = request.app.state.orchestrator.tts
    ok = tts.set_persona(body.persona)
    if not ok:
        available = list(tts.list_personas().keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona '{body.persona}'. Available: {available}",
        )
    return {
        "status": "ok",
        "active": tts.active_persona,
        "voice_name": tts._voice_name,
    }


@router.post("/voice/persona/add")
async def add_persona(request: Request, body: AddPersonaRequest):
    """
    Register a new custom voice persona.

    Body: { "name": "whisper", "voice_name": "en-US-AriaNeural",
            "rate": "0.85", "pitch": "-2Hz", "volume": "soft",
            "description": "Quiet and intimate" }
    """
    tts = request.app.state.orchestrator.tts
    tts.add_persona(body.name, body.model_dump(exclude={"name"}))
    return {
        "status": "ok",
        "persona": body.name,
        "config": tts.list_personas()[body.name],
    }


# ── Voice Session Logs ─────────────────────────────────────────

@router.get("/voice/session")
async def get_current_session(request: Request):
    """
    Return the current voice session's turns and conversation history.

    Response:
    {
        "session_id": "vs_20260223_...",
        "turn_count": 3,
        "turns": [ ... ],
        "conversation_history": [ {"role": "user", "content": "..."}, ... ]
    }
    """
    logger = request.app.state.orchestrator.session_logger
    return {
        "session_id": logger.session_id,
        "turn_count": logger.turn_count,
        "turns": logger.get_turns(),
        "conversation_history": logger.get_conversation_history(),
    }


@router.get("/voice/sessions")
async def list_sessions(request: Request, days: int = 7):
    """
    List all saved voice session files from the last N days.
    Returns an array of { session_id, file_path, started_at, total_turns }.
    """
    from datetime import datetime, timedelta

    base_dir = Path(__file__).resolve().parent.parent / "memory" / "voice_sessions"
    sessions = []

    if not base_dir.exists():
        return {"sessions": []}

    cutoff = datetime.now() - timedelta(days=days)

    for json_file in sorted(base_dir.rglob("vs_*.json"), reverse=True):
        try:
            # Quick date check from the folder structure (YYYY/MM/DD)
            parts = json_file.relative_to(base_dir).parts
            if len(parts) >= 3:
                file_date = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                if file_date < cutoff:
                    continue

            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            sessions.append({
                "session_id": data.get("session_id"),
                "started_at": data.get("started_at"),
                "ended_at": data.get("ended_at"),
                "total_turns": data.get("total_turns", 0),
                "file_path": str(json_file),
            })
        except Exception:
            continue

    return {"sessions": sessions, "count": len(sessions)}


@router.get("/voice/sessions/{session_id}")
async def get_session_detail(request: Request, session_id: str):
    """
    Return full details of a specific saved voice session.
    """
    base_dir = Path(__file__).resolve().parent.parent / "memory" / "voice_sessions"

    # Search for the session file
    matches = list(base_dir.rglob(f"{session_id}.json"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    with open(matches[0], "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


@router.delete("/voice/session")
async def clear_current_session(request: Request):
    """
    End and flush the current voice session (useful for manual reset).
    """
    logger = request.app.state.orchestrator.session_logger
    path = logger.end_session()
    return {
        "status": "ok",
        "saved_to": path,
    }
