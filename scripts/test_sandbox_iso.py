import asyncio
import httpx
import sys

async def test_sandbox():
    print("🛡️ Testing Sandbox Isolation...")
    base_url = "http://localhost:8000/api/canvas"
    surface_id = "main-canvas"
    
    # Push a raw HTML/JS Sandbox component
    sandbox_payload = {
        "components": [
            {
                "id": "sandbox_root",
                "component": "Sandbox",
                "props": {
                    "html": """
                    <div style="background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: white; padding: 20px; border-radius: 10px; font-family: sans-serif;">
                        <h2>Sandbox App</h2>
                        <p>This is raw HTML/JS running in an isolated iframe.</p>
                        <button id='btn' style='padding: 8px 16px; cursor: pointer;'>Click me for JS Alert</button>
                        <script>
                            document.getElementById('btn').onclick = () => {
                                alert('Hello from the Sandbox Isolation Layer!');
                            };
                        </script>
                    </div>
                    """
                }
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        print("🚀 Pushing Sandbox component...")
        resp = await client.post(f"{base_url}/test-update/{surface_id}", json=sandbox_payload)
        print(f"Server response: {resp.status_code}")
        print("✨ Check your browser for the Blue Sandbox App!")

if __name__ == "__main__":
    asyncio.run(test_sandbox())
