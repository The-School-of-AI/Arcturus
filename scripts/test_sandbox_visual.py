import asyncio
import httpx
import sys

async def test_sandbox_visual():
    print("🛡️ Testing Sandbox with Visual Feedback...")
    base_url = "http://localhost:8000/api/canvas"
    surface_id = "main-canvas"
    
    # Push a raw HTML/JS Sandbox component that changes color when clicked
    sandbox_payload = {
        "components": [
            {
                "id": "sandbox_root",
                "component": "Sandbox",
                "props": {
                    "html": """
                    <div id='box' style="background: #1e3a8a; color: white; padding: 20px; border-radius: 10px; font-family: sans-serif; transition: background 0.3s; text-align: center;">
                        <h2>Sandbox App</h2>
                        <p>Click the button below. The box should turn GREEN.</p>
                        <button id='btn' style='padding: 8px 16px; cursor: pointer; background: white; color: black; border: none; border-radius: 4px; font-weight: bold;'>
                            Test Script Execution
                        </button>
                        <script>
                            const btn = document.getElementById('btn');
                            const box = document.getElementById('box');
                            btn.onclick = () => {
                                box.style.background = '#059669'; // Emerald Green
                                btn.innerText = 'Scripts Working! ✅';
                                // Try alert if modals are allowed
                                try { alert('Success: JavaScript is running!'); } catch(e) {}
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
        print("✨ Check your browser. The box should turn green when you click!")

if __name__ == "__main__":
    asyncio.run(test_sandbox_visual())
