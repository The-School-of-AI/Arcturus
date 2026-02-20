import asyncio
import json
import websockets
import time

async def demo_whiteboard():
    surface_id = f"whiteboard_demo_{int(time.time())}"
    uri = f"ws://localhost:8000/api/canvas/ws/{surface_id}"
    
    print(f"🚀 Starting Whiteboard Demo on Surface: {surface_id}")
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Create Surface
            create_msg = {
                "type": "createSurface",
                "surfaceId": surface_id,
                "title": "Strategy Whiteboard"
            }
            await websocket.send(json.dumps(create_msg))
            print("✅ Surface created.")
            
            # 2. Push Whiteboard Widget
            # Example elements: A rectangle and some text
            elements = [
                {
                    "id": "rect1",
                    "type": "rectangle",
                    "x": 100,
                    "y": 100,
                    "width": 200,
                    "height": 100,
                    "strokeColor": "#3b82f6",
                    "backgroundColor": "transparent",
                    "fillStyle": "hachure",
                    "strokeWidth": 1,
                    "strokeStyle": "solid",
                    "roughness": 1,
                    "opacity": 100,
                },
                {
                    "id": "text1",
                    "type": "text",
                    "x": 120,
                    "y": 130,
                    "width": 160,
                    "height": 40,
                    "text": "Arcturus Strategy",
                    "fontSize": 20,
                    "fontFamily": 1,
                    "textAlign": "center",
                    "verticalAlign": "middle",
                    "strokeColor": "#f3f4f6",
                    "backgroundColor": "transparent",
                }
            ]
            
            update_msg = {
                "type": "updateComponents",
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": "wb_1",
                        "component": "Whiteboard",
                        "props": {
                            "title": "Phase 2 Planning",
                            "elements": elements
                        }
                    }
                ]
            }
            await websocket.send(json.dumps(update_msg))
            print("✅ Whiteboard widget pushed with initial elements.")
            
            # 3. Listen for events (Bi-directional check)
            print("🎧 Listening for user events (Try drawing or clicking in the UI)...")
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                if data.get("type") == "user_event":
                    print(f"🔔 RECEIVED EVENT: {data.get('event_type')} from {data.get('component_id')}")
                    if data.get("event_type") == "drawing_change":
                        count = len(data.get("data", {}).get("elements", []))
                        print(f"   📝 Drawing updated! Current elements: {count}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(demo_whiteboard())
