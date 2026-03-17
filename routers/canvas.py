from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from shared.state import get_canvas_ws, get_canvas_runtime
import logging

router = APIRouter(prefix="/canvas", tags=["canvas"])
logger = logging.getLogger("canvas.router")

@router.websocket("/ws/{surface_id}")
async def canvas_websocket(websocket: WebSocket, surface_id: str):
    """
    WebSocket endpoint for a specific canvas surface.
    """
    ws_handler = get_canvas_ws()
    runtime = get_canvas_runtime()
    await ws_handler.connect(websocket, surface_id)

    # Push initial state if it exists
    state = runtime.get_surface_state(surface_id)
    if state:
        from canvas.schema import UpdateComponentsMessage, UpdateDataModelMessage, UpdateHtmlMessage
        # Send components
        if state.get("components"):
            msg = UpdateComponentsMessage(surfaceId=surface_id, components=state["components"])
            await websocket.send_json(msg.model_dump())
        # Send data
        if state.get("data"):
            msg = UpdateDataModelMessage(surfaceId=surface_id, data=state["data"])
            await websocket.send_json(msg.model_dump())
        # Send html
        if state.get("html"):
            msg = UpdateHtmlMessage(surfaceId=surface_id, html=state["html"], title=state.get("html_title"))
            await websocket.send_json(msg.model_dump())
    
    try:
        while True:
            # Receive messages from the client (user events)
            data = await websocket.receive_json()
            await ws_handler.handle_user_event(surface_id, data)
    except WebSocketDisconnect:
        ws_handler.disconnect(websocket, surface_id)
    except Exception as e:
        logger.error(f"WebSocket error on surface {surface_id}: {e}")
        ws_handler.disconnect(websocket, surface_id)

@router.get("/surfaces")
async def list_surfaces():
    """List all canvas surfaces with metadata."""
    runtime = get_canvas_runtime()
    surfaces = []
    for sid, state in runtime.surfaces.items():
        comps = state.get("components", [])
        surfaces.append({
            "id": sid,
            "title": state.get("html_title") or sid,
            "mode": "sandbox" if state.get("html") else "widgets",
            "component_count": len(comps),
            "has_data": bool(state.get("data")),
        })
    return {"surfaces": surfaces}

@router.get("/state/{surface_id}")
async def get_canvas_state(surface_id: str):
    """
    Retrieve the current state of a surface.
    """
    runtime = get_canvas_runtime()
    state = runtime.get_surface_state(surface_id)
    if not state:
        raise HTTPException(status_code=404, detail="Surface not found")
    return state

@router.post("/test-update/{surface_id}")
async def test_update_canvas(surface_id: str, payload: dict):
    """
    Test endpoint to simulate agent pushing components or data.
    """
    runtime = get_canvas_runtime()
    if "components" in payload:
        await runtime.push_components(surface_id, payload["components"])
    if "data" in payload:
        await runtime.update_data(surface_id, payload["data"])
    if "html" in payload:
        await runtime.push_html(surface_id, payload["html"], payload.get("title"))
    return {"status": "ok"}

@router.delete("/state/{surface_id}/component/{component_id}")
async def delete_canvas_component(surface_id: str, component_id: str):
    """Delete a single component from a surface."""
    runtime = get_canvas_runtime()
    state = runtime.get_surface_state(surface_id)
    if not state:
        raise HTTPException(status_code=404, detail="Surface not found")
    comps = state.get("components", [])
    filtered = [c for c in comps if (c.get("id") if isinstance(c, dict) else getattr(c, "id", None)) != component_id]
    if len(filtered) == len(comps):
        raise HTTPException(status_code=404, detail="Component not found")
    await runtime.push_components(surface_id, [c if isinstance(c, dict) else c.model_dump() for c in filtered])
    return {"status": "deleted", "component_id": component_id}

@router.patch("/state/{surface_id}/component/{component_id}/rename")
async def rename_canvas_component(surface_id: str, component_id: str, payload: dict):
    """Rename (update title prop) of a component on a surface."""
    runtime = get_canvas_runtime()
    state = runtime.get_surface_state(surface_id)
    if not state:
        raise HTTPException(status_code=404, detail="Surface not found")
    new_title = payload.get("title", "Untitled")
    comps = state.get("components", [])
    found = False
    updated = []
    for c in comps:
        d = c if isinstance(c, dict) else c.model_dump()
        if d.get("id") == component_id:
            d.setdefault("props", {})["title"] = new_title
            found = True
        updated.append(d)
    if not found:
        raise HTTPException(status_code=404, detail="Component not found")
    await runtime.push_components(surface_id, updated)
    return {"status": "renamed", "component_id": component_id, "title": new_title}
