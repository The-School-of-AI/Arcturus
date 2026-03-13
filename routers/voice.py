from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import json
import threading

router = APIRouter(tags=["voice"])


def _get_orch(request: Request):
    """Return the orchestrator or raise 503 if the voice pipeline isn't running."""
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=503, detail="Voice pipeline not running.")
    return orch

# ── Privacy mode: thread-safe guard for service hot-swap ───────────────────
_privacy_swap_lock = threading.Lock()


def _hot_swap_voice_services(orch, enable_privacy: bool) -> dict:
    """
    Hot-swap STT and TTS services on the live orchestrator *without* a server
    restart.  Called while holding _privacy_swap_lock.

    Privacy ON  → STT: Whisper (local)   TTS: Piper (local)
    Privacy OFF → STT: Deepgram (cloud)  TTS: Azure (cloud)

    Returns a dict describing what was actually switched.
    """
    from voice.config import VOICE_CONFIG

    # ── 1. Stop current STT (non-blocking) ─────────────────────────────
    old_stt = orch.stt
    if old_stt is not None:
        try:
            old_stt.stop()
        except Exception as e:
            print(f"⚠️ [Privacy] Failed to stop old STT: {e}")

    # ── 2. Build new STT ────────────────────────────────────────────────
    stt_cfg     = VOICE_CONFIG.get("stt", {})
    sample_rate = stt_cfg.get("sample_rate", 16000)
    noise_reduce = stt_cfg.get("noise_reduce", True)

    if enable_privacy:
        from voice.stt_service import STTService
        w_cfg = stt_cfg.get("whisper", {})
        new_stt = STTService(
            sample_rate=sample_rate,
            on_text_callback=orch.on_text,
            model_size=w_cfg.get("model_size", "small"),
            device=w_cfg.get("device", "cpu"),
            noise_reduce=noise_reduce,
        )
        new_stt_label = f"Whisper/{w_cfg.get('model_size', 'small')} (local)"
    else:
        from voice.deepgram_stt_service import DeepgramSTTService
        dg_cfg = stt_cfg.get("deepgram", {})
        new_stt = DeepgramSTTService(
            sample_rate=sample_rate,
            on_text_callback=orch.on_text,
            language=dg_cfg.get("language", "en"),
            noise_reduce=noise_reduce,
        )
        new_stt_label = "Deepgram Nova-2 (cloud)"

    new_stt.start()
    orch.stt = new_stt
    VOICE_CONFIG["stt_provider"] = "whisper" if enable_privacy else "deepgram"

    # ── 3. Cancel current TTS and build the new one ─────────────────────
    try:
        orch.tts.cancel()
    except Exception:
        pass

    if enable_privacy:
        from voice.piper_tts_service import PiperTTSService
        piper_cfg = VOICE_CONFIG.get("piper_tts", {})
        new_tts = PiperTTSService(
            model_path=piper_cfg.get("model_path"),
            length_scale=piper_cfg.get("length_scale", 1.0),
            sentence_silence=piper_cfg.get("sentence_silence", 0.15),
            speaker_id=piper_cfg.get("speaker_id"),
        )
        new_tts_label = "Piper (local)"
    else:
        from voice.tts_service import TTSService
        tts_cfg = VOICE_CONFIG.get("tts", {})
        new_tts = TTSService(
            voice_name=tts_cfg.get("voice_name"),
            personas=tts_cfg.get("personas"),
            active_persona=tts_cfg.get("active_persona"),
        )
        new_tts_label = "Azure Neural (cloud)"

    orch.tts = new_tts
    VOICE_CONFIG["tts_provider"] = "piper" if enable_privacy else "azure"

    print(f"🔒 [Privacy] Mode {'ON' if enable_privacy else 'OFF'} — "
          f"STT: {new_stt_label}, TTS: {new_tts_label}")

    return {
        "privacy_mode": enable_privacy,
        "stt": new_stt_label,
        "tts": new_tts_label,
    }




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
    orch = _get_orch(request)
    orch.on_wake({})
    return {"status": "listening"}


# ── Privacy Mode ───────────────────────────────────────────────

@router.get("/voice/privacy")
async def get_privacy_mode(request: Request):
    """
    Return the current privacy mode state.

    Response:
    {
        "privacy_mode": true,
        "stt_provider": "whisper",
        "tts_provider": "piper"
    }
    """
    from voice.config import VOICE_CONFIG
    stt = VOICE_CONFIG.get("stt_provider", "deepgram")
    tts = VOICE_CONFIG.get("tts_provider", "azure")
    # Privacy mode = both services are local
    is_private = (stt == "whisper" and tts == "piper")
    return {
        "privacy_mode": is_private,
        "stt_provider": stt,
        "tts_provider": tts,
    }


class SetPrivacyRequest(BaseModel):
    enabled: bool


@router.post("/voice/privacy")
async def set_privacy_mode(request: Request, body: SetPrivacyRequest):
    """
    Enable or disable Privacy Mode.

    Privacy ON  → STT switches to Whisper (local), TTS switches to Piper (local).
                  No audio/transcript data leaves the device.
    Privacy OFF → STT switches to Deepgram (cloud), TTS switches to Azure Neural.

    The swap is performed live — no server restart required.

    Body: { "enabled": true }

    Response:
    {
        "status": "ok",
        "privacy_mode": true,
        "stt": "Whisper/small (local)",
        "tts": "Piper (local)"
    }
    """
    orch = _get_orch(request)

    with _privacy_swap_lock:
        result = _hot_swap_voice_services(orch, enable_privacy=body.enabled)

    return {"status": "ok", **result}




@router.get("/voice/wake")
async def get_wake_state(request: Request):
    """
    Polling-friendly endpoint: returns whether a wake word has been detected
    since the last call, then clears the flag.

    The frontend polls this at ~1s intervals as a reliable fallback to the SSE
    stream. Zero asyncio involvement — purely synchronous state read.
    """
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        return {"wake": False, "state": "IDLE"}

    woke = orch.wake_detected
    if woke:
        orch.wake_detected = False   # consume: next poll returns False

    return {
        "wake": woke,
        "state": getattr(orch, "state", "IDLE"),
    }


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
    tts = _get_orch(request).tts
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
    tts = _get_orch(request).tts
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
    tts = _get_orch(request).tts
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
    logger = _get_orch(request).session_logger
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
    logger = _get_orch(request).session_logger
    path = logger.end_session()
    return {
        "status": "ok",
        "saved_to": path,
    }


# ── Dictation Mode ─────────────────────────────────────────────

@router.post("/voice/dictation/start")
async def start_dictation(request: Request):
    """
    Enter Dictation Mode: STT stays active, but every transcript fragment
    is accumulated into a long-form document instead of being sent to Nexus.

    The TTS announces entry into dictation mode.  Any ongoing TTS/Nexus run
    is cancelled.

    Response:
    {
        "status": "dictating",
        "session_id": "dict_20260302_..."
    }
    """
    orch = _get_orch(request)
    session_id = orch.start_dictation()
    return {"status": "dictating", "session_id": session_id}


@router.post("/voice/dictation/stop")
async def stop_dictation(request: Request):
    """
    Stop Dictation Mode, finalise the document, and save it to disk.
    Orchestrator returns to IDLE after this call.

    Response:
    {
        "status": "stopped",
        "session_id": "dict_...",
        "word_count": 142,
        "text": "The full dictated document...",
        "saved_to": "memory/dictation/2026/03/dictation_dict_....txt"
    }
    """
    orch = _get_orch(request)
    result = orch.stop_dictation()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "stopped", **result}


@router.get("/voice/dictation/current")
async def get_dictation_status(request: Request):
    """
    Return the current dictation state and a live preview of the document
    being built.  Useful for UI polling while dictation is active.

    Response (when active):
    {
        "active": true,
        "session_id": "dict_...",
        "started_at": "2026-03-02T...",
        "fragment_count": 12,
        "word_count": 94,
        "preview": "First 500 chars...",
        "text": "Full text so far..."
    }

    Response (when inactive):
    { "active": false }
    """
    orch = _get_orch(request)
    return orch.get_dictation_status()
