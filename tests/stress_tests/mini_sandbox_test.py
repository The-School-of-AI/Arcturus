
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import sys
import os

async def test_sandbox_direct():
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "mcp_servers/server_sandbox.py"],
        env=os.environ.copy()
    )
    
    print("Connecting to sandbox...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected. Calling tool...")
            try:
                result = await session.call_tool("run_python_script", {"code": "print('Direct Test Success'); 1+1"})
                print(f"Result: {result}")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_sandbox_direct())
