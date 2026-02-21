import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from .schema import (
    CreateSurfaceMessage, 
    UpdateComponentsMessage, 
    UpdateDataModelMessage, 
    DeleteSurfaceMessage,
    EvalJSMessage,
    UIComponent
)

class CanvasRuntime:
    """
    The Brain of the Canvas. 
    Manages surface states and provides methods for agents to interact with the UI.
    """
    def __init__(self, ws_handler, storage_path: str = "storage/canvas"):
        self.ws_handler = ws_handler
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.surfaces: Dict[str, Dict[str, Any]] = {} # surfaceId -> {components: [], data: {}}
        self.load_snapshots()

    async def create_surface(self, surface_id: str, title: str = "New Canvas", catalog: str = "default"):
        """Initialize a new canvas region."""
        msg = CreateSurfaceMessage(surfaceId=surface_id, title=title, catalogId=catalog)
        self.surfaces[surface_id] = {"components": [], "data": {}}
        await self.ws_handler.broadcast_to_surface(surface_id, msg.model_dump())

    async def push_components(self, surface_id: str, components: List[Dict[str, Any]]):
        """Full replacement of components on a surface."""
        if surface_id not in self.surfaces:
            await self.create_surface(surface_id)
        
        # Validate components against schema
        validated_components = [UIComponent(**c) for c in components]
        self.surfaces[surface_id]["components"] = validated_components
        
        msg = UpdateComponentsMessage(surfaceId=surface_id, components=validated_components)
        await self.ws_handler.broadcast_to_surface(surface_id, msg.model_dump())

    async def update_data(self, surface_id: str, data: Dict[str, Any]):
        """Update the data model (partial delta)."""
        if surface_id not in self.surfaces:
            return
            
        self.surfaces[surface_id]["data"].update(data)
        msg = UpdateDataModelMessage(surfaceId=surface_id, data=data)
        await self.ws_handler.broadcast_to_surface(surface_id, msg.model_dump())

    async def eval_js(self, surface_id: str, code: str):
        """Execute arbitrary JS in the sandboxed context."""
        msg = EvalJSMessage(surfaceId=surface_id, code=code)
        await self.ws_handler.broadcast_to_surface(surface_id, msg.model_dump())

    async def delete_surface(self, surface_id: str):
        """Remove a surface and its state."""
        if surface_id in self.surfaces:
            del self.surfaces[surface_id]
            msg = DeleteSurfaceMessage(surfaceId=surface_id)
            await self.ws_handler.broadcast_to_surface(surface_id, msg.model_dump())

    def get_surface_state(self, surface_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the current state of a surface (for agent reasoning)."""
        return self.surfaces.get(surface_id)

    def save_snapshots(self):
        """Persist all surface states to disk."""
        for surface_id, state in self.surfaces.items():
            path = self.storage_path / f"{surface_id}.json"
            # Convert UIComponents back to dicts for JSON serialization
            serializable_state = {
                "components": [c.model_dump() if hasattr(c, "model_dump") else c for c in state["components"]],
                "data": state["data"]
            }
            path.write_text(json.dumps(serializable_state, indent=2), encoding="utf-8")

    def load_snapshots(self):
        """Restore surface states from disk on startup."""
        if not self.storage_path.exists():
            return
        for path in self.storage_path.glob("*.json"):
            surface_id = path.stem
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.surfaces[surface_id] = data
            except Exception:
                pass
