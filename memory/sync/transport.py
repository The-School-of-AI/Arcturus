"""
P11 Phase 4 Sync Engine — HTTP client for push/pull.

Calls sync server POST /sync/push and POST /sync/pull.
"""

import httpx

from memory.sync.schema import PushRequest, PushResponse, PullRequest, PullResponse, SyncChange


def push_changes(
    base_url: str,
    request: PushRequest,
    *,
    timeout: float = 30.0,
) -> PushResponse:
    """POST /sync/push to sync server."""
    url = f"{base_url.rstrip('/')}/sync/push"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                json=request.model_dump(mode="json"),
            )
            resp.raise_for_status()
            data = resp.json()
            return PushResponse(
                accepted=data.get("accepted", True),
                cursor=data.get("cursor", ""),
                errors=data.get("errors", []),
            )
    except Exception as e:
        return PushResponse(
            accepted=False,
            cursor="",
            errors=[str(e)],
        )


def pull_changes(
    base_url: str,
    request: PullRequest,
    *,
    timeout: float = 30.0,
) -> PullResponse:
    """POST /sync/pull to sync server."""
    url = f"{base_url.rstrip('/')}/sync/pull"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                json=request.model_dump(mode="json"),
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("changes", [])
            changes = [
                SyncChange.model_validate(c) if isinstance(c, dict) else c
                for c in raw
            ]
            return PullResponse(changes=changes, cursor=data.get("cursor", ""))
    except Exception as e:
        return PullResponse(changes=[], cursor="")


async def push_changes_async(
    base_url: str,
    request: PushRequest,
    *,
    timeout: float = 30.0,
) -> PushResponse:
    """Async POST /sync/push."""
    url = f"{base_url.rstrip('/')}/sync/push"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                json=request.model_dump(mode="json"),
            )
            resp.raise_for_status()
            data = resp.json()
            return PushResponse(
                accepted=data.get("accepted", True),
                cursor=data.get("cursor", ""),
                errors=data.get("errors", []),
            )
    except Exception as e:
        return PushResponse(
            accepted=False,
            cursor="",
            errors=[str(e)],
        )


async def pull_changes_async(
    base_url: str,
    request: PullRequest,
    *,
    timeout: float = 30.0,
) -> PullResponse:
    """Async POST /sync/pull."""
    url = f"{base_url.rstrip('/')}/sync/pull"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                json=request.model_dump(mode="json"),
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("changes", [])
            changes = [
                SyncChange.model_validate(c) if isinstance(c, dict) else c
                for c in raw
            ]
            return PullResponse(changes=changes, cursor=data.get("cursor", ""))
    except Exception as e:
        return PullResponse(changes=[], cursor="")
