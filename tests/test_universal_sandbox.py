
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from core.sandbox.executor import UniversalSandbox

async def _run_sandbox():
    sandbox = UniversalSandbox()
    
    # 1. Simple math
    result = await sandbox.run("print(1+1); 2+2")
    return result

def test_sandbox():
    result = asyncio.run(_run_sandbox())
    assert result["status"] == "success"
    assert result["result"] == 4

if __name__ == "__main__":
    asyncio.run(_run_sandbox())
