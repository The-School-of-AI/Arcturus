import asyncio
import httpx
import sys

async def simulate_live_agent():
    print("🤖 Agent Simulation starting (using REST API)...")
    base_url = "http://localhost:8000/api/canvas"
    surface_id = "main-canvas"
    
    async with httpx.AsyncClient() as client:
        # 1. Update the chart data live
        print("📈 Updating chart data via REST...")
        new_data = [
            {"time": "10:15", "score": 95},
            {"time": "10:20", "score": 98},
            {"time": "10:25", "score": 99}
        ]
        resp = await client.post(f"{base_url}/test-update/{surface_id}", json={"data": {"data": new_data}})
        print(f"Server response: {resp.status_code}")
        await asyncio.sleep(2)
        
        # 2. Add a Monaco Editor widget live
        print("📝 Adding code editor widget via REST...")
        # Get current state first
        state_resp = await client.get(f"{base_url}/state/{surface_id}")
        state = state_resp.json()
        components = state["components"]
        
        components.append({
            "id": "editor",
            "component": "MonacoEditor",
            "props": {
                "code": "print('Hello from Agentic AI!')\n# This was added live via A2UI and REST API!",
                "language": "python"
            }
        })
        
        resp = await client.post(f"{base_url}/test-update/{surface_id}", json={"components": components})
        print(f"Server response: {resp.status_code}")
        print("✨ Updates pushed. Check your browser!")

if __name__ == "__main__":
    asyncio.run(simulate_live_agent())
