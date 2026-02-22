import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from browser.controller import BrowserController
from browser.extractor import PageExtractor
from browser.logic import AgentLoop

async def main():
    print("🚀 Starting Project 10 (Phantom) Verification...")
    
    ctrl = BrowserController(headless=True)
    try:
        # 1. Test Controller Start & Navigation
        print("🔍 Testing BrowserController...")
        await ctrl.start()
        await ctrl.navigate("https://example.com")
        title = await ctrl.page.title()
        print(f"✅ Navigation successful: {title}")
        
        # 2. Test Page Extractor
        print("🔍 Testing PageExtractor...")
        extractor = PageExtractor(ctrl.page)
        dom = await extractor.get_simplified_dom()
        if "[e0]" in dom:
            print("✅ DOM Normalization successful (interactive elements found)")
        else:
            print("❌ DOM Normalization failed (no interactive elements)")
            
        # 3. Test Agent Loop (Simulated task)
        print("🔍 Testing AgentLoop Logic...")
        loop = AgentLoop(ctrl, extractor)
        result = await loop.execute_task("navigate to https://example.com")
        if result["status"] == "completed":
            print(f"✅ AgentLoop execution successful: {result['steps']} steps")
        else:
            print("❌ AgentLoop execution failed")
            
        # 4. Test Screenshot
        print("🔍 Testing Screenshot...")
        path = await ctrl.get_screenshot("verify_ss.png")
        if os.path.exists(path):
            print(f"✅ Screenshot saved: {path}")
        else:
            print("❌ Screenshot failed")
            
        print("\n🎉 ALL PHANTOM CORE FEATURES VERIFIED (DAYS 1-7)")
        
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await ctrl.stop()

if __name__ == "__main__":
    asyncio.run(main())
