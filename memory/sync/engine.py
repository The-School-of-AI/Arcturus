"""
P11 Phase 4 Sync Engine — orchestrates push/pull, merge, apply.

Offline-first: push local changes, pull remote, merge (LWW), apply to local store.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from memory.sync_config import get_device_id, get_sync_server_url, is_sync_engine_enabled
from memory.sync.change_tracker import (
    build_memory_deltas,
    build_push_changes,
    build_space_deltas,
)
from memory.sync.merge import lww_wins
from memory.sync.schema import (
    MemoryDelta,
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
    SpaceDelta,
    SyncChange,
)
from memory.sync.transport import pull_changes, push_changes

_CURSOR_PATH = Path(__file__).parent.parent.parent / "memory" / "remme_index" / "sync_cursor.json"


def _load_cursor() -> str:
    try:
        if _CURSOR_PATH.exists():
            import json
            data = json.loads(_CURSOR_PATH.read_text())
            return data.get("cursor", "") or ""
    except Exception:
        pass
    return ""


def _save_cursor(cursor: str) -> None:
    try:
        import json
        _CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CURSOR_PATH.write_text(json.dumps({"cursor": cursor}, indent=2))
    except Exception:
        pass


class SyncEngine:
    """
    Sync engine: push local changes, pull remote, merge (LWW), apply.
    """

    def __init__(
        self,
        *,
        user_id: str,
        device_id: Optional[str] = None,
        sync_server_url: Optional[str] = None,
        store: Any = None,
        kg: Any = None,
        get_embedding_fn: Optional[Callable[[str], Any]] = None,
    ):
        self.user_id = user_id
        self.device_id = device_id or get_device_id()
        self.sync_server_url = (sync_server_url or get_sync_server_url()).rstrip("/")
        self._store = store
        self._kg = kg
        self._get_embedding = get_embedding_fn

    def push(self) -> PushResponse:
        """Push local changes to sync server. Returns response with cursor."""
        if not self.sync_server_url:
            return PushResponse(accepted=False, cursor="", errors=["SYNC_SERVER_URL not set"])
        if not self._store:
            return PushResponse(accepted=False, cursor="", errors=["Vector store not configured"])
        if not self._kg or not getattr(self._kg, "enabled", False):
            # Spaces optional for push (memories only)
            spaces: list[dict] = []
            policy_map: dict[str, str] = {}
        else:
            spaces = self._kg.get_spaces_for_user(self.user_id)
            policy_map = {s["space_id"]: s.get("sync_policy", "sync") for s in spaces}

        def get_policy(sid: str) -> str:
            return policy_map.get(sid, "sync")

        memories = self._store.get_all() if hasattr(self._store, "get_all") else []
        mem_deltas = build_memory_deltas(
            memories,
            device_id=self.device_id,
            get_policy=get_policy,
        )
        space_deltas = build_space_deltas(spaces, device_id=self.device_id)
        changes = build_push_changes(mem_deltas, space_deltas)
        req = PushRequest(user_id=self.user_id, device_id=self.device_id, changes=changes)
        return push_changes(self.sync_server_url, req)

    def pull(self) -> PullResponse:
        """Pull remote changes, merge (LWW), apply to local store. Returns response."""
        if not self.sync_server_url:
            return PullResponse(changes=[], cursor="")
        cursor = _load_cursor()
        req = PullRequest(
            user_id=self.user_id,
            device_id=self.device_id,
            since_cursor=cursor,
        )
        resp = pull_changes(self.sync_server_url, req)
        if resp.changes:
            self._apply_changes(resp.changes)
        if resp.cursor:
            _save_cursor(resp.cursor)
        return resp

    def sync(self) -> tuple[PushResponse, PullResponse]:
        """Push then pull. Returns (push_resp, pull_resp)."""
        push_resp = self.push()
        pull_resp = self.pull()
        return push_resp, pull_resp

    def _apply_changes(self, changes: list[SyncChange]) -> None:
        """Apply pulled changes to local store (LWW merge, then write)."""
        for c in changes:
            if c.type == "memory":
                self._apply_memory_change(c)
            elif c.type == "space":
                self._apply_space_change(c)

    def _apply_memory_change(self, c: SyncChange) -> None:
        payload = c.payload or {}
        memory_id = payload.get("memory_id", "")
        text = payload.get("text", "")
        meta = payload.get("payload", {})
        if isinstance(meta, dict):
            meta = dict(meta)
        else:
            meta = {}
        deleted = c.deleted
        updated_at = c.updated_at
        device_id = payload.get("device_id", "")

        if not self._store:
            return

        local = None
        if hasattr(self._store, "get") and memory_id:
            local = self._store.get(memory_id)
        local_ts = (local or {}).get("updated_at", "")
        local_dev = (local or {}).get("device_id", "")

        # LWW: skip apply if local wins
        if local and lww_wins(local_ts, local_dev, updated_at, device_id):
            return

        if deleted:
            if hasattr(self._store, "delete") and memory_id:
                self._store.delete(memory_id)
            return

        meta["updated_at"] = updated_at
        meta["device_id"] = device_id
        meta["version"] = c.version

        if local:
            if hasattr(self._store, "update"):
                emb = None
                if self._get_embedding and text:
                    emb = self._get_embedding(text)
                self._store.update(memory_id, text=text, embedding=emb, metadata=meta)
        else:
            if self._get_embedding and text:
                emb = self._get_embedding(text)
                meta["space_id"] = meta.get("space_id", "__global__")
                meta["category"] = meta.get("category", "general")
                meta["source"] = meta.get("source", "sync")
                if hasattr(self._store, "sync_upsert"):
                    self._store.sync_upsert(memory_id, text, emb, meta)
                elif hasattr(self._store, "add"):
                    self._store.add(
                        text,
                        emb,
                        category=meta.get("category", "general"),
                        source=meta.get("source", "sync"),
                        metadata=meta,
                        session_id=meta.get("session_id"),
                        space_id=meta.get("space_id"),
                        skip_kg_ingest=True,
                    )

    def _apply_space_change(self, c: SyncChange) -> None:
        payload = c.payload or {}
        space_id = payload.get("space_id", "")
        if not space_id or not self._kg or not getattr(self._kg, "enabled", False):
            return
        if c.deleted:
            if hasattr(self._kg, "delete_space"):
                self._kg.delete_space(space_id)
            return
        name = payload.get("name", "")
        description = payload.get("description", "")
        sync_policy = payload.get("sync_policy", "sync")
        if hasattr(self._kg, "upsert_space"):
            self._kg.upsert_space(
                space_id=space_id,
                user_id=self.user_id,
                name=name,
                description=description,
                sync_policy=sync_policy,
                version=c.version,
                device_id=payload.get("device_id", ""),
                updated_at=c.updated_at,
            )


def get_sync_engine(
    user_id: Optional[str] = None,
    store: Any = None,
    kg: Any = None,
) -> Optional[SyncEngine]:
    """Factory: return SyncEngine if sync enabled and URL set, else None."""
    if not is_sync_engine_enabled() or not get_sync_server_url():
        return None
    uid = user_id
    if not uid:
        try:
            from memory.user_id import get_user_id
            uid = get_user_id()
        except Exception:
            return None
    if not store:
        try:
            from shared.state import get_remme_store
            store = get_remme_store()
        except Exception:
            store = None
    if not kg:
        try:
            from memory.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
        except Exception:
            kg = None
    get_emb = None
    try:
        from remme.utils import get_embedding
        get_emb = get_embedding
    except Exception:
        pass
    return SyncEngine(
        user_id=uid,
        store=store,
        kg=kg,
        get_embedding_fn=get_emb,
    )
