import asyncio
import aiohttp
import sys

API_BASE = "http://127.0.0.1:8000/api"

async def check_endpoint(session, url, name):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                print(f"✅ {name}: 200 OK")
                return True
            else:
                text = await response.text()
                print(f"❌ {name}: {response.status} - {text}")
                return False
    except Exception as e:
        print(f"❌ {name}: Failed connection - {e}")
        return False

async def main():
    print("Checking Settings API endpoints...")
    async with aiohttp.ClientSession() as session:
        # Check Main Settings
        await check_endpoint(session, f"{API_BASE}/settings", "Settings")
        
        # Check Prompts
        await check_endpoint(session, f"{API_BASE}/prompts", "Prompts")
        
        # Check Skills
        await check_endpoint(session, f"{API_BASE}/skills/list", "Skills List")
        
        # Check Gemini Status
        await check_endpoint(session, f"{API_BASE}/gemini/status", "Gemini Status")

if __name__ == "__main__":
    asyncio.run(main())
