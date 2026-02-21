import asyncio
import base64
import json
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

import logging

logger = logging.getLogger("canvas.runtime")

class CanvasRuntime:
    """
    The Brain of the Canvas. 
    Manages surface states and provides methods for agents to interact with the UI.
    """
    def __init__(self, ws_handler, storage_path: str = "data/canvas"):
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
        
        try:
            # Validate components against schema
            validated_components = [UIComponent(**c) for c in components]
            self.surfaces[surface_id]["components"] = validated_components
            
            # Persist immediately
            self.save_snapshots()
            
            msg = UpdateComponentsMessage(surfaceId=surface_id, components=validated_components)
            await self.ws_handler.broadcast_to_surface(surface_id, msg.model_dump())
        except Exception as e:
            import logging
            logging.getLogger("canvas.runtime").error(f"Failed to push components to {surface_id}: {e}")

    async def update_component_props(self, surface_id: str, component_id: str, props: Dict[str, Any]):
        """Partial update of a specific component's props. Creates surface if it doesn't exist."""
        
        if surface_id not in self.surfaces:
            self.surfaces[surface_id] = {
                "components": [],
                "data": {},
                "title": f"Surface: {surface_id}"
            }

        if "components" not in self.surfaces[surface_id]:
            self.surfaces[surface_id]["components"] = []
            
        components = self.surfaces[surface_id]["components"]
        updated = False
        
        target_id = str(component_id).strip().lower()
        
        for comp in components:
            cid = str(comp.id if hasattr(comp, "id") else comp.get("id", "")).strip().lower()
            if cid == target_id:
                if hasattr(comp, "props"):
                    comp.props.update(props)
                else:
                    if "props" not in comp:
                        comp["props"] = {}
                    comp["props"].update(props)
                
                # Special: If this is the main whiteboard/kanban, also save to specific files
                await self._save_specific_local_files(comp, props)
                
                updated = True
                break
        
        if not updated:
            new_comp = {
                "id": component_id,
                "component": "Whiteboard", # Default assumption if creating from scratch
                "props": props,
                "children": []
            }
            components.append(new_comp)
            await self._save_specific_local_files(new_comp, props)
            updated = True
        
        if updated:
            self.save_snapshots()

    async def _save_specific_local_files(self, comp, props):
        """Helper to save specific state to user-requested local files."""
        try:
            component_type = comp.component if hasattr(comp, "component") else comp.get("component")
            
            # 1. Whiteboard -> Canvas_Pic_Current.json
            if component_type == "Whiteboard" and "elements" in props:
                path = Path("Canvas_Pic_Current.json")
                out = {"elements": props["elements"], "appState": props.get("appState", {})}
                path.write_text(json.dumps(out, indent=2), encoding="utf-8")

            # 2. Kanban -> Kanban_Current.json
            if component_type == "Kanban" and "initialTasks" in props:
                path = Path("Kanban_Current.json")
                out = {"tasks": props["initialTasks"]}
                path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save specific local files: {e}")

    async def save_image_snapshot(self, surface_id: str, snapshot_base64: str):
        """Save a base64 image snapshot to disk."""
        try:
            if "," in snapshot_base64:
                snapshot_base64 = snapshot_base64.split(",")[1]
            
            img_data = base64.b64decode(snapshot_base64)
            path = Path("Canvas_Pic_Current.png")
            path.write_bytes(img_data)
            logger.info(f"Successfully saved image snapshot to {path}")
        except Exception as e:
            logger.error(f"Failed to save image snapshot: {e}")

    def get_surface_state(self, surface_id: str) -> Optional[Dict[str, Any]]:
        """Get the current state of a surface."""
        return self.surfaces.get(surface_id)

    async def update_data(self, surface_id: str, data: Dict[str, Any]):
        """Update the data model (partial delta)."""
        if surface_id not in self.surfaces:
            return
            
        self.surfaces[surface_id]["data"].update(data)
        self.save_snapshots() # Persist data changes too
        msg = UpdateDataModelMessage(surfaceId=surface_id, data=data)
        await self.ws_handler.broadcast_to_surface(surface_id, msg.model_dump())

    def save_snapshots(self):
        """Persist all surface states to disk."""
        import logging
        logger = logging.getLogger("canvas.runtime")
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            for surface_id, state in self.surfaces.items():
                path = self.storage_path / f"{surface_id}.json"
                # Convert UIComponents back to dicts for JSON serialization
                serializable_state = {
                    "components": [c.model_dump() if hasattr(c, "model_dump") else c for c in state.get("components", [])],
                    "data": state.get("data", {})
                }
                
                try:
                    out_json = json.dumps(serializable_state, indent=2)
                    path.write_text(out_json, encoding="utf-8")
                    logger.info(f"Snapshot saved for surface: {surface_id}")
                except Exception as json_e:
                    logger.error(f"Failed to JSON dump {surface_id}: {json_e}")
                    
        except Exception as e:
            logger.error(f"Failed to save snapshots: {e}")

    def load_snapshots(self):
        """Restore surface states from disk on startup."""
        import logging
        logger = logging.getLogger("canvas.runtime")
        if not self.storage_path.exists():
            return
        for path in self.storage_path.glob("*.json"):
            surface_id = path.stem
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.surfaces[surface_id] = data
                logger.info(f"Restored surface {surface_id} from snapshot")
            except Exception as e:
                logger.error(f"Failed to load snapshot {path}: {e}")
