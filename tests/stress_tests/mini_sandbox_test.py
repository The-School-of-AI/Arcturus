
import os
import asyncio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .conftest import require_stress_opt_in, require_integration_opt_in


pytestmark = [pytest.mark.stress, pytest.mark.integration]


async def _sandbox_direct():
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
                text = ""
                if getattr(result, "content", None):
                    text = result.content[0].text
                assert "Direct Test Success" in text
            except Exception as e:
                pytest.fail(f"Sandbox tool call failed: {e}")


def test_sandbox_direct():
    require_stress_opt_in()
    require_integration_opt_in()
    asyncio.run(_sandbox_direct())

if __name__ == "__main__":
    asyncio.run(_sandbox_direct())
