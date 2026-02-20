from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, List
import json
import logging

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

    async def broadcast_to_surface(self, surface_id: str, message: dict):
        """Send a message to all clients connected to a specific surface."""
        if surface_id not in self.active_connections:
            return

        disconnected_sockets = set()
        for websocket in self.active_connections[surface_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {surface_id}: {e}")
                disconnected_sockets.add(websocket)
        
        # Cleanup failed sockets
        for socket in disconnected_sockets:
            self.disconnect(socket, surface_id)

    async def handle_user_event(self, surface_id: str, data: dict):
        """
        Handle incoming events from the user (e.g., clicks).
        In a real app, this would route to the Agent Core's event loop.
        """
        logger.info(f"User event on {surface_id}: {data}")
        # Implementation hook: Route this to core/loop.py or a callback
