from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, List
import json
import logging
from shared.state import get_canvas_runtime

logger = logging.getLogger("canvas.ws")

class CanvasWSHandler:
    """
    Manages WebSocket connections for the visual workspace.
    Routes messages between the Agent and the Frontend.
    """
    def __init__(self):
        # surfaceId -> Set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, surface_id: str):
        await websocket.accept()
        if surface_id not in self.active_connections:
            self.active_connections[surface_id] = set()
        self.active_connections[surface_id].add(websocket)
        logger.info(f"Connected to canvas surface: {surface_id}")

    def disconnect(self, websocket: WebSocket, surface_id: str):
        if surface_id in self.active_connections:
            self.active_connections[surface_id].remove(websocket)
            if not self.active_connections[surface_id]:
                del self.active_connections[surface_id]
        logger.info(f"Disconnected from canvas surface: {surface_id}")

    async def broadcast_to_surface(self, surface_id: str, message: dict, exclude_socket: WebSocket = None):
        """Send a message to all clients connected to a specific surface, optionally excluding one."""
        if surface_id not in self.active_connections:
            return

        disconnected_sockets = set()
        for websocket in self.active_connections[surface_id]:
            if websocket == exclude_socket:
                continue
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {surface_id}: {e}")
                disconnected_sockets.add(websocket)
        
        # Cleanup failed sockets
        for socket in disconnected_sockets:
            self.disconnect(socket, surface_id)

    async def handle_user_event(self, surface_id: str, data: dict, sender_socket: WebSocket = None):
        """
        Handle incoming events from the user.
        Broadcast the event to all listeners BUT the sender to avoid echo loops.
        """
        event_type = data.get("event_type")
        logger.info(f"handle_user_event: surface={surface_id}, event={event_type}")
        
        # 1. Update Persistent State if this is a drawing change
        if data.get("type") == "user_event" and event_type == "drawing_change":
            component_id = data.get("component_id")
            drawing_data = data.get("data", {})
            
            elements = drawing_data.get("elements")
            app_state = drawing_data.get("appState")
            
            if component_id and drawing_data:
                try:
                    runtime = get_canvas_runtime()
                    await runtime.update_component_props(surface_id, component_id, {
                        "elements": elements,
                        "appState": app_state
                    })
                except Exception as e:
                    logger.error(f"Failed to update persistent state for drawing_change: {e}", exc_info=True)
            else:
                logger.warning(f"Missing component_id ({component_id}) or drawing_data ({bool(drawing_data)}) in event")

        # 1b. Update Persistent State if this is a Kanban update
        if data.get("type") == "user_event" and event_type == "kanban_update":
            component_id = data.get("component_id")
            kanban_data = data.get("data", {})
            
            if component_id and kanban_data:
                try:
                    runtime = get_canvas_runtime()
                    await runtime.update_component_props(surface_id, component_id, kanban_data)
                except Exception as e:
                    print(f"[DEBUG] Failed to update persistent state for kanban_update: {e}", flush=True)

        # 1c. Handle Snapshot Result
        if data.get("type") == "snapshotResult":
            snapshot = data.get("snapshot")
            if snapshot:
                try:
                    runtime = get_canvas_runtime()
                    await runtime.save_image_snapshot(surface_id, snapshot)
                except Exception as e:
                    logger.error(f"Error saving snapshot: {e}")

        # 2. Broadcast to all OTHER clients on this surface
        await self.broadcast_to_surface(surface_id, data, exclude_socket=sender_socket)
        logger.warning(f"✅ Handled {event_type if event_type else data.get('type')} for {surface_id} | Broacasted to listeners")
