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
        from canvas.schema import UpdateComponentsMessage, UpdateDataModelMessage
        # Send components
        if state.get("components"):
            msg = UpdateComponentsMessage(surfaceId=surface_id, components=state["components"])
            await websocket.send_json(msg.model_dump())
        # Send data
        if state.get("data"):
            msg = UpdateDataModelMessage(surfaceId=surface_id, data=state["data"])
            await websocket.send_json(msg.model_dump())
    
    try:
        while True:
            # Receive messages from the client (user events)
            data = await websocket.receive_json()
            await ws_handler.handle_user_event(surface_id, data, sender_socket=websocket)
    except WebSocketDisconnect:
        ws_handler.disconnect(websocket, surface_id)
    except Exception as e:
        logger.error(f"WebSocket error on surface {surface_id}: {e}")
        ws_handler.disconnect(websocket, surface_id)

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
    return {"status": "ok"}
