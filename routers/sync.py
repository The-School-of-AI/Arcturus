"""
P11 Phase 4 Sync Engine — backend API.

POST /sync/push — receive batch of changes, merge (LWW) into store, append to sync log.
POST /sync/pull — return changes since cursor (from sync log).
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from core.auth.context import get_current_user_id
from memory.sync.schema import PullRequest, PullResponse, PushRequest, PushResponse, SyncChange
from memory.sync_config import is_sync_engine_enabled, get_sync_server_url

router = APIRouter(prefix="/sync", tags=["Sync"])

_USER_ID_FILE = Path(__file__).parent.parent / "memory" / "remme_index" / "user_id.json"


def _user_id_for_sync() -> str | None:
    """User ID for background sync: request context, then persisted file (e.g. Electron desktop)."""
    uid = get_current_user_id()
    if uid:
        return uid
    if _USER_ID_FILE.exists():
        try:
            data = json.loads(_USER_ID_FILE.read_text())
            return data.get("user_id") or None
        except Exception:
            pass
    return None


async def run_sync_background(user_id: str | None = None) -> None:
    """
    Run SyncEngine.sync() (push then pull) in a background thread.
    No-op if sync engine is disabled or SYNC_SERVER_URL not set.
    Used on app startup and after add_memory/create_space.
    Pass user_id when called from a request handler so the background task has identity; else uses file/context.
    """
    if not is_sync_engine_enabled() or not get_sync_server_url():
        return
    uid = user_id or _user_id_for_sync()
    if not uid:
        return
    try:
        from memory.sync.engine import get_sync_engine
        engine = get_sync_engine(user_id=uid)
        if not engine:
            return
        # sync() is blocking (HTTP); run in thread to not block event loop
        push_resp, pull_resp = await asyncio.to_thread(engine.sync)
        if push_resp.errors or pull_resp.changes:
            # Optional: log for debugging
            pass
    except Exception:
        pass  # Don't fail startup or request on sync errors

_SYNC_LOG_DIR = Path(__file__).parent.parent / "memory" / "remme_index" / "sync_logs"


def _log_path(user_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)[:64]
    return _SYNC_LOG_DIR / f"{safe}.json"


def _load_log(user_id: str) -> tuple[list[dict], int]:
    """Load sync log for user. Returns (entries, next_seq)."""
    p = _log_path(user_id)
    if not p.exists():
        return [], 1
    try:
        data = json.loads(p.read_text())
        entries = data.get("entries", [])
        next_seq = data.get("next_seq", len(entries) + 1)
        return entries, next_seq
    except Exception:
        return [], 1


def _append_to_log(user_id: str, changes: list[dict]) -> int:
    """Append changes to log. Returns last seq written."""
    if not changes:
        return 0
    p = _log_path(user_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    entries, next_seq = _load_log(user_id)
    for i, ch in enumerate(changes):
        entries.append({"seq": next_seq + i, "change": ch})
    new_next = next_seq + len(changes)
    p.write_text(json.dumps({"entries": entries, "next_seq": new_next}, indent=2))
    return new_next - 1


def _apply_change_to_store(change: SyncChange, user_id: str) -> None:
    """Apply a single change to local Qdrant + Neo4j (LWW merge)."""
    from memory.sync.merge import lww_wins

    if change.type == "memory":
        payload = change.payload or {}
        memory_id = payload.get("memory_id", "")
        text = payload.get("text", "")
        meta = payload.get("payload", {}) or {}
        deleted = change.deleted
        updated_at = change.updated_at
        device_id = payload.get("device_id", "")

        store = None
        try:
            from shared.state import get_remme_store
            store = get_remme_store()
        except Exception:
            pass
        if not store:
            return

        local = store.get(memory_id) if hasattr(store, "get") else None
        local_ts = (local or {}).get("updated_at", "")
        local_dev = (local or {}).get("device_id", "")
        if local and lww_wins(local_ts, local_dev, updated_at, device_id):
            return

        if deleted:
            if hasattr(store, "delete"):
                store.delete(memory_id)
            return

        meta["updated_at"] = updated_at
        meta["device_id"] = device_id
        meta["version"] = change.version
        meta["user_id"] = user_id

        if local:
            if hasattr(store, "update"):
                emb = None
                try:
                    from remme.utils import get_embedding
                    emb = get_embedding(text) if text else None
                except Exception:
                    pass
                store.update(memory_id, text=text, embedding=emb, metadata=meta)
        else:
            if hasattr(store, "sync_upsert") and text:
                try:
                    from remme.utils import get_embedding
                    emb = get_embedding(text)
                    store.sync_upsert(memory_id, text, emb, meta)
                except Exception:
                    pass

    elif change.type == "space":
        payload = change.payload or {}
        space_id = payload.get("space_id", "")
        if not space_id or change.deleted:
            try:
                from memory.knowledge_graph import get_knowledge_graph
                kg = get_knowledge_graph()
                if kg and kg.enabled and hasattr(kg, "delete_space"):
                    kg.delete_space(space_id)
            except Exception:
                pass
            return
        try:
            from memory.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            if kg and kg.enabled and hasattr(kg, "upsert_space"):
                kg.upsert_space(
                    space_id=space_id,
                    user_id=user_id,
                    name=payload.get("name", ""),
                    description=payload.get("description", ""),
                    sync_policy=payload.get("sync_policy", "sync"),
                    version=change.version,
                    device_id=payload.get("device_id", ""),
                    updated_at=change.updated_at,
                )
        except Exception:
            pass

    elif change.type == "episodic":
        payload = change.payload or {}
        episodic_id = payload.get("episodic_id") or payload.get("session_id", "")
        if not episodic_id:
            return
        try:
            from memory.backends.episodic_qdrant_store import EpisodicQdrantStore
            store = EpisodicQdrantStore()
            if change.deleted:
                store.delete(episodic_id)
                return
            skeleton_json = payload.get("skeleton_json", "{}")
            original_query = payload.get("original_query", "")
            outcome = payload.get("outcome", "completed")
            uid = payload.get("user_id") or user_id
            space_id = payload.get("space_id", "__global__")
            emb = None
            try:
                from remme.utils import get_embedding
                import json
                sk = json.loads(skeleton_json) if isinstance(skeleton_json, str) else {}
                searchable = original_query
                for n in sk.get("nodes", []):
                    tg = n.get("task_goal") or n.get("description") or ""
                    if tg:
                        searchable += "\n" + str(tg)[:300]
                    inst = n.get("instruction", "") or ""
                    if inst:
                        searchable += "\n" + str(inst)[:300]
                emb = get_embedding(searchable or original_query or "episode")
            except Exception:
                pass
            if emb is not None:
                store.sync_upsert(
                    session_id=episodic_id,
                    skeleton_json=skeleton_json,
                    original_query=original_query,
                    outcome=outcome,
                    user_id=uid,
                    space_id=space_id,
                    embedding=emb,
                    updated_at=change.updated_at,
                )
        except Exception:
            pass


@router.post("/push", response_model=PushResponse)
async def sync_push(request: PushRequest) -> PushResponse:
    """
    Receive batch of changes from client. Merge (LWW) into store, append to sync log.
    Requires SYNC_ENGINE_ENABLED. user_id is derived from auth context (JWT/X-User-Id), not body.
    """
    if not is_sync_engine_enabled():
        raise HTTPException(status_code=503, detail="Sync engine not enabled")
    user_id = get_current_user_id()
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required for sync")
    errors = []
    for c in request.changes:
        try:
            _apply_change_to_store(c, user_id)
        except Exception as e:
            errors.append(str(e))
    changes_dump = [c.model_dump(mode="json") for c in request.changes]
    last_seq = _append_to_log(user_id, changes_dump)
    cursor = str(last_seq) if request.changes else ""
    return PushResponse(
        accepted=len(errors) == 0,
        cursor=cursor,
        errors=errors if errors else [],
    )


@router.post("/trigger")
async def sync_trigger():
    """
    Manually trigger sync (push then pull). Uses local user_id and store.
    Returns { push: {...}, pull: {...} }.
    """
    if not is_sync_engine_enabled():
        raise HTTPException(status_code=503, detail="Sync engine not enabled")
    try:
        from memory.sync.engine import get_sync_engine
        engine = get_sync_engine()
        if not engine:
            raise HTTPException(status_code=503, detail="Sync engine not available (check SYNC_SERVER_URL)")
        push_resp, pull_resp = engine.sync()
        return {
            "push": {"accepted": push_resp.accepted, "errors": push_resp.errors},
            "pull": {"changes_count": len(pull_resp.changes), "cursor": pull_resp.cursor},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pull", response_model=PullResponse)
async def sync_pull(request: PullRequest) -> PullResponse:
    """
    Return changes since cursor from sync log.
    user_id is derived from auth context (JWT/X-User-Id), not body.
    """
    if not is_sync_engine_enabled():
        raise HTTPException(status_code=503, detail="Sync engine not enabled")
    user_id = get_current_user_id()
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required for sync")
    entries, _ = _load_log(user_id)
    since = 0
    try:
        since = int(request.since_cursor or "0")
    except ValueError:
        pass
    out = []
    for e in entries:
        seq = e.get("seq", 0)
        if seq > since:
            ch = e.get("change", {})
            out.append(SyncChange.model_validate(ch))
    cursor = str(max((e.get("seq", 0) for e in entries), default=0))
    return PullResponse(changes=out, cursor=cursor)
