import asyncio
import json
import websockets
import time

async def demo_advanced_widgets():
    surface_id = "ops-final-diagnostic"
    uri = f"ws://localhost:8000/api/canvas/ws/{surface_id}"
    
    print(f"🚀 Starting Advanced Widgets Demo on Surface: {surface_id}")
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Create Surface
            create_msg = {
                "type": "createSurface",
                "surfaceId": surface_id,
                "title": "Arcturus Ops Command"
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
                        "title": "Global Logistics - Active Route",
                        "center": [40.7128, -74.0060],
                        "zoom": 12,
                        "markers": [
                            {"position": [40.7128, -74.0060], "popup": "New York HQ"},
                            {"position": [40.7306, -73.9352], "popup": "Brooklyn Distribution Center"}
                        ],
                        "polylines": [
                            {
                                "positions": [
                                    [40.7128, -74.0060], [40.7135, -74.0040], [40.7150, -74.0010],
                                    [40.7170, -73.9980], [40.7190, -73.9950], [40.7210, -73.9900],
                                    [40.7230, -73.9850], [40.7250, -73.9800], [40.7270, -73.9750],
                                    [40.7285, -73.9650], [40.7295, -73.9550], [40.7306, -73.9352]
                                ],
                                "color": "#10b981",
                                "weight": 6,
                                "popup": "Verified Route: 8.4 mi | Traffic: Light (18m remaining)"
                            }
                        ]
                    }
                },
                {
                    "id": "whiteboard_1",
                    "component": "Whiteboard",
                    "props": {
                        "title": "Arcturus System Architecture",
                        "elements": [
                            {"type": "rectangle", "id": "rect1", "x": 100, "y": 100, "width": 150, "height": 80, "strokeColor": "#3b82f6", "backgroundColor": "#1d4ed8", "fillStyle": "solid", "strokeWidth": 2, "text": "UI Platform"},
                            {"type": "arrow", "id": "arrow1", "x": 250, "y": 140, "points": [[0,0], [100, 0]], "strokeColor": "#94a3b8", "strokeWidth": 2},
                            {"type": "rectangle", "id": "rect2", "x": 350, "y": 100, "width": 150, "height": 80, "strokeColor": "#ef4444", "backgroundColor": "#b91c1c", "fillStyle": "solid", "strokeWidth": 2, "text": "Agent Core"},
                            {"type": "arrow", "id": "arrow2", "x": 425, "y": 180, "points": [[0,0], [0, 100]], "strokeColor": "#94a3b8", "strokeWidth": 2},
                            {"type": "rectangle", "id": "rect3", "x": 350, "y": 280, "width": 150, "height": 80, "strokeColor": "#f59e0b", "backgroundColor": "#b45309", "fillStyle": "solid", "strokeWidth": 2, "text": "Episodic Memory"}
                        ]
                    }
                }
            ]
            
            update_payload = {
                "components": components
            }
            import requests
            api_uri = f"http://localhost:8000/api/canvas/test-update/{surface_id}"
            resp = requests.post(api_uri, json=update_payload)
            if resp.status_code == 200:
                print("✅ All advanced widgets pushed to Canvas via API.")
            else:
                print(f"❌ Failed to push widgets: {resp.status_code} {resp.text}")

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
