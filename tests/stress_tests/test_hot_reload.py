
import asyncio
import pytest
from mcp_servers.multi_mcp import MultiMCP
from .conftest import require_stress_opt_in, require_integration_opt_in


pytestmark = [pytest.mark.stress, pytest.mark.integration]


async def _hot_reload():
    """
    Test recovery from MCP server failure.
    1. Start MultiMCP.
    2. Call a tool to verify it works.
    3. Kill the server.
    4. Call the tool again (should fail or trigger reconnect).
    5. Manual restart if needed, or check if MultiMCP handles it.
    """
    m = MultiMCP()
    await m.start()
    
    server_name = "sandbox" # A reliably fast local server
    tool_name = "run_python_script"
    args = {"code": "print('Alive')"}
    
    print(f"Testing {server_name}...")
    
    try:
        # Step 2: Initial Call
        res = await m.route_tool_call(tool_name, args)
        print(f"✅ Initial Call: {res.content[0].text[:50]}")
        
        # Step 3: Kill it
        print("💀 Killing server...")
        await m.kill_server(server_name)
        
        # Step 4: Call again
        print("🔄 Calling again (should trigger recovery or error)...")
        try:
            # MultiMCP currently doesn't auto-restart on every call failure, 
            # but it should allow re-starting.
            # Let's see if we can re-start manually.
            config = m.server_configs.get(server_name)
            await m._start_server(server_name, config)
            
            res2 = await m.route_tool_call(tool_name, args)
            text = res2.content[0].text if getattr(res2, "content", None) else ""
            assert "Alive" in text
            return
        except Exception as e:
            pytest.fail(f"Recovery Failed: {e}")

    finally:
        await m.stop()


def test_hot_reload():
    require_stress_opt_in()
    require_integration_opt_in()
    asyncio.run(_hot_reload())


if __name__ == "__main__":
    asyncio.run(_hot_reload())
