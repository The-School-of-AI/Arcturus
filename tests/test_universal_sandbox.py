
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from core.sandbox.executor import UniversalSandbox

async def test_sandbox():
    sandbox = UniversalSandbox()
    
    # 1. Simple math
    result = await sandbox.run("print(1+1); 2+2")
    print(f"Status: {result['status']}")
    print(f"Result: {result['result']}")
    print(f"Logs: {result['logs'].strip()}")
    
    if result['status'] == 'success' and result['result'] == 4:
        print("✅ Basic Sandbox verified!")
    else:
        print("❌ Sandbox failed verification.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_sandbox())
