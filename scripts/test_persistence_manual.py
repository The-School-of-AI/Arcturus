import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from canvas.runtime import CanvasRuntime
from canvas.schema import UIComponent

async def test_persistence():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test")
    
    # Setup dummy runtime (with dummy ws_handler)
    class DummyWS:
        async def broadcast_to_surface(self, *args, **kwargs):
            pass
            
    storage_dir = Path("storage/test_canvas")
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    runtime = CanvasRuntime(DummyWS(), storage_path=str(storage_dir))
    
    surface_id = "test_surface"
    comp_id = "wb_1"
    
    # 1. Create surface and push initial component
    logger.info("Steps: 1. Push components")
    await runtime.push_components(surface_id, [
        {
            "id": comp_id,
            "component": "Whiteboard",
            "props": {"title": "Initial", "elements": []}
        }
    ])
    
    # Verify file exists
    snapshot_path = storage_dir / f"{surface_id}.json"
    if not snapshot_path.exists():
        logger.error("❌ Snapshot was NOT created after push_components")
        return
        
    initial_data = json.loads(snapshot_path.read_text())
    logger.info(f"Initial snapshot elements: {len(initial_data['components'][0]['props']['elements'])}")
    
    # 2. Update props
    logger.info("Steps: 2. Update component props")
    new_elements = [{"type": "rectangle", "id": "rect1", "x": 10, "y": 10}]
    await runtime.update_component_props(surface_id, comp_id, {
        "elements": new_elements,
        "appState": {"viewBackgroundColor": "#ff0000"}
    })
    
    # 3. Verify on disk
    updated_data = json.loads(snapshot_path.read_text())
    elements_count = len(updated_data['components'][0]['props']['elements'])
    logger.info(f"Updated snapshot elements: {elements_count}")
    
    if elements_count == 1:
        logger.info("✅ SUCCESS: Persistence is working in Runtime")
    else:
        logger.error("❌ FAILURE: Snapshot was not updated on disk")
        
    # Cleanup
    # snapshot_path.unlink()
    # storage_dir.rmdir()

if __name__ == "__main__":
    asyncio.run(test_persistence())
