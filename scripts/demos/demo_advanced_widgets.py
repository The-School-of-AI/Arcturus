import asyncio
import json
import websockets
import time

async def demo_advanced_widgets():
    surface_id = f"advanced_demo_{int(time.time())}"
    uri = f"ws://localhost:8000/api/canvas/ws/{surface_id}"
    
    print(f"🚀 Starting Advanced Widgets Demo on Surface: {surface_id}")
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Create Surface
            create_msg = {
                "type": "createSurface",
                "surfaceId": surface_id,
                "title": "Project Control Center"
            }
            await websocket.send(json.dumps(create_msg))
            print("✅ Surface created.")
            
            # 2. Define Components
            components = [
                {
                    "id": "kanban_1",
                    "component": "Kanban",
                    "props": {
                        "title": "Development Sprint",
                        "initialTasks": [
                            {"id": "t1", "content": "Implement Whiteboard", "columnId": "done"},
                            {"id": "t2", "content": "Implement Map View", "columnId": "done"},
                            {"id": "t3", "content": "Implement Kanban", "columnId": "in_progress"},
                            {"id": "t4", "content": "Test Bi-directional Sync", "columnId": "todo"},
                        ]
                    }
                },
                {
                    "id": "map_1",
                    "component": "Map",
                    "props": {
                        "title": "Global Logistics",
                        "center": [40.7128, -74.0060],
                        "zoom": 10,
                        "markers": [
                            {"position": [40.7128, -74.0060], "popup": "New York HQ"},
                            {"position": [40.7306, -73.9352], "popup": "Brooklyn Distribution Center"}
                        ]
                    }
                },
                {
                    "id": "whiteboard_1",
                    "component": "Whiteboard",
                    "props": {
                        "title": "System Architecture",
                        "elements": [
                            {"type": "rectangle", "x": 10, "y": 10, "width": 100, "height": 50, "strokeColor": "#3b82f6"}
                        ]
                    }
                }
            ]
            
            update_msg = {
                "type": "updateComponents",
                "surfaceId": surface_id,
                "components": components
            }
            await websocket.send(json.dumps(update_msg))
            print("✅ All advanced widgets pushed to Canvas.")

            # 3. Test Snapshot Capture (Task P06-6.1)
            print("📸 Requesting snapshot capture...")
            snapshot_req = {
                "type": "captureSnapshot",
                "surfaceId": surface_id
            }
            await websocket.send(json.dumps(snapshot_req))
            
            # 4. Listen for events and snapshot results
            print("🎧 Monitoring real-time interaction loop...")
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                if data.get("type") == "snapshotResult":
                    print(f"✅ Snapshot received! Size: {len(data.get('snapshot', ''))} bytes")
                    # In a real scenario, we'd save this to storage/canvas/snapshots/
                    print("   🖼️  Vision Integration VERIFIED.")
                
                elif data.get("type") == "user_event":
                    comp_id = data.get("component_id")
                    ev_type = data.get("event_type")
                    print(f"🔔 EVENT [Surface: {surface_id}]: {ev_type} on {comp_id}")
                    if ev_type == "drawing_change":
                         print("   🎨 Sketching detected...")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(demo_advanced_widgets())
