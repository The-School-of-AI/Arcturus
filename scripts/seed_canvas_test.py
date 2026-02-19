import asyncio
import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from shared.state import get_canvas_runtime

async def seed_canvas():
    print("🌱 Seeding canvas state...")
    runtime = get_canvas_runtime()
    
    # Mock WS handler to avoid connection errors in script
    class MockWS:
        async def broadcast_to_surface(self, sid, msg):
            print(f"📡 Broadcast to {sid}: {msg['type']}")
            
    runtime.ws_handler = MockWS()
    
    surface_id = "main-canvas"
    
    # 1. Create Surface
    await runtime.create_surface(surface_id, title="Verification Canvas")
    
    # 2. Push Components
    components = [
        {
            "id": "root",
            "component": "Container",
            "props": {"className": "p-6 space-y-4"},
            "children": ["title", "chart"]
        },
        {
            "id": "title",
            "component": "Text",
            "props": {"content": "System Verification Report", "style": {"fontSize": "24px", "fontWeight": "bold"}}
        },
        {
            "id": "chart",
            "component": "LineChart",
            "props": {
                "title": "Agent Performance Over Time",
                "xKey": "time",
                "lines": [{"key": "score", "color": "#10B981"}],
                "data": [
                    {"time": "10:00", "score": 85},
                    {"time": "10:05", "score": 88},
                    {"time": "10:10", "score": 92}
                ]
            }
        }
    ]
    await runtime.push_components(surface_id, components)
    
    # 3. Save Snapshots
    runtime.save_snapshots()
    print("✅ State seeded and persisted to disk.")

if __name__ == "__main__":
    asyncio.run(seed_canvas())
